-- ===================================
-- CALIMARA DATABASE SCHEMA
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
    is_suspended BOOLEAN DEFAULT FALSE COMMENT 'User suspension status',
    suspension_reason TEXT COMMENT 'Reason for user suspension',
    suspended_at DATETIME COMMENT 'When user was suspended',
    suspended_by INT COMMENT 'Admin who suspended the user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_google_id (google_id),
    INDEX idx_created_at (created_at),
    INDEX idx_is_suspended (is_suspended),
    FOREIGN KEY (suspended_by) REFERENCES users(id) ON DELETE SET NULL
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
    moderation_status ENUM('approved', 'pending', 'rejected', 'flagged') DEFAULT 'approved' COMMENT 'Content moderation status',
    moderation_reason TEXT COMMENT 'Reason for moderation action',
    toxicity_score DECIMAL(3,2) COMMENT 'Perspective API toxicity score (0-1)',
    moderated_by INT COMMENT 'Admin who performed moderation action',
    moderated_at DATETIME COMMENT 'When moderation action was taken',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_slug (slug),
    INDEX idx_category (category),
    INDEX idx_view_count (view_count),
    INDEX idx_created_at (created_at),
    INDEX idx_category_views (category, view_count),
    INDEX idx_moderation_status (moderation_status),
    INDEX idx_toxicity_score (toxicity_score)
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
    moderation_status ENUM('approved', 'pending', 'rejected', 'flagged') DEFAULT 'pending' COMMENT 'Content moderation status',
    moderation_reason TEXT COMMENT 'Reason for moderation action',
    toxicity_score DECIMAL(3,2) COMMENT 'Perspective API toxicity score (0-1)',
    moderated_by INT COMMENT 'Admin who performed moderation action',
    moderated_at DATETIME COMMENT 'When moderation action was taken',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_post_id (post_id),
    INDEX idx_user_id (user_id),
    INDEX idx_approved (approved),
    INDEX idx_post_approved (post_id, approved),
    INDEX idx_moderation_status (moderation_status),
    INDEX idx_toxicity_score (toxicity_score)
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
-- FEATURED POSTS TABLE
-- ===================================
CREATE TABLE featured_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'User who is featuring the post',
    post_id INT NOT NULL COMMENT 'Post being featured',
    position INT NOT NULL COMMENT 'Position order (1, 2, or 3)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_user_position (user_id, position),
    UNIQUE KEY unique_user_post (user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_post_id (post_id),
    INDEX idx_position (position),
    
    CONSTRAINT chk_featured_position CHECK (position BETWEEN 1 AND 3)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- USER AWARDS TABLE
-- ===================================
CREATE TABLE user_awards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT 'User who received the award',
    award_title VARCHAR(255) NOT NULL COMMENT 'Title of the award',
    award_description TEXT COMMENT 'Description of the achievement',
    award_date DATE NOT NULL COMMENT 'Date when award was received',
    award_type ENUM('writing', 'community', 'milestone', 'special') DEFAULT 'writing' COMMENT 'Type of award',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_award_date (award_date),
    INDEX idx_award_type (award_type)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- CONVERSATIONS TABLE
-- ===================================
CREATE TABLE conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user1_id INT NOT NULL COMMENT 'First participant (lower user ID)',
    user2_id INT NOT NULL COMMENT 'Second participant (higher user ID)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_participants (user1_id, user2_id),
    FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user1_id (user1_id),
    INDEX idx_user2_id (user2_id),
    INDEX idx_updated_at (updated_at),
    
    CONSTRAINT chk_different_users CHECK (user1_id != user2_id),
    CONSTRAINT chk_user_order CHECK (user1_id < user2_id)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- MESSAGES TABLE
-- ===================================
CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL COMMENT 'Reference to conversation',
    sender_id INT NOT NULL COMMENT 'User who sent the message',
    content TEXT NOT NULL COMMENT 'Message content',
    is_read BOOLEAN DEFAULT FALSE COMMENT 'Whether message has been read by recipient',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_conversation_id (conversation_id),
    INDEX idx_sender_id (sender_id),
    INDEX idx_created_at (created_at),
    INDEX idx_is_read (is_read),
    INDEX idx_conversation_created (conversation_id, created_at)
) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ===================================
-- SAMPLE DATA
-- ===================================

-- God Admin account
INSERT INTO users (username, email, google_id, subtitle, avatar_seed) VALUES (
    'admin',
    'dangocan@outlook.com',
    'god-admin-google-id-000000000',
    'Calimara Platform Administrator - Moderation & User Management',
    'admin-shapes'
);

-- Test user (google_id will be replaced by initdb.py)
INSERT INTO users (username, email, google_id, subtitle, avatar_seed, facebook_url, tiktok_url, instagram_url, x_url, bluesky_url, buymeacoffee_url) VALUES (
    'dangocan',
    'dangocan@outlook.com',
    'test-google-id-123456789',
    'Scriitor și developer român',
    'dangocan-shapes',
    'https://facebook.com/dangocan',
    'https://tiktok.com/@dangocan',
    'https://instagram.com/dangocan',
    'https://x.com/dangocan',
    'https://bsky.app/profile/dangocan.bsky.social',
    'https://buymeacoffee.com/dangocan'
);

-- Sample posts for the test user (dangocan is now user_id = 2)
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Primul meu gând', 'primul-meu-gand', 'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea.', 'proza', 15);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Limbrici și poezie', 'limbrici-si-poezie', 'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.', 'poezie', 23);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'O zi obișnuită', 'o-zi-obisnuita', 'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie.', 'proza', 8);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Reflecții despre timp', 'reflectii-despre-timp', 'Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu.', 'jurnal', 12);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(2, 'Scrisoare către viitorul meu', 'scrisoare-catre-viitorul-meu', 'Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum.\n\nCu drag,\nEu din trecut', 'scrisoare', 19);

-- Additional test users
INSERT INTO users (username, email, google_id, subtitle, avatar_seed) VALUES (
    'mireasufletului',
    'mirabela@poezie.ro',
    'test-google-id-234567890',
    'Poezii din inima României, scrise cu drag pentru sufletele românești',
    'mireasufletului-shapes'
);

INSERT INTO users (username, email, google_id, subtitle, avatar_seed) VALUES (
    'vanatordecuvinte',
    'alex.scriitor@literatura.ro',
    'test-google-id-345678901',
    'Vânez cuvintele prin labirintul gândurilor și le prind în capcana poveștilor',
    'vanatordecuvinte-shapes'
);

INSERT INTO users (username, email, google_id, subtitle, avatar_seed) VALUES (
    'filedintramvai',
    'elena.urban@bucuresti.ro',
    'test-google-id-456789012',
    'File din tramvaiul vieții - observații urban-poetice din București',
    'filedintramvai-shapes'
);

-- Posts for mireasufletului (user_id = 3)
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(3, 'Dor de țară', 'dor-de-tara', 'Când vântul bate prin câmpurile de grâu\nȘi miroase a pâine și a cer senin,\nAtunci știu că sunt acasă, în România,\nÎn țara mea, cu dor și bucurie.', 'poezie', 42);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(3, 'Amintiri din copilărie', 'amintiri-din-copilarie', 'Strada copilăriei mele era presărată cu flori de tei și râsete de copii. Vara se întindea nesfârșit, ca o pătură caldă peste zilele noastre fără griji. Alergam desculți pe iarbă și credeam că lumea întreagă ne aparține.', 'proza', 31);

-- Posts for vanatordecuvinte (user_id = 4)
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(4, 'Labirintul din metrou', 'labirintul-din-metrou', 'Coborând în subteranele Bucureștiului, descoperi un alt univers. Aici, în tunelurile de beton, se întâlnesc destine diferite, fiecare cu povestea lui. Observ și notez, ca un etnograf al timpurilor moderne.', 'proza', 28);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(4, 'Manifest pentru cuvinte', 'manifest-pentru-cuvinte', 'Cuvintele sunt arme și sunt medicamente,\nSunt poduri și sunt ziduri,\nSunt întrebări și sunt răspunsuri.\nEu le vânez cu plasa imaginației\nȘi le eliberez în cărțile mele.', 'poezie', 35);

-- Posts for filedintramvai (user_id = 5)
INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(5, 'Stația Victoriei dimineața', 'statia-victoriei-dimineata', 'Ora 7:30, stația Victoriei. Un om citește ziarul, o femeie se uită pe geam, un copil râde. Fiecare pasager e o poveste în tramvaiul 41. Bucureștiul se trezește încet, iar eu notez tot ce văd.', 'jurnal', 18);

INSERT INTO posts (user_id, title, slug, content, category, view_count) VALUES 
(5, 'Ghid de supraviețuire urbană', 'ghid-de-supravietuire-urbana', 'Pentru a supraviețui în jungla de beton: învață să citești semne invizibile, să găsești frumusețe în colțuri uitate, să asculți poveștile străzii. Orașul e un organism viu - trebuie doar să știi să-l asculți.', 'eseu', 22);

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
-- dangocan's best friends (user_id = 2)
(2, 3, 1),  -- mireasufletului as 1st best friend
(2, 4, 2),  -- vanatordecuvinte as 2nd best friend
(2, 5, 3),  -- filedintramvai as 3rd best friend

-- mireasufletului's best friends (user_id = 3)
(3, 2, 1),  -- dangocan as 1st best friend
(3, 5, 2),  -- filedintramvai as 2nd best friend
(3, 4, 3),  -- vanatordecuvinte as 3rd best friend

-- vanatordecuvinte's best friends (user_id = 4)
(4, 5, 1),  -- filedintramvai as 1st best friend
(4, 2, 2),  -- dangocan as 2nd best friend
(4, 3, 3);  -- mireasufletului as 3rd best friend

-- Sample featured posts
INSERT INTO featured_posts (user_id, post_id, position) VALUES 
-- dangocan's featured posts (user_id = 2, posts 1-5)
(2, 2, 1),  -- "Limbrici și poezie" as 1st featured
(2, 4, 2),  -- "Reflecții despre timp" as 2nd featured
(2, 1, 3),  -- "Primul meu gând" as 3rd featured

-- mireasufletului's featured posts (user_id = 3, posts 6-7)
(3, 6, 1),  -- "Dor de țară" as 1st featured
(3, 7, 2),  -- "Amintiri din copilărie" as 2nd featured

-- vanatordecuvinte's featured posts (user_id = 4, posts 8-9)
(4, 8, 1),  -- "Labirintul din metrou" as 1st featured
(4, 9, 2);  -- "Manifest pentru cuvinte" as 2nd featured

-- Sample user awards
INSERT INTO user_awards (user_id, award_title, award_description, award_date, award_type) VALUES 
-- dangocan's awards (user_id = 2)
(2, 'Primul Gând', 'Prima postare pe platforma Calimara', '2024-01-15', 'milestone'),
(2, 'Poet Popular', 'Peste 50 de aprecieri pentru poezii', '2024-02-20', 'writing'),
(2, 'Blogger Dedicat', '5 postări în prima lună', '2024-02-01', 'community'),

-- mireasufletului's awards (user_id = 3)
(3, 'Inima României', 'Poezie despre patriotism cu peste 40 de aprecieri', '2024-03-10', 'writing'),
(3, 'Scriitor Prolific', '10 postări publicate', '2024-03-15', 'milestone'),

-- vanatordecuvinte's awards (user_id = 4)
(4, 'Observator Urban', 'Serie de articole despre București', '2024-02-25', 'writing'),
(4, 'Filosof Modern', 'Manifest pentru cuvinte - lucrare excepțională', '2024-03-01', 'special'),

-- filedintramvai's awards (user_id = 5)
(5, 'Cronist al Orașului', 'Jurnale urbane apreciate de comunitate', '2024-03-05', 'writing');

-- Sample conversations
INSERT INTO conversations (user1_id, user2_id) VALUES 
-- dangocan (2) and mireasufletului (3)
(2, 3),
-- dangocan (2) and vanatordecuvinte (4)  
(2, 4),
-- mireasufletului (3) and vanatordecuvinte (4)
(3, 4);

-- Sample messages
INSERT INTO messages (conversation_id, sender_id, content, is_read) VALUES 
-- Conversation between dangocan and mireasufletului
(1, 2, 'Salut! Mi-a plăcut foarte mult poezia ta despre dorul de țară. Îmi amintește de sentimentele mele din copilărie.', TRUE),
(1, 3, 'Mulțumesc frumos! Și mie îmi plac gândurile tale despre limbrici și poezie. E o metaforă foarte interesantă.', TRUE),
(1, 2, 'Da, am vrut să arăt că și lucrurile aparent simple au frumusețea lor. Poate colaborăm la un proiect împreună?', FALSE),

-- Conversation between dangocan and vanatordecuvinte
(2, 4, 'Bună! Am citit textul tău despre metropolitanul din București. Foarte captivant stilul tău!', TRUE),
(2, 2, 'Salut! Mulțumesc pentru apreciere. Mi-ar plăcea să citesc mai multe din observațiile tale urbane.', TRUE),
(2, 4, 'Cu siguranță! Poate ne întâlnim să discutăm despre literatură și oraș.', FALSE),

-- Conversation between mireasufletului and vanatordecuvinte
(3, 3, 'Salut Alex! Manifestul tău pentru cuvinte m-a impresionat profund. Filozofia ta despre scriere rezonează cu mine.', TRUE),
(3, 4, 'Mulțumesc, Mirabela! Și poeziile tale sunt pline de emoție autentică. Cred că avem viziuni similare despre literatura română.', FALSE);