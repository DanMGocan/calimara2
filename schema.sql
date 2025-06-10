-- ===================================
-- CALIMARA DATABASE SCHEMA
-- Romanian Writers Microblogging Platform
-- ===================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- ===================================
-- USERS TABLE
-- ===================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL COMMENT 'Unique username for subdomain',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'User email for authentication',
    password_hash VARCHAR(255) NOT NULL COMMENT 'Bcrypt hashed password',
    subtitle VARCHAR(500) COMMENT 'Optional blog subtitle/description',
    avatar_seed VARCHAR(100) COMMENT 'DiceBear avatar seed for generating avatars',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- POSTS TABLE
-- ===================================
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'Reference to post author',
    title VARCHAR(255) NOT NULL COMMENT 'Post title',
    content TEXT NOT NULL COMMENT 'Post content',
    category VARCHAR(100) COMMENT 'Category key',
    genre VARCHAR(100) COMMENT 'Genre key within category',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_category (category),
    INDEX idx_genre (genre),
    INDEX idx_created_at (created_at),
    INDEX idx_category_genre (category, genre)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- COMMENTS TABLE
-- ===================================
CREATE TABLE comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT 'Reference to commented post',
    user_id INT COMMENT 'Reference to commenter (NULL for anonymous)',
    author_name VARCHAR(255) COMMENT 'Name for anonymous commenters',
    author_email VARCHAR(255) COMMENT 'Email for anonymous commenters',
    content TEXT NOT NULL COMMENT 'Comment content',
    approved BOOLEAN DEFAULT FALSE COMMENT 'Admin approval status',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_approved (approved),
    INDEX idx_post_approved (post_id, approved)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- LIKES TABLE
-- ===================================
CREATE TABLE likes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT 'Reference to liked post',
    user_id INT COMMENT 'Reference to liker (NULL for anonymous)',
    ip_address VARCHAR(45) COMMENT 'IP address for anonymous likes',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_user_like (post_id, user_id),
    UNIQUE KEY unique_ip_like (post_id, ip_address),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_ip_address (ip_address)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- TAGS TABLE
-- ===================================
CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT 'Reference to tagged post',
    tag_name VARCHAR(12) NOT NULL COMMENT 'Tag name (max 12 characters)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_tag_name (tag_name),
    INDEX idx_tag_search (tag_name, post_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- SAMPLE DATA
-- ===================================

-- Test user (password will be replaced by initdb.py)
INSERT INTO users (username, email, password_hash, subtitle, avatar_seed) VALUES (
    'gandurisilimbrici',
    'sad@sad.sad',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O',
    'Mi-am facut si io blog, sa nu mor prost lol',
    'gandurisilimbrici-shapes'
);

-- Sample posts for the test user
INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(1, 'Primul meu gând', 'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea.', 'proza', 'povestiri_scurte');

INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(1, 'Limbrici și poezie', 'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.', 'poezie', 'poezie_lirica');

INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(1, 'O zi obișnuită', 'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie.', 'proza', 'povestiri_scurte');

INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(1, 'Reflecții despre timp', 'Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu.', 'jurnal', 'jurnale_personale');

INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(1, 'Scrisoare către viitorul meu', 'Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum.\n\nCu drag,\nEu din trecut', 'scrisoare', 'scrisori_personale');

-- Sample comments
INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
(1, 'Maria Popescu', 'maria@example.com', 'Ce frumos ai scris! Abia aștept să citesc mai multe din gândurile tale.', TRUE);

INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
(2, 'Ion Creangă', 'ion@example.com', 'Poezia ta despre limbrici m-a emoționat. Comparația cu poezia este genială!', TRUE);

INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
(1, 'Ana Blandiana', 'ana@example.com', 'Primul gând este adesea cel mai autentic. Continuă să scrii!', TRUE);

-- Sample tags
INSERT INTO tags (post_id, tag_name) VALUES 
(1, 'gânduri'),
(1, 'debut'),
(1, 'pasiune'),
(2, 'natură'),
(2, 'poezie'),
(2, 'limbrici'),
(3, 'cotidian'),
(3, 'reflecții'),
(4, 'timp'),
(4, 'filozofie'),
(5, 'scrisoare'),
(5, 'viitor');