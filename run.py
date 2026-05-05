#!/usr/bin/env python3
"""
Calimara development/server runner.
Initializes the database from schema.sql, installs frontend
dependencies, and starts uvicorn.
"""
import os
import sys
import shutil
import signal
import socket
import subprocess
import atexit
import time
import re
import getpass
import pwd
import grp
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"

load_dotenv(PROJECT_ROOT / ".env")

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "calimara_db")
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "localhost").strip()
SUBDOMAIN_SUFFIX = os.getenv("SUBDOMAIN_SUFFIX", ".localhost").strip()
PUBLIC_SCHEME = os.getenv("PUBLIC_SCHEME", "").strip()
SYSTEMD_SERVICE_NAME = os.getenv("SYSTEMD_SERVICE_NAME", "calimara").strip()
DEV_PREMIUM_USER_EMAIL = "gocandan@gmail.com"
DEV_PREMIUM_USER_USERNAME = "gocandan"
DEV_PREMIUM_USER_GOOGLE_ID = "seed-google-gocandan"
REQUIRED_SEED_TABLES = {
    "users": 5,
    "posts": 1,
    "shop_items": 1,
}
# Track child processes for cleanup
child_processes = []


def cleanup():
    """Kill all child processes on exit."""
    for proc in child_processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


atexit.register(cleanup)


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\nShutting down...")
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def public_base_url() -> str:
    """Return the public browser URL configured for links and OAuth redirects."""
    if "://" in MAIN_DOMAIN:
        return MAIN_DOMAIN.rstrip("/")

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    redirect_scheme = urlparse(redirect_uri).scheme
    scheme = PUBLIC_SCHEME or redirect_scheme or ("https" if env_bool("HTTPS_ONLY") else "http")
    return f"{scheme}://{MAIN_DOMAIN}".rstrip("/")


def systemd_available() -> bool:
    """Return True when this host appears to be booted with systemd."""
    return shutil.which("systemctl") is not None and Path("/run/systemd/system").exists()


def sudo_prefix() -> list[str]:
    if os.geteuid() == 0:
        return []
    return ["sudo"]


def service_unit_name() -> str:
    return SYSTEMD_SERVICE_NAME if SYSTEMD_SERVICE_NAME.endswith(".service") else f"{SYSTEMD_SERVICE_NAME}.service"


def service_file_path() -> Path:
    return Path("/etc/systemd/system") / service_unit_name()


