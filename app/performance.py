from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import models
from .week_util import utcnow_naive


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_INTERVAL_SECONDS = 60
HISTORY_RETENTION_HOURS = 24
PROCESS_COMMAND_LIMIT = 220


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _round(value: Any, digits: int = 2) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _iso(value: Any) -> str | None:
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _seconds_since(timestamp: float | None) -> int | None:
    if not timestamp:
        return None
    return max(0, int(datetime.now().timestamp() - timestamp))


def _process_role(name: str, cmd_text: str, ppid: int | None = None, app_server_pids: set[int] | None = None) -> str | None:
    lowered_name = name.lower()
    lowered_cmd = cmd_text.lower()
    project_marker = str(PROJECT_ROOT).lower()
    if "process_ai_jobs.py" in lowered_cmd:
        return "ai_worker"
    if "process_email_outbox.py" in lowered_cmd:
        return "email_worker"
    if "run.py" in lowered_cmd and "--serve" in lowered_cmd:
        return "app_server"
    if ppid in (app_server_pids or set()) and "multiprocessing.spawn" in lowered_cmd:
        return "app_worker"
    if "app.main:app" in lowered_cmd or ("uvicorn" in lowered_cmd and project_marker in lowered_cmd):
        return "app_worker"
    if lowered_name.startswith("nginx"):
        return "nginx"
    if "postgres" in lowered_name:
        return "postgres"
    return None


def _process_payload(proc: psutil.Process, role: str) -> dict:
    memory_info = proc.info.get("memory_info")
    cmdline = proc.info.get("cmdline") or []
    command = " ".join(cmdline)[:PROCESS_COMMAND_LIMIT]
    return {
        "pid": proc.info.get("pid"),
        "role": role,
        "name": proc.info.get("name"),
        "status": proc.info.get("status") or "unknown",
        "cpu_percent": _round(proc.info.get("cpu_percent"), 1),
        "rss_bytes": int(getattr(memory_info, "rss", 0) or 0),
        "uptime_seconds": _seconds_since(proc.info.get("create_time")),
        "command": command,
    }


def _aggregate_processes(processes: list[dict], role: str) -> dict:
    selected = [proc for proc in processes if proc["role"] == role]
    return {
        "count": len(selected),
        "rss_bytes": sum(int(proc.get("rss_bytes") or 0) for proc in selected),
        "cpu_percent": _round(sum(float(proc.get("cpu_percent") or 0) for proc in selected), 1),
    }


def process_metrics() -> dict:
    processes: list[dict] = []
    entries: list[tuple[psutil.Process, list[str]]] = []
    app_server_pids: set[int] = set()
    for proc in psutil.process_iter(["pid", "ppid", "name", "status", "create_time", "memory_info", "cpu_percent", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            entries.append((proc, cmdline))
            if _process_role(proc.info.get("name") or "", " ".join(cmdline)) == "app_server":
                app_server_pids.add(int(proc.info.get("pid") or 0))
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    for proc, cmdline in entries:
        try:
            role = _process_role(
                proc.info.get("name") or "",
                " ".join(cmdline),
                proc.info.get("ppid"),
                app_server_pids,
            )
            if not role:
                continue
            processes.append(_process_payload(proc, role))
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    processes.sort(key=lambda item: (item["role"], item["pid"] or 0))
    worker_roles = {"app_server", "app_worker", "ai_worker", "email_worker"}
    return {
        "workers": [proc for proc in processes if proc["role"] in worker_roles],
        "services": {
            "nginx": _aggregate_processes(processes, "nginx"),
            "postgres": _aggregate_processes(processes, "postgres"),
        },
    }


def host_metrics() -> dict:
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "cpu_count": psutil.cpu_count(logical=True) or 0,
        "cpu_percent": _round(psutil.cpu_percent(interval=None), 1),
        "load_average": {
            "one_minute": _round(load[0], 2),
            "five_minutes": _round(load[1], 2),
            "fifteen_minutes": _round(load[2], 2),
        },
        "memory": {
            "total_bytes": int(memory.total),
            "available_bytes": int(memory.available),
            "used_bytes": int(memory.used),
            "used_percent": _round(memory.percent, 1),
        },
        "swap": {
            "total_bytes": int(swap.total),
            "used_bytes": int(swap.used),
            "used_percent": _round(swap.percent, 1),
        },
        "disk": {
            "path": "/",
            "total_bytes": int(disk.total),
            "used_bytes": int(disk.used),
            "free_bytes": int(disk.free),
            "used_percent": _round(disk.percent, 1),
        },
        "booted_at": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        "uptime_seconds": _seconds_since(psutil.boot_time()),
    }


def runtime_config() -> dict:
    return {
        "python_version": sys.version.split()[0],
        "pid": os.getpid(),
        "uvicorn_workers": _env_int("UVICORN_WORKERS", 1),
        "db_pool_size": _env_int("DB_POOL_SIZE", 5),
        "db_max_overflow": _env_int("DB_MAX_OVERFLOW", 5),
        "db_pool_timeout": _env_int("DB_POOL_TIMEOUT", 10),
        "db_pool_recycle": _env_int("DB_POOL_RECYCLE", 1800),
        "public_api_cache_ttl_seconds": _env_int("PUBLIC_API_CACHE_TTL_SECONDS", 60),
        "slow_request_ms": _env_int("SLOW_REQUEST_MS", 750),
        "ai_worker_enabled": os.getenv("AI_WORKER_ENABLED", "true").lower() != "false",
        "email_worker_enabled": os.getenv("EMAIL_WORKER_ENABLED", "true").lower() != "false",
    }


def database_metrics(db: Session) -> dict:
    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "unknown")
    if dialect != "postgresql":
        return {
            "available": False,
            "dialect": dialect,
            "reason": "PostgreSQL metrics are not available for this test database.",
        }
    try:
        connections = db.execute(text(
            """
            SELECT
                count(*) AS total,
                count(*) FILTER (WHERE state = 'active') AS active,
                count(*) FILTER (WHERE state = 'idle') AS idle,
                count(*) FILTER (WHERE wait_event IS NOT NULL) AS waiting
            FROM pg_stat_activity
            WHERE datname = current_database()
            """
        )).mappings().one()
        cache_hit_percent = db.execute(text(
            """
            SELECT COALESCE(
                100.0 * SUM(heap_blks_hit) / NULLIF(SUM(heap_blks_hit) + SUM(heap_blks_read), 0),
                0
            ) AS ratio
            FROM pg_statio_user_tables
            """
        )).scalar()
        settings_rows = db.execute(text(
            """
            SELECT name, setting, unit
            FROM pg_settings
            WHERE name IN ('max_connections', 'shared_buffers', 'effective_cache_size', 'work_mem')
            """
        )).mappings().all()
        settings = {
            row["name"]: {"setting": row["setting"], "unit": row["unit"]}
            for row in settings_rows
        }
        size_bytes = db.execute(text("SELECT pg_database_size(current_database())")).scalar()
        version = db.execute(text("SHOW server_version")).scalar()
        return {
            "available": True,
            "dialect": dialect,
            "server_version": version,
            "size_bytes": int(size_bytes or 0),
            "cache_hit_percent": _round(cache_hit_percent, 2),
            "connections": {
                "total": int(connections["total"] or 0),
                "active": int(connections["active"] or 0),
                "idle": int(connections["idle"] or 0),
                "waiting": int(connections["waiting"] or 0),
                "max": int(settings.get("max_connections", {}).get("setting") or 0),
            },
            "settings": {
                key: value
                for key, value in settings.items()
                if key != "max_connections"
            },
        }
    except SQLAlchemyError as exc:
        db.rollback()
        return {"available": False, "dialect": dialect, "error": str(exc.__class__.__name__)}


def queue_metrics(db: Session) -> dict:
    now = utcnow_naive()
    try:
        ai_by_status = {
            str(status or "unknown"): int(count or 0)
            for status, count in db.query(models.AIJob.status, func.count()).group_by(models.AIJob.status).all()
        }
        email_by_status = {
            str(status or "unknown"): int(count or 0)
            for status, count in db.query(models.EmailOutbox.status, func.count()).group_by(models.EmailOutbox.status).all()
        }
        return {
            "ai": {
                "by_status": ai_by_status,
                "due": db.query(models.AIJob).filter(models.AIJob.status == "pending", models.AIJob.run_after <= now).count(),
                "processing": ai_by_status.get("processing", 0),
                "failed": ai_by_status.get("failed", 0),
            },
            "email": {
                "by_status": email_by_status,
                "due": db.query(models.EmailOutbox).filter(models.EmailOutbox.status == "queued", models.EmailOutbox.run_after <= now).count(),
                "sending": email_by_status.get("sending", 0),
                "failed": email_by_status.get("failed", 0),
            },
        }
    except SQLAlchemyError as exc:
        db.rollback()
        return {"available": False, "error": str(exc.__class__.__name__)}


