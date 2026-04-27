#!/usr/bin/env python3
"""Process pending Google TTS jobs for approved posts."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app.audio_service import process_pending_tts_jobs
from app.database import SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=int(os.getenv("AUDIO_JOB_LIMIT", "5")))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        processed = process_pending_tts_jobs(db, limit=args.limit)
        print(f"Processed {processed} audio job(s).")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
