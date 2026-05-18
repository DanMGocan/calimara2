from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app import schemas
from app.utils import get_avatar_url, normalize_external_url, validate_social_url, validate_youtube_playlist_url


def test_get_avatar_url_encodes_custom_seed():
    url = get_avatar_url("seed with spaces & symbols", size=42)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "api.dicebear.com"
    assert query["seed"] == ["seed with spaces & symbols"]
    assert query["size"] == ["42"]


def test_external_url_helpers_normalize_schemeless_urls_and_reject_unsafe_schemes():
    assert normalize_external_url("facebook.com/calimara") == "https://facebook.com/calimara"
    assert normalize_external_url("//facebook.com/calimara") == "https://facebook.com/calimara"
    assert validate_social_url("https://www.facebook.com/calimara", "facebook")
    assert validate_social_url("http://instagram.com/calimara", "instagram")
    assert validate_social_url("facebook.com/calimara", "facebook")
    assert validate_social_url("www.facebook.com/calimara", "facebook")
    assert validate_youtube_playlist_url("youtube.com/playlist?list=PL123")

    assert not validate_social_url("javascript://facebook.com/alert", "facebook")
    assert not validate_social_url("ftp://instagram.com/calimara", "instagram")
    assert not validate_social_url("instagram.com/calimara", "facebook")
    assert not validate_youtube_playlist_url("youtube.com/watch?v=abc")


def test_profile_link_schemas_store_normalized_external_urls():
    social_links = schemas.SocialLinksUpdate.model_validate(
        {
            "facebook_url": "facebook.com/calimara",
            "youtube_playlist_url": "youtube.com/playlist?list=PL123",
        }
    )
    profile_settings = schemas.UserProfileSettingsUpdate.model_validate(
        {"buymeacoffee_url": "buymeacoffee.com/calimara"}
    )

    assert social_links.facebook_url == "https://facebook.com/calimara"
    assert social_links.youtube_playlist_url == "https://youtube.com/playlist?list=PL123"
    assert profile_settings.buymeacoffee_url == "https://buymeacoffee.com/calimara"


def test_site_feedback_page_url_rejects_non_http_schemes():
    assert schemas.SiteFeedbackCreate(
        kind="feedback",
        message="mesaj",
        page_url="https://calimara.test/profil",
    ).page_url == "https://calimara.test/profil"

    assert schemas.SiteFeedbackCreate(kind="bug", message="mesaj", page_url=" ").page_url is None

    with pytest.raises(ValidationError):
        schemas.SiteFeedbackCreate(kind="bug", message="mesaj", page_url="javascript://calimara.test")
