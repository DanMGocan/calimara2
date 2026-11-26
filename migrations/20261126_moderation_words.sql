-- Admin-editable moderation word list (replaces the hardcoded list in app/moderation.py).
-- Idempotent and additive: safe to run more than once.
CREATE TABLE IF NOT EXISTS moderation_words (
    id SERIAL PRIMARY KEY,
    word VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(20) DEFAULT 'profanity' NOT NULL,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT ck_moderation_words_category CHECK (category IN ('profanity', 'hate_speech')),
    CONSTRAINT fk_moderation_words_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Seed only into an empty table, so re-running never restores words an admin removed.
INSERT INTO moderation_words (word, category)
SELECT v.word, v.category FROM (VALUES
    ('pula', 'profanity'), ('pulă', 'profanity'), ('muie', 'profanity'), ('futut', 'profanity'),
    ('cacat', 'profanity'), ('căcat', 'profanity'), ('nenorocit', 'profanity'), ('jegos', 'profanity'),
    ('curvă', 'profanity'), ('curve', 'profanity'), ('pizda', 'profanity'), ('pizdă', 'profanity'),
    ('dracu', 'profanity'), ('mortii', 'profanity'), ('morții', 'profanity'), ('naiba', 'profanity'),
    ('dumnezeu', 'profanity'), ('ma-ta', 'profanity'), ('mă-ta', 'profanity'), ('ma-tii', 'profanity'),
    ('mă-tii', 'profanity'), ('idiot', 'profanity'), ('prost', 'profanity'), ('tâmpit', 'profanity'),
    ('tampit', 'profanity'), ('retardat', 'profanity'), ('debil', 'profanity'), ('cretin', 'profanity'),
    ('cioară', 'hate_speech'), ('jidan', 'hate_speech'), ('evreu de căcat', 'hate_speech'),
    ('țigan împuțit', 'hate_speech'), ('tigan imputit', 'hate_speech')
) AS v(word, category)
WHERE NOT EXISTS (SELECT 1 FROM moderation_words)
ON CONFLICT (word) DO NOTHING;
