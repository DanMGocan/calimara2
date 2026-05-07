CREATE TABLE IF NOT EXISTS site_feedback (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(20) NOT NULL
        CONSTRAINT ck_site_feedback_kind
        CHECK (kind IN ('feedback', 'bug')),
    user_id INT,
    username_snapshot VARCHAR(255),
    email_snapshot VARCHAR(255),
    message TEXT NOT NULL,
    page_url VARCHAR(1000),
    user_agent TEXT,
    client_context JSONB DEFAULT '{}'::jsonb NOT NULL,
    status VARCHAR(20) DEFAULT 'open' NOT NULL
        CONSTRAINT ck_site_feedback_status
        CHECK (status IN ('open', 'closed')),
    admin_note TEXT,
    resolved_by INT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT fk_site_feedback_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_site_feedback_resolver FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_site_feedback_kind ON site_feedback(kind);
CREATE INDEX IF NOT EXISTS idx_site_feedback_status_created ON site_feedback(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_site_feedback_user ON site_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_site_feedback_resolved_by ON site_feedback(resolved_by);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'trg_site_feedback_updated_at'
    ) THEN
        CREATE TRIGGER trg_site_feedback_updated_at
            BEFORE UPDATE ON site_feedback
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;
