-- Forum Phase 4: thread/reply edit metadata, thread follows, reply likes.
-- Idempotent and additive only. Applied after 20261127_forum_sections.sql.

ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS edited_by INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forum_threads_edited_by') THEN
        ALTER TABLE forum_threads ADD CONSTRAINT fk_forum_threads_edited_by
            FOREIGN KEY (edited_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE forum_replies ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE forum_replies ADD COLUMN IF NOT EXISTS edited_by INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forum_replies_edited_by') THEN
        ALTER TABLE forum_replies ADD CONSTRAINT fk_forum_replies_edited_by
            FOREIGN KEY (edited_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS forum_thread_follows (
    id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT uq_forum_thread_follows_thread_user UNIQUE (thread_id, user_id),
    CONSTRAINT fk_forum_thread_follows_thread FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_thread_follows_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_forum_thread_follows_thread ON forum_thread_follows(thread_id);
CREATE INDEX IF NOT EXISTS idx_forum_thread_follows_user ON forum_thread_follows(user_id);

CREATE TABLE IF NOT EXISTS forum_reply_likes (
    id SERIAL PRIMARY KEY,
    reply_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT uq_forum_reply_likes_reply_user UNIQUE (reply_id, user_id),
    CONSTRAINT fk_forum_reply_likes_reply FOREIGN KEY (reply_id) REFERENCES forum_replies(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_reply_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_forum_reply_likes_reply ON forum_reply_likes(reply_id);
CREATE INDEX IF NOT EXISTS idx_forum_reply_likes_user ON forum_reply_likes(user_id);
