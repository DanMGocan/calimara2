import pytest
from pydantic import ValidationError

from app import rich_text, schemas
from app.schemas.common import PROFILE_DESCRIPTION_CHARACTER_LIMIT


def test_sanitize_rich_text_keeps_literary_formatting_and_strips_unsafe_html():
    sanitized = rich_text.sanitize_rich_text(
        '<p>Text</p><script>alert(1)</script><img src=x>'
        '<strong onclick="bad()">bold</strong><a href="https://x.test">link</a>'
    )

    assert "<p>Text</p>" in sanitized
    assert "<strong>bold</strong>" in sanitized
    assert "link" in sanitized
    assert "<script" not in sanitized
    assert "alert(1)" not in sanitized
    assert "<img" not in sanitized
    assert "onclick" not in sanitized
    assert "<a" not in sanitized


def test_empty_editor_document_normalizes_to_blank_and_fails_required_schema():
    assert rich_text.sanitize_rich_text("<p><br></p>") == ""
    assert rich_text.rich_text_to_plain_text("<p><br></p>") == ""

    with pytest.raises(ValidationError):
        schemas.CommentCreate(content="<p><br></p>")


def test_content_schemas_store_sanitized_html_strings():
    post = schemas.PostCreate(
        title="Titlu",
        category="poezie",
        content='<p>Salut <em onclick="bad()">lume</em></p><script>bad()</script>',
    )
    reply = schemas.ForumReplyCreate(
        content='<blockquote>Răspuns</blockquote><img src=x><u data-x="1">ok</u>',
    )

    assert post.content == "<p>Salut <em>lume</em></p>"
    assert reply.content == "<blockquote>Răspuns</blockquote><u>ok</u>"


def test_poetry_line_breaks_are_preserved_inside_paragraphs():
    content = "<p>vers 1<br>vers 2</p><p>strofa 2</p>"
    post = schemas.PostCreate(title="Titlu", category="poezie", content=content)

    assert post.content == content
    assert rich_text.sanitize_rich_text(content) == content
    assert rich_text.rich_text_to_plain_text(content) == "vers 1\nvers 2\n\nstrofa 2"


def test_canonical_paste_html_remains_valid_rich_text():
    content = "<p>Primul <strong>rând</strong> curat</p><p>vers unu<br>vers doi cu <em>accent</em></p>"

    assert rich_text.sanitize_rich_text(content) == content
    assert rich_text.rich_text_to_plain_text(content) == "Primul rând curat\n\nvers unu\nvers doi cu accent"


def test_paste_artifacts_are_removed_from_rich_text():
    content = "<p>Cu\u200bv\u00adânt&nbsp;&nbsp;curat</p><p>\ufeffAlt rând</p>"
    sanitized = rich_text.sanitize_rich_text(content)

    assert sanitized == "<p>Cuvânt  curat</p><p>Alt rând</p>"
    assert rich_text.rich_text_to_plain_text(content) == "Cuvânt curat\n\nAlt rând"


def test_profile_subtitle_is_sanitized_and_limited_by_visible_text():
    assert PROFILE_DESCRIPTION_CHARACTER_LIMIT == 400
    valid_description = "x" * PROFILE_DESCRIPTION_CHARACTER_LIMIT
    too_long_description = "x" * (PROFILE_DESCRIPTION_CHARACTER_LIMIT + 1)
    setup = schemas.UserSetup(
        username="autor",
        avatar_seed="autor-shapes",
        subtitle='<p>Bio <strong onclick="bad()">scurt</strong></p>',
    )
    setup_at_limit = schemas.UserSetup(
        username="autor",
        avatar_seed="autor-shapes",
        subtitle=f"<p>{valid_description}</p>",
    )

    assert setup.subtitle == "<p>Bio <strong>scurt</strong></p>"
    assert setup_at_limit.subtitle == f"<p>{valid_description}</p>"
    assert schemas.UserProfileUpdate(subtitle=f"<p>{valid_description}</p>").subtitle == f"<p>{valid_description}</p>"
    assert schemas.DiacriticsRequest(kind="profile_description", content=f"<p>{valid_description}</p>").content == f"<p>{valid_description}</p>"

    with pytest.raises(ValidationError):
        schemas.UserSetup(username="autor", avatar_seed="autor-shapes", subtitle=f"<p>{too_long_description}</p>")

    with pytest.raises(ValidationError):
        schemas.UserProfileUpdate(subtitle=f"<p>{too_long_description}</p>")

    with pytest.raises(ValidationError):
        schemas.DiacriticsRequest(kind="profile_description", content=f"<p>{too_long_description}</p>")


def test_post_content_limits_count_visible_text_not_html_tags():
    poetry = schemas.PostCreate(
        title="Titlu",
        category="poezie",
        content=f"<p>{'x' * 10000}</p>",
    )
    story = schemas.PostCreate(
        title="Titlu",
        category="proza_scurta",
        content=f"<p>{'x' * 50000}</p>",
    )

    assert rich_text.rich_text_to_plain_text(poetry.content) == "x" * 10000
    assert rich_text.rich_text_to_plain_text(story.content) == "x" * 50000

    with pytest.raises(ValidationError):
        schemas.PostCreate(title="Titlu", category="poezie", content=f"<p>{'x' * 10001}</p>")

    with pytest.raises(ValidationError):
        schemas.PostCreate(title="Titlu", category="proza_scurta", content=f"<p>{'x' * 50001}</p>")

    with pytest.raises(ValidationError):
        schemas.PostDraftSave(title="Ciornă", category="poezie", content=f"<p>{'x' * 10001}</p>")


