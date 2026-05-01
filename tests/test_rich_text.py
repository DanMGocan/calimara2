import pytest
from pydantic import ValidationError

from app import rich_text, schemas


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


def test_empty_quill_document_normalizes_to_blank_and_fails_required_schema():
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


def test_profile_subtitle_is_sanitized_and_limited_by_visible_text():
    setup = schemas.UserSetup(
        username="autor",
        avatar_seed="autor-shapes",
        subtitle='<p>Bio <strong onclick="bad()">scurt</strong></p>',
    )

    assert setup.subtitle == "<p>Bio <strong>scurt</strong></p>"
    assert schemas.UserProfileUpdate(subtitle=f"<p>{'x' * 1000}</p>").subtitle == f"<p>{'x' * 1000}</p>"

    with pytest.raises(ValidationError):
        schemas.UserProfileUpdate(subtitle=f"<p>{'x' * 1001}</p>")


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


def test_comment_and_title_limits_are_enforced():
    assert schemas.CommentCreate(content=f"<p>{'x' * 2500}</p>").content == f"<p>{'x' * 2500}</p>"

    with pytest.raises(ValidationError):
        schemas.CommentCreate(content=f"<p>{'x' * 2501}</p>")

    with pytest.raises(ValidationError):
        schemas.PostCreate(title="x" * 121, category="poezie", content="valid")

    with pytest.raises(ValidationError):
        schemas.ForumThreadCreate(section="general", title="x" * 121, content="valid")


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
