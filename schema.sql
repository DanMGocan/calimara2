-- ===================================
-- CALIMARA DATABASE SCHEMA (PostgreSQL)
-- Romanian Writers Microblogging Platform
-- ===================================

-- Drop tables in reverse order of dependency
DROP TABLE IF EXISTS stripe_events CASCADE;
DROP TABLE IF EXISTS super_likes CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS ai_jobs CASCADE;
DROP TABLE IF EXISTS moderation_logs CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS likes CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS best_friends CASCADE;
DROP TABLE IF EXISTS featured_posts CASCADE;
DROP TABLE IF EXISTS user_equipped_items CASCADE;
DROP TABLE IF EXISTS user_inventory CASCADE;
DROP TABLE IF EXISTS shop_items CASCADE;
DROP TABLE IF EXISTS gologani_transactions CASCADE;
DROP TABLE IF EXISTS user_awards CASCADE;
DROP TABLE IF EXISTS forum_replies CASCADE;
DROP TABLE IF EXISTS forum_threads CASCADE;
DROP TABLE IF EXISTS club_board_messages CASCADE;
DROP TABLE IF EXISTS club_join_requests CASCADE;
DROP TABLE IF EXISTS club_members CASCADE;
DROP TABLE IF EXISTS clubs CASCADE;
DROP TABLE IF EXISTS collection_posts CASCADE;
DROP TABLE IF EXISTS collections CASCADE;
DROP TABLE IF EXISTS post_audio CASCADE;
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
    stripe_customer_id VARCHAR(100) UNIQUE,
    stripe_subscription_id VARCHAR(100) UNIQUE,
    premium_tier VARCHAR(20) DEFAULT 'free' NOT NULL,
    premium_period_start TIMESTAMP,
    premium_until TIMESTAMP,
    gologani_balance INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_suspended_by FOREIGN KEY (suspended_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_is_suspended ON users(is_suspended);
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX idx_users_premium_tier ON users(premium_tier);
CREATE INDEX idx_users_premium_period_start ON users(premium_period_start);
CREATE INDEX idx_users_premium_until ON users(premium_until);

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
    ai_critic_requested BOOLEAN DEFAULT FALSE NOT NULL,
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
CREATE INDEX idx_posts_ai_critic_requested ON posts(ai_critic_requested);
CREATE INDEX idx_posts_view_count ON posts(view_count);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE INDEX idx_posts_category_genre_views ON posts(category, genre, view_count);
CREATE INDEX idx_posts_moderation_status ON posts(moderation_status);
CREATE INDEX idx_posts_toxicity_score ON posts(toxicity_score);
CREATE INDEX idx_posts_themes ON posts USING GIN (themes);
CREATE INDEX idx_posts_feelings ON posts USING GIN (feelings);
CREATE INDEX idx_posts_theme_analysis_status ON posts(theme_analysis_status);

-- ===================================
-- POST AUDIO TABLE
-- ===================================
CREATE TABLE post_audio (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    requester_user_id INT,
    source VARCHAR(20) NOT NULL CHECK (source IN ('tts', 'author')),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (status IN ('pending', 'processing', 'ready', 'flagged', 'rejected', 'failed', 'cancelled')),
    tts_character_count INT DEFAULT 0 NOT NULL,
    quota_period_start TIMESTAMP,
    quota_period_end TIMESTAMP,
    storage_backend VARCHAR(20),
    storage_key VARCHAR(500),
    content_type VARCHAR(100),
    duration_seconds DOUBLE PRECISION,
    byte_size INT,
    voice_name VARCHAR(120),
    language_code VARCHAR(20),
    transcript TEXT,
    transcript_confidence DOUBLE PRECISION,
    transcript_match_score DOUBLE PRECISION,
    moderation_status VARCHAR(20),
    moderation_reason TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_post_audio_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_post_audio_requester FOREIGN KEY (requester_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_post_audio_post_id ON post_audio(post_id);
CREATE INDEX idx_post_audio_requester_user_id ON post_audio(requester_user_id);
CREATE INDEX idx_post_audio_status ON post_audio(status);
CREATE INDEX idx_post_audio_source_status ON post_audio(source, status);
CREATE INDEX idx_post_audio_tts_quota ON post_audio(requester_user_id, quota_period_start, quota_period_end);

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
    is_robot BOOLEAN DEFAULT FALSE NOT NULL,
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
CREATE INDEX idx_comments_is_robot ON comments(post_id, is_robot);

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
-- COLLECTIONS TABLE
-- ===================================
CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    owner_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    slug VARCHAR(140) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_collections_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_collections_owner_id ON collections(owner_id);
CREATE INDEX idx_collections_slug ON collections(slug);
CREATE INDEX idx_collections_created_at ON collections(created_at);

-- ===================================
-- COLLECTION_POSTS TABLE (junction with consent-flow status)
-- ===================================
CREATE TABLE collection_posts (
    id SERIAL PRIMARY KEY,
    collection_id INT NOT NULL,
    post_id INT NOT NULL,
    initiator_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    position INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,

    CONSTRAINT unique_collection_post UNIQUE (collection_id, post_id),
    CONSTRAINT fk_cp_collection FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    CONSTRAINT fk_cp_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_cp_initiator FOREIGN KEY (initiator_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_cp_collection_status ON collection_posts(collection_id, status);
CREATE INDEX idx_cp_post_status ON collection_posts(post_id, status);
CREATE INDEX idx_cp_initiator ON collection_posts(initiator_id);

-- ===================================
-- CLUBS TABLE
-- ===================================
CREATE TABLE clubs (
    id SERIAL PRIMARY KEY,
    owner_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    slug VARCHAR(140) UNIQUE NOT NULL,
    description TEXT,
    motto VARCHAR(200),
    avatar_seed VARCHAR(100),
    theme VARCHAR(200),
    speciality VARCHAR(20) NOT NULL
        CHECK (speciality IN ('poezie', 'proza_scurta')),
    featured_post_id INT,
    featured_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_clubs_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_clubs_featured_post FOREIGN KEY (featured_post_id) REFERENCES posts(id) ON DELETE SET NULL
);

CREATE INDEX idx_clubs_owner_id ON clubs(owner_id);
CREATE INDEX idx_clubs_slug ON clubs(slug);
CREATE INDEX idx_clubs_speciality ON clubs(speciality);
CREATE INDEX idx_clubs_created_at ON clubs(created_at);

-- ===================================
-- CLUB MEMBERS TABLE
-- ===================================
CREATE TABLE club_members (
    id SERIAL PRIMARY KEY,
    club_id INT NOT NULL,
    user_id INT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_club_member UNIQUE (club_id, user_id),
    CONSTRAINT fk_cm_club FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE,
    CONSTRAINT fk_cm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_cm_club_role ON club_members(club_id, role);
CREATE INDEX idx_cm_user ON club_members(user_id);

-- ===================================
-- CLUB JOIN REQUESTS TABLE
-- (handles both apply-to-join and invitations via the `direction` column)
-- ===================================
CREATE TABLE club_join_requests (
    id SERIAL PRIMARY KEY,
    club_id INT NOT NULL,
    user_id INT NOT NULL,
    direction VARCHAR(20) NOT NULL
        CHECK (direction IN ('application', 'invitation')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    initiator_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    responded_by INT,

    CONSTRAINT fk_cjr_club FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE,
    CONSTRAINT fk_cjr_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_cjr_initiator FOREIGN KEY (initiator_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_cjr_responder FOREIGN KEY (responded_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Only one pending request per (club, user) pair at a time. Approved/rejected
-- rows are kept for history and don't conflict with future requests.
CREATE UNIQUE INDEX uq_cjr_pending ON club_join_requests (club_id, user_id) WHERE status = 'pending';
CREATE INDEX idx_cjr_club_status ON club_join_requests(club_id, status);
CREATE INDEX idx_cjr_user_status ON club_join_requests(user_id, status);

-- ===================================
-- CLUB BOARD MESSAGES TABLE
-- ===================================
CREATE TABLE club_board_messages (
    id SERIAL PRIMARY KEY,
    club_id INT NOT NULL,
    author_id INT NOT NULL,
    parent_id INT,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cbm_club FOREIGN KEY (club_id) REFERENCES clubs(id) ON DELETE CASCADE,
    CONSTRAINT fk_cbm_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_cbm_parent FOREIGN KEY (parent_id) REFERENCES club_board_messages(id) ON DELETE CASCADE
);

CREATE INDEX idx_cbm_club_created ON club_board_messages(club_id, created_at DESC);
CREATE INDEX idx_cbm_parent ON club_board_messages(parent_id);

-- ===================================
-- FORUM THREADS TABLE
-- ===================================
CREATE TABLE forum_threads (
    id SERIAL PRIMARY KEY,
    author_id INT NOT NULL,
    section VARCHAR(40) NOT NULL
        CHECK (section IN ('general', 'poezie', 'proza_scurta', 'feedback', 'anunturi')),
    title VARCHAR(160) NOT NULL,
    slug VARCHAR(220) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    view_count INT DEFAULT 0 NOT NULL,
    is_locked BOOLEAN DEFAULT FALSE NOT NULL,
    is_pinned BOOLEAN DEFAULT FALSE NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (moderation_status IN ('pending', 'approved', 'flagged', 'rejected')),
    moderation_reason TEXT,
    toxicity_score FLOAT,
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_forum_threads_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_threads_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_forum_threads_author ON forum_threads(author_id);
CREATE INDEX idx_forum_threads_section_activity ON forum_threads(section, last_activity_at DESC);
CREATE INDEX idx_forum_threads_status_activity ON forum_threads(moderation_status, is_pinned DESC, last_activity_at DESC);
CREATE INDEX idx_forum_threads_last_activity ON forum_threads(last_activity_at DESC);
CREATE INDEX idx_forum_threads_slug ON forum_threads(slug);

-- ===================================
-- FORUM REPLIES TABLE
-- ===================================
CREATE TABLE forum_replies (
    id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL,
    author_id INT NOT NULL,
    content TEXT NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (moderation_status IN ('pending', 'approved', 'flagged', 'rejected')),
    moderation_reason TEXT,
    toxicity_score FLOAT,
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_forum_replies_thread FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_replies_author FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_replies_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_forum_replies_thread_created ON forum_replies(thread_id, created_at ASC);
CREATE INDEX idx_forum_replies_author ON forum_replies(author_id);
CREATE INDEX idx_forum_replies_status ON forum_replies(moderation_status);

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
-- GOLOGANI LEDGER
-- ===================================
CREATE TABLE gologani_transactions (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    amount INT NOT NULL,
    balance_after INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    source_type VARCHAR(50),
    source_id INT,
    idempotency_key VARCHAR(160) UNIQUE NOT NULL,
    description VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_gologani_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_gologani_user_created ON gologani_transactions(user_id, created_at DESC);
CREATE INDEX idx_gologani_event_type ON gologani_transactions(event_type);
CREATE INDEX idx_gologani_source ON gologani_transactions(source_type, source_id);
CREATE INDEX idx_gologani_idempotency ON gologani_transactions(idempotency_key);

-- ===================================
-- SHOP ITEMS TABLE
-- ===================================
CREATE TABLE shop_items (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(120) UNIQUE NOT NULL,
    name VARCHAR(180) NOT NULL,
    description TEXT,
    price INT NOT NULL CHECK (price >= 0),
    slot VARCHAR(40) NOT NULL,
    asset_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    sort_order INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shop_items_slug ON shop_items(slug);
CREATE INDEX idx_shop_items_active_order ON shop_items(is_active, sort_order, id);
CREATE INDEX idx_shop_items_slot ON shop_items(slot);

INSERT INTO shop_items (slug, name, description, price, slot, sort_order)
VALUES
    (
        'manuscrisul-scrisorii-a-iii-a',
        'Manuscrisul Scrisorii a III-a',
        'Un manuscris de vitrină pentru profilul tău.',
        120,
        'profile_badge',
        10
    ),
    (
        'costumul-de-nunta-al-lui-nichita-stanescu',
        'Costumul de nuntă al lui Nichita Stănescu',
        'Un costum literar pentru apariții de cenaclu.',
        250,
        'costume',
        20
    );

-- ===================================
-- USER INVENTORY TABLE
-- ===================================
CREATE TABLE user_inventory (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    item_id INT NOT NULL,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_user_inventory_item UNIQUE (user_id, item_id),
    CONSTRAINT fk_inventory_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_inventory_item FOREIGN KEY (item_id) REFERENCES shop_items(id) ON DELETE CASCADE
);

CREATE INDEX idx_inventory_user ON user_inventory(user_id);
CREATE INDEX idx_inventory_item ON user_inventory(item_id);

-- ===================================
-- USER EQUIPPED ITEMS TABLE
-- ===================================
CREATE TABLE user_equipped_items (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    item_id INT NOT NULL,
    slot VARCHAR(40) NOT NULL,
    equipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_user_equipped_slot UNIQUE (user_id, slot),
    CONSTRAINT fk_equipped_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_equipped_item FOREIGN KEY (item_id) REFERENCES shop_items(id) ON DELETE CASCADE
);

CREATE INDEX idx_equipped_user ON user_equipped_items(user_id);
CREATE INDEX idx_equipped_item ON user_equipped_items(item_id);

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
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('post', 'comment', 'audio', 'forum_thread', 'forum_reply')),
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
-- AI JOBS TABLE
-- ===================================
CREATE TABLE ai_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(80) NOT NULL,
    target_type VARCHAR(40) NOT NULL,
    target_id INT NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempts INT DEFAULT 0 NOT NULL,
    max_attempts INT DEFAULT 3 NOT NULL,
    run_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    locked_at TIMESTAMP,
    locked_by VARCHAR(120),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_jobs_status_run_after ON ai_jobs(status, run_after, id);
CREATE INDEX idx_ai_jobs_target ON ai_jobs(target_type, target_id);
CREATE INDEX idx_ai_jobs_type_target_status ON ai_jobs(job_type, target_type, target_id, status);

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
-- SUPER LIKES TABLE
-- ===================================
CREATE TABLE super_likes (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_super_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_super_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_super_likes_user_post UNIQUE (user_id, post_id)
);

CREATE INDEX idx_super_likes_user_created_at ON super_likes(user_id, created_at);
CREATE INDEX idx_super_likes_post ON super_likes(post_id);

-- ===================================
-- STRIPE EVENTS TABLE (webhook idempotency)
-- ===================================
CREATE TABLE stripe_events (
    id VARCHAR(100) PRIMARY KEY,
    type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
CREATE TRIGGER trg_post_audio_updated_at BEFORE UPDATE ON post_audio
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_ai_jobs_updated_at BEFORE UPDATE ON ai_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_best_friends_updated_at BEFORE UPDATE ON best_friends
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_featured_posts_updated_at BEFORE UPDATE ON featured_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_collections_updated_at BEFORE UPDATE ON collections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_clubs_updated_at BEFORE UPDATE ON clubs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_club_board_messages_updated_at BEFORE UPDATE ON club_board_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_forum_threads_updated_at BEFORE UPDATE ON forum_threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_forum_replies_updated_at BEFORE UPDATE ON forum_replies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_user_awards_updated_at BEFORE UPDATE ON user_awards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_shop_items_updated_at BEFORE UPDATE ON shop_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
