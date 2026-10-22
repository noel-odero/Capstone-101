using System.Security.Claims;
using Amr.Api.Authentication;
using Amr.Application.Interfaces.Identity;
using Microsoft.AspNetCore.Http;

namespace Amr.UnitTests.Authentication;

public class AuthenticationUnitTests
{
    private sealed class FakeClock(DateTimeOffset now) : TimeProvider
    {
        public DateTimeOffset Now { get; set; } = now;

        public override DateTimeOffset GetUtcNow() => Now;
    }

    private sealed class InMemoryAccounts : IUserAccounts
    {
        public Dictionary<string, UserAccount> ByEmail { get; } = [];

        public Dictionary<Guid, int> Failures { get; } = [];

        public Dictionary<Guid, DateTimeOffset> Locks { get; } = [];

        public FakeClock? Clock { get; init; }

        public Task<UserAccount?> FindByEmailAsync(string normalizedEmail, CancellationToken cancellationToken)
        {
            if (!ByEmail.TryGetValue(normalizedEmail, out var user))
            {
                return Task.FromResult<UserAccount?>(null);
            }

            return Task.FromResult<UserAccount?>(user with { LockedUntilUtc = Locks.TryGetValue(user.Id, out var until) ? until : null });
        }

        public Task<UserAccount?> CreateAsync(string email, string normalizedEmail, string displayName, string passwordHash, CancellationToken cancellationToken)
        {
            if (ByEmail.ContainsKey(normalizedEmail))
            {
                return Task.FromResult<UserAccount?>(null);
            }

            var user = new UserAccount(Guid.NewGuid(), email, displayName, passwordHash, null);
            ByEmail[normalizedEmail] = user;
            return Task.FromResult<UserAccount?>(user);
        }

        public Task RecordFailedSignInAsync(Guid userId, int threshold, TimeSpan lockoutDuration, CancellationToken cancellationToken)
        {
            Failures[userId] = Failures.GetValueOrDefault(userId) + 1;
            if (Failures[userId] >= threshold)
            {
                Locks[userId] = Clock!.Now + lockoutDuration;
                Failures[userId] = 0;
            }

            return Task.CompletedTask;
        }

        public Task RecordSuccessfulSignInAsync(Guid userId, CancellationToken cancellationToken)
        {
            Failures[userId] = 0;
            Locks.Remove(userId);
            return Task.CompletedTask;
        }
    }

    private static (AccountService Service, InMemoryAccounts Accounts, FakeClock Clock) CreateService(AuthOptions? options = null)
    {
        var clock = new FakeClock(new DateTimeOffset(2026, 10, 19, 12, 0, 0, TimeSpan.Zero));
        var accounts = new InMemoryAccounts { Clock = clock };
        return (new AccountService(accounts, new PasswordService(), options ?? new AuthOptions(), clock), accounts, clock);
    }

    [Fact]
    public void A_password_is_stored_only_as_a_salted_hash_that_verifies_the_same_password()
    {
        var passwords = new PasswordService();

        var first = passwords.Hash("correct horse battery");
        var second = passwords.Hash("correct horse battery");

        Assert.DoesNotContain("correct horse battery", first, StringComparison.Ordinal);
        Assert.NotEqual(first, second);
        Assert.True(passwords.Verify(first, "correct horse battery"));
        Assert.False(passwords.Verify(first, "correct horse batterY"));
        Assert.False(passwords.Verify(first, string.Empty));
    }

    [Theory]
    [InlineData("Ada@Example.org", "ada@example.org")]
    [InlineData("  ada@example.org  ", "ada@example.org")]
    public void Emails_are_matched_trimmed_and_case_insensitively(string input, string expected) =>
        Assert.Equal(expected, AccountService.NormalizeEmail(input));

    [Fact]
    public async Task Registering_keeps_the_email_as_typed_and_defaults_the_name_to_its_local_part()
    {
        var (service, accounts, _) = CreateService();

        var outcome = await service.RegisterAsync(" Ada.Lovelace@Example.org ", "a long enough password", null, CancellationToken.None);

        Assert.Equal(AccountStatus.Succeeded, outcome.Status);
        Assert.Equal("Ada.Lovelace@Example.org", outcome.User!.Email);
        Assert.Equal("Ada.Lovelace", outcome.User.DisplayName);
        Assert.NotEqual("a long enough password", outcome.User.PasswordHash);
        Assert.Contains("ada.lovelace@example.org", accounts.ByEmail.Keys);
    }

    [Fact]
    public async Task Registering_the_same_email_twice_is_refused_whatever_its_case()
    {
        var (service, _, _) = CreateService();
        await service.RegisterAsync("ada@example.org", "a long enough password", "Ada", CancellationToken.None);

        var again = await service.RegisterAsync("ADA@example.org", "another long password", "Impostor", CancellationToken.None);

        Assert.Equal(AccountStatus.EmailTaken, again.Status);
        Assert.Null(again.User);
    }

