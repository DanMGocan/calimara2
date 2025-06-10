import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from passlib.context import CryptContext

# Get the project root directory (parent of scripts directory)
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"

# Database connection details from environment variables or default
DB_USER = os.getenv("MYSQL_USER", "admin")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "QuietUptown1801__")
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = os.getenv("MYSQL_DATABASE", "calimara_db")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def init_db():
    """
    Initializes the database using the schema.sql file.
    This will drop existing tables and create new ones with sample data.
    """
    print("=" * 50)
    print("CALIMARA DATABASE INITIALIZATION")
    print("=" * 50)
    
    # Check if schema.sql exists
    if not SCHEMA_FILE.exists():
        print(f"Error: Schema file not found at {SCHEMA_FILE}")
        print("Please ensure schema.sql exists in the project root directory.")
        sys.exit(1)
    
    print(f"Using schema file: {SCHEMA_FILE}")
    
    # Connect to MySQL server without specifying a database initially
    # This is needed to create the database if it doesn't exist
    server_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
    server_engine = create_engine(server_url)

    try:
        with server_engine.connect() as connection:
            # Create the database if it doesn't exist
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
            connection.commit()
        print(f"✓ Database '{DB_NAME}' ensured to exist.")
    except SQLAlchemyError as e:
        print(f"✗ Error ensuring database exists: {e}")
        return False

    # Now connect to the specific database
    engine = create_engine(DATABASE_URL)

    try:
        # Read the schema file
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_content = f.read()
        
        print(f"✓ Schema file loaded ({len(schema_content)} characters)")
        
        # We need to handle the bcrypt password hash separately since it contains special characters
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        test_password_hash = pwd_context.hash("123")
        
        # Replace the placeholder password hash in schema with actual hash
        schema_content = schema_content.replace(
            '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O',
            test_password_hash
        )

        with engine.connect() as connection:
            # Split the schema into individual statements and execute them
            statements = [stmt.strip() for stmt in schema_content.split(';') if stmt.strip()]
            
            executed_count = 0
            for statement in statements:
                if statement and not statement.startswith('--'):
                    try:
                        connection.execute(text(statement))
                        executed_count += 1
                    except SQLAlchemyError as e:
                        # Skip certain errors that are expected (like SHOW TABLES, DESCRIBE)
                        if "doesn't exist" not in str(e) and "Unknown column" not in str(e):
                            print(f"Warning executing statement: {e}")
                            print(f"Statement: {statement[:100]}...")
            
            connection.commit()
            print(f"✓ Schema executed successfully ({executed_count} statements)")

            # Verify the initialization worked
            result = connection.execute(text("SELECT COUNT(*) FROM users;"))
            user_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM posts;"))
            post_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM comments;"))
            comment_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM likes;"))
            like_count = result.scalar()
            
            print("\n" + "=" * 30)
            print("DATABASE INITIALIZATION SUMMARY")
            print("=" * 30)
            print(f"Users created: {user_count}")
            print(f"Posts created: {post_count}")
            print(f"Comments created: {comment_count}")
            print(f"Likes created: {like_count}")
            print("=" * 30)
            print("✓ Database initialization complete!")
            print("\nTest user credentials:")
            print("  Username: gandurisilimbrici")
            print("  Email: sad@sad.sad")
            print("  Password: 123")
            print("  Blog URL: gandurisilimbrici.calimara.ro")
            
            return True

    except FileNotFoundError:
        print(f"✗ Error: Could not read schema file at {SCHEMA_FILE}")
        return False
    except SQLAlchemyError as e:
        print(f"✗ Error during database initialization: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
