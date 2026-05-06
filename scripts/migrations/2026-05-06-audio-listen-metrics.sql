ALTER TABLE users
    ADD COLUMN IF NOT EXISTS seconds_listened INT DEFAULT 0 NOT NULL;

ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS seconds_listened INT DEFAULT 0 NOT NULL;

CREATE TABLE IF NOT EXISTS audio_listen_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(64) NOT NULL UNIQUE,
    audio_id INT NOT NULL,
    post_id INT NOT NULL,
    content_owner_id INT NOT NULL,
    listener_user_id INT,
    seconds INT NOT NULL
        CONSTRAINT ck_audio_listen_events_seconds
        CHECK (seconds > 0 AND seconds <= 60),
    mode VARCHAR(20) NOT NULL
        CONSTRAINT ck_audio_listen_events_mode
        CHECK (mode IN ('poezie', 'proza_scurta', 'toate')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT fk_audio_listen_audio FOREIGN KEY (audio_id) REFERENCES post_audio(id) ON DELETE CASCADE,
    CONSTRAINT fk_audio_listen_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_audio_listen_owner FOREIGN KEY (content_owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_audio_listen_listener FOREIGN KEY (listener_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audio_listen_created_at ON audio_listen_events(created_at);
CREATE INDEX IF NOT EXISTS idx_audio_listen_audio ON audio_listen_events(audio_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audio_listen_post ON audio_listen_events(post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audio_listen_owner ON audio_listen_events(content_owner_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audio_listen_listener ON audio_listen_events(listener_user_id, created_at);
