import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Database connection details from environment variables or default
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "QuietUptown1801__")
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = os.getenv("MYSQL_PORT", "3306")
DB_NAME = os.getenv("MYSQL_DATABASE", "calimara_db")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def init_db():
    """
    Initializes the database by dropping existing tables and creating new ones.
    """
    # Connect to MySQL server without specifying a database initially
    # This is needed to create the database if it doesn't exist
    server_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
    server_engine = create_engine(server_url)

    try:
        with server_engine.connect() as connection:
            # Create the database if it doesn't exist
            connection.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
            connection.commit()
        print(f"Database '{DB_NAME}' ensured to exist.")
    except SQLAlchemyError as e:
        print(f"Error ensuring database exists: {e}")
        return

    # Now connect to the specific database
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as connection:
            # Drop tables in reverse order of dependency
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            connection.execute(text("DROP TABLE IF EXISTS likes;"))
            connection.execute(text("DROP TABLE IF EXISTS comments;"))
            connection.execute(text("DROP TABLE IF EXISTS posts;"))
            connection.execute(text("DROP TABLE IF EXISTS users;"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            connection.commit()
            print("Existing tables dropped.")

            # Create tables
            connection.execute(text("""
                CREATE TABLE users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """))
            print("Table 'users' created.")

            connection.execute(text("""
                CREATE TABLE posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """))
            print("Table 'posts' created.")

            connection.execute(text("""
                CREATE TABLE comments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    post_id INT NOT NULL,
                    user_id INT,
                    author_name VARCHAR(255),
                    author_email VARCHAR(255),
                    content TEXT NOT NULL,
                    approved BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """))
            print("Table 'comments' created.")

            connection.execute(text("""
                CREATE TABLE likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    post_id INT NOT NULL,
                    user_id INT,
                    ip_address VARCHAR(45),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (post_id, user_id), -- A logged-in user can only like a post once
                    UNIQUE (post_id, ip_address), -- An unlogged user (from an IP) can only like a post once
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """))
            print("Table 'likes' created.")

            print("Database initialization complete.")

    except SQLAlchemyError as e:
        print(f"Error during database initialization: {e}")

if __name__ == "__main__":
    init_db()
