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
    Initializes the database by creating tables and inserting sample data.
    This will drop existing tables and create new ones with sample data.
    """
    print("=" * 50)
    print("CALIMARA DATABASE INITIALIZATION")
    print("=" * 50)
    
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
        with engine.connect() as connection:
            print("Dropping existing tables...")
            
            # Drop tables safely with foreign key constraints
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            connection.execute(text("DROP TABLE IF EXISTS likes"))
            connection.execute(text("DROP TABLE IF EXISTS comments"))
            connection.execute(text("DROP TABLE IF EXISTS posts"))
            connection.execute(text("DROP TABLE IF EXISTS users"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            print("✓ Existing tables dropped")
            
            print("Creating tables...")
            
            # Create users table
            connection.execute(text("""
                CREATE TABLE users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    subtitle VARCHAR(500),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_email (email),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            print("✓ Table users created")
            
            # Create posts table
            connection.execute(text("""
                CREATE TABLE posts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(100),
                    genre VARCHAR(100),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_category (category),
                    INDEX idx_genre (genre),
                    INDEX idx_created_at (created_at),
                    INDEX idx_category_genre (category, genre),
                    INDEX idx_user_created (user_id, created_at)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            print("✓ Table posts created")
            
            # Create comments table
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
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_post_id (post_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_approved (approved),
                    INDEX idx_created_at (created_at),
                    INDEX idx_post_approved (post_id, approved)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            print("✓ Table comments created")
            
            # Create likes table
            connection.execute(text("""
                CREATE TABLE likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    post_id INT NOT NULL,
                    user_id INT,
                    ip_address VARCHAR(45),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_like (post_id, user_id),
                    UNIQUE KEY unique_ip_like (post_id, ip_address),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_post_id (post_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_ip_address (ip_address),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            print("✓ Table likes created")
            
            print("Inserting sample data...")
            
            # Create test user
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            test_password_hash = pwd_context.hash("123")
            
            connection.execute(text("""
                INSERT INTO users (username, email, password_hash, subtitle) VALUES 
                (:username, :email, :password_hash, :subtitle)
            """), {
                "username": "gandurisilimbrici",
                "email": "sad@sad.sad",
                "password_hash": test_password_hash,
                "subtitle": "Mi-am facut si io blog, sa nu mor prost lol"
            })
            print("✓ Test user created")
            
            # Get user ID
            result = connection.execute(text("SELECT id FROM users WHERE username = 'gandurisilimbrici'"))
            test_user_id = result.scalar()
            
            # Create sample posts
            sample_posts = [
                {
                    "user_id": test_user_id,
                    "title": "Primul meu gând",
                    "content": "Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea. Este doar începutul unei aventuri literare care sper să ne ducă pe drumuri neexplorate ale creativității și expresiei artistice.",
                    "category": "proza",
                    "genre": "povestiri_scurte"
                },
                {
                    "user_id": test_user_id,
                    "title": "Limbrici și poezie",
                    "content": "Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.\n\nÎn tăcerea pământului umed\nSe ascund taine și povești,\nCa versurile care iau naștere\nÎn adâncul inimii noastre.",
                    "category": "poezie",
                    "genre": "poezie_lirica"
                },
                {
                    "user_id": test_user_id,
                    "title": "O zi obișnuită",
                    "content": "O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie. Să fim recunoscători pentru fiecare clipă ce ni se oferă și să prețuim frumusețea din lucrurile simple ale vieții cotidiene.",
                    "category": "proza",
                    "genre": "povestiri_scurte"
                },
                {
                    "user_id": test_user_id,
                    "title": "Reflecții despre timp",
                    "content": "Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu, să le privesc îndeaproape și să înțeleg ce povești ascund în ele.",
                    "category": "jurnal",
                    "genre": "jurnale_personale"
                },
                {
                    "user_id": test_user_id,
                    "title": "Scrisoare către viitorul meu",
                    "content": "Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum. Sper că ai reușit să găsești drumul tău în această lume complexă și că poezia încă îți umple sufletul de bucurie.\n\nCu drag,\nEu din trecut",
                    "category": "scrisoare",
                    "genre": "scrisori_personale"
                }
            ]
            
            for post in sample_posts:
                connection.execute(text("""
                    INSERT INTO posts (user_id, title, content, category, genre)
                    VALUES (:user_id, :title, :content, :category, :genre)
                """), post)
            print("✓ Sample posts created")
            
            # Create sample comments
            connection.execute(text("""
                INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
                (1, 'Maria Popescu', 'maria@example.com', 'Ce frumos ai scris! Abia aștept să citesc mai multe din gândurile tale.', TRUE),
                (2, 'Ion Creangă', 'ion@example.com', 'Poezia ta despre limbrici m-a emoționat. Comparația cu poezia este genială!', TRUE),
                (1, 'Ana Blandiana', 'ana@example.com', 'Primul gând este adesea cel mai autentic. Continuă să scrii!', TRUE)
            """))
            print("✓ Sample comments created")
            
            # Create sample likes
            connection.execute(text("""
                INSERT INTO likes (post_id, ip_address) VALUES 
                (1, '192.168.1.100'),
                (1, '192.168.1.101'),
                (2, '192.168.1.102'),
                (2, '192.168.1.103'),
                (2, '192.168.1.104'),
                (3, '192.168.1.105')
            """))
            print("✓ Sample likes created")
            
            connection.commit()

            # Verify the initialization worked
            result = connection.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM posts"))
            post_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM comments"))
            comment_count = result.scalar()
            
            result = connection.execute(text("SELECT COUNT(*) FROM likes"))
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

    except SQLAlchemyError as e:
        print(f"✗ Error during database initialization: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
