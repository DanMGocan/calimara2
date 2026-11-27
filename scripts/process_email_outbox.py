#!/usr/bin/env python3
"""Process queued transactional emails."""

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app import email_service, worker_errors
from app.database import SessionLocal


def run_once(limit: int, worker_id: str) -> int:
    db = SessionLocal()
    try:
        return email_service.process_email_outbox(db, limit=limit, worker=worker_id)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(os.getenv("EMAIL_OUTBOX_LIMIT", "20")))
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--sleep", type=float, default=float(os.getenv("EMAIL_OUTBOX_SLEEP_SECONDS", "5")))
    args = parser.parse_args()

    worker_id = email_service.worker_id()
    if not args.loop:
        processed = run_once(args.limit, worker_id)
        print(f"Processed {processed} email(s).")
        return 0

    print(f"Processing email outbox as {worker_id}. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                processed = run_once(args.limit, worker_id)
            except Exception as exc:
                if worker_errors.database_unavailable(exc):
                    # Usually PostgreSQL restarting after a security update: wait, no traceback.
                    print("Email worker: database unavailable, retrying in 5s", file=sys.stderr)
                    time.sleep(max(args.sleep, 5))
                    continue
                print(f"Email worker iteration failed: {exc}", file=sys.stderr)
                traceback.print_exc()
                time.sleep(args.sleep)
                continue
            if processed == 0:
                time.sleep(args.sleep)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
