-- Forum: admin-managed sections, pin/lock metadata, pinned replies, per-user thread reads.
-- Idempotent. Drops the hard-coded CHECK on forum_threads.section (approved by the owner)
-- so admins can create new sections; no data is deleted.

CREATE TABLE IF NOT EXISTS forum_sections (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(60) UNIQUE NOT NULL,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(300),
    position INT DEFAULT 0 NOT NULL,
    staff_only BOOLEAN DEFAULT FALSE NOT NULL,
    is_featured BOOLEAN DEFAULT FALSE NOT NULL,
    is_archived BOOLEAN DEFAULT FALSE NOT NULL,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_forum_sections_creator FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_forum_sections_position ON forum_sections(position, id);

INSERT INTO forum_sections (slug, name, description, position, staff_only, is_featured) VALUES
    ('anunturi', 'Anunțuri', 'Noutăți și anunțuri de la echipa Călimara.', 0, TRUE, TRUE),
    ('general', 'Discuții generale', 'Întrebări și conversații libere între autori.', 1, FALSE, FALSE),
    ('poezie', 'Poezie', 'Despre scrisul și cititul poeziei.', 2, FALSE, FALSE),
    ('proza_scurta', 'Proză scurtă', 'Despre proză scurtă: tehnică, lecturi, ateliere.', 3, FALSE, FALSE)
ON CONFLICT (slug) DO NOTHING;

-- Any thread whose section is not a known section yet gets one, so nothing is orphaned.
INSERT INTO forum_sections (slug, name, position)
SELECT DISTINCT t.section, t.section, 100
FROM forum_threads t
WHERE NOT EXISTS (SELECT 1 FROM forum_sections s WHERE s.slug = t.section)
ON CONFLICT (slug) DO NOTHING;

-- Sections are now rows, not a fixed list.
ALTER TABLE forum_threads DROP CONSTRAINT IF EXISTS forum_threads_section_check;
ALTER TABLE forum_threads DROP CONSTRAINT IF EXISTS ck_forum_threads_section;
ALTER TABLE forum_threads ALTER COLUMN section TYPE VARCHAR(60);

ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP;
ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS pinned_by INT;
ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP;
ALTER TABLE forum_threads ADD COLUMN IF NOT EXISTS locked_by INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forum_threads_pinned_by') THEN
        ALTER TABLE forum_threads ADD CONSTRAINT fk_forum_threads_pinned_by
            FOREIGN KEY (pinned_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forum_threads_locked_by') THEN
        ALTER TABLE forum_threads ADD CONSTRAINT fk_forum_threads_locked_by
            FOREIGN KEY (locked_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE forum_threads SET pinned_at = COALESCE(updated_at, created_at) WHERE is_pinned AND pinned_at IS NULL;
UPDATE forum_threads SET locked_at = COALESCE(updated_at, created_at) WHERE is_locked AND locked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_forum_threads_section_pinned_activity
    ON forum_threads(section, is_pinned DESC, last_activity_at DESC);

ALTER TABLE forum_replies ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE forum_replies ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP;
ALTER TABLE forum_replies ADD COLUMN IF NOT EXISTS pinned_by INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_forum_replies_pinned_by') THEN
        ALTER TABLE forum_replies ADD CONSTRAINT fk_forum_replies_pinned_by
            FOREIGN KEY (pinned_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS forum_thread_reads (
    id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL,
    user_id INT NOT NULL,
    first_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT uq_forum_thread_reads_thread_user UNIQUE (thread_id, user_id),
    CONSTRAINT fk_forum_thread_reads_thread FOREIGN KEY (thread_id) REFERENCES forum_threads(id) ON DELETE CASCADE,
    CONSTRAINT fk_forum_thread_reads_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_forum_thread_reads_user ON forum_thread_reads(user_id);
