import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SCHEMA_FILE = PROJECT_ROOT / "schema.sql"

# Database connection details from environment variables
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "calimara_db")

if not DB_USER or not DB_PASSWORD:
    print("Error: DB_USER and DB_PASSWORD must be set in .env")
    sys.exit(1)


def ensure_database_exists():
    """Connect to the default 'postgres' database and create the target DB if needed."""
    server_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
    server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")

    try:
        with server_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": DB_NAME}
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
                print(f"  Database '{DB_NAME}' created.")
            else:
                print(f"  Database '{DB_NAME}' already exists.")
        return True
    except SQLAlchemyError as e:
        print(f"  Error ensuring database exists: {e}")
        return False
    finally:
        server_engine.dispose()


def init_db():
    print("=" * 50)
    print("CALIMARA DATABASE INITIALIZATION (PostgreSQL)")
    print("=" * 50)

    if not SCHEMA_FILE.exists():
        print(f"Error: Schema file not found at {SCHEMA_FILE}")
        return False

    print(f"Using schema file: {SCHEMA_FILE}")

    # Ensure the database exists
    if not ensure_database_exists():
        return False

    # Connect to the target database
    database_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(database_url)

    try:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_content = f.read()

        print(f"Schema file loaded ({len(schema_content)} characters)")

        with engine.connect() as connection:
            print("Executing database schema...")

            # Split schema into individual statements
            statements = []
            current_statement = []
            in_function = False

            for line in schema_content.split('\n'):
                stripped = line.strip()
                if not stripped or stripped.startswith('--'):
                    continue

                current_statement.append(line)

                # Track $$ delimited function bodies
                dollar_count = line.count('$$')
                if dollar_count % 2 == 1:
                    in_function = not in_function

                if stripped.endswith(';') and not in_function:
                    stmt = '\n'.join(current_statement).strip()
                    if stmt:
                        statements.append(stmt)
                    current_statement = []

            # Execute each statement
            executed_count = 0
            for stmt in statements:
                try:
                    connection.execute(text(stmt))
                    executed_count += 1

                    stmt_upper = stmt.upper().strip()
                    if stmt_upper.startswith('CREATE TABLE'):
                        table_name = stmt.split()[2]
                        print(f"  Table {table_name} created")
                    elif stmt_upper.startswith('INSERT INTO USERS'):
                        print("  Users created")
                    elif stmt_upper.startswith('INSERT INTO POSTS'):
                        print("  Sample posts created")

                except SQLAlchemyError as e:
                    error_msg = str(e)
                    if any(kw in stmt.upper().strip() for kw in ['CREATE TABLE', 'CREATE INDEX']):
                        print(f"  Error (non-fatal): {error_msg}")
                    else:
                        print(f"  Warning: {error_msg}")
                    print(f"  Statement: {stmt[:100]}...")

            connection.commit()
            print(f"Schema executed successfully ({executed_count} statements)")

            # Verify
            try:
                tables = ['users', 'posts', 'comments', 'likes', 'tags',
                          'best_friends', 'featured_posts', 'user_awards',
                          'conversations', 'messages', 'moderation_logs',
                          'dramas', 'drama_characters', 'drama_acts',
                          'drama_replies', 'drama_likes', 'drama_comments',
                          'drama_invitations', 'notifications']
                print("\n" + "=" * 30)
                print("DATABASE SUMMARY")
                print("=" * 30)
                for table in tables:
                    count = connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    print(f"  {table}: {count} rows")
                print("=" * 30)
                print("Database initialization complete!")
                return True
            except SQLAlchemyError as e:
                print(f"Error verifying database: {e}")
                return False

    except SQLAlchemyError as e:
        print(f"Error during database initialization: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
