from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app import schemas
from app.utils import get_avatar_url, validate_social_url


def test_get_avatar_url_encodes_custom_seed():
    url = get_avatar_url("seed with spaces & symbols", size=42)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "api.dicebear.com"
    assert query["seed"] == ["seed with spaces & symbols"]
    assert query["size"] == ["42"]


def test_validate_social_url_rejects_non_http_schemes():
    assert validate_social_url("https://www.facebook.com/calimara", "facebook")
    assert validate_social_url("http://instagram.com/calimara", "instagram")

    assert not validate_social_url("javascript://facebook.com/alert", "facebook")
    assert not validate_social_url("ftp://instagram.com/calimara", "instagram")
    assert not validate_social_url("facebook.com/calimara", "facebook")


def test_site_feedback_page_url_rejects_non_http_schemes():
    assert schemas.SiteFeedbackCreate(
        kind="feedback",
        message="mesaj",
        page_url="https://calimara.test/profil",
    ).page_url == "https://calimara.test/profil"

    assert schemas.SiteFeedbackCreate(kind="bug", message="mesaj", page_url=" ").page_url is None

    with pytest.raises(ValidationError):
        schemas.SiteFeedbackCreate(kind="bug", message="mesaj", page_url="javascript://calimara.test")
