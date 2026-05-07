ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS email_comment_notifications BOOLEAN DEFAULT TRUE NOT NULL,
    ADD COLUMN IF NOT EXISTS email_mention_notifications BOOLEAN DEFAULT TRUE NOT NULL,
    ADD COLUMN IF NOT EXISTS email_analytics_digest BOOLEAN DEFAULT TRUE NOT NULL,
    ADD COLUMN IF NOT EXISTS email_admin_announcements BOOLEAN DEFAULT TRUE NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_last_login_at ON users(last_login_at);

CREATE TABLE IF NOT EXISTS email_campaigns (
    id SERIAL PRIMARY KEY,
    actor_user_id INT,
    subject VARCHAR(255) NOT NULL,
    html_content TEXT NOT NULL,
    text_content TEXT NOT NULL,
    filters JSONB DEFAULT '{}'::jsonb,
    selected_user_ids JSONB DEFAULT '[]'::jsonb,
    matched_count INT DEFAULT 0 NOT NULL,
    recipient_count INT DEFAULT 0 NOT NULL,
    queued_count INT DEFAULT 0 NOT NULL,
    status VARCHAR(20) DEFAULT 'queued' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    queued_at TIMESTAMP,
    CONSTRAINT fk_email_campaign_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_email_campaign_actor ON email_campaigns(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_email_campaign_created ON email_campaigns(created_at);
CREATE INDEX IF NOT EXISTS idx_email_campaign_status ON email_campaigns(status);

CREATE TABLE IF NOT EXISTS email_outbox (
    id BIGSERIAL PRIMARY KEY,
    campaign_id INT,
    recipient_user_id INT,
    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255),
    email_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    html_content TEXT NOT NULL,
    text_content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    dedupe_key VARCHAR(255) UNIQUE,
    status VARCHAR(20) DEFAULT 'queued' NOT NULL,
    attempts INT DEFAULT 0 NOT NULL,
    max_attempts INT DEFAULT 3 NOT NULL,
    run_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    locked_at TIMESTAMP,
    locked_by VARCHAR(100),
    provider_message_id VARCHAR(255),
    error_message TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_email_outbox_campaign FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id) ON DELETE SET NULL,
    CONSTRAINT fk_email_outbox_user FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_email_outbox_campaign ON email_outbox(campaign_id);
CREATE INDEX IF NOT EXISTS idx_email_outbox_user ON email_outbox(recipient_user_id);
CREATE INDEX IF NOT EXISTS idx_email_outbox_type ON email_outbox(email_type);
CREATE INDEX IF NOT EXISTS idx_email_outbox_status_run ON email_outbox(status, run_after);