def user_activity_metrics(db: Session) -> dict:
    now = utcnow_naive()
    active_cutoff = now - timedelta(minutes=15)
    day_cutoff = now - timedelta(hours=24)
    real_logged_in_filters = [
        models.PageView.user_id != None,
        models.PageView.is_bot == False,
        models.PageView.is_duplicate == False,
    ]
    try:
        active_now = db.query(func.count(func.distinct(models.PageView.user_id))).filter(
            *real_logged_in_filters,
            models.PageView.created_at >= active_cutoff,
        ).scalar()
        active_24h = db.query(func.count(func.distinct(models.PageView.user_id))).filter(
            *real_logged_in_filters,
            models.PageView.created_at >= day_cutoff,
        ).scalar()
        return {
            "active_now": int(active_now or 0),
            "active_window_minutes": 15,
            "active_24h": int(active_24h or 0),
            "active_24h_window_hours": 24,
        }
    except SQLAlchemyError as exc:
        db.rollback()
        return {"available": False, "error": str(exc.__class__.__name__)}


def collect_performance_metrics(db: Session) -> dict:
    captured_at = utcnow_naive()
    return {
        "captured_at": captured_at.isoformat(),
        "host": host_metrics(),
        "processes": process_metrics(),
        "database": database_metrics(db),
        "queues": queue_metrics(db),
        "users": user_activity_metrics(db),
        "runtime": runtime_config(),
    }


def _snapshots_available(db: Session) -> bool:
    try:
        return inspect(db.get_bind()).has_table(models.AdminPerformanceSnapshot.__tablename__)
    except SQLAlchemyError:
        db.rollback()
        return False


def maybe_store_performance_snapshot(db: Session, metrics: dict) -> dict:
    if not _snapshots_available(db):
        return {"available": False, "stored": False, "reason": "missing_table"}
    try:
        latest = (
            db.query(models.AdminPerformanceSnapshot)
            .order_by(models.AdminPerformanceSnapshot.captured_at.desc())
            .first()
        )
        now = utcnow_naive()
        if latest and latest.captured_at and latest.captured_at > now - timedelta(seconds=SNAPSHOT_INTERVAL_SECONDS):
            return {"available": True, "stored": False, "latest_at": _iso(latest.captured_at)}
        db.add(models.AdminPerformanceSnapshot(metrics=metrics))
        cutoff = now - timedelta(hours=HISTORY_RETENTION_HOURS)
        db.query(models.AdminPerformanceSnapshot).filter(models.AdminPerformanceSnapshot.captured_at < cutoff).delete(synchronize_session=False)
        db.commit()
        return {"available": True, "stored": True, "latest_at": now.isoformat()}
    except SQLAlchemyError as exc:
        db.rollback()
        return {"available": False, "stored": False, "error": str(exc.__class__.__name__)}


def performance_history(db: Session, hours: int = HISTORY_RETENTION_HOURS) -> dict:
    if not _snapshots_available(db):
        return {"available": False, "points": [], "reason": "missing_table"}
    cutoff = utcnow_naive() - timedelta(hours=max(1, min(hours, HISTORY_RETENTION_HOURS)))
    try:
        rows = (
            db.query(models.AdminPerformanceSnapshot)
            .filter(models.AdminPerformanceSnapshot.captured_at >= cutoff)
            .order_by(models.AdminPerformanceSnapshot.captured_at.asc())
            .all()
        )
        return {
            "available": True,
            "points": [
                {"captured_at": _iso(row.captured_at), "metrics": row.metrics or {}}
                for row in rows
            ],
        }
    except SQLAlchemyError as exc:
        db.rollback()
        return {"available": False, "points": [], "error": str(exc.__class__.__name__)}