    [Fact]
    public async Task Sign_in_needs_the_right_password_and_gives_the_same_answer_for_a_wrong_password_and_an_unknown_email()
    {
        var (service, _, _) = CreateService();
        await service.RegisterAsync("ada@example.org", "a long enough password", "Ada", CancellationToken.None);

        var ok = await service.SignInAsync("Ada@example.org", "a long enough password", CancellationToken.None);
        var wrongPassword = await service.SignInAsync("ada@example.org", "not the password!", CancellationToken.None);
        var unknown = await service.SignInAsync("nobody@example.org", "a long enough password", CancellationToken.None);

        Assert.Equal(AccountStatus.Succeeded, ok.Status);
        Assert.Equal("Ada", ok.User!.DisplayName);
        Assert.Equal(AccountStatus.InvalidCredentials, wrongPassword.Status);
        Assert.Equal(AccountStatus.InvalidCredentials, unknown.Status);
        Assert.Null(wrongPassword.User);
        Assert.Null(unknown.User);
    }

    [Fact]
    public async Task Repeated_wrong_passwords_lock_the_account_even_against_the_right_password_until_the_lockout_ends()
    {
        var (service, _, clock) = CreateService(new AuthOptions { MaxFailedSignIns = 3, LockoutMinutes = 10 });
        await service.RegisterAsync("ada@example.org", "a long enough password", "Ada", CancellationToken.None);

        for (var attempt = 0; attempt < 3; attempt++)
        {
            Assert.Equal(AccountStatus.InvalidCredentials, (await service.SignInAsync("ada@example.org", "wrong password!", CancellationToken.None)).Status);
        }

        var locked = await service.SignInAsync("ada@example.org", "a long enough password", CancellationToken.None);
        Assert.Equal(AccountStatus.LockedOut, locked.Status);
        Assert.Equal(TimeSpan.FromMinutes(10), locked.RetryAfter);

        clock.Now += TimeSpan.FromMinutes(11);
        Assert.Equal(AccountStatus.Succeeded, (await service.SignInAsync("ada@example.org", "a long enough password", CancellationToken.None)).Status);
    }

    [Fact]
    public async Task A_successful_sign_in_resets_the_failure_count()
    {
        var (service, _, _) = CreateService(new AuthOptions { MaxFailedSignIns = 3 });
        await service.RegisterAsync("ada@example.org", "a long enough password", "Ada", CancellationToken.None);

        for (var round = 0; round < 3; round++)
        {
            await service.SignInAsync("ada@example.org", "wrong password!", CancellationToken.None);
            await service.SignInAsync("ada@example.org", "wrong password!", CancellationToken.None);
            Assert.Equal(AccountStatus.Succeeded, (await service.SignInAsync("ada@example.org", "a long enough password", CancellationToken.None)).Status);
        }
    }

    [Theory]
    [InlineData("anoel.odero@gmail.com")]
    [InlineData("first.last+tag@sub.example.co.uk")]
    [InlineData("o'brien@example.ie")]
    [InlineData("user_name-1@my-domain.org")]
    [InlineData("A@b.io")]
    [InlineData("x@xn--bcher-kva.example")]
    public void Ordinary_real_world_email_addresses_are_accepted(string email) =>
        Assert.True(new System.ComponentModel.DataAnnotations.RegularExpressionAttribute(RegisterRequest.EmailPattern).IsValid(email));

    [Theory]
    [InlineData("plainaddress")]
    [InlineData("@example.org")]
    [InlineData("name@")]
    [InlineData("name@example")]
    [InlineData("name@example.c")]
    [InlineData("name@-example.org")]
    [InlineData("name@example..org")]
    [InlineData(".name@example.org")]
    [InlineData("name.@example.org")]
    [InlineData("na..me@example.org")]
    [InlineData("na me@example.org")]
    [InlineData("name@exa mple.org")]
    [InlineData("name@@example.org")]
    [InlineData("name@example.org\n")]
    public void Malformed_email_addresses_are_rejected(string email) =>
        Assert.False(new System.ComponentModel.DataAnnotations.RegularExpressionAttribute(RegisterRequest.EmailPattern).IsValid(email));

    [Fact]
    public void The_session_principal_carries_only_the_id_name_and_email()
    {
        var user = new UserAccount(Guid.Parse("0f8fad5b-d9cb-469f-a165-70867728950e"), "ada@example.org", "Ada", "hash-must-not-leak", null);

        var principal = AmrAuthentication.CreatePrincipal(user);

        Assert.True(principal.Identity!.IsAuthenticated);
        Assert.Equal("0f8fad5b-d9cb-469f-a165-70867728950e", principal.FindFirstValue(ClaimTypes.NameIdentifier));
        Assert.Equal("Ada", principal.FindFirstValue(ClaimTypes.Name));
        Assert.Equal("ada@example.org", principal.FindFirstValue(ClaimTypes.Email));
        Assert.DoesNotContain(principal.Claims, claim => claim.Value.Contains("hash-must-not-leak", StringComparison.Ordinal));
    }

    [Fact]
    public void The_current_user_is_only_the_authenticated_principals_subject()
    {
        var accessor = new HttpContextAccessor { HttpContext = new DefaultHttpContext() };
        var user = new HttpContextCurrentUser(accessor);
        Assert.Null(user.UserId);

        accessor.HttpContext.User = new ClaimsPrincipal(new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, "42")], "cookie"));
        Assert.Equal("42", user.UserId);

        accessor.HttpContext.User = new ClaimsPrincipal(new ClaimsIdentity([new Claim(ClaimTypes.NameIdentifier, "42")]));
        Assert.Null(user.UserId);

        accessor.HttpContext = null;
        Assert.Null(user.UserId);
    }
}
