-- ===================================
-- CALIMARA DATABASE SCHEMA (PostgreSQL)
-- Romanian Writers Microblogging Platform
-- ===================================

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS notifications CASCADE;
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

