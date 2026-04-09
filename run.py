#!/usr/bin/env python3
"""
Calimara local development server.
Initializes the database from schema.sql, installs frontend
dependencies, and starts uvicorn.
"""
import os
import sys
import shutil
import signal
import subprocess
import atexit
from pathlib import Path
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


def check_env():
    """Verify required environment variables are set."""
    missing = []
    if not DB_USER:
        missing.append("DB_USER")
    if not DB_PASSWORD:
        missing.append("DB_PASSWORD")
    if not os.getenv("SESSION_SECRET_KEY"):
        missing.append("SESSION_SECRET_KEY")

    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Please configure them in your .env file.")
        sys.exit(1)


def init_database():
    """Ensure database exists and initialize from schema.sql."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    # 1. Check PostgreSQL connectivity
    try:
        server_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
        server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
        with server_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        server_engine.dispose()
    except Exception as e:
        print(f"  Cannot connect to PostgreSQL at {DB_HOST}:{DB_PORT}")
        print(f"  Error: {e}")
        print("\n  Make sure PostgreSQL is running. On Ubuntu/Debian:")
        print("    sudo systemctl start postgresql")
        print("    sudo -u postgres createuser --createdb " + (DB_USER or "calimara_user"))
        print(f'    sudo -u postgres psql -c "ALTER USER {DB_USER or "calimara_user"} PASSWORD \'{DB_PASSWORD or "calimara_pass"}\';"')
        sys.exit(1)

    # 2. Create database if it doesn't exist
    try:
        server_engine = create_engine(
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
            isolation_level="AUTOCOMMIT"
        )
        with server_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": DB_NAME}
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
                print(f"  Database '{DB_NAME}' created.")
            else:
                print(f"  Database '{DB_NAME}' exists.")
        server_engine.dispose()
    except SQLAlchemyError as e:
        print(f"  Error creating database: {e}")
        sys.exit(1)

    # 3. Execute schema.sql
    if not SCHEMA_FILE.exists():
        print(f"  Error: Schema file not found at {SCHEMA_FILE}")
        sys.exit(1)

    database_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(database_url)

    try:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_content = f.read()

        with engine.connect() as connection:
            # Parse statements (handling $$ function bodies)
            statements = []
            current_statement = []
            in_function = False

            for line in schema_content.split('\n'):
                stripped = line.strip()
                if not stripped or stripped.startswith('--'):
                    continue
                current_statement.append(line)
                dollar_count = line.count('$$')
                if dollar_count % 2 == 1:
                    in_function = not in_function
                if stripped.endswith(';') and not in_function:
                    stmt = '\n'.join(current_statement).strip()
                    if stmt:
                        statements.append(stmt)
                    current_statement = []

            executed = 0
            for stmt in statements:
                try:
                    connection.execute(text(stmt))
                    executed += 1
                except SQLAlchemyError:
                    pass  # DROP IF EXISTS / CREATE IF NOT EXISTS are fine to fail

            connection.commit()

            # Verify tables
            tables = ['users', 'posts', 'comments', 'likes', 'tags',
                      'best_friends', 'featured_posts', 'user_awards',
                      'conversations', 'messages', 'moderation_logs',
                      'dramas', 'drama_characters', 'drama_acts',
                      'drama_replies', 'drama_likes', 'drama_comments',
                      'drama_invitations', 'notifications']
            for table in tables:
                count = connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {count} rows")

            print(f"  Schema executed ({executed} statements)")

    except Exception as e:
        print(f"  Database initialization failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()


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
    frontend_env.write_text(
        f"VITE_MAIN_DOMAIN={main_domain}\n"
        f"VITE_SUBDOMAIN_SUFFIX={subdomain_suffix}\n"
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


def main():
    print()
    print("  ╔═══════════════════════════════════════╗")
    print("  ║     CALIMARA - Development Server     ║")
    print("  ╚═══════════════════════════════════════╝")
    print()

    # 1. Check environment
    print("[1/4] Checking environment...")
    check_env()
    print("  Environment: OK")

    # 2. Initialize database (always runs schema.sql)
    print("[2/4] Initializing database...")
    init_database()

    # 3. Check Node.js & setup frontend
    print("[3/4] Setting up frontend...")
    npm = check_node()
    has_frontend = setup_frontend(npm)

    # 4. Start server
    print("[4/4] Starting server...")

    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    port = int(os.getenv("UVICORN_PORT", "8000"))

    if has_frontend:
        build_frontend(npm)

    print(f"  Starting server on http://{host}:{port}")
    print("  Press Ctrl+C to stop.\n")

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
