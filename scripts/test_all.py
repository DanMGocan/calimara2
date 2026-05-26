#!/usr/bin/env python3
"""Run the full Calimara regression suite.

This command intentionally exercises both backend tests and real browser flows.
It uses the configured development database, but E2E setup is constrained to
deterministic e2e-prefixed records managed by scripts/e2e_data.py.
"""

from __future__ import annotations

import argparse
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
LOG_DIR = ROOT / "temp" / "e2e-logs"
DEFAULT_BACKEND_PORT = 18100
DEFAULT_FRONTEND_PORT = 18173
__test__ = False


class RunningProcess:
    def __init__(self, name: str, process: subprocess.Popen, log_path: Path):
        self.name = name
        self.process = process
        self.log_path = log_path

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except Exception:
            self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception:
                self.process.kill()
            self.process.wait(timeout=5)


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd), env=env, check=True)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_url(url: str, *, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request = Request(url, headers={"Accept": "application/json,text/html"})
            with urlopen(request, timeout=3) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001 - diagnostics only
            last_error = exc
        time.sleep(0.5)
    detail = f": {last_error}" if last_error else ""
    raise RuntimeError(f"Timed out waiting for {url}{detail}")


def tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    data = path.read_text(errors="replace").splitlines()
    return "\n".join(data[-lines:])


def build_e2e_env(backend_port: int, frontend_port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "CALIMARA_RESET_DATABASE": "false",
            "AI_WORKER_ENABLED": "false",
            "MAIN_DOMAIN": "localhost",
            "SUBDOMAIN_SUFFIX": ".localhost",
            "PUBLIC_SCHEME": "http",
            "HTTPS_ONLY": "false",
            "GOOGLE_REDIRECT_URI": f"http://localhost:{frontend_port}/auth/google/callback",
            "FACEBOOK_REDIRECT_URI": f"http://localhost:{frontend_port}/autentificare/facebook/raspuns",
            "STATS_ENABLED": "false",
            "BOT_DETECTION_ENABLED": "false",
            "MODERATION_ENABLED": "false",
            "AI_CRITIC_ENABLED": "false",
            "EMAILS_ENABLED": "false",
            "AUDIO_STORAGE_BACKEND": "local",
            "AUDIO_LOCAL_DIR": str(ROOT / "temp" / "e2e" / "audio"),
            "PROFILE_MEDIA_STORAGE_BACKEND": "local",
            "PROFILE_MEDIA_LOCAL_DIR": str(ROOT / "temp" / "e2e" / "profile-media"),
            "VITE_DEV_PORT": str(frontend_port),
            "VITE_API_PROXY_TARGET": f"http://127.0.0.1:{backend_port}",
            "VITE_MAIN_DOMAIN": "localhost",
            "VITE_SUBDOMAIN_SUFFIX": ".localhost",
            "VITE_ADS_ENABLED": "false",
            "E2E_BASE_URL": f"http://localhost:{frontend_port}",
            "E2E_API_BASE_URL": f"http://127.0.0.1:{backend_port}",
        }
    )
    return env


def start_process(name: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> RunningProcess:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    log_file = log_path.open("w", encoding="utf-8")
    print(f"\n$ {' '.join(command)}  # log: {log_path}")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return RunningProcess(name, process, log_path)


def ensure_frontend_dependencies() -> None:
    if not command_exists("npm"):
        raise RuntimeError("npm is required for frontend build and Playwright tests.")
    if not (FRONTEND / "node_modules").exists():
        run(["npm", "install"], cwd=FRONTEND)


def maybe_install_browser(skip_install: bool, env: dict[str, str]) -> None:
    if skip_install:
        return
    run(["npx", "playwright", "install", "chromium"], cwd=FRONTEND, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend, build, and browser regression tests.")
    parser.add_argument("--headed", action="store_true", help="Run Playwright headed.")
    parser.add_argument("--keep-e2e-data", action="store_true", help="Leave e2e_* records in the dev DB for debugging.")
    parser.add_argument("--skip-browser", action="store_true", help="Run pytest and frontend build only.")
    parser.add_argument("--skip-browser-install", action="store_true", help="Do not run playwright install chromium.")
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    args = parser.parse_args()

    backend_port = free_port(args.backend_port)
    frontend_port = free_port(args.frontend_port)
    e2e_env = build_e2e_env(backend_port, frontend_port)
    processes: list[RunningProcess] = []

    try:
        ensure_frontend_dependencies()
        run([sys.executable, "-m", "pytest", "tests"])
        run(["npm", "run", "build"], cwd=FRONTEND)

        if args.skip_browser:
            return 0

        maybe_install_browser(args.skip_browser_install, e2e_env)
        run([sys.executable, "scripts/e2e_data.py", "cleanup"], env=e2e_env)
        run([sys.executable, "scripts/e2e_data.py", "seed"], env=e2e_env)

        backend = start_process(
            "backend",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(backend_port),
            ],
            cwd=ROOT,
            env=e2e_env,
        )
        processes.append(backend)
        wait_for_url(f"http://127.0.0.1:{backend_port}/api/prima-pagina?category=toate")

        frontend = start_process(
            "frontend",
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=FRONTEND,
            env=e2e_env,
        )
        processes.append(frontend)
        wait_for_url(f"http://localhost:{frontend_port}/")

        command = ["npm", "run", "test:e2e"]
        if args.headed:
            command.append("--")
            command.append("--headed")
        run(command, cwd=FRONTEND, env=e2e_env)
        return 0
    except (subprocess.CalledProcessError, RuntimeError, URLError) as exc:
        print(f"\nFull test suite failed: {exc}", file=sys.stderr)
        for running in processes:
            print(f"\n--- {running.name} log tail ({running.log_path}) ---", file=sys.stderr)
            print(tail(running.log_path), file=sys.stderr)
        return 1
    finally:
        for running in reversed(processes):
            running.stop()
        if not args.keep_e2e_data and not args.skip_browser:
            try:
                run([sys.executable, "scripts/e2e_data.py", "cleanup"], env=e2e_env)
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                print(f"E2E cleanup failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
