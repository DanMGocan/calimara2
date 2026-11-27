-- Idempotent, additive migration adding three Romanian literary artefact shop items.
INSERT INTO shop_items (slug, name, description, price, slot, asset_url, is_active, sort_order)
VALUES
    (
        'sicriul-de-plumb-al-lui-bacovia',
        'Sicriul de plumb al lui Bacovia',
        '„Dormeau adânc sicriele de plumb...” Un artefact simbolist din universul lui George Bacovia.',
        220,
        'profile_badge',
        '/assets/items/profile_badge/sicriul-de-plumb-al-lui-bacovia.png',
        TRUE,
        40
    ),
    (
        'dintele-de-balena-al-lui-marin-sorescu',
        'Dintele de balenă al lui Marin Sorescu',
        'O relicvă gravată din burta chitului lui Iona, în spiritul lui Marin Sorescu.',
        190,
        'profile_badge',
        '/assets/items/profile_badge/dintele-de-balena-al-lui-marin-sorescu.png',
        TRUE,
        50
    ),
    (
        'portretul-veronicai-al-lui-mihai-eminescu',
        'Portretul Veronicăi al lui Mihai Eminescu',
        'Un medalion oval de epocă păstrând chipul Veronicăi Micle, muza lui Mihai Eminescu.',
        240,
        'profile_badge',
        '/assets/items/profile_badge/portretul-veronicai-al-lui-mihai-eminescu.png',
        TRUE,
        60
    )
ON CONFLICT (slug) DO NOTHING;
