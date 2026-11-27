"""Tests for scripts/nightly_report.py."""

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "nightly_report.py"
spec = importlib.util.spec_from_file_location("nightly_report_under_test", SCRIPT)
report = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = report
spec.loader.exec_module(report)

NOW = datetime(2026, 11, 28, 3, 30, tzinfo=timezone.utc)


def _status(tmp_path, **data):
    path = tmp_path / "last_backup.json"
    path.write_text(json.dumps(data))
    return path


def test_backup_ok_lists_db_media_and_cleanup(tmp_path):
    path = _status(
        tmp_path, ok=True, at=(NOW - timedelta(hours=1)).isoformat(), size_bytes=340_000,
        kept=["a", "b"], media={"files": 3, "bytes": 2_000_000, "uploaded": 1, "moved_to_deleted": 0},
        sweep={"deleted": 2, "deleted_bytes": 4096},
    )
    checks = report.check_backup(NOW, path)
    assert [c.name for c in checks] == ["Database backup", "Media backup", "Server file cleanup"]
    assert all(c.ok for c in checks)
    assert "2 kept" in checks[0].detail and "Deleted 2" in checks[2].detail


def test_backup_failure_and_staleness_and_missing(tmp_path):
    failed = _status(tmp_path, ok=False, at=NOW.isoformat(), error="upload: timeout")
    assert report.check_backup(NOW, failed)[0].ok is False
    assert "timeout" in report.check_backup(NOW, failed)[0].detail

    stale = _status(tmp_path, ok=True, at=(NOW - timedelta(hours=30)).isoformat())
    assert report.check_backup(NOW, stale)[0].ok is False

    assert report.check_backup(NOW, tmp_path / "missing.json")[0].ok is False


LOG = '''INFO:     1.2.3.4:0 - "GET / HTTP/1.1" 200 OK
INFO:     1.2.3.4:0 - "GET /api/audio/postari/10 HTTP/1.1" 500 Internal Server Error
INFO:     1.2.3.4:0 - "GET /api/audio/postari/10 HTTP/1.1" 500 Internal Server Error
INFO:     54.1.1.1:0 - "POST /api/stripe/notificare HTTP/1.1" 200 OK
INFO:     54.1.1.1:0 - "POST /api/stripe/notificare HTTP/1.1" 400 Bad Request
Traceback (most recent call last):
psycopg2.OperationalError: connection refused
Traceback (most recent call last):
  File "/home/dan/calimara2/run.py", line 73, in signal_handler
SystemExit: 0
Exception ignored in atexit callback: <bound method finalize._exitfunc>
'''


def test_app_log_counts_real_errors_and_webhooks():
    errors, stripe = report.summarize_app_log(LOG)

    assert errors.ok is False
    assert errors.detail.startswith("1 tracebacks, 2 server errors")
    assert "/api/audio/postari/10 ×2" in errors.detail
    assert "psycopg2.OperationalError: connection refused" in errors.detail
    assert stripe.ok is False and "1 accepted, 1 rejected (HTTP 400)" in stripe.detail


def test_shutdown_noise_alone_is_ok():
    log = 'Traceback (most recent call last):\nSystemExit: 0\nINFO: "GET / HTTP/1.1" 200 OK\n'
    errors, stripe = report.summarize_app_log(log)
    assert errors.ok is True and stripe.ok is True


def test_crashing_check_is_reported_not_fatal():
    def boom(now):
        raise RuntimeError("journal unreadable")

    results = report.run_checks(NOW, [("Broken", boom), ("Fine", lambda now: [report.Check("Fine", True, "ok")])])

    assert [(c.name, c.ok) for c in results] == [("Broken", False), ("Fine", True)]
    assert "journal unreadable" in results[0].detail


def test_email_lists_failures_first_and_escapes_html():
    results = [report.Check("Disk space", True, "5% used"), report.Check("Backup", False, "<b>boom</b>")]
    subject, html_body, text = report.build_email(results, NOW)

    assert subject == "Călimara nightly report 2026-11-28: 1 problem"
    assert html_body.index("Failed (1)") < html_body.index("Working (1)")
    assert "&lt;b&gt;boom&lt;/b&gt;" in html_body and "<b>boom</b>" not in html_body
    assert text.index("FAILED") < text.index("WORKING")

    subject_ok, _, _ = report.build_email([report.Check("Disk space", True, "ok")], NOW)
    assert subject_ok.endswith("all OK")


def test_send_failure_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(report, "run_checks", lambda now: [report.Check("Disk space", True, "ok")])

    def fail(*args):
        raise RuntimeError("Brevo down")

    monkeypatch.setattr(report, "send_email", fail)
    assert report.main([]) == 1
    assert "Brevo down" in capsys.readouterr().err


def test_sends_to_configured_recipient(monkeypatch):
    sent = {}
    monkeypatch.setattr(report, "run_checks", lambda now: [report.Check("Disk space", True, "ok")])
    monkeypatch.setattr(report, "send_email", lambda to, subject, h, t: sent.update(to=to, subject=subject) or "id-1")
    monkeypatch.setenv("NIGHTLY_REPORT_EMAIL", "contact@calimara.ro")

    assert report.main([]) == 0
    assert sent["to"] == "contact@calimara.ro" and "all OK" in sent["subject"]


def test_website_down_still_checks_public_site(monkeypatch):
    def fake(url):
        if "127.0.0.1" in url:
            raise ConnectionRefusedError("refused")
        return 200

    monkeypatch.setattr(report, "_http_status", fake)
    local, public = report.check_website()

    assert local.ok is False and "refused" in local.detail
    assert public.ok is True


def test_backup_status_tolerates_naive_time_and_nulls(tmp_path):
    path = _status(
        tmp_path, ok=True, at=(NOW - timedelta(hours=1)).replace(tzinfo=None).isoformat(), size_bytes=None,
        kept=None, media={"files": None, "bytes": None, "uploaded": None, "moved_to_deleted": None},
        sweep={"deleted": None, "deleted_bytes": None},
    )
    assert all(c.ok for c in report.check_backup(NOW, path))
