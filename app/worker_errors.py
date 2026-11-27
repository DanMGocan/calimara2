"""Classify errors in the background worker loops."""

from sqlalchemy import exc as sa_exc

# Messages PostgreSQL/psycopg2 give while the server restarts or is down.
_DATABASE_DOWN = (
    "connection refused",
    "could not connect to server",
    "the database system is shutting down",
    "the database system is starting up",
    "terminating connection due to administrator command",
    "server closed the connection unexpectedly",
)


def database_unavailable(error: BaseException) -> bool:
    """True if the error (or one it was raised from) means the database is not reachable right now.

    Automatic security updates restart PostgreSQL for a few seconds; the worker
    should wait and retry quietly instead of logging a full traceback.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (sa_exc.DisconnectionError, sa_exc.InvalidatePoolError)):
            return True
        if isinstance(current, (sa_exc.OperationalError, sa_exc.InterfaceError)) or type(current).__name__ in {
            "OperationalError",
            "InterfaceError",
        }:
            message = str(current).lower()
            if any(marker in message for marker in _DATABASE_DOWN):
                return True
        current = current.__cause__ or current.__context__
    return False
