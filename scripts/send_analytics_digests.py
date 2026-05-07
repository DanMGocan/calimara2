#!/usr/bin/env python3
"""Queue due analytics digest emails."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app import email_service
from app.database import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="UTC date to evaluate in YYYY-MM-DD format. Defaults to current UTC date.")
    args = parser.parse_args()
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else None

    db = SessionLocal()
    try:
        queued = email_service.queue_due_analytics_digests(db, today=today)
        print(f"Queued {queued} analytics digest email(s).")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