def service_exists() -> bool:
    if not systemd_available():
        return False
    result = subprocess.run(
        ["systemctl", "cat", service_unit_name()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def systemd_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")


def service_user_and_group() -> tuple[str, str]:
    username = os.getenv("SUDO_USER") or getpass.getuser()
    try:
        info = pwd.getpwnam(username)
        group = grp.getgrgid(info.pw_gid).gr_name
    except KeyError:
        group = username
    return username, group


def python_for_service() -> Path:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def build_systemd_unit() -> str:
    user, group = service_user_and_group()
    python_bin = python_for_service()
    path_env = os.environ.get(
        "PATH",
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    )
    service_name = service_unit_name()
    return f"""[Unit]
Description=Calimara FastAPI application
After=network-online.target postgresql.service nginx.service
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={PROJECT_ROOT}
Environment="PYTHONUNBUFFERED=1"
Environment="PATH={systemd_escape(path_env)}"
ExecStart={python_bin} {PROJECT_ROOT / "run.py"} --serve
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
"""


def run_systemctl(*args: str):
    subprocess.run([*sudo_prefix(), "systemctl", *args], check=True)


def install_systemd_service():
    """Create and enable the systemd service used to keep Calimara online."""
    if not systemd_available():
        print("  systemd was not detected. Starting in the foreground instead.")
        return False

    if not SYSTEMD_SERVICE_NAME:
        print("  SYSTEMD_SERVICE_NAME is empty. Starting in the foreground instead.")
        return False

    unit_path = service_file_path()
    unit_content = build_systemd_unit()

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        tmp.write(unit_content)
        tmp_path = tmp.name

    try:
        subprocess.run(
            [*sudo_prefix(), "install", "-m", "0644", tmp_path, str(unit_path)],
            check=True,
        )
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass

    run_systemctl("daemon-reload")
    run_systemctl("enable", service_unit_name())
    print(f"  Installed systemd service: {unit_path}")
    return True


def manage_systemd_service_if_needed():
    """Install/restart the persistent service for normal interactive runs."""
    if "--serve" in sys.argv or os.getenv("CALIMARA_SKIP_SYSTEMD", "").lower() in ("1", "true", "yes"):
        return

    if not systemd_available():
        print("  systemd was not detected. Continuing in foreground mode.")
        return

    print("[0/4] Checking systemd service...")

    if not service_exists():
        print(f"  {service_unit_name()} was not found. Creating it now.")
        install_systemd_service()
    else:
        print(f"  {service_unit_name()}: OK")

    print(f"  Restarting {service_unit_name()} with automatic restarts enabled.")
    run_systemctl("restart", service_unit_name())
    run_systemctl("enable", service_unit_name())
    print()
    print(f"  Service started: {service_unit_name()}")
    print(f"  Public URL: {public_base_url()}")
    print()
    print("  Follow logs with:")
    print(f"    journalctl -u {service_unit_name()} -f")
    print()
    print("  Stop the service with:")
    print(f"    sudo systemctl stop {service_unit_name()}")
    print()
    print("  Note: run.py does not run database migrations.")
    print("  Existing database data is preserved unless CALIMARA_RESET_DATABASE=true is set.")
    sys.exit(0)


def check_env():
    """Verify required environment variables are set."""
    missing = []
    if not DB_USER:
        missing.append("DB_USER")
    if not DB_PASSWORD:
        missing.append("DB_PASSWORD")
    if not os.getenv("SESSION_SECRET_KEY"):
        missing.append("SESSION_SECRET_KEY")
    if not MAIN_DOMAIN:
        missing.append("MAIN_DOMAIN")
    if not SUBDOMAIN_SUFFIX:
        missing.append("SUBDOMAIN_SUFFIX")

    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Please configure them in your .env file.")
        sys.exit(1)

    if not SUBDOMAIN_SUFFIX.startswith("."):
        print("SUBDOMAIN_SUFFIX must start with a dot, e.g. .calimara.ro")
        sys.exit(1)

    google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    expected_redirect_uri = f"{public_base_url()}/autentificare/google/raspuns"
    if google_redirect_uri and google_redirect_uri != expected_redirect_uri:
        print("  Warning: GOOGLE_REDIRECT_URI does not match the configured public domain.")
        print(f"  Expected: {expected_redirect_uri}")
        print(f"  Current:  {google_redirect_uri}")


def check_port_available(host: str, port: int):
    """Fail before resetting the database if the app port is already in use."""
    bind_host = "" if host in ("0.0.0.0", "::") else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_host, port))
    except OSError as exc:
        print(f"  Cannot start server on {host}:{port}")
        print(f"  Error: {exc}")
        print("\n  Stop the existing server first, or set UVICORN_PORT to a free port.")
        sys.exit(1)


def seed_dev_premium_user(database_url):
    """Seed a local test user with the top paid tier enabled."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        username,
                        email,
                        google_id,
                        subtitle,
                        avatar_seed,
                        is_admin,
                        is_moderator,
                        premium_tier,
                        premium_until
                    )
                    VALUES (
                        :username,
                        :email,
                        :google_id,
                        :subtitle,
                        :avatar_seed,
                        TRUE,
                        TRUE,
                        'author_audio',
                        CURRENT_TIMESTAMP + INTERVAL '10 years'
                    )
                    ON CONFLICT (email) DO UPDATE SET
                        is_admin = TRUE,
                        is_moderator = TRUE,
                        premium_tier = 'author_audio',
                        premium_until = CURRENT_TIMESTAMP + INTERVAL '10 years',
                        subtitle = EXCLUDED.subtitle,
                        avatar_seed = EXCLUDED.avatar_seed,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "username": DEV_PREMIUM_USER_USERNAME,
                    "email": DEV_PREMIUM_USER_EMAIL,
                    "google_id": DEV_PREMIUM_USER_GOOGLE_ID,
                    "subtitle": "cont local pentru testarea abonamentelor",
                    "avatar_seed": "gocandan-premium",
                },
            )
        print(f"  Seed: {DEV_PREMIUM_USER_EMAIL} La cenaclu' Flacara account")
    finally:
        engine.dispose()


def _database_url(database_name: str):
    from sqlalchemy.engine import URL

    return URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=database_name,
    )


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier or ""):
        raise RuntimeError(f"Unsafe database name: {identifier!r}")
    return f'"{identifier}"'


def _statement_preview(statement: str) -> str:
    compact = " ".join(statement.split())
    return compact[:220] + ("..." if len(compact) > 220 else "")


def _schema_statements(schema_content: str) -> list[str]:
    statements = []
    current_statement = []
    in_function = False

    for line in schema_content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current_statement.append(line)
        dollar_count = line.count("$$")
        if dollar_count % 2 == 1:
            in_function = not in_function
        if stripped.endswith(";") and not in_function:
            stmt = "\n".join(current_statement).strip()
            if stmt:
                statements.append(stmt)
            current_statement = []

    if current_statement:
        raise RuntimeError("schema.sql ended with an unterminated SQL statement")
    if in_function:
        raise RuntimeError("schema.sql ended inside a dollar-quoted function body")
    if not statements:
        raise RuntimeError("schema.sql did not contain any executable statements")
    return statements


def verify_seed_data(database_url):
    """Fail fast if a reset produced an empty or partially seeded database."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            for table_name, minimum_count in REQUIRED_SEED_TABLES.items():
                count = connection.execute(
                    text(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}")
                ).scalar_one()
                if count < minimum_count:
                    raise RuntimeError(
                        f"Seed verification failed: {table_name} has {count} rows, "
                        f"expected at least {minimum_count}."
                    )

            dev_user = connection.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": DEV_PREMIUM_USER_EMAIL},
            ).first()
            if dev_user is None:
                raise RuntimeError(
                    f"Seed verification failed: {DEV_PREMIUM_USER_EMAIL} was not created."
                )
    finally:
        engine.dispose()


