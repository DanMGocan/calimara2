"""Background workers wait quietly while the database restarts."""

from pathlib import Path

import psycopg2
from sqlalchemy import exc as sa_exc

from app.worker_errors import database_unavailable

ROOT = Path(__file__).resolve().parents[1]


def _wrapped(message: str) -> sa_exc.OperationalError:
    return sa_exc.OperationalError("SELECT 1", {}, psycopg2.OperationalError(message))


def test_restart_errors_are_recognised():
    assert database_unavailable(_wrapped('connection to server at "localhost" (::1), port 5432 failed: Connection refused'))
    assert database_unavailable(_wrapped("FATAL:  the database system is starting up"))
    assert database_unavailable(_wrapped("server closed the connection unexpectedly"))
    assert database_unavailable(sa_exc.InvalidatePoolError())


def test_cause_chain_is_followed():
    try:
        try:
            raise _wrapped("Connection refused")
        except sa_exc.OperationalError as inner:
            raise RuntimeError("iteration failed") from inner
    except RuntimeError as outer:
        assert database_unavailable(outer)


def test_real_errors_still_count():
    assert not database_unavailable(_wrapped('relation "posts" does not exist'))
    assert not database_unavailable(ValueError("Connection refused"))
    assert not database_unavailable(sa_exc.IntegrityError("INSERT", {}, Exception("duplicate key")))


def test_worker_loops_use_it():
    for name in ("scripts/process_ai_jobs.py", "scripts/process_email_outbox.py"):
        source = (ROOT / name).read_text()
        assert "worker_errors.database_unavailable(exc)" in source
        assert source.index("database_unavailable") < source.index("traceback.print_exc()")
