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
DROP TABLE IF EXISTS best_friends;
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
    password_hash VARCHAR(255) NOT NULL COMMENT 'Bcrypt hashed password',
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
    slug VARCHAR(300) UNIQUE NOT NULL COMMENT 'SEO-friendly URL slug',
    content TEXT NOT NULL COMMENT 'Post content',
    category VARCHAR(100) COMMENT 'Category key',
    view_count INT DEFAULT 0 NOT NULL COMMENT 'Number of times post has been viewed',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_slug (slug),
    INDEX idx_category (category),
    INDEX idx_view_count (view_count),
    INDEX idx_created_at (created_at),
    INDEX idx_category_views (category, view_count)
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
-- BEST FRIENDS TABLE
-- ===================================
CREATE TABLE best_friends (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'User who is selecting best friends',
    friend_user_id INT NOT NULL COMMENT 'User who is being selected as best friend',
    position INT NOT NULL COMMENT 'Position order (1, 2, or 3)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_user_position (user_id, position),
    UNIQUE KEY unique_user_friend (user_id, friend_user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (friend_user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_friend_user_id (friend_user_id),
    INDEX idx_position (position),
    
    CONSTRAINT chk_position CHECK (position BETWEEN 1 AND 3),
    CONSTRAINT chk_no_self_friend CHECK (user_id != friend_user_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- SAMPLE DATA
-- ===================================

-- Test user (password will be replaced by initdb.py)
INSERT INTO users (username, email, password_hash, subtitle, avatar_seed, facebook_url, tiktok_url, instagram_url, x_url, bluesky_url, buymeacoffee_url) VALUES (
    'gandurisilimbrici',
    'sad@sad.sad',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O',
    'Mi-am facut si io blog, sa nu mor prost lol',
    'gandurisilimbrici-shapes',
    'https://facebook.com/gandurisilimbrici',
    'https://tiktok.com/@gandurisilimbrici',
    'https://instagram.com/gandurisilimbrici',
    'https://x.com/gandurisilimbrici',
    'https://bsky.app/profile/gandurisilimbrici.bsky.social',
    'https://buymeacoffee.com/gandurisilimbrici'
);

-- Sample posts for the test user
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Primul meu gând', 'primul-meu-gand', 'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea.', 'proza', 15);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Limbrici și poezie', 'limbrici-si-poezie', 'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.', 'poezie', 23);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'O zi obișnuită', 'o-zi-obisnuita', 'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie.', 'proza', 8);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Reflecții despre timp', 'reflectii-despre-timp', 'Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu.', 'jurnal', 12);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(1, 'Scrisoare către viitorul meu', 'scrisoare-catre-viitorul-meu', 'Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum.\n\nCu drag,\nEu din trecut', 'scrisoare', 19);

-- Additional test users
INSERT INTO users (username, email, password_hash, subtitle, avatar_seed) VALUES (
    'mireasufletului',
    'mirabela@poezie.ro',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O',
    'Poezii din inima României, scrise cu drag pentru sufletele românești',
    'mireasufletului-shapes'
);

INSERT INTO users (username, email, password_hash, subtitle, avatar_seed) VALUES (
    'vanatordecuvinte',
    'alex.scriitor@literatura.ro',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5YhF8lVJ5Hn5N5O',
    'Vânez cuvintele prin labirintul gândurilor și le prind în capcana poveștilor',
    'vanatordecuvinte-shapes'
);

INSERT INTO users (username, email, password_hash, subtitle, avatar_seed) VALUES (
    'filedintramvai',
    'elena.urban@bucuresti.ro',
    '$2b$12$KIXaQQWU8jT7nBp3rEJ5PeZmVQKJhF8lVJ5Hn5N5N5YhF8lVJ5Hn5N5O',
    'File din tramvaiul vieții - observații urban-poetice din București',
    'filedintramvai-shapes'
);

-- Posts for mireasufletului
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Dor de țară', 'dor-de-tara', 'Când vântul bate prin câmpurile de grâu\nȘi miroase a pâine și a cer senin,\nAtunci știu că sunt acasă, în România,\nÎn țara mea, cu dor și bucurie.', 'poezie', 42);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Amintiri din copilărie', 'amintiri-din-copilarie', 'Strada copilăriei mele era presărată cu flori de tei și râsete de copii. Vara se întindea nesfârșit, ca o pătură caldă peste zilele noastre fără griji. Alergam desculți pe iarbă și credeam că lumea întreagă ne aparține.', 'proza', 31);

-- Posts for vanatordecuvinte  
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(3, 'Labirintul din metrou', 'labirintul-din-metrou', 'Coborând în subteranele Bucureștiului, descoperi un alt univers. Aici, în tunelurile de beton, se întâlnesc destine diferite, fiecare cu povestea lui. Observ și notez, ca un etnograf al timpurilor moderne.', 'proza', 28);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(3, 'Manifest pentru cuvinte', 'manifest-pentru-cuvinte', 'Cuvintele sunt arme și sunt medicamente,\nSunt poduri și sunt ziduri,\nSunt întrebări și sunt răspunsuri.\nEu le vânez cu plasa imaginației\nȘi le eliberez în cărțile mele.', 'poezie', 35);

-- Posts for filedintramvai
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(4, 'Stația Victoriei dimineața', 'statia-victoriei-dimineata', 'Ora 7:30, stația Victoriei. Un om citește ziarul, o femeie se uită pe geam, un copil râde. Fiecare pasager e o poveste în tramvaiul 41. Bucureștiul se trezește încet, iar eu notez tot ce văd.', 'jurnal', 18);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(4, 'Ghid de supraviețuire urbană', 'ghid-de-supravietuire-urbana', 'Pentru a supraviețui în jungla de beton: învață să citești semne invizibile, să găsești frumusețe în colțuri uitate, să asculți poveștile străzii. Orașul e un organism viu - trebuie doar să știi să-l asculți.', 'eseu', 22);

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

-- Sample best friends relationships
INSERT INTO best_friends (user_id, friend_user_id, position) VALUES 
-- gandurisilimbrici's best friends
(1, 2, 1),  -- mireasufletului as 1st best friend
(1, 3, 2),  -- vanatordecuvinte as 2nd best friend
(1, 4, 3),  -- filedintramvai as 3rd best friend

-- mireasufletului's best friends  
(2, 1, 1),  -- gandurisilimbrici as 1st best friend
(2, 4, 2),  -- filedintramvai as 2nd best friend
(2, 3, 3),  -- vanatordecuvinte as 3rd best friend

-- vanatordecuvinte's best friends
(3, 4, 1),  -- filedintramvai as 1st best friend
(3, 1, 2),  -- gandurisilimbrici as 2nd best friend
(3, 2, 3);  -- mireasufletului as 3rd best friend