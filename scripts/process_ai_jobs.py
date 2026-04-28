#!/usr/bin/env python3
"""Process queued AI jobs."""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app import ai_queue
from app.database import SessionLocal


def run_once(limit: int, worker_id: str) -> int:
    db = SessionLocal()
    try:
        return ai_queue.process_ai_jobs(db, limit=limit, worker=worker_id)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(os.getenv("AI_JOB_LIMIT", "10")))
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--sleep", type=float, default=float(os.getenv("AI_JOB_SLEEP_SECONDS", "2")))
    args = parser.parse_args()

    worker_id = ai_queue.worker_id()
    if not args.loop:
        processed = run_once(args.limit, worker_id)
        print(f"Processed {processed} AI job(s).")
        return 0

    print(f"Processing AI jobs as {worker_id}. Press Ctrl+C to stop.")
    try:
        while True:
            processed = run_once(args.limit, worker_id)
            if processed == 0:
                time.sleep(args.sleep)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
