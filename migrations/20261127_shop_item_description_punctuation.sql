-- Replace the long dash in the Bacovia shop item description with a sentence break.
-- Idempotent: only rewrites the row while it still has the original text.
UPDATE shop_items
SET description = '„Dormeau adânc sicriele de plumb...” Un artefact simbolist din universul lui George Bacovia.'
WHERE slug = 'sicriul-de-plumb-al-lui-bacovia'
  AND description = '„Dormeau adânc sicriele de plumb...” ' || chr(8212) || ' artefact simbolist din universul lui George Bacovia.';