def test_explanatory_note_is_trimmed_optional_and_limited():
    post = schemas.PostCreate(
        title="Titlu",
        category="poezie",
        content="valid",
        explanatory_note="  O notă scurtă.  ",
    )
    draft = schemas.PostDraftSave(
        title="Ciornă",
        category="poezie",
        content="<p>valid</p>",
        explanatory_note="   ",
    )

    assert post.explanatory_note == "O notă scurtă."
    assert draft.explanatory_note is None

    with pytest.raises(ValidationError):
        schemas.PostCreate(title="Titlu", category="poezie", content="valid", explanatory_note="x" * 301)

    with pytest.raises(ValidationError):
        schemas.PostDraftSave(title="Ciornă", category="poezie", content="valid", explanatory_note="x" * 301)


def test_comment_and_title_limits_are_enforced():
    assert schemas.CommentCreate(content=f"<p>{'x' * 2500}</p>").content == f"<p>{'x' * 2500}</p>"

    with pytest.raises(ValidationError):
        schemas.CommentCreate(content=f"<p>{'x' * 2501}</p>")

    with pytest.raises(ValidationError):
        schemas.PostCreate(title="x" * 121, category="poezie", content="valid")

    with pytest.raises(ValidationError):
        schemas.ForumThreadCreate(section="general", title="x" * 121, content="valid")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: schemas.PostCreate(title="   ", category="poezie", content="valid"),
        lambda: schemas.ForumThreadCreate(section="general", title="   ", content="valid"),
        lambda: schemas.ClubCreate(title="   ", speciality="poezie"),
        lambda: schemas.ClubBoardMessageCreate(title="Atelier", content="   "),
        lambda: schemas.ClubInviteRequest(username="   "),
        lambda: schemas.SeriesCreate(title="   "),
        lambda: schemas.TheatrePlayCreate(title="   "),
        lambda: schemas.TheatreCharacterInput(name="   ", description="Descriere"),
        lambda: schemas.TheatreCharacterCreate(name="Personaj", description="   "),
        lambda: schemas.TheatreSceneCreate(title="   ", content="valid", first_character_id=1),
        lambda: schemas.StafetaCreate(title="   ", initial_content="valid"),
        lambda: schemas.StafetaAssignSpecific(username="   "),
        lambda: schemas.ShopItemCreate(slug="obiect", name="   ", price=1),
        lambda: schemas.AdminReasonRequest(reason="   "),
        lambda: schemas.AdminEmailCampaignCreate(subject="   ", html_content="valid"),
    ],
)
def test_required_schema_strings_reject_whitespace_only_values(factory):
    with pytest.raises(ValidationError):
        factory()


def test_required_schema_strings_are_trimmed_before_length_validation():
    title = "x" * 120
    post = schemas.PostCreate(title=f" {title} ", category="poezie", content="valid")
    forum_thread = schemas.ForumThreadCreate(section="general", title="  Discuție  ", content="valid")
    club = schemas.ClubCreate(title="  Atelier  ", speciality="poezie")
    club_message = schemas.ClubBoardMessageCreate(title="  Fir  ", content="  Mesaj  ")
    series = schemas.SeriesCreate(title="  Serie  ", description="  Descriere  ")
    theatre = schemas.TheatrePlayCreate(
        title="  Piesă  ",
        characters=[schemas.TheatreCharacterInput(name="  Autor  ", description="  Descriere  ")],
    )
    stafeta = schemas.StafetaCreate(title="  Ștafetă  ", initial_content="valid")
    shop_item = schemas.ShopItemCreate(slug=" obiect ", name="  Nume  ", description="  Descriere  ", price=1)
    admin_reason = schemas.AdminReasonRequest(reason="  Motiv  ")
    email_campaign = schemas.AdminEmailCampaignCreate(subject="  Subiect  ", html_content="valid")

    assert post.title == title
    assert forum_thread.title == "Discuție"
    assert club.title == "Atelier"
    assert club_message.title == "Fir"
    assert club_message.content == "Mesaj"
    assert series.title == "Serie"
    assert series.description == "Descriere"
    assert theatre.title == "Piesă"
    assert theatre.characters[0].name == "Autor"
    assert theatre.characters[0].description == "Descriere"
    assert stafeta.title == "Ștafetă"
    assert shop_item.slug == "obiect"
    assert shop_item.name == "Nume"
    assert shop_item.description == "Descriere"
    assert admin_reason.reason == "Motiv"
    assert email_campaign.subject == "Subiect"


def test_diacritics_theatre_payload_trims_optional_text_before_empty_check():
    with pytest.raises(ValidationError):
        schemas.DiacriticsRequest(kind="theatre_play", title="   ")

    request = schemas.DiacriticsRequest(
        kind="theatre_play",
        title="  Piesa  ",
        description="  Descriere  ",
        characters=[{"index": 0, "description": "  Personaj  "}],
    )

    assert request.title == "Piesa"
    assert request.description == "Descriere"
    assert request.characters[0].description == "Personaj"


def test_diacritics_post_requests_use_selected_category_limit():
    schemas.DiacriticsRequest(
        kind="post",
        title="Titlu",
        category="poezie",
        content=f"<p>{'x' * 10000}</p>",
    )

    with pytest.raises(ValidationError):
        schemas.DiacriticsRequest(kind="post", title="Titlu", content="valid")

    with pytest.raises(ValidationError):
        schemas.DiacriticsRequest(
            kind="post",
            title="Titlu",
            category="poezie",
            content=f"<p>{'x' * 10001}</p>",
        )
