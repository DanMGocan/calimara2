#!/usr/bin/env python3
"""Email a nightly health report: what worked and what failed in the last 24 hours.

Runs from calimara-nightly-report.timer, after the nightly backup. Sends to
NIGHTLY_REPORT_EMAIL (default contact@calimara.ro) straight through Brevo, so
the report still arrives when the database is down. `--dry-run` prints it.

Each check is independent: one that crashes is reported as failed, never
stops the others or the email.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

BACKUP_STATUS_FILE = PROJECT_ROOT / "logs" / "last_backup.json"
BACKUP_MAX_AGE = timedelta(hours=26)
DISK_WARN_PERCENT = 85


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


# --- helpers ---------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 30) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout


def _journal(unit: str, since: str = "-24h") -> str:
    return _run(["journalctl", "-u", unit, "--since", since, "--no-pager", "-q", "-o", "cat"], timeout=60)


def _http_status(url: str) -> int:
    import httpx

    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        return client.get(url).status_code


def _kib(value: float) -> str:
    return f"{value / 1024:.0f} KiB" if value < 1024 * 1024 else f"{value / 1024 / 1024:.1f} MiB"


# --- checks ----------------------------------------------------------------


def check_backup(now: datetime, status_file: Path = BACKUP_STATUS_FILE) -> list[Check]:
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [Check("Backup", False, "No backup status found: the backup has not run.")]
    at = datetime.fromisoformat(data["at"]) if data.get("at") else None
    if at is not None and at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if at is None or now - at > BACKUP_MAX_AGE:
        when = at.strftime("%Y-%m-%d %H:%M UTC") if at else "never"
        return [Check("Backup", False, f"Last backup ran {when}, more than 26 hours ago.")]
    if not data.get("ok"):
        return [Check("Backup", False, data.get("error") or "Backup failed (no error recorded).")]

    checks = [Check("Database backup", True, f"{_kib(data.get('size_bytes') or 0)} dump, {len(data.get('kept') or [])} kept in the bucket.")]
    media = data.get("media")
    if media:
        checks.append(Check(
            "Media backup", True,
            f"{media.get('files') or 0} files ({_kib(media.get('bytes') or 0)}), {media.get('uploaded') or 0} uploaded, "
            f"{media.get('moved_to_deleted') or 0} moved to media-deleted.",
        ))
    sweep = data.get("sweep")
    if sweep:
        checks.append(Check(
            "Server file cleanup", True,
            f"Deleted {sweep.get('deleted') or 0} unused files ({_kib(sweep.get('deleted_bytes') or 0)}).",
        ))
    return checks


def _website_check(name: str, url: str) -> Check:
    try:
        code = _http_status(url)
    except Exception as exc:  # refused, timeout, DNS: the site is down for visitors
        return Check(name, False, f"Unreachable: {type(exc).__name__}: {exc}"[:300])
    return Check(name, code == 200, f"HTTP {code}")


def check_website() -> list[Check]:
    domain = os.getenv("MAIN_DOMAIN", "calimara.ro").strip() or "calimara.ro"
    return [
        _website_check("Website (server)", "http://127.0.0.1:8000/"),
        _website_check(f"Website (https://{domain})", f"https://{domain}/"),
    ]


def check_services() -> list[Check]:
    checks = []
    for unit, label in (("calimara", "App service"), ("postgresql@16-main", "PostgreSQL")):
        state = _run(["systemctl", "is-active", unit]).strip() or "unknown"
        checks.append(Check(label, state == "active", state))
    restarts = len(re.findall(r"Started calimara\.service", _run(
        ["journalctl", "-u", "calimara", "--since", "-24h", "--no-pager", "-q"], timeout=60)))
    if restarts > 3:
        checks.append(Check("App restarts", False, f"{restarts} restarts in 24h."))
    return checks


def check_disk(path: str = "/") -> list[Check]:
    usage = shutil.disk_usage(path)
    percent = usage.used / usage.total * 100
    return [Check("Disk space", percent < DISK_WARN_PERCENT, f"{percent:.0f}% used, {usage.free / 1024**3:.0f} GB free.")]


def summarize_app_log(log: str) -> list[Check]:
    """Errors and failed requests from the app's log text."""
    # Restarts print SystemExit tracebacks from run.py's signal handler: not errors.
    shutdowns = len(re.findall(r"^SystemExit\b", log, flags=re.MULTILINE))
    tracebacks = max(0, log.count("Traceback (most recent call last)") - shutdowns)
    error_lines = [
        line.strip() for line in re.findall(r"^[\w.]*(?:Error|Exception)\b:? .*$", log, flags=re.MULTILINE)
        if not line.startswith("Exception ignored")
    ]
    server_errors = re.findall(r'"[A-Z]+ (\S+) HTTP/[\d.]+" (5\d\d)', log)
    webhook = re.findall(r'"POST /api/stripe/notificare HTTP/[\d.]+" (\d{3})', log)
    webhook_bad = [code for code in webhook if code != "200"]

    checks = []
    detail = f"{tracebacks} tracebacks, {len(server_errors)} server errors (5xx)."
    if server_errors:
        paths: dict[str, int] = {}
        for path, _code in server_errors:
            paths[path] = paths.get(path, 0) + 1
        top = sorted(paths.items(), key=lambda item: -item[1])[:3]
        detail += " Most: " + ", ".join(f"{path} ×{count}" for path, count in top)
    if tracebacks and error_lines:
        counts: dict[str, int] = {}
        for line in error_lines:
            counts[line[:160]] = counts.get(line[:160], 0) + 1
        common, times = max(counts.items(), key=lambda item: (item[1], len(item[0])))
        detail += f" Most common: {common} (×{times})"
    checks.append(Check("App errors", tracebacks == 0 and not server_errors, detail))
    if webhook:
        checks.append(Check(
            "Stripe payment notifications", not webhook_bad,
            f"{len(webhook) - len(webhook_bad)} accepted, {len(webhook_bad)} rejected"
            + (f" (HTTP {', '.join(sorted(set(webhook_bad)))})." if webhook_bad else "."),
        ))
    else:
        checks.append(Check("Stripe payment notifications", True, "None received."))
    return checks


