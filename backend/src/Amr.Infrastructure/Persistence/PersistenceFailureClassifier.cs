using System.Data.Common;
using System.Net.Sockets;
using Amr.Application.Errors;
using Npgsql;

namespace Amr.Infrastructure.Persistence;

/// <summary>
/// Decides whether a database exception means the database cannot be reached (503) or the write itself was rejected (500).
/// Connection, authentication, resource and shutdown failures are "unavailable"; constraint and schema errors are not.
/// </summary>
internal static class PersistenceFailureClassifier
{
    public static AmrException ForWrite(Exception exception) =>
        IsUnavailable(exception) ? PersistenceErrors.Unavailable(exception) : PersistenceErrors.Failed(exception);

    public static AmrException ForRead(Exception exception) => PersistenceErrors.ReadFailed(exception);

    public static bool IsUnavailable(Exception exception)
    {
        for (var current = exception; current is not null; current = current.InnerException)
        {
            switch (current)
            {
                case PostgresException postgres:
                    return IsUnavailableSqlState(postgres.SqlState);
                case NpgsqlException or SocketException or TimeoutException or IOException:
                    return true;
                case DbException:
                    return false;
            }
        }

        return false;
    }

    /// <summary>Classes 08 (connection), 28 (authorization), 53 (resources), 57P (operator shutdown) and 58 (system error).</summary>
    private static bool IsUnavailableSqlState(string sqlState) =>
        sqlState.StartsWith("08", StringComparison.Ordinal)
        || sqlState.StartsWith("28", StringComparison.Ordinal)
        || sqlState.StartsWith("53", StringComparison.Ordinal)
        || sqlState.StartsWith("57P", StringComparison.Ordinal)
        || sqlState.StartsWith("58", StringComparison.Ordinal);
}
