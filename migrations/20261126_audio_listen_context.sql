-- Tag each listen event with where it was played, so the free daily listening quota
-- (20 minutes in the continuous player) does not count single-post listening.
-- Idempotent and additive: safe to run more than once. Existing rows become 'post'.
ALTER TABLE audio_listen_events
    ADD COLUMN IF NOT EXISTS context VARCHAR(10) DEFAULT 'post' NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_audio_listen_events_context'
    ) THEN
        ALTER TABLE audio_listen_events
            ADD CONSTRAINT ck_audio_listen_events_context CHECK (context IN ('player', 'post'));
    END IF;
END $$;
