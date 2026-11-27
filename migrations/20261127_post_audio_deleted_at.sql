-- Authors can delete their audio. Deleted TTS audio keeps its row (marked with
-- deleted_at, file removed) so it still counts toward that month's TTS quota.
ALTER TABLE post_audio ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