def check_app_log() -> list[Check]:
    return summarize_app_log(_journal("calimara"))


def check_database(now: datetime) -> list[Check]:
    from sqlalchemy import func, text

    from app import models
    from app.database import SessionLocal

    since = (now - timedelta(hours=24)).replace(tzinfo=None)
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks = [Check("Database", True, "Reachable.")]
        sent = db.query(func.count(models.EmailOutbox.id)).filter(
            models.EmailOutbox.status == "sent", models.EmailOutbox.updated_at >= since).scalar() or 0
        failed = db.query(func.count(models.EmailOutbox.id)).filter(
            models.EmailOutbox.status == "failed", models.EmailOutbox.updated_at >= since).scalar() or 0
        stuck = db.query(func.count(models.EmailOutbox.id)).filter(
            models.EmailOutbox.status == "queued",
            models.EmailOutbox.created_at < now.replace(tzinfo=None) - timedelta(hours=1)).scalar() or 0
        checks.append(Check("Emails", failed == 0 and stuck == 0, f"{sent} sent, {failed} failed, {stuck} waiting over an hour."))
        done = db.query(func.count(models.AIJob.id)).filter(
            models.AIJob.status == "completed", models.AIJob.updated_at >= since).scalar() or 0
        job_failures = db.query(models.AIJob.job_type, func.count(models.AIJob.id)).filter(
            models.AIJob.status == "failed", models.AIJob.updated_at >= since).group_by(models.AIJob.job_type).all()
        failed_jobs = sum(count for _, count in job_failures)
        detail = f"{done} completed, {failed_jobs} failed."
        if job_failures:
            detail += " Failed: " + ", ".join(f"{job_type} ×{count}" for job_type, count in job_failures)
        checks.append(Check("AI jobs (moderation, critic, audio)", failed_jobs == 0, detail))
        return checks
    finally:
        db.close()


