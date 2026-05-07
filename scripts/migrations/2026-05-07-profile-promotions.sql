-- Expand profile promotion slots:
-- - 4 own posts in featured_posts positions 1..4
-- - 2 other-author posts in featured_posts positions 5..6
-- - 2 promoted authors in best_friends positions 1..2

DELETE FROM best_friends WHERE position > 2;
DELETE FROM featured_posts WHERE position > 6;

ALTER TABLE best_friends
    DROP CONSTRAINT IF EXISTS chk_bf_position;

ALTER TABLE best_friends
    ADD CONSTRAINT chk_bf_position CHECK (position BETWEEN 1 AND 2);

ALTER TABLE featured_posts
    DROP CONSTRAINT IF EXISTS chk_fp_position;

ALTER TABLE featured_posts
    ADD CONSTRAINT chk_fp_position CHECK (position BETWEEN 1 AND 6);
