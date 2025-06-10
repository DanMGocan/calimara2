-- ===================================
-- CALIMARA DATABASE SCHEMA
-- Romanian Writers Microblogging Platform
-- ===================================

-- Set character set and collation for Unicode support
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- Disable foreign key checks for clean table drops
SET FOREIGN_KEY_CHECKS = 0;

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS likes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- ===================================
-- USERS TABLE
-- Stores writer accounts
-- ===================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL COMMENT 'Unique username for subdomain (e.g., user.calimara.ro)',
    email VARCHAR(255) UNIQUE NOT NULL COMMENT 'User email for authentication',
    password_hash VARCHAR(255) NOT NULL COMMENT 'Bcrypt hashed password',
    subtitle VARCHAR(500) COMMENT 'Optional blog subtitle/description',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci 
COMMENT='User accounts for writers and poets';

-- ===================================
-- POSTS TABLE
-- Stores literary works (poems, prose, etc.)
-- ===================================
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'Reference to post author',
    title VARCHAR(255) NOT NULL COMMENT 'Post title',
    content TEXT NOT NULL COMMENT 'Post content (poem, prose, etc.)',
    category VARCHAR(100) COMMENT 'Category key (poezie, proza, teatru, etc.)',
    genre VARCHAR(100) COMMENT 'Genre key within category',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Indexes for performance
    INDEX idx_user_id (user_id),
    INDEX idx_category (category),
    INDEX idx_genre (genre),
    INDEX idx_created_at (created_at),
    INDEX idx_category_genre (category, genre),
    INDEX idx_user_created (user_id, created_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci 
COMMENT='Literary posts (poems, prose, essays, etc.)';

-- ===================================
-- COMMENTS TABLE
-- Stores reader comments on posts
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
    
    -- Foreign key constraints
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    
    -- Indexes for performance
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_approved (approved),
    INDEX idx_created_at (created_at),
    INDEX idx_post_approved (post_id, approved)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci 
COMMENT='Comments on literary posts with moderation support';

-- ===================================
-- LIKES TABLE
-- Stores likes/hearts on posts
-- ===================================
CREATE TABLE likes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT 'Reference to liked post',
    user_id INT COMMENT 'Reference to liker (NULL for anonymous)',
    ip_address VARCHAR(45) COMMENT 'IP address for anonymous likes',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraints to prevent duplicate likes
    UNIQUE KEY unique_user_like (post_id, user_id) COMMENT 'One like per user per post',
    UNIQUE KEY unique_ip_like (post_id, ip_address) COMMENT 'One like per IP per post',
    
    -- Foreign key constraints
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    
    -- Indexes for performance
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_ip_address (ip_address),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci 
COMMENT='Likes/hearts on posts with anonymous support';

-- ===================================
-- SAMPLE DATA
-- Test user and posts for development
-- ===================================

-- Test user (password: "123")
INSERT INTO users (username, email, password_hash, subtitle) VALUES (
    'gandurisilimbrici',
    'sad@sad.sad',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O', -- bcrypt hash for "123"
    'Mi-am facut si io blog, sa nu mor prost lol'
);

-- Get the test user ID (this will be 1 for the first user)
SET @test_user_id = LAST_INSERT_ID();

-- Sample posts for different categories
INSERT INTO posts (user_id, title, content, category, genre) VALUES 
(
    @test_user_id,
    'Primul meu gând',
    'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea. Este doar începutul unei aventuri literare care sper să ne ducă pe drumuri neexplorate ale creativității și expresiei artistice.',
    'proza',
    'povestiri_scurte'
),
(
    @test_user_id,
    'Limbrici și poezie',
    'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.\n\nÎn tăcerea pământului umed\nSe ascund taine și povești,\nCa versurile care iau naștere\nÎn adâncul inimii noastre.',
    'poezie',
    'poezie_lirica'
),
(
    @test_user_id,
    'O zi obișnuită',
    'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie. Să fim recunoscători pentru fiecare clipă ce ni se oferă și să prețuim frumusețea din lucrurile simple ale vieții cotidiene.',
    'proza',
    'povestiri_scurte'
),
(
    @test_user_id,
    'Reflecții despre timp',
    'Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu, să le privesc îndeaproape și să înțeleg ce povești ascund în ele.',
    'jurnal',
    'jurnale_personale'
),
(
    @test_user_id,
    'Scrisoare către viitorul meu',
    'Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum. Sper că ai reușit să găsești drumul tău în această lume complexă și că poezia încă îți umple sufletul de bucurie.\n\nCu drag,\nEu din trecut',
    'scrisoare',
    'scrisori_personale'
);

-- Sample approved comments
INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES 
(1, 'Maria Popescu', 'maria@example.com', 'Ce frumos ai scris! Abia aștept să citesc mai multe din gândurile tale.', TRUE),
(2, 'Ion Creangă', 'ion@example.com', 'Poezia ta despre limbrici m-a emoționat. Comparația cu poezia este genială!', TRUE),
(1, 'Ana Blandiana', 'ana@example.com', 'Primul gând este adesea cel mai autentic. Continuă să scrii!', TRUE);

-- Sample likes (simulating some popularity)
INSERT INTO likes (post_id, ip_address) VALUES 
(1, '192.168.1.100'),
(1, '192.168.1.101'),
(2, '192.168.1.102'),
(2, '192.168.1.103'),
(2, '192.168.1.104'),
(3, '192.168.1.105');

-- ===================================
-- SCHEMA VALIDATION
-- ===================================

-- Verify tables were created successfully
SHOW TABLES;

-- Show table structure for verification
DESCRIBE users;
DESCRIBE posts;  
DESCRIBE comments;
DESCRIBE likes;

-- Show sample data counts
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'posts' as table_name, COUNT(*) as row_count FROM posts
UNION ALL  
SELECT 'comments' as table_name, COUNT(*) as row_count FROM comments
UNION ALL
SELECT 'likes' as table_name, COUNT(*) as row_count FROM likes;

-- ===================================
-- END OF SCHEMA
-- ===================================