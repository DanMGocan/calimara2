from collections import Counter

from app import rich_text
from app.schemas.common import POST_CONTENT_CHARACTER_LIMITS
from scripts import seed


LONG_FORM_SEED_SLUGS = {
    "punguta-cu-doi-bani",
    "ursul-pacalit-de-vulpe",
    "capra-cu-trei-iezi",
    "povestea-unui-om-lenes",
    "danila-prepeleac",
    "fata-babei-si-fata-mosneagului",
    "soacra-cu-trei-nurori",
    "ivan-turbinca",
}

NEW_LONG_POEM_SLUGS = {
    "scrisoarea-i-fragment-de-seed",
    "luceafarul-fragment-de-seed",
    "glossa-adaptare-de-seed",
}


def test_seed_posts_render_only_literary_text_and_expected_shape():
    assert len(seed.POSTS) == 16
    assert len({row["slug"] for row in seed.POSTS}) == 16
    assert Counter(row["category"] for row in seed.POSTS) == {
        "proza_scurta": 8,
        "poezie": 8,
    }
    assert not hasattr(seed, "AI_TEST_NOTICE")

    for row in seed.POSTS:
        assert row["source_author"]
        assert row["source_name"].startswith("Wikisource - ")
        assert row["source_url"].startswith("https://ro.wikisource.org/wiki/")

        rendered = seed._seed_content_html(row)
        plain_rendered = rich_text.rich_text_to_plain_text(rendered)
        assert "Text de seed" not in plain_rendered
        assert "domeniul public" not in plain_rendered
        assert row["source_name"] not in plain_rendered
        assert row["source_url"] not in plain_rendered
        assert "inteligență artificială" not in plain_rendered

        limit = POST_CONTENT_CHARACTER_LIMITS[row["category"]]
        assert len(rich_text.rich_text_to_plain_text(rendered)) <= limit


def test_seed_fixture_has_longer_story_and_poetry_samples():
    posts_by_slug = {row["slug"]: row for row in seed.POSTS}

    for slug in LONG_FORM_SEED_SLUGS:
        plain = rich_text.rich_text_to_plain_text(posts_by_slug[slug]["content"])
        assert len(plain) > 900

    for slug in NEW_LONG_POEM_SLUGS:
        plain = rich_text.rich_text_to_plain_text(posts_by_slug[slug]["content"])
        assert len(plain) > 650


def test_seed_audio_links_target_existing_seed_posts():
    post_slugs = {row["slug"] for row in seed.POSTS}
    audio_slugs = {row["post_slug"] for row in seed.POST_AUDIO}

    assert len(seed.POST_AUDIO) == 23
    assert audio_slugs == post_slugs
    assert Counter(row["storage_backend"] for row in seed.POST_AUDIO) == {"s3": 23}

    for row in seed.POST_AUDIO:
        assert row["storage_backend"] == "s3"
        assert row["status"] == "ready"
        assert row["moderation_status"] == "approved"
        assert row["content_type"] == "audio/mpeg"
        assert row["storage_key"].endswith(".mp3")
