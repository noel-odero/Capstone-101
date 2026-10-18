using System.Net.Sockets;
using Amr.Application.Errors;
using Amr.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.UnitTests.Infrastructure;

/// <summary>Which database failures are "the database is unavailable" (503) and which are "the write was rejected" (500).</summary>
public class PersistenceFailureClassifierTests
{
    private static PostgresException Postgres(string sqlState) => new("message", "ERROR", "ERROR", sqlState);

    [Theory]
    [InlineData("08006")]
    [InlineData("08001")]
    [InlineData("28P01")]
    [InlineData("53300")]
    [InlineData("57P01")]
    [InlineData("57P03")]
    [InlineData("58030")]
    public void Connection_authentication_resource_and_shutdown_failures_are_unavailability(string sqlState)
    {
        var error = PersistenceFailureClassifier.ForWrite(new DbUpdateException("wrapped", Postgres(sqlState)));

        Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.DatabaseUnavailable), (error.Category, error.Code));
    }

    [Theory]
    [InlineData("23505")]
    [InlineData("23503")]
    [InlineData("23514")]
    [InlineData("42P01")]
    [InlineData("22001")]
    public void Constraint_and_schema_failures_are_persistence_failures_not_unavailability(string sqlState)
    {
        var error = PersistenceFailureClassifier.ForWrite(new DbUpdateException("wrapped", Postgres(sqlState)));

        Assert.Equal((ErrorCategory.Internal, ErrorCodes.PersistenceFailed), (error.Category, error.Code));
    }

    [Fact]
    public void A_refused_connection_and_a_timeout_are_unavailability()
    {
        var refused = new NpgsqlException("connect failed", new SocketException((int)SocketError.ConnectionRefused));
        var timeout = new NpgsqlException("timeout", new TimeoutException());

        Assert.Equal(ErrorCodes.DatabaseUnavailable, PersistenceFailureClassifier.ForWrite(refused).Code);
        Assert.Equal(ErrorCodes.DatabaseUnavailable, PersistenceFailureClassifier.ForWrite(new InvalidOperationException("outer", timeout)).Code);
    }

    [Fact]
    public void An_unrelated_exception_is_a_persistence_failure()
    {
        Assert.Equal(ErrorCodes.PersistenceFailed, PersistenceFailureClassifier.ForWrite(new InvalidOperationException("bug")).Code);
    }

    [Fact]
    public void Errors_keep_the_cause_for_logs_but_say_nothing_about_it_to_clients()
    {
        var cause = Postgres("23505");

        var error = PersistenceFailureClassifier.ForWrite(new DbUpdateException("duplicate key value violates unique constraint ix_secret", cause));

        Assert.Same(cause, error.InnerException!.InnerException);
        Assert.DoesNotContain("constraint", error.Message, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("No record exists", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void Reads_that_fail_are_reported_as_an_unavailable_database()
    {
        var error = PersistenceFailureClassifier.ForRead(Postgres("42P01"));

        Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.DatabaseUnavailable), (error.Category, error.Code));
        Assert.DoesNotContain("No record exists", error.Message, StringComparison.Ordinal);
    }
}
