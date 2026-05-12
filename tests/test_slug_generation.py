from app.repositories.clubs import _generate_club_slug
from app.repositories.posts import generate_slug
from app.repositories.series import _generate_series_slug


def test_generate_slug_transliterates_romanian_diacritics():
    assert generate_slug("Știință și poezie în călimară") == "stiinta-si-poezie-in-calimara"


def test_generate_slug_uses_fallback_for_empty_results():
    assert generate_slug("!!!", fallback="discutie") == "discutie"


def test_series_and_club_slugs_use_shared_diacritic_safe_generation():
    assert _generate_series_slug("Cărți și povești") == "carti-si-povesti"
    assert _generate_club_slug("Poezie & Șoapte") == "poezie-soapte"