CHECKS: list[tuple[str, Callable[[datetime], list[Check]]]] = [
    ("Backup", check_backup),
    ("Website", lambda now: check_website()),
    ("Services", lambda now: check_services()),
    ("Database", check_database),
    ("App log", lambda now: check_app_log()),
    ("Disk space", lambda now: check_disk()),
]


def run_checks(now: datetime, checks=None) -> list[Check]:
    results: list[Check] = []
    for label, fn in checks or CHECKS:
        try:
            results.extend(fn(now))
        except Exception as exc:  # a broken check is itself a failure to report
            results.append(Check(label, False, f"Check crashed: {type(exc).__name__}: {exc}"[:300]))
    return results


# --- email -----------------------------------------------------------------


def build_email(results: list[Check], now: datetime) -> tuple[str, str, str]:
    failed = [check for check in results if not check.ok]
    passed = [check for check in results if check.ok]
    day = now.strftime("%Y-%m-%d")
    if failed:
        subject = f"Călimara nightly report {day}: {len(failed)} problem{'s' if len(failed) != 1 else ''}"
    else:
        subject = f"Călimara nightly report {day}: all OK"

    def rows(checks: list[Check], mark: str, colour: str) -> str:
        return "".join(
            f'<tr><td style="padding:6px 10px 6px 0;color:{colour};font-weight:bold;vertical-align:top;">{mark}</td>'
            f'<td style="padding:6px 12px 6px 0;vertical-align:top;"><strong>{html.escape(c.name)}</strong></td>'
            f'<td style="padding:6px 0;vertical-align:top;">{html.escape(c.detail)}</td></tr>'
            for c in checks
        )

    sections = []
    if failed:
        sections.append(f'<h2 style="font-size:16px;color:#a12a1f;">Failed ({len(failed)})</h2>'
                        f'<table role="presentation" style="border-collapse:collapse;">{rows(failed, "✗", "#a12a1f")}</table>')
    sections.append(f'<h2 style="font-size:16px;color:#2f6b3a;">Working ({len(passed)})</h2>'
                    f'<table role="presentation" style="border-collapse:collapse;">{rows(passed, "✓", "#2f6b3a")}</table>')
    html_body = (
        '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.45;color:#1f1d1b;">'
        f'<p>Health check for the last 24 hours, run {now.strftime("%Y-%m-%d %H:%M UTC")}.</p>'
        + "".join(sections) + "</div>"
    )

    lines = [subject, ""]
    if failed:
        lines += [f"FAILED ({len(failed)})"] + [f"  ✗ {c.name}: {c.detail}" for c in failed] + [""]
    lines += [f"WORKING ({len(passed)})"] + [f"  ✓ {c.name}: {c.detail}" for c in passed]
    return subject, html_body, "\n".join(lines)


def send_email(recipient: str, subject: str, html_body: str, text_body: str) -> str:
    from app import email_service

    message = SimpleNamespace(
        recipient_email=recipient,
        recipient_name="Călimara",
        subject=subject,
        html_content=html_body,
        text_content=text_body,
    )
    return email_service._send_with_brevo(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the report instead of emailing it")
    args = parser.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    now = datetime.now(timezone.utc)
    results = run_checks(now)
    subject, html_body, text_body = build_email(results, now)
    if args.dry_run:
        print(text_body)
        return 0
    recipient = (os.getenv("NIGHTLY_REPORT_EMAIL") or "contact@calimara.ro").strip()
    try:
        message_id = send_email(recipient, subject, html_body, text_body)
    except Exception as exc:
        print(f"Report email FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(text_body, file=sys.stderr)
        return 1
    print(f"Report sent to {recipient} ({message_id or 'no id'}): {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