def init_database():
    """Ensure database exists and initialize from schema.sql."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    if DB_NAME in {"postgres", "template0", "template1"}:
        print(f"  Refusing to reset PostgreSQL system database: {DB_NAME}")
        sys.exit(1)

    reset_database = env_bool("CALIMARA_RESET_DATABASE", False)

    # 1. Check PostgreSQL connectivity and current database state.
    try:
        server_url = _database_url("postgres")
        server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with server_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            database_exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": DB_NAME},
            ).first() is not None
        server_engine.dispose()
    except Exception as e:
        print(f"  Cannot connect to PostgreSQL at {DB_HOST}:{DB_PORT}")
        print(f"  Error: {e}")
        print("\n  Make sure PostgreSQL is running. On Ubuntu/Debian:")
        print("    sudo systemctl start postgresql")
        print("    sudo -u postgres createuser --createdb " + (DB_USER or "calimara_user"))
        print(f'    sudo -u postgres psql -c "ALTER USER {DB_USER or "calimara_user"} PASSWORD \'{DB_PASSWORD or "calimara_pass"}\';"')
        sys.exit(1)

    if database_exists and not reset_database:
        database_url = _database_url(DB_NAME)
        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                users_table = connection.execute(
                    text("SELECT to_regclass('public.users')")
                ).scalar()
            if users_table:
                print(f"  Database '{DB_NAME}' exists. Preserving data.")
                print("  No migrations are run; reset/destroy the database to apply schema.sql changes.")
                return
            print(f"  Database '{DB_NAME}' exists but schema is missing. Initializing schema.")
        except SQLAlchemyError as e:
            print(f"  Error checking existing database schema: {e}")
            sys.exit(1)
        finally:
            engine.dispose()

    # 2. Create the database if missing, or reset it only when explicitly requested.
    if not database_exists or reset_database:
        try:
            server_engine = create_engine(
                _database_url("postgres"),
                isolation_level="AUTOCOMMIT"
            )
            quoted_db_name = _quote_identifier(DB_NAME)
            with server_engine.connect() as conn:
                if database_exists and reset_database:
                    # Terminate existing connections so DROP DATABASE can proceed.
                    conn.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :dbname AND pid <> pg_backend_pid()"
                        ),
                        {"dbname": DB_NAME},
                    )
                    conn.execute(text(f"DROP DATABASE IF EXISTS {quoted_db_name}"))
                conn.execute(text(f"CREATE DATABASE {quoted_db_name}"))
                action = "reset" if database_exists and reset_database else "created"
                print(f"  Database '{DB_NAME}' {action}.")
            server_engine.dispose()
        except (RuntimeError, SQLAlchemyError) as e:
            print(f"  Error preparing database: {e}")
            sys.exit(1)

    # 3. Execute schema.sql
    if not SCHEMA_FILE.exists():
        print(f"  Error: Schema file not found at {SCHEMA_FILE}")
        sys.exit(1)

    database_url = _database_url(DB_NAME)
    engine = create_engine(database_url)

    try:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_content = f.read()

        with engine.connect() as connection:
            statements = _schema_statements(schema_content)
            executed = 0
            for stmt in statements:
                try:
                    connection.execute(text(stmt))
                    executed += 1
                except SQLAlchemyError as exc:
                    raise RuntimeError(
                        f"schema.sql statement {executed + 1} failed: "
                        f"{_statement_preview(stmt)}"
                    ) from exc

            connection.commit()

            print(f"  Schema executed ({executed} statements)")

            # Write DB epoch to invalidate stale session cookies
            epoch_file = PROJECT_ROOT / ".db_epoch"
            epoch_file.write_text(str(int(time.time())))
            print(f"  DB epoch updated (stale sessions invalidated)")

    except Exception as e:
        print(f"  Database initialization failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

    # Seed sample Romanian content so every page has something to show.
    try:
        from scripts.seed import main as seed_main
        seed_main(quiet=False)
    except Exception as e:
        print(f"  Seed step failed: {e}")
        sys.exit(1)

    try:
        seed_dev_premium_user(database_url)
        verify_seed_data(database_url)
        print("  Seed verification: OK")
    except Exception as e:
        print(f"  Seed verification failed: {e}")
        sys.exit(1)


def check_node():
    """Check if Node.js and npm are available."""
    node = shutil.which("node")
    npm = shutil.which("npm")

    if not node or not npm:
        print("  Node.js and npm are required for the frontend.")
        print("  Install Node.js: https://nodejs.org/ or use nvm:")
        print("    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash")
        print("    nvm install --lts")
        sys.exit(1)

    version = subprocess.check_output([node, "--version"], text=True).strip()
    print(f"  Node.js: {version}")
    return npm


def setup_frontend(npm):
    """Install frontend dependencies and sync .env variables."""
    if not FRONTEND_DIR.exists():
        print("  Frontend directory not found. Skipping frontend setup.")
        return False

    # Install dependencies if node_modules missing
    if not (FRONTEND_DIR / "node_modules").exists():
        print("  Installing frontend dependencies...")
        result = subprocess.run(
            [npm, "install"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            print(f"  npm install failed:\n{result.stdout.decode()}")
            sys.exit(1)
        print("  Frontend dependencies installed.")
    else:
        print("  Frontend dependencies: OK")

    # Sync VITE_ env vars from root .env to frontend/.env
    frontend_env = FRONTEND_DIR / ".env"
    main_domain = os.getenv("MAIN_DOMAIN", "localhost")
    subdomain_suffix = os.getenv("SUBDOMAIN_SUFFIX", ".localhost")
    ad_env = {
        "VITE_ADS_ENABLED": os.getenv("VITE_ADS_ENABLED", "false"),
        "VITE_ADSENSE_CLIENT_ID": os.getenv("VITE_ADSENSE_CLIENT_ID", ""),
        "VITE_ADSENSE_SLOT_RAIL": os.getenv("VITE_ADSENSE_SLOT_RAIL", ""),
        "VITE_ADSENSE_SLOT_INLINE": os.getenv("VITE_ADSENSE_SLOT_INLINE", ""),
        "VITE_ADSENSE_SLOT_POST_FOOTER": os.getenv("VITE_ADSENSE_SLOT_POST_FOOTER", ""),
    }
    frontend_env.write_text(
        f"VITE_MAIN_DOMAIN={main_domain}\n"
        f"VITE_SUBDOMAIN_SUFFIX={subdomain_suffix}\n"
        + "".join(f"{key}={value}\n" for key, value in ad_env.items())
    )

    return True


def build_frontend(npm):
    """Build the frontend for production."""
    print("  Building frontend for production...")
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        print(f"  Frontend build failed:\n{result.stdout.decode()}")
        sys.exit(1)
    print("  Frontend built successfully.")


def start_ai_worker():
    """Start the background AI job worker for moderation and follow-up jobs."""
    if os.getenv("AI_WORKER_ENABLED", "true").lower() != "true":
        print("  AI worker disabled by AI_WORKER_ENABLED=false")
        return None

    worker_script = PROJECT_ROOT / "scripts" / "process_ai_jobs.py"
    if not worker_script.exists():
        print(f"  AI worker script missing: {worker_script}")
        return None

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        [sys.executable, str(worker_script), "--loop"],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    child_processes.append(proc)
    print(f"  AI moderation worker started (pid {proc.pid})")
    return proc


def main():
    print()
    print("  ╔═══════════════════════════════════════╗")
    print("  ║     CALIMARA - Development Server     ║")
    print("  ╚═══════════════════════════════════════╝")
    print()

    manage_systemd_service_if_needed()

    # 1. Check environment
    print("[1/4] Checking environment...")
    check_env()
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))
    check_port_available(host, port)
    print("  Environment: OK")

    # 2. Initialize the database from schema.sql when missing or explicitly reset.
    print("[2/4] Initializing database...")
    init_database()

    # 3. Check Node.js & setup frontend
    print("[3/4] Setting up frontend...")
    npm = check_node()
    has_frontend = setup_frontend(npm)

    # 4. Start server
    print("[4/4] Starting server...")

    if has_frontend:
        build_frontend(npm)

    start_ai_worker()

    public_url = public_base_url()
    forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
    print(f"  Public URL: {public_url}")
    print(f"  Uvicorn bind: http://{host}:{port}")
    if host in ("127.0.0.1", "localhost"):
        print("  Expecting a local reverse proxy to serve HTTP/HTTPS for the public domain.")
    print("  Press Ctrl+C to stop.\n")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
