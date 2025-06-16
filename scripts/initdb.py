import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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
        print(f"✗ Error: Schema file not found at {SCHEMA_FILE}")
        print("Please ensure schema.sql exists in the project root directory.")
        return False
    
    print(f"Using schema file: {SCHEMA_FILE}")
    
    # Connect to MySQL server without specifying a database initially
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
        # Read and process the schema file
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_content = f.read()
        
        print(f"✓ Schema file loaded ({len(schema_content)} characters)")
        
        # Note: No password hashing needed for Google OAuth authentication
        # The google_id placeholders in schema.sql will remain as test values

        with engine.connect() as connection:
            print("Executing database schema...")
            
            # Split schema into individual statements
            statements = []
            current_statement = []
            
            for line in schema_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                current_statement.append(line)
                
                if line.endswith(';'):
                    stmt = ' '.join(current_statement).strip()
                    if stmt:
                        statements.append(stmt)
                    current_statement = []
            
            # Execute each statement
            executed_count = 0
            for stmt in statements:
                try:
                    connection.execute(text(stmt))
                    executed_count += 1
                    
                    # Show progress for key operations
                    if stmt.upper().startswith('CREATE TABLE'):
                        table_name = stmt.split()[2]
                        print(f"✓ Table {table_name} created")
                    elif stmt.upper().startswith('INSERT INTO USERS'):
                        print("✓ Test users created")
                    elif stmt.upper().startswith('INSERT INTO POSTS'):
                        print("✓ Sample posts created")
                    elif stmt.upper().startswith('INSERT INTO COMMENTS'):
                        print("✓ Sample comments created")
                    elif stmt.upper().startswith('INSERT INTO LIKES'):
                        print("✓ Sample likes created")
                    elif stmt.upper().startswith('INSERT INTO TAGS'):
                        print("✓ Sample tags created")
                    elif stmt.upper().startswith('INSERT INTO BEST_FRIENDS'):
                        print("✓ Best friends relationships created")
                    elif stmt.upper().startswith('INSERT INTO FEATURED_POSTS'):
                        print("✓ Featured posts created")
                    elif stmt.upper().startswith('INSERT INTO USER_AWARDS'):
                        print("✓ User awards created")
                    elif stmt.upper().startswith('INSERT INTO CONVERSATIONS'):
                        print("✓ Sample conversations created")
                    elif stmt.upper().startswith('INSERT INTO MESSAGES'):
                        print("✓ Sample messages created")
                        
                except SQLAlchemyError as e:
                    # Skip validation statements that might fail
                    if any(cmd in stmt.upper() for cmd in ['SHOW', 'DESCRIBE', 'SELECT \'']):
                        continue
                    else:
                        print(f"Warning: {e}")
                        print(f"Statement: {stmt[:100]}...")
            
            connection.commit()
            print(f"✓ Schema executed successfully ({executed_count} statements)")

            # Verify the initialization worked
            try:
                result = connection.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM posts"))
                post_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM comments"))
                comment_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM likes"))
                like_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM tags"))
                tag_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM best_friends"))
                best_friends_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM featured_posts"))
                featured_posts_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM user_awards"))
                awards_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM conversations"))
                conversations_count = result.scalar()
                
                result = connection.execute(text("SELECT COUNT(*) FROM messages"))
                messages_count = result.scalar()
                
                print("\n" + "=" * 30)
                print("DATABASE INITIALIZATION SUMMARY")
                print("=" * 30)
                print(f"Users created: {user_count}")
                print(f"Posts created: {post_count}")
                print(f"Comments created: {comment_count}")
                print(f"Likes created: {like_count}")
                print(f"Tags created: {tag_count}")
                print(f"Best friends: {best_friends_count}")
                print(f"Featured posts: {featured_posts_count}")
                print(f"User awards: {awards_count}")
                print(f"Conversations: {conversations_count}")
                print(f"Messages: {messages_count}")
                print("=" * 30)
                print("✓ Database initialization complete!")
                print("\n=== ACCOUNT INFORMATION ===")
                print("\nGod Admin Account:")
                print("  Username: admin")
                print("  Email: admin@calimara.ro")
                print("  Authentication: Google OAuth (test google_id: god-admin-google-id-000000000)")
                print("  Blog URL: admin.calimara.ro")
                print("  Access: Full moderation control panel")
                print("\nMain User Account:")
                print("  Username: dangocan")
                print("  Email: dangocan@outlook.com")
                print("  Authentication: Google OAuth (test google_id: test-google-id-123456789)")
                print("  Blog URL: dangocan.calimara.ro")
                print("\nNote: Users now authenticate via Google OAuth instead of local passwords.")
                
                return True
                
            except SQLAlchemyError as e:
                print(f"✗ Error verifying database: {e}")
                return False

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