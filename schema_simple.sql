-- ===================================
-- CALIMARA DATABASE SCHEMA - SIMPLIFIED
-- Romanian Writers Microblogging Platform
-- ===================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS best_friends;
DROP TABLE IF EXISTS featured_posts;
DROP TABLE IF EXISTS user_awards;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tags; 

SET FOREIGN_KEY_CHECKS = 1;

-- ===================================
-- USERS TABLE
-- ===================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL COMMENT 'Unique username for subdomain',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'User email for authentication',
    google_id VARCHAR(100) UNIQUE NOT NULL COMMENT 'Google OAuth unique identifier',
    subtitle VARCHAR(500) COMMENT 'Optional blog subtitle/description',
    avatar_seed VARCHAR(100) COMMENT 'DiceBear avatar seed for generating avatars',
    facebook_url VARCHAR(300) COMMENT 'Facebook profile/page URL',
    tiktok_url VARCHAR(300) COMMENT 'TikTok profile URL',
    instagram_url VARCHAR(300) COMMENT 'Instagram profile URL',
    x_url VARCHAR(300) COMMENT 'X (Twitter) profile URL',
    bluesky_url VARCHAR(300) COMMENT 'BlueSky profile URL',
    patreon_url VARCHAR(300) COMMENT 'Patreon page URL',
    paypal_url VARCHAR(300) COMMENT 'PayPal donation URL',
    buymeacoffee_url VARCHAR(300) COMMENT 'Buy Me a Coffee page URL',
    is_admin BOOLEAN DEFAULT FALSE COMMENT 'User has admin privileges',
    is_moderator BOOLEAN DEFAULT FALSE COMMENT 'User has moderation privileges',
    is_suspended BOOLEAN DEFAULT FALSE COMMENT 'User suspension status',
    suspension_reason TEXT COMMENT 'Reason for user suspension',
    suspended_at DATETIME COMMENT 'When user was suspended',
    suspended_by INT COMMENT 'Admin who suspended the user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_google_id (google_id),
    FOREIGN KEY (suspended_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================
-- POSTS TABLE
-- ===================================
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(300) UNIQUE NOT NULL COMMENT 'SEO-friendly URL slug',
    content TEXT NOT NULL,
    category VARCHAR(100) COMMENT 'Category key from categories.py',
    view_count INT DEFAULT 0 COMMENT 'Track post views',
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL,
    moderation_reason TEXT,
    toxicity_score FLOAT,
    moderated_by INT,
    moderated_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_slug (slug),
    INDEX idx_created_at (created_at),
    INDEX idx_category (category),
    INDEX idx_moderation_status (moderation_status),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================
-- COMMENTS TABLE
-- ===================================
CREATE TABLE comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT COMMENT 'Null for anonymous comments',
    author_name VARCHAR(255) COMMENT 'Name for anonymous comments',
    author_email VARCHAR(255) COMMENT 'Email for anonymous comments',
    content TEXT NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    moderation_status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    moderation_reason TEXT,
    toxicity_score FLOAT,
    moderated_by INT,
    moderated_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_approved (approved),
    INDEX idx_created_at (created_at),
    INDEX idx_moderation_status (moderation_status),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================
-- LIKES TABLE
-- ===================================
CREATE TABLE likes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT COMMENT 'Null for IP-based anonymous likes',
    ip_address VARCHAR(45) COMMENT 'IP address for anonymous likes',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_ip_address (ip_address),
    UNIQUE KEY unique_user_like (post_id, user_id),
    UNIQUE KEY unique_ip_like (post_id, ip_address),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================
-- TAGS TABLE
-- ===================================
CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    tag_name VARCHAR(12) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_post_id (post_id),
    INDEX idx_tag_name (tag_name),
    UNIQUE KEY unique_post_tag (post_id, tag_name),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ===================================
-- SAMPLE DATA
-- ===================================

-- Main admin user account (dangocan with admin privileges)
INSERT INTO users (username, email, google_id, subtitle, avatar_seed, facebook_url, tiktok_url, instagram_url, x_url, bluesky_url, buymeacoffee_url, is_admin, is_moderator) VALUES (
    'dangocan',
    'gocandan@gmail.com',
    'admin-google-id-123456789',
    'Scriitor și developer român - Administrator Calimara',
    'dangocan-shapes',
    'https://facebook.com/dangocan',
    'https://tiktok.com/@dangocan',
    'https://instagram.com/dangocan',
    'https://x.com/dangocan',
    'https://bsky.app/profile/dangocan.bsky.social',
    'https://buymeacoffee.com/dangocan',
    TRUE,
    TRUE
);

-- Sample posts for the admin user
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Primul meu gând', 'primul-meu-gand', 'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea.', 'proza', 15);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Limbrici și poezie', 'limbrici-si-poezie', 'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.', 'poezie', 23);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'O zi obișnuită', 'o-zi-obisnuita', 'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie.', 'proza', 8);

-- Sample comment
INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
(1, 'Maria Popescu', 'maria@example.com', 'Ce frumos ai scris! Abia aștept să citesc mai multe din gândurile tale.', TRUE);

-- Sample tags
INSERT INTO tags (post_id, tag_name) VALUES 
(1, 'gânduri'),
(1, 'debut'),
(1, 'pasiune'),
(2, 'natură'),
(2, 'poezie'),
(2, 'limbrici');