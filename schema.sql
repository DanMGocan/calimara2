-- ===================================
-- CALIMARA DATABASE SCHEMA (PostgreSQL)
-- Romanian Writers Microblogging Platform
-- ===================================

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS drama_invitations CASCADE;
DROP TABLE IF EXISTS drama_comments CASCADE;
DROP TABLE IF EXISTS drama_likes CASCADE;
DROP TABLE IF EXISTS drama_replies CASCADE;
DROP TABLE IF EXISTS drama_acts CASCADE;
DROP TABLE IF EXISTS drama_characters CASCADE;
DROP TABLE IF EXISTS dramas CASCADE;
DROP TABLE IF EXISTS moderation_logs CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS likes CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS best_friends CASCADE;
DROP TABLE IF EXISTS featured_posts CASCADE;
DROP TABLE IF EXISTS user_awards CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ===================================
-- USERS TABLE
-- ===================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    google_id VARCHAR(100) UNIQUE NOT NULL,
    subtitle VARCHAR(500),
    avatar_seed VARCHAR(100),
    facebook_url VARCHAR(300),
    tiktok_url VARCHAR(300),
    instagram_url VARCHAR(300),
    x_url VARCHAR(300),
    bluesky_url VARCHAR(300),
    patreon_url VARCHAR(300),
    paypal_url VARCHAR(300),
    buymeacoffee_url VARCHAR(300),
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    is_moderator BOOLEAN DEFAULT FALSE NOT NULL,
    is_suspended BOOLEAN DEFAULT FALSE NOT NULL,
    suspension_reason TEXT,
    suspended_at TIMESTAMP,
    suspended_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_suspended_by FOREIGN KEY (suspended_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_is_suspended ON users(is_suspended);

-- ===================================
-- POSTS TABLE
-- ===================================
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(300) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    genre VARCHAR(100),
    view_count INT DEFAULT 0 NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    themes JSONB DEFAULT '[]'::jsonb,
    feelings JSONB DEFAULT '[]'::jsonb,
    theme_analysis_status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (theme_analysis_status IN ('pending', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_posts_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_slug ON posts(slug);
CREATE INDEX idx_posts_category ON posts(category);
CREATE INDEX idx_posts_genre ON posts(genre);
CREATE INDEX idx_posts_view_count ON posts(view_count);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE INDEX idx_posts_category_genre_views ON posts(category, genre, view_count);
CREATE INDEX idx_posts_moderation_status ON posts(moderation_status);
CREATE INDEX idx_posts_toxicity_score ON posts(toxicity_score);
CREATE INDEX idx_posts_themes ON posts USING GIN (themes);
CREATE INDEX idx_posts_feelings ON posts USING GIN (feelings);
CREATE INDEX idx_posts_theme_analysis_status ON posts(theme_analysis_status);

-- ===================================
-- COMMENTS TABLE
-- ===================================
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    content TEXT NOT NULL,
    approved BOOLEAN DEFAULT FALSE,
    moderation_status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_comments_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_user_id ON comments(user_id);
CREATE INDEX idx_comments_approved ON comments(approved);
CREATE INDEX idx_comments_post_approved ON comments(post_id, approved);
CREATE INDEX idx_comments_moderation_status ON comments(moderation_status);
CREATE INDEX idx_comments_toxicity_score ON comments(toxicity_score);

-- ===================================
-- LIKES TABLE
-- ===================================
CREATE TABLE likes (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_user_like UNIQUE (post_id, user_id),
    CONSTRAINT unique_ip_like UNIQUE (post_id, ip_address),
    CONSTRAINT fk_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_likes_post_id ON likes(post_id);
CREATE INDEX idx_likes_user_id ON likes(user_id);
CREATE INDEX idx_likes_ip_address ON likes(ip_address);

-- ===================================
-- TAGS TABLE
-- ===================================
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    tag_name VARCHAR(12) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_tags_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);

CREATE INDEX idx_tags_post_id ON tags(post_id);
CREATE INDEX idx_tags_tag_name ON tags(tag_name);
CREATE INDEX idx_tags_tag_search ON tags(tag_name, post_id);

-- ===================================
-- BEST FRIENDS TABLE
-- ===================================
CREATE TABLE best_friends (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    friend_user_id INT NOT NULL,
    position INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_bf_user_position UNIQUE (user_id, position),
    CONSTRAINT unique_bf_user_friend UNIQUE (user_id, friend_user_id),
    CONSTRAINT fk_bf_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_bf_friend FOREIGN KEY (friend_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_bf_position CHECK (position BETWEEN 1 AND 3),
    CONSTRAINT chk_bf_no_self_friend CHECK (user_id != friend_user_id)
);

CREATE INDEX idx_bf_user_id ON best_friends(user_id);
CREATE INDEX idx_bf_friend_user_id ON best_friends(friend_user_id);
CREATE INDEX idx_bf_position ON best_friends(position);

-- ===================================
-- FEATURED POSTS TABLE
-- ===================================
CREATE TABLE featured_posts (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    post_id INT NOT NULL,
    position INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_fp_user_position UNIQUE (user_id, position),
    CONSTRAINT unique_fp_user_post UNIQUE (user_id, post_id),
    CONSTRAINT fk_fp_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_fp_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT chk_fp_position CHECK (position BETWEEN 1 AND 3)
);

CREATE INDEX idx_fp_user_id ON featured_posts(user_id);
CREATE INDEX idx_fp_post_id ON featured_posts(post_id);
CREATE INDEX idx_fp_position ON featured_posts(position);

-- ===================================
-- USER AWARDS TABLE
-- ===================================
CREATE TABLE user_awards (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    award_title VARCHAR(255) NOT NULL,
    award_description TEXT,
    award_date DATE NOT NULL,
    award_type VARCHAR(20) DEFAULT 'writing' NOT NULL
        CHECK (award_type IN ('writing', 'community', 'milestone', 'special')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_awards_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_awards_user_id ON user_awards(user_id);
CREATE INDEX idx_awards_date ON user_awards(award_date);
CREATE INDEX idx_awards_type ON user_awards(award_type);

-- ===================================
-- CONVERSATIONS TABLE
-- ===================================
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user1_id INT NOT NULL,
    user2_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_participants UNIQUE (user1_id, user2_id),
    CONSTRAINT fk_conv_user1 FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_user2 FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_different_users CHECK (user1_id != user2_id),
    CONSTRAINT chk_user_order CHECK (user1_id < user2_id)
);

CREATE INDEX idx_conv_user1_id ON conversations(user1_id);
CREATE INDEX idx_conv_user2_id ON conversations(user2_id);
CREATE INDEX idx_conv_updated_at ON conversations(updated_at);

-- ===================================
-- MESSAGES TABLE
-- ===================================
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL,
    sender_id INT NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_msg_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_msg_sender FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_msg_conversation_id ON messages(conversation_id);
CREATE INDEX idx_msg_sender_id ON messages(sender_id);
CREATE INDEX idx_msg_created_at ON messages(created_at);
CREATE INDEX idx_msg_is_read ON messages(is_read);
CREATE INDEX idx_msg_conversation_created ON messages(conversation_id, created_at);

-- ===================================
-- MODERATION LOGS TABLE
-- ===================================
CREATE TABLE moderation_logs (
    id SERIAL PRIMARY KEY,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('post', 'comment')),
    content_id INT NOT NULL,
    user_id INT,
    ai_decision VARCHAR(20) NOT NULL CHECK (ai_decision IN ('approved', 'flagged', 'rejected')),
    toxicity_score DECIMAL(3,2),
    harassment_score DECIMAL(3,2),
    hate_speech_score DECIMAL(3,2),
    sexually_explicit_score DECIMAL(3,2),
    dangerous_content_score DECIMAL(3,2),
    romanian_profanity_score DECIMAL(3,2),
    ai_reason TEXT,
    ai_details JSONB,
    human_decision VARCHAR(20) CHECK (human_decision IN ('approved', 'rejected', 'pending')),
    human_reason TEXT,
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_modlog_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_modlog_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_modlog_content ON moderation_logs(content_type, content_id);
CREATE INDEX idx_modlog_user_id ON moderation_logs(user_id);
CREATE INDEX idx_modlog_ai_decision ON moderation_logs(ai_decision);
CREATE INDEX idx_modlog_human_decision ON moderation_logs(human_decision);
CREATE INDEX idx_modlog_toxicity ON moderation_logs(toxicity_score);
CREATE INDEX idx_modlog_created_at ON moderation_logs(created_at);
CREATE INDEX idx_modlog_pending_review ON moderation_logs(ai_decision, human_decision);
CREATE INDEX idx_modlog_moderator ON moderation_logs(moderated_by);

-- ===================================
-- DRAMAS TABLE
-- ===================================
CREATE TABLE dramas (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(300) UNIQUE NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'in_progress' NOT NULL
        CHECK (status IN ('in_progress', 'completed')),
    is_open_for_applications BOOLEAN DEFAULT TRUE,
    view_count INT DEFAULT 0 NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dramas_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_dramas_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dramas_slug ON dramas(slug);
CREATE INDEX idx_dramas_user_id ON dramas(user_id);
CREATE INDEX idx_dramas_status ON dramas(status);
CREATE INDEX idx_dramas_view_count ON dramas(view_count);
CREATE INDEX idx_dramas_created_at ON dramas(created_at);

-- ===================================
-- DRAMA CHARACTERS TABLE
-- ===================================
CREATE TABLE drama_characters (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    character_description TEXT,
    is_creator BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_user UNIQUE (drama_id, user_id),
    CONSTRAINT unique_drama_character_name UNIQUE (drama_id, character_name),
    CONSTRAINT fk_dc_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_dc_drama_id ON drama_characters(drama_id);

-- ===================================
-- DRAMA ACTS TABLE
-- ===================================
CREATE TABLE drama_acts (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    act_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    setting TEXT,
    status VARCHAR(20) DEFAULT 'active' NOT NULL
        CHECK (status IN ('active', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_act_number UNIQUE (drama_id, act_number),
    CONSTRAINT fk_da_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
);

CREATE INDEX idx_da_drama_id ON drama_acts(drama_id);

-- ===================================
-- DRAMA REPLIES TABLE
-- ===================================
CREATE TABLE drama_replies (
    id SERIAL PRIMARY KEY,
    act_id INT NOT NULL,
    character_id INT NOT NULL,
    content TEXT NOT NULL,
    stage_direction VARCHAR(500),
    position INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dr_act FOREIGN KEY (act_id) REFERENCES drama_acts(id) ON DELETE CASCADE,
    CONSTRAINT fk_dr_character FOREIGN KEY (character_id) REFERENCES drama_characters(id) ON DELETE CASCADE
);

CREATE INDEX idx_dr_act_position ON drama_replies(act_id, position);

-- ===================================
-- DRAMA LIKES TABLE
-- ===================================
CREATE TABLE drama_likes (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_user_like UNIQUE (drama_id, user_id),
    CONSTRAINT unique_drama_ip_like UNIQUE (drama_id, ip_address),
    CONSTRAINT fk_dl_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dl_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dl_drama_id ON drama_likes(drama_id);

-- ===================================
-- DRAMA COMMENTS TABLE
-- ===================================
CREATE TABLE drama_comments (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT,
    author_name VARCHAR(255),
    content TEXT NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dco_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dco_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dco_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dco_drama_moderation ON drama_comments(drama_id, moderation_status);

-- ===================================
-- DRAMA INVITATIONS TABLE
-- ===================================
CREATE TABLE drama_invitations (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('invitation', 'application')),
    character_name VARCHAR(100),
    message TEXT,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,

    CONSTRAINT fk_di_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_di_from FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_di_to FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_di_drama_to_status ON drama_invitations(drama_id, to_user_id, status);

-- ===================================
-- NOTIFICATIONS TABLE
-- ===================================
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    link VARCHAR(500),
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notif_user_read_created ON notifications(user_id, is_read, created_at);
CREATE INDEX idx_notif_user_id ON notifications(user_id);

-- ===================================
-- PAGE VIEWS TABLE (Analytics)
-- ===================================
CREATE TABLE page_views (
    id BIGSERIAL PRIMARY KEY,
    content_type VARCHAR(20) NOT NULL,
    content_id INT,
    content_key VARCHAR(255),
    user_id INT,
    ip_address VARCHAR(45) NOT NULL,
    session_id VARCHAR(255),
    user_agent TEXT,
    is_bot BOOLEAN DEFAULT FALSE NOT NULL,
    bot_reason VARCHAR(100),
    device_type VARCHAR(10),
    referrer_url TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE NOT NULL,
    content_owner_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_pv_created_at ON page_views(created_at);
CREATE INDEX idx_pv_content ON page_views(content_type, content_id, created_at);
CREATE INDEX idx_pv_content_key ON page_views(content_type, content_key, created_at);
CREATE INDEX idx_pv_owner ON page_views(content_owner_id, created_at);
CREATE INDEX idx_pv_dedup ON page_views(ip_address, content_type, content_id, created_at);
CREATE INDEX idx_pv_bot ON page_views(is_bot, created_at);

-- ===================================
-- DAILY STATS TABLE (Aggregated Analytics)
-- ===================================
CREATE TABLE daily_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    content_type VARCHAR(20) NOT NULL,
    content_id INT,
    content_key VARCHAR(255),
    content_owner_id INT,
    total_views INT DEFAULT 0,
    unique_views INT DEFAULT 0,
    bot_views INT DEFAULT 0,
    logged_in_views INT DEFAULT 0,
    anonymous_views INT DEFAULT 0,
    desktop_views INT DEFAULT 0,
    mobile_views INT DEFAULT 0,
    tablet_views INT DEFAULT 0,
    CONSTRAINT unique_daily_stat UNIQUE (stat_date, content_type, content_key)
);

CREATE INDEX idx_ds_date ON daily_stats(stat_date);
CREATE INDEX idx_ds_owner ON daily_stats(content_owner_id, stat_date);
CREATE INDEX idx_ds_content ON daily_stats(content_type, content_id, stat_date);

-- ===================================
-- UPDATED_AT TRIGGER FUNCTION
-- ===================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_posts_updated_at BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_best_friends_updated_at BEFORE UPDATE ON best_friends
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_featured_posts_updated_at BEFORE UPDATE ON featured_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_user_awards_updated_at BEFORE UPDATE ON user_awards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_dramas_updated_at BEFORE UPDATE ON dramas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_drama_replies_updated_at BEFORE UPDATE ON drama_replies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===================================
-- SAMPLE DATA
-- ===================================

-- Main admin user account
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

-- Sample posts for the admin user (dangocan is user_id = 1)
INSERT INTO posts (user_id, title, slug, content, category, view_count, themes, feelings, theme_analysis_status) VALUES
(1, 'Primul meu gând', 'primul-meu-gand', 'Acesta este primul meu gând, o colecție de idei fără sens, dar pline de pasiune. Sper să vă placă această călătorie în mintea mea.', 'proza', 15, '["reflectie", "arta", "identitate"]'::jsonb, '["pasiune", "speranta", "curiozitate"]'::jsonb, 'completed'),
(1, 'Limbrici și poezie', 'limbrici-si-poezie', E'Chiar și limbricii au o frumusețe aparte,\nO mișcare lentă, dar hotărâtă prin pământ.\nAșa și poezia se strecoară în suflet\nȘi lasă urme adânci, veșnice în timp.', 'poezie', 23, '["natura", "arta", "filozofie"]'::jsonb, '["admiratie", "liniste", "uimire"]'::jsonb, 'completed'),
(1, 'O zi obișnuită', 'o-zi-obisnuita', 'O zi obișnuită, cu cafea, soare și multă muncă. Dar chiar și în banal, găsim momente de inspirație și bucurie.', 'proza', 8, '["cotidian", "oras", "inspiratie"]'::jsonb, '["liniste", "bucurie", "multumire"]'::jsonb, 'completed'),
(1, 'Reflecții despre timp', 'reflectii-despre-timp', 'Timpul este un râu care curge mereu înainte, fără să se întoarcă vreodată. În aceste pagini de jurnal încerc să opresc câteva picături din acest râu.', 'jurnal', 12, '["timp", "filozofie", "memorie"]'::jsonb, '["nostalgie", "melancolie", "contemplare"]'::jsonb, 'completed'),
(1, 'Scrisoare către viitorul meu', 'scrisoare-catre-viitorul-meu', E'Dragă eu din viitor,\n\nÎți scriu aceste rânduri cu speranța că vei fi mai înțelept decât sunt eu acum.\n\nCu drag,\nEu din trecut', 'scrisoare', 19, '["timp", "destin", "identitate"]'::jsonb, '["speranta", "nostalgie", "tandrete"]'::jsonb, 'completed');

-- Additional test users
INSERT INTO users (username, email, google_id, subtitle, avatar_seed) VALUES
('mireasufletului', 'mirabela@poezie.ro', 'test-google-id-234567890', 'Poezii din inima României, scrise cu drag pentru sufletele românești', 'mireasufletului-shapes'),
('vanatordecuvinte', 'alex.scriitor@literatura.ro', 'test-google-id-345678901', 'Vânez cuvintele prin labirintul gândurilor și le prind în capcana poveștilor', 'vanatordecuvinte-shapes'),
('filedintramvai', 'elena.urban@bucuresti.ro', 'test-google-id-456789012', 'File din tramvaiul vieții - observații urban-poetice din București', 'filedintramvai-shapes');

-- Posts for mireasufletului (user_id = 2)
INSERT INTO posts (user_id, title, slug, content, category, view_count, themes, feelings, theme_analysis_status) VALUES
(2, 'Dor de țară', 'dor-de-tara', E'Când vântul bate prin câmpurile de grâu\nȘi miroase a pâine și a cer senin,\nAtunci știu că sunt acasă, în România,\nÎn țara mea, cu dor și bucurie.', 'poezie', 42, '["patriotism", "dor", "natura", "sat"]'::jsonb, '["nostalgie", "bucurie", "iubire", "liniste"]'::jsonb, 'completed'),
(2, 'Amintiri din copilărie', 'amintiri-din-copilarie', 'Strada copilăriei mele era presărată cu flori de tei și râsete de copii. Vara se întindea nesfârșit, ca o pătură caldă peste zilele noastre fără griji. Alergam desculți pe iarbă și credeam că lumea întreagă ne aparține.', 'proza', 31, '["copilarie", "memorie", "natura"]'::jsonb, '["nostalgie", "bucurie", "libertate"]'::jsonb, 'completed');

-- Posts for vanatordecuvinte (user_id = 3)
INSERT INTO posts (user_id, title, slug, content, category, view_count, themes, feelings, theme_analysis_status) VALUES
(3, 'Labirintul din metrou', 'labirintul-din-metrou', 'Coborând în subteranele Bucureștiului, descoperi un alt univers. Aici, în tunelurile de beton, se întâlnesc destine diferite, fiecare cu povestea lui. Observ și notez, ca un etnograf al timpurilor moderne.', 'proza', 28, '["oras", "calatorie", "destin"]'::jsonb, '["uimire", "melancolie", "curiozitate"]'::jsonb, 'completed'),
(3, 'Manifest pentru cuvinte', 'manifest-pentru-cuvinte', E'Cuvintele sunt arme și sunt medicamente,\nSunt poduri și sunt ziduri,\nSunt întrebări și sunt răspunsuri.\nEu le vânez cu plasa imaginației\nȘi le eliberez în cărțile mele.', 'poezie', 35, '["arta", "libertate", "filozofie"]'::jsonb, '["pasiune", "incredere", "determinare"]'::jsonb, 'completed');

-- Posts for filedintramvai (user_id = 4)
INSERT INTO posts (user_id, title, slug, content, category, view_count, themes, feelings, theme_analysis_status) VALUES
(4, 'Stația Victoriei dimineața', 'statia-victoriei-dimineata', 'Ora 7:30, stația Victoriei. Un om citește ziarul, o femeie se uită pe geam, un copil râde. Fiecare pasager e o poveste în tramvaiul 41. Bucureștiul se trezește încet, iar eu notez tot ce văd.', 'jurnal', 18, '["oras", "cotidian", "calatorie"]'::jsonb, '["liniste", "curiozitate", "contemplare"]'::jsonb, 'completed'),
(4, 'Ghid de supraviețuire urbană', 'ghid-de-supravietuire-urbana', 'Pentru a supraviețui în jungla de beton: învață să citești semne invizibile, să găsești frumusețe în colțuri uitate, să asculți poveștile străzii. Orașul e un organism viu - trebuie doar să știi să-l asculți.', 'eseu', 22, '["oras", "natura", "libertate"]'::jsonb, '["incredere", "speranta", "determinare"]'::jsonb, 'completed');

-- Sample comments
INSERT INTO comments (post_id, author_name, author_email, content, approved) VALUES
(1, 'Maria Popescu', 'maria@example.com', 'Ce frumos ai scris! Abia aștept să citesc mai multe din gândurile tale.', TRUE),
(1, 'Ion Creangă', 'ion@example.com', 'Poezia ta despre limbrici m-a emoționat. Comparația cu poezia este genială!', TRUE),
(1, 'Ana Blandiana', 'ana@example.com', 'Primul gând este adesea cel mai autentic. Continuă să scrii!', TRUE);

-- Sample tags
INSERT INTO tags (post_id, tag_name) VALUES
(1, 'gânduri'), (1, 'debut'), (1, 'pasiune'), (1, 'natură'), (1, 'poezie'), (1, 'limbrici'),
(3, 'cotidian'), (3, 'reflecții'),
(4, 'timp'), (4, 'filozofie'),
(5, 'scrisoare'), (5, 'viitor');

-- Sample best friends relationships
INSERT INTO best_friends (user_id, friend_user_id, position) VALUES
(1, 2, 1), (1, 3, 2), (1, 4, 3),
(2, 1, 1), (2, 4, 2), (2, 3, 3),
(3, 4, 1), (3, 1, 2), (3, 2, 3);

-- Sample featured posts
INSERT INTO featured_posts (user_id, post_id, position) VALUES
(1, 2, 1), (1, 4, 2), (1, 1, 3),
(2, 6, 1), (2, 7, 2),
(3, 8, 1), (3, 9, 2);

-- Sample user awards
INSERT INTO user_awards (user_id, award_title, award_description, award_date, award_type) VALUES
(1, 'Primul Gând', 'Prima postare pe platforma Calimara', '2024-01-15', 'milestone'),
(1, 'Poet Popular', 'Peste 50 de aprecieri pentru poezii', '2024-02-20', 'writing'),
(1, 'Blogger Dedicat', '5 postări în prima lună', '2024-02-01', 'community'),
(2, 'Inima României', 'Poezie despre patriotism cu peste 40 de aprecieri', '2024-03-10', 'writing'),
(2, 'Scriitor Prolific', '10 postări publicate', '2024-03-15', 'milestone'),
(3, 'Observator Urban', 'Serie de articole despre București', '2024-02-25', 'writing'),
(3, 'Filosof Modern', 'Manifest pentru cuvinte - lucrare excepțională', '2024-03-01', 'special'),
(4, 'Cronist al Orașului', 'Jurnale urbane apreciate de comunitate', '2024-03-05', 'writing');

-- Sample conversations
INSERT INTO conversations (user1_id, user2_id) VALUES
(1, 2), (1, 3), (2, 3);

-- Sample messages
INSERT INTO messages (conversation_id, sender_id, content, is_read) VALUES
(1, 1, 'Salut! Mi-a plăcut foarte mult poezia ta despre dorul de țară. Îmi amintește de sentimentele mele din copilărie.', TRUE),
(1, 2, 'Mulțumesc frumos! Și mie îmi plac gândurile tale despre limbrici și poezie. E o metaforă foarte interesantă.', TRUE),
(1, 1, 'Da, am vrut să arăt că și lucrurile aparent simple au frumusețea lor. Poate colaborăm la un proiect împreună?', FALSE),
(2, 3, 'Bună! Am citit textul tău despre metropolitanul din București. Foarte captivant stilul tău!', TRUE),
(2, 1, 'Salut! Mulțumesc pentru apreciere. Mi-ar plăcea să citesc mai multe din observațiile tale urbane.', TRUE),
(2, 3, 'Cu siguranță! Poate ne întâlnim să discutăm despre literatură și oraș.', FALSE),
(3, 2, 'Salut Alex! Manifestul tău pentru cuvinte m-a impresionat profund. Filozofia ta despre scriere rezonează cu mine.', TRUE),
(3, 3, 'Mulțumesc, Mirabela! Și poeziile tale sunt pline de emoție autentică. Cred că avem viziuni similare despre literatura română.', FALSE);

-- ===================================
-- SAMPLE DRAMA DATA
-- ===================================

-- Drama created by dangocan (user_id = 1)
INSERT INTO dramas (user_id, title, slug, description, status, is_open_for_applications) VALUES
(1, 'Ultima Noapte de Dragoste', 'ultima-noapte-de-dragoste', 'O piesa despre iubire, tradare si regasire intr-un Bucuresti interbelic. Doua personaje se intalnesc intr-o cafenea si isi spun povestile.', 'in_progress', TRUE);

-- Characters for the drama
INSERT INTO drama_characters (drama_id, user_id, character_name, character_description, is_creator) VALUES
(1, 1, 'Stefan', 'Un tanar scriitor idealist care crede in puterea cuvintelor', TRUE),
(1, 2, 'Elena', 'O poetesa misterioasa cu un trecut plin de secrete', FALSE);

-- Act 1
INSERT INTO drama_acts (drama_id, act_number, title, setting, status) VALUES
(1, 1, 'Intalnirea', 'O cafenea din centrul Bucurestiului, seara. Lumina slaba, muzica de jazz in fundal.', 'active');

-- Sample replies
INSERT INTO drama_replies (act_id, character_id, content, stage_direction, position) VALUES
(1, 1, 'Buna seara. Scuzati-ma, este liber locul acesta?', '(apropiindu-se de masa cu un zambet timid)', 1),
(1, 2, 'Liber ca versul alb. Va rog, luati loc.', '(ridicand privirea din carte)', 2),
(1, 1, 'Multumesc. Observ ca cititi poezie. Bacovia?', '(asezandu-se si privind coperta cartii)', 3),
(1, 2, 'Eminescu, de fapt. Dar apreciez ca ati recunoscut poezia de la distanta.', '(zambind enigmatic)', 4);

-- A completed drama
INSERT INTO dramas (user_id, title, slug, description, status, is_open_for_applications, view_count) VALUES
(3, 'Dialog la Marginea Lumii', 'dialog-la-marginea-lumii', 'Doi calatori se intalnesc la capatul pamantului si descopera ca au aceeasi destinatie.', 'completed', FALSE, 42);

INSERT INTO drama_characters (drama_id, user_id, character_name, character_description, is_creator) VALUES
(2, 3, 'Calator', 'Un filozof ratacitor in cautarea adevarului', TRUE),
(2, 4, 'Straina', 'O femeie care a vazut totul si nu se mai mira de nimic', FALSE);

INSERT INTO drama_acts (drama_id, act_number, title, setting, status) VALUES
(2, 1, 'La Capatul Drumului', 'O stanca deasupra oceanului. Vant puternic. Apus de soare.', 'completed');

INSERT INTO drama_replies (act_id, character_id, content, stage_direction, position) VALUES
(2, 3, 'Am ajuns. In sfarsit, am ajuns la marginea lumii.', '(privind in zare)', 1),
(2, 4, 'Nu exista margine. Doar un alt inceput.', '(aparand din ceata)', 2),
(2, 3, 'Cine esti?', '(intorcandu-se surprins)', 3),
(2, 4, 'Sunt cea care a fost mereu aici. Intrebarea este: de ce ai venit?', NULL, 4);

-- Sample drama likes
INSERT INTO drama_likes (drama_id, user_id) VALUES
(1, 2), (1, 3), (1, 4),
(2, 1), (2, 2);

-- Sample drama comments
INSERT INTO drama_comments (drama_id, user_id, content) VALUES
(1, 3, 'Ce dialog frumos! Abia astept sa vad cum continua povestea.'),
(1, 4, 'Atmosfera cafenelei este captivanta. Felicitari autorilor!'),
(2, 1, 'O piesa filosofica profunda. Finalul m-a emotionat.');
