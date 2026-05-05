import argparse
from datetime import date, datetime, timedelta

from app.database import SessionLocal
from app.routers.admin_routes import aggregate_admin_daily_metrics
from app.statistics import aggregate_daily_stats


def parse_target_date(raw: str | None) -> date:
    if not raw:
        return date.today() - timedelta(days=1)
    return datetime.strptime(raw, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate Calimara admin dashboard metrics.")
    parser.add_argument("--date", help="Date to aggregate in YYYY-MM-DD format. Defaults to yesterday.")
    args = parser.parse_args()

    target_date = parse_target_date(args.date)
    db = SessionLocal()
    try:
        aggregate_daily_stats(db, target_date)
        aggregate_admin_daily_metrics(db, target_date)
    finally:
        db.close()


if __name__ == "__main__":
    main()
