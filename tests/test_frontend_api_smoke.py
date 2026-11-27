import os
import base64
import re
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

from app import auth, crud, diacritics, models, object_storage, profile_media, schemas, statistics, stripe_service, text_formatting
from app.database import get_db
from app.main import app


ROOT = Path(__file__).resolve().parents[1]

SMOKE_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class SmokeData:
    user_id: int
    peer_id: int
    target_id: int
    invitee_id: int
    post_id: int
    peer_post_id: int
    pending_post_id: int
    draft_id: int
    comment_id: int
    conversation_id: int
    message_id: int
    notification_id: int
    pending_friendship_id: int
    series_id: int
    series_slug: str
    club_id: int
    club_slug: str
    club_request_id: int
    board_message_id: int
    theatre_play_id: int
    theatre_slug: str
    theatre_character_id: int
    theatre_scene_id: int
    theatre_request_id: int
    stafeta_work_id: int
    stafeta_slug: str
    stafeta_assignment_id: int
    forum_thread_id: int
    forum_thread_slug: str
    forum_reply_id: int
    shop_item_id: int
    unowned_shop_item_id: int
    super_liked_post_id: int
    audio_id: int
    audio_playlist_id: int
    moderation_log_id: int
    site_feedback_id: int


@dataclass(frozen=True)
class SmokeCase:
    name: str
    method: str
    path: Callable[[SmokeData], str]
    expected: Iterable[int]
    json: Callable[[SmokeData], dict] | None = None
    files: Callable[[SmokeData], dict] | None = None
    headers: dict | None = None


def _create_user(
    db: Session,
    username: str,
    *,
    is_admin: bool = False,
    is_moderator: bool = False,
    premium: bool = False,
    balance: int = 0,
) -> models.User:
    user = models.User(
        username=username,
        email=f"{username}@example.com",
        google_id=f"google-{username}",
        subtitle=f"{username} subtitle",
        avatar_seed=f"{username}-seed",
        is_admin=is_admin,
        is_moderator=is_moderator,
        premium_tier="rapsod" if premium else "free",
        premium_period_start=(
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        ) if premium else None,
        premium_until=(
            datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
        ) if premium else None,
        stripe_customer_id=f"cus_{username}" if premium else None,
        gologani_balance=balance,
    )
    db.add(user)
    db.add(models.PlatformAllowedEmail(email=user.email, note="smoke"))
    db.flush()
    return user


def _create_post(
    db: Session,
    owner: models.User,
    slug: str,
    *,
    category: str = "poezie",
    moderation_status: str = "approved",
) -> models.Post:
    post = models.Post(
        user_id=owner.id,
        title=slug.replace("-", " ").title(),
        slug=slug,
        content=f"Smoke content for {slug}",
        category=category,
        moderation_status=moderation_status,
    )
    db.add(post)
    db.flush()
    return post


def _seed_local_media(key: str) -> None:
    path = profile_media.local_path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SMOKE_PNG_BYTES)


def _seed_smoke_data(db: Session, audio_dir) -> SmokeData:
    user = _create_user(
        db,
        "smokeauthor",
        is_admin=True,
        is_moderator=True,
        premium=True,
        balance=500,
    )
    user.profile_photo_storage_backend = "local"
    user.profile_photo_storage_key = f"users/{user.id}/profil-smoke.webp"
    user.profile_photo_content_type = profile_media.PROFILE_MEDIA_CONTENT_TYPE
    user.profile_photo_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_local_media(user.profile_photo_storage_key)
    peer = _create_user(db, "smokereader", premium=True, balance=50)
    target = _create_user(db, "smoketarget")
    invitee = _create_user(db, "smokeinvitee")
    db.add(models.PlatformAllowedEmail(email="new-password-smoke@example.com", note="smoke"))

    post = _create_post(db, user, "smoke-poem", category="poezie")
    peer_post = _create_post(db, peer, "reader-story", category="proza_scurta")
    super_liked_post = _create_post(db, target, "target-poem", category="poezie")
    pending_post = _create_post(db, user, "pending-poem", moderation_status="pending")
    draft = models.PostDraft(
        user_id=user.id,
        title="Smoke Draft",
        content="<p>Draft smoke body</p>",
        category="proza_scurta",
    )
    db.add(draft)

    comment = models.Comment(
        post_id=post.id,
        user_id=peer.id,
        content="Approved smoke comment",
        approved=True,
        moderation_status="approved",
    )
    db.add(comment)

    conversation = models.Conversation(user1_id=user.id, user2_id=peer.id)
    db.add(conversation)
    db.flush()
    message = models.Message(
        conversation_id=conversation.id,
        sender_id=peer.id,
        content="Smoke message",
        is_read=False,
    )
    db.add(message)

    notification = models.Notification(
        user_id=user.id,
        type="smoke",
        title="Smoke notification",
        message="Verification notification",
        link="/panou",
    )
    db.add(notification)

    friendship_user1_id, friendship_user2_id = sorted([user.id, peer.id])
    pending_friendship = models.Friendship(
        user1_id=friendship_user1_id,
        user2_id=friendship_user2_id,
        requested_by_id=peer.id,
        status="pending",
    )
    db.add(pending_friendship)
    accepted_user1_id, accepted_user2_id = sorted([user.id, target.id])
    db.add(
        models.Friendship(
            user1_id=accepted_user1_id,
            user2_id=accepted_user2_id,
            requested_by_id=user.id,
            status="accepted",
            responded_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.add_all(
        [
            models.UserFollow(follower_id=peer.id, followed_id=user.id),
            models.UserFollow(follower_id=user.id, followed_id=target.id),
        ]
    )

    series = models.Series(
        owner_id=user.id,
        title="Smoke Series",
        slug="smoke-series",
        description="Smoke series description",
    )
    db.add(series)
    db.flush()
    db.add(
        models.SeriesPost(
            series_id=series.id,
            post_id=post.id,
            position=1,
        )
    )

    club = models.Club(
        owner_id=user.id,
        title="Smoke Club",
        slug="smoke-club",
        description="Smoke club description",
        speciality="poezie",
        featured_post_id=post.id,
        featured_until=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7),
    )
    db.add(club)
    db.flush()
    club.profile_photo_storage_backend = "local"
    club.profile_photo_storage_key = f"clubs/{club.id}/profil-smoke.webp"
    club.profile_photo_content_type = profile_media.PROFILE_MEDIA_CONTENT_TYPE
    club.profile_photo_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_local_media(club.profile_photo_storage_key)
    db.add_all(
        [
            models.ClubMember(club_id=club.id, user_id=user.id, role="owner"),
            models.ClubMember(club_id=club.id, user_id=peer.id, role="member"),
        ]
    )
    club_request = models.ClubJoinRequest(
        club_id=club.id,
        user_id=target.id,
        direction="application",
        status="pending",
        initiator_id=target.id,
    )
    db.add(club_request)
    board_message = models.ClubBoardMessage(
        club_id=club.id,
        author_id=user.id,
        content="Smoke board message",
    )
    db.add(board_message)

    theatre_play = models.TheatrePlay(
        creator_id=user.id,
        title="Smoke Theatre Play",
        slug="smoke-theatre-play",
        description="Smoke theatre description",
        status="active",
    )
    db.add(theatre_play)
    db.flush()
    theatre_character = models.TheatreCharacter(
        play_id=theatre_play.id,
        name="Narator",
        description="Smoke narrator",
        status="approved",
        approved_by=user.id,
        approved_at=datetime.now(timezone.utc).replace(tzinfo=None),
        assigned_user_id=user.id,
    )
    db.add(theatre_character)
    db.flush()
    theatre_scene = models.TheatreScene(
        play_id=theatre_play.id,
        scene_number=1,
        title="Smoke Scene",
        opened_by=user.id,
    )
    db.add(theatre_scene)
    db.flush()
    theatre_play.current_scene_id = theatre_scene.id
    theatre_play.current_character_id = theatre_character.id
    theatre_play.current_actor_user_id = user.id
    db.add_all(
        [
            models.TheatreMember(play_id=theatre_play.id, user_id=user.id, role="creator"),
            models.TheatreEntry(
                play_id=theatre_play.id,
                scene_id=theatre_scene.id,
                author_id=user.id,
                character_id=theatre_character.id,
                entry_type="line",
                content="<p>Smoke theatre line</p>",
                position=1,
                moderation_status="approved",
            ),
        ]
    )
    theatre_request = models.TheatreJoinRequest(
        play_id=theatre_play.id,
        user_id=target.id,
        direction="application",
        status="pending",
        initiator_id=target.id,
    )
    db.add(theatre_request)

    db.add(models.StafetaParticipant(user_id=peer.id, is_active=True, desired_slots=3))
    stafeta_work = models.StafetaWork(
        creator_id=user.id,
        title="Smoke Stafeta",
        slug="smoke-stafeta",
        category="poezie",
        status="active",
        deadline_days=1,
        max_characters=400,
        current_holder_user_id=user.id,
    )
    db.add(stafeta_work)
    db.flush()
    stafeta_assignment = models.StafetaAssignment(
        work_id=stafeta_work.id,
        user_id=user.id,
        assigned_by_id=user.id,
        source="creator",
        status="active",
        due_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
    )
    db.add(stafeta_assignment)
    db.flush()
    stafeta_work.current_assignment_id = stafeta_assignment.id
    db.add(
        models.StafetaSegment(
            work_id=stafeta_work.id,
            assignment_id=stafeta_assignment.id,
            author_id=user.id,
            content="<p>Smoke stafeta start</p>",
            position=1,
            next_target_mode="random",
            moderation_status="approved",
        )
    )

    forum_thread = models.ForumThread(
        author_id=user.id,
        section="general",
        title="Smoke Forum Thread",
        slug="smoke-forum-thread",
        content="Smoke forum content",
        moderation_status="approved",
    )
    db.add(forum_thread)
    db.flush()
    forum_reply = models.ForumReply(
        thread_id=forum_thread.id,
        author_id=peer.id,
        content="Smoke forum reply",
        moderation_status="approved",
    )
    db.add(forum_reply)

    owned_item = models.ShopItem(
        slug="smoke-owned-item",
        name="Smoke Owned Item",
        description="Owned smoke item",
        price=10,
        slot="profile_badge",
        sort_order=1,
    )
    unowned_item = models.ShopItem(
        slug="smoke-unowned-item",
        name="Smoke Unowned Item",
        description="Unowned smoke item",
        price=25,
        slot="costume",
        sort_order=2,
    )
    db.add_all([owned_item, unowned_item])
    db.flush()
    db.add(models.UserInventoryItem(user_id=user.id, item_id=owned_item.id))
    db.add(
        models.UserEquippedItem(
            user_id=user.id,
            item_id=owned_item.id,
            slot=owned_item.slot,
        )
    )
    db.add(models.Like(user_id=user.id, post_id=super_liked_post.id))
    db.add(models.SuperLike(user_id=user.id, post_id=super_liked_post.id))
    db.add(models.CommentReaction(user_id=user.id, comment_id=comment.id, reaction_type="funny"))

    storage_key = "smoke/audio.mp3"
    audio_path = audio_dir / storage_key
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"ID3 smoke audio")
    audio = models.PostAudio(
        post_id=post.id,
        source="tts",
        status="ready",
        storage_backend="local",
        storage_key=storage_key,
        content_type="audio/mpeg",
        byte_size=15,
    )
    db.add(audio)
    audio_playlist = models.AudioPlaylist(
        owner_id=user.id,
        title="Smoke playlist",
    )
    db.add(audio_playlist)
    db.flush()
    db.add(
        models.AudioPlaylistItem(
            playlist_id=audio_playlist.id,
            post_id=post.id,
            position=1,
        )
    )

    moderation_log = models.ModerationLog(
        content_type="comment",
        content_id=comment.id,
        user_id=peer.id,
        ai_decision="flagged",
        toxicity_score=0.75,
        harassment_score=0.10,
        hate_speech_score=0.10,
        sexually_explicit_score=0.00,
        dangerous_content_score=0.00,
        romanian_profanity_score=0.10,
        ai_reason="smoke review",
        human_decision="pending",
    )
    db.add(moderation_log)
    site_feedback = models.SiteFeedback(
        kind="feedback",
        user_id=user.id,
        username_snapshot=user.username,
        email_snapshot=user.email,
        message="Smoke feedback",
        page_url="https://calimara.test/smoke",
        client_context={"viewport": "1200x800"},
        status="open",
    )
    db.add(site_feedback)

    db.commit()
    for item in (
        user,
        peer,
        target,
        invitee,
        post,
        peer_post,
        super_liked_post,
        pending_post,
        draft,
        comment,
        conversation,
        message,
        notification,
        series,
        club,
        club_request,
        board_message,
        theatre_play,
        theatre_character,
        theatre_scene,
        theatre_request,
        stafeta_work,
        stafeta_assignment,
        forum_thread,
        forum_reply,
        owned_item,
        unowned_item,
        audio,
        audio_playlist,
        moderation_log,
        site_feedback,
    ):
        db.refresh(item)

    return SmokeData(
        user_id=user.id,
        peer_id=peer.id,
        target_id=target.id,
        invitee_id=invitee.id,
        post_id=post.id,
        peer_post_id=peer_post.id,
        pending_post_id=pending_post.id,
        draft_id=draft.id,
        comment_id=comment.id,
        conversation_id=conversation.id,
        message_id=message.id,
        notification_id=notification.id,
        pending_friendship_id=pending_friendship.id,
        series_id=series.id,
        series_slug=series.slug,
        club_id=club.id,
        club_slug=club.slug,
        club_request_id=club_request.id,
        board_message_id=board_message.id,
        theatre_play_id=theatre_play.id,
        theatre_slug=theatre_play.slug,
        theatre_character_id=theatre_character.id,
        theatre_scene_id=theatre_scene.id,
        theatre_request_id=theatre_request.id,
        stafeta_work_id=stafeta_work.id,
        stafeta_slug=stafeta_work.slug,
        stafeta_assignment_id=stafeta_assignment.id,
        forum_thread_id=forum_thread.id,
        forum_thread_slug=forum_thread.slug,
        forum_reply_id=forum_reply.id,
        shop_item_id=owned_item.id,
        unowned_shop_item_id=unowned_item.id,
        super_liked_post_id=super_liked_post.id,
        audio_id=audio.id,
        audio_playlist_id=audio_playlist.id,
        moderation_log_id=moderation_log.id,
        site_feedback_id=site_feedback.id,
    )


@pytest.fixture
def smoke_client(monkeypatch, tmp_path):
    audio_dir = tmp_path / "audio"
    monkeypatch.setenv("AUDIO_STORAGE_BACKEND", "local")
    monkeypatch.setenv("AUDIO_LOCAL_DIR", str(audio_dir))
    monkeypatch.setenv("PROFILE_MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("PROFILE_MEDIA_LOCAL_DIR", str(tmp_path / "profile-media"))
    monkeypatch.setattr(statistics, "STATS_ENABLED", False)
    monkeypatch.setattr(
        stripe_service,
        "create_or_get_customer",
        lambda **kwargs: kwargs.get("existing_customer_id") or "cus_smoke",
    )
    monkeypatch.setattr(
        stripe_service,
        "create_checkout_session",
        lambda **kwargs: "https://stripe.test/checkout",
    )
    monkeypatch.setattr(
        stripe_service,
        "create_billing_portal_session",
        lambda customer_id: "https://stripe.test/portal",
    )
    monkeypatch.setattr(
        stripe_service,
        "create_coffee_checkout_session",
        lambda **kwargs: "https://stripe.test/coffee",
    )
    monkeypatch.setattr(
        stripe_service,
        "coffee_offer",
        lambda: {"available": True, "price": "12,00 lei", "unit_amount": 1200, "currency": "ron", "max_quantity": 20},
    )
    monkeypatch.setattr(
        stripe_service,
        "list_premium_plans",
        lambda: [
            {
                "key": "trubadur",
                "name": "Trubadur",
                "eyebrow": "Bronz",
                "price": "3,99 €",
                "cadence": "/ lună",
                "summary": "Smoke premium plan",
                "benefits": ["Smoke benefit"],
                "available": True,
            }
        ],
    )
    monkeypatch.setattr(
        object_storage,
        "list_objects",
        lambda **_kwargs: {
            "objects": [
                {
                    "Key": "posts/smoke-admin-object.txt",
                    "Size": 5,
                    "LastModified": datetime.now(timezone.utc),
                    "ETag": "smoke",
                }
            ],
            "next_cursor": None,
            "is_truncated": False,
        },
    )
    monkeypatch.setattr(object_storage, "presigned_get_url", lambda key, **_kwargs: f"https://storage.test/{key}")
    monkeypatch.setattr(object_storage, "signed_url_ttl_seconds", lambda: 600)
    monkeypatch.setattr(object_storage, "head_object_metadata", lambda _key: {"ContentLength": 5})
    monkeypatch.setattr(object_storage, "delete_object", lambda _key: None)
    monkeypatch.setattr(
        diacritics,
        "add_diacritics",
        lambda **kwargs: {
            "title": "Orașul" if kwargs.get("title") is not None else None,
            "content": "Șapte țări",
            "changed": True,
        },
    )
    monkeypatch.setattr(text_formatting, "validate_post_formatting_context", lambda **_kwargs: None)
    monkeypatch.setattr(
        text_formatting,
        "format_post_content",
        lambda **kwargs: {
            "category": "poezie",
            "content": "<p>vers unu<br>vers doi</p>",
            "changed": kwargs.get("category") != "poezie",
        },
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    models.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    data = _seed_smoke_data(db, audio_dir)

    def override_get_db():
        yield db

    def override_current_user() -> models.User:
        user = db.get(models.User, data.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user

    def override_required_user(
        current_user: models.User = Depends(override_current_user),
    ) -> models.User:
        return current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[auth.get_current_user] = override_current_user
    app.dependency_overrides[auth.get_required_user] = override_required_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, data

    app.dependency_overrides.clear()
    db.close()
    models.Base.metadata.drop_all(engine)
    engine.dispose()


def _path(value: str) -> Callable[[SmokeData], str]:
    return lambda _data: value


def _json(value: dict) -> Callable[[SmokeData], dict]:
    return lambda _data: value


SMOKE_CASES = [
    SmokeCase("fetchMe", "GET", _path("/api/utilizator/eu"), {200}),
    SmokeCase("updateMe", "PUT", _path("/api/utilizator/eu"), {200}, _json({"subtitle": "Updated smoke profile", "avatar_seed": "updated-seed"})),
    SmokeCase("updateProfileSettings", "PUT", _path("/api/utilizator/profil"), {200}, _json({
        "cover_seed": "smokeauthor-cover-stars",
        "location": "București",
        "youtube_playlist_url": "https://www.youtube.com/playlist?list=PLsmoke123",
        "paypal_url": "https://paypal.me/smokeauthor",
        "patreon_url": "https://patreon.com/smokeauthor",
        "instagram_url": "https://instagram.com/smokeauthor",
    })),
    SmokeCase("updateSocialLinks", "PUT", _path("/api/utilizator/linkuri-sociale"), {200}, _json({"instagram_url": "https://instagram.com/smokeauthor", "paypal_url": "https://paypal.me/smokeauthor"})),
    SmokeCase("fetchEmailPreferences", "GET", _path("/api/utilizator/email-preferinte"), {200}),
    SmokeCase("updateEmailPreferences", "PUT", _path("/api/utilizator/email-preferinte"), {200}, _json({
        "email_comment_notifications": False,
        "email_mention_notifications": True,
        "email_analytics_digest": False,
        "email_admin_announcements": True,
    })),
    SmokeCase("updatePassword", "PUT", _path("/api/utilizator/parola"), {400}, _json({"current_password": "wrong", "new_password": "new-long-password"})),
    SmokeCase("uploadProfileMedia", "POST", _path("/api/utilizator/media/profil"), {200}, files=lambda _data: {"file": ("profile.png", SMOKE_PNG_BYTES, "image/png")}),
    SmokeCase("uploadCoverMedia", "POST", _path("/api/utilizator/media/coperta"), {200}, files=lambda _data: {"file": ("cover.png", SMOKE_PNG_BYTES, "image/png")}),
    SmokeCase("deleteProfileMedia", "DELETE", _path("/api/utilizator/media/profil"), {200}),
    SmokeCase("updateLegacyPromotedAuthors", "PUT", _path("/api/utilizator/prieteni-apropiati"), {200}, _json({"friends": ["smokereader"]})),
    SmokeCase("searchUsers", "GET", _path("/api/utilizatori/cauta?q=smoke"), {200}),
    SmokeCase("fetchUsersDirectory", "GET", _path("/api/utilizatori?sort=newest&relationship=all"), {200}),
    SmokeCase("fetchFriendsState", "GET", _path("/api/prieteni"), {200}),
    SmokeCase("fetchFriendshipStatus", "GET", lambda data: f"/api/prieteni/status/{data.peer_id}", {200}),
    SmokeCase("sendFriendRequest", "POST", lambda data: f"/api/prieteni/cereri/{data.peer_id}", {200}, _json({})),
    SmokeCase("acceptFriendRequest", "POST", lambda data: f"/api/prieteni/cereri/{data.pending_friendship_id}/accepta", {200}, _json({})),
    SmokeCase("deleteFriendRequest", "DELETE", lambda data: f"/api/prieteni/cereri/{data.pending_friendship_id}", {200}),
    SmokeCase("removeFriend", "DELETE", lambda data: f"/api/prieteni/{data.target_id}", {200}),
    SmokeCase("fetchFollowStatus", "GET", lambda data: f"/api/urmariri/status/{data.peer_id}", {200}),
    SmokeCase("followUser", "POST", lambda data: f"/api/urmariri/{data.peer_id}", {200}, _json({})),
    SmokeCase("unfollowUser", "DELETE", lambda data: f"/api/urmariri/{data.peer_id}", {200}),
    SmokeCase("fetchFollowers", "GET", _path("/api/utilizatori/smokeauthor/urmaritori"), {200}),
    SmokeCase("fetchFollowing", "GET", _path("/api/utilizatori/smokeauthor/urmariti"), {200}),
    SmokeCase("fetchPromotions", "GET", _path("/api/utilizator/promovari"), {200}),
    SmokeCase("searchPromotions", "GET", _path("/api/utilizator/promovari/cauta?q=smoke"), {200}),
    SmokeCase("updatePromotions", "PUT", _path("/api/utilizator/promovari"), {200}, lambda data: {
        "own_post_ids": [data.post_id],
        "author_ids": [data.peer_id],
        "other_post_ids": [data.peer_post_id],
    }),
    SmokeCase("promoteAuthor", "POST", lambda data: f"/api/utilizator/promovari/autori/{data.target_id}", {200}),
    SmokeCase("unpromoteAuthor", "DELETE", lambda data: f"/api/utilizator/promovari/autori/{data.target_id}", {200}),
    SmokeCase("promotePost", "POST", lambda data: f"/api/utilizator/promovari/postari/{data.peer_post_id}", {200}),
    SmokeCase("unpromotePost", "DELETE", lambda data: f"/api/utilizator/promovari/postari/{data.peer_post_id}", {200}),
    SmokeCase("fetchPublicProfile", "GET", _path("/api/utilizator/smokeauthor/profil"), {200}),
    SmokeCase("fetchPublicProfileMedia", "GET", _path("/api/utilizatori/smokeauthor/media/profil"), {200}),
    SmokeCase("fetchDataExport", "GET", _path("/api/portabilitate/export"), {200}),
    SmokeCase("importDataExport", "POST", _path("/api/portabilitate/import"), {200}, _json({
        "format": "calimara-user-export",
        "version": 1,
        "export_id": "smoke-import-export",
        "exported_at": "2026-05-21T00:00:00Z",
        "source_username": "smokeauthor",
        "profile": {"location": "Smoke import"},
        "media": {},
        "posts": [{
            "stable_id": "post:smokeauthor:imported-smoke:2026-05-21T00:00:00",
            "source_id": 999001,
            "title": "Imported smoke",
            "slug": "imported-smoke",
            "content": "<p>Imported smoke content.</p>",
            "category": "poezie",
            "created_at": "2026-05-21T00:00:00",
            "updated_at": "2026-05-21T00:00:00",
            "metrics": {"view_count": 3, "likes_count": 2, "super_likes_count": 1}
        }],
    })),
    SmokeCase("updateFeaturedPosts", "PUT", _path("/api/utilizator/postari-recomandate"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchLanding", "GET", _path("/api/prima-pagina?category=toate"), {200}),
    SmokeCase("fetchLegacyLandingAlias", "GET", _path("/api/landing?category=toate"), {200}),
    SmokeCase("fetchBlog", "GET", _path("/api/bloguri/smokeauthor"), {200}),
    SmokeCase("fetchAllWorks", "GET", _path("/api/bloguri/smokeauthor/toate-operele"), {200}),
    SmokeCase("fetchPostDetail", "GET", _path("/api/bloguri/smokeauthor/postari/smoke-poem"), {200}),
    SmokeCase("fetchPostPdf", "GET", _path("/api/bloguri/smokeauthor/postari/smoke-poem/pdf"), {200}),
    SmokeCase("fetchPublicInventory", "GET", _path("/api/utilizator/smokeauthor/inventar"), {200}),
    SmokeCase("fetchPostAudioStatus", "GET", lambda data: f"/api/audio/postari/{data.post_id}", {200}),
    SmokeCase("fetchRandomUser", "GET", _path("/api/utilizatori/aleatoriu"), {200}),
    SmokeCase("fetchClubs", "GET", _path("/api/cluburi?limit=50"), {200}),
    SmokeCase("fetchRandomClub", "GET", _path("/api/cluburi/aleatoriu"), {200}),
    SmokeCase("fetchClub", "GET", _path("/api/cluburi/smoke-club"), {200}),
    SmokeCase("fetchPublicClubMedia", "GET", _path("/api/cluburi/smoke-club/media/profil"), {200}),
    SmokeCase("fetchArchive", "GET", _path("/api/postari/arhiva"), {200}),
    SmokeCase("fetchOwnedPostForEdit", "GET", lambda data: f"/api/postari/{data.post_id}/editare", {200}),
    SmokeCase("fetchPostDrafts", "GET", _path("/api/postari/ciorne"), {200}),
    SmokeCase("fetchPostDraft", "GET", lambda data: f"/api/postari/ciorne/{data.draft_id}", {200}),
    SmokeCase("createPostDraft", "POST", _path("/api/postari/ciorne"), {201}, _json({"title": "Smoke Draft New", "content": "<p>Draft body</p>", "category": "poezie"})),
    SmokeCase("updatePostDraft", "PUT", lambda data: f"/api/postari/ciorne/{data.draft_id}", {200}, _json({"title": "Smoke Draft Updated", "content": "<p>Updated draft body</p>", "category": "proza_scurta"})),
    SmokeCase("deletePostDraft", "DELETE", lambda data: f"/api/postari/ciorne/{data.draft_id}", {204}),
    SmokeCase("fetchPostMonths", "GET", _path("/api/postari/luni"), {200}),
    SmokeCase("fetchRandomPosts", "GET", _path("/api/postari/aleatoriu?category=poezie"), {200}),
    SmokeCase("createPost", "POST", _path("/api/postari/"), {200}, _json({"title": "Smoke Created Post", "content": "Created smoke body", "category": "proza_scurta", "ai_critic": False})),
    SmokeCase("fetchDiacriticsQuota", "GET", _path("/api/scriere/diacritice/cota"), {200}),
    SmokeCase("addDiacritics", "POST", _path("/api/scriere/diacritice"), {200}, _json({"kind": "forum_thread", "title": "Orasul", "content": "Sapte tari"})),
    SmokeCase("addPrivateMessageDiacritics", "POST", _path("/api/scriere/diacritice"), {200}, _json({"kind": "private_message", "content": "Mesaj fara diacritice"})),
    SmokeCase("formatPostWithAi", "POST", _path("/api/scriere/formatare-ai"), {200}, _json({"category": "proza_scurta", "content": "<p>vers unu<br>vers doi</p>"})),
    SmokeCase("updatePost", "PUT", lambda data: f"/api/postari/{data.post_id}", {200}, _json({"title": "Smoke Poem Updated", "content": "Updated smoke body", "category": "poezie"})),
    SmokeCase("deletePost", "DELETE", _path("/api/postari/999999"), {404}),
    SmokeCase("createComment", "POST", lambda data: f"/api/postari/{data.post_id}/comentarii", {200}, _json({"content": "Smoke authenticated comment"})),
    SmokeCase("reportPost", "POST", lambda data: f"/api/postari/{data.peer_post_id}/raportari", {201}, _json({"reason_type": "offensive", "details": "Smoke report"})),
    SmokeCase("approveComment", "PUT", lambda data: f"/api/comentarii/{data.comment_id}/aproba", {200}, _json({})),
    SmokeCase("reactToComment", "POST", lambda data: f"/api/comentarii/{data.comment_id}/reactii", {200}, _json({"reaction_type": "helpful"})),
    SmokeCase("removeCommentReaction", "DELETE", lambda data: f"/api/comentarii/{data.comment_id}/reactii", {200}),
    SmokeCase("deleteComment", "DELETE", lambda data: f"/api/comentarii/{data.comment_id}", {204}),
    SmokeCase("likePost", "POST", lambda data: f"/api/postari/{data.peer_post_id}/aprecieri", {200}, _json({})),
    SmokeCase("removeLike", "DELETE", lambda data: f"/api/postari/{data.super_liked_post_id}/aprecieri", {204}),
    SmokeCase("fetchLikeCount", "GET", lambda data: f"/api/postari/{data.post_id}/aprecieri/numar", {200}),
    SmokeCase("fetchConversations", "GET", _path("/api/mesaje/conversatii"), {200}),
    SmokeCase("fetchConversation", "GET", lambda data: f"/api/mesaje/conversatii/{data.conversation_id}", {200}),
    SmokeCase("sendConversationMessage", "POST", lambda data: f"/api/mesaje/conversatii/{data.conversation_id}", {200}, _json({"content": "Smoke reply"})),
    SmokeCase("sendMessage", "POST", _path("/api/mesaje/trimite"), {200}, _json({"username": "smokereader", "content": "Smoke direct message"})),
    SmokeCase("reportMessage", "POST", lambda data: f"/api/mesaje/{data.message_id}/raportari", {201}, _json({"reason_type": "offensive", "details": "Smoke message report"})),
    SmokeCase("fetchUnreadMessageCount", "GET", _path("/api/mesaje/necitite"), {200}),
    SmokeCase("deleteConversation", "DELETE", _path("/api/mesaje/conversatii/999999"), {404}),
    SmokeCase("searchConversations", "GET", _path("/api/mesaje/cauta?q=smoke"), {200}),
    SmokeCase("fetchNotifications", "GET", _path("/api/notificari"), {200}),
    SmokeCase("fetchUnreadNotificationCount", "GET", _path("/api/notificari/necitite"), {200}),
    SmokeCase("markNotificationRead", "PUT", lambda data: f"/api/notificari/{data.notification_id}/citita", {200}, _json({})),
    SmokeCase("markNotificationUnread", "PUT", lambda data: f"/api/notificari/{data.notification_id}/necitita", {200}, _json({})),
    SmokeCase("markAllNotificationsRead", "PUT", _path("/api/notificari/citeste-toate"), {200}, _json({})),
    SmokeCase("deleteNotification", "DELETE", lambda data: f"/api/notificari/{data.notification_id}", {200}),
    SmokeCase("fetchPlatformStats", "GET", _path("/api/statistici/platforma"), {200}),
    SmokeCase("fetchPostStats", "GET", lambda data: f"/api/statistici/postare/{data.post_id}", {200}),
    SmokeCase("fetchAuthorStats", "GET", _path("/api/statistici/autor/smokeauthor"), {200}),
    SmokeCase("fetchCategoryStats", "GET", _path("/api/statistici/categorie/poezie"), {200}),
    SmokeCase("fetchAdminOnlyOverviewStats", "GET", _path("/api/statistici/ansamblu"), {200}),
    SmokeCase("fetchMyStats", "GET", _path("/api/statistici/ale-mele"), {200}),
    SmokeCase("createSeries", "POST", _path("/api/serii/"), {201}, _json({"title": "Created Series", "description": "Created through smoke"})),
    SmokeCase("fetchRandomSeries", "GET", _path("/api/serii/aleatoriu"), {200}),
    SmokeCase("fetchSeries", "GET", _path("/api/serii/smoke-series"), {200}),
    SmokeCase("fetchSeriesPdf", "GET", _path("/api/serii/smoke-series/pdf"), {200}),
    SmokeCase("fetchUserSeries", "GET", _path("/api/utilizatori/smokeauthor/serii"), {200}),
    SmokeCase("updateSeries", "PUT", lambda data: f"/api/serii/{data.series_id}", {200}, _json({"title": "Updated Smoke Series"})),
    SmokeCase("deleteSeries", "DELETE", _path("/api/serii/999999"), {404}),
    SmokeCase("addPostToSeries", "POST", lambda data: f"/api/serii/{data.series_id}/postari", {403}, lambda data: {"post_id": data.peer_post_id}),
    SmokeCase("reorderSeriesPosts", "PUT", lambda data: f"/api/serii/{data.series_id}/postari/ordine", {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("removePostFromSeries", "DELETE", lambda data: f"/api/serii/{data.series_id}/postari/999999", {404}),
    SmokeCase("fetchMySeries", "GET", _path("/api/utilizator/serii"), {200}),
    SmokeCase("fetchManagedSeries", "GET", lambda data: f"/api/utilizator/serii/{data.series_id}/gestioneaza", {200}),
    SmokeCase("fetchPostSeries", "GET", lambda data: f"/api/postari/{data.post_id}/serie", {200}),
    SmokeCase("fetchForumThreads", "GET", _path("/api/forum/discutii?section=general"), {200}),
    SmokeCase("fetchForumSections", "GET", _path("/api/forum/sectiuni"), {200}),
    SmokeCase("fetchForumThread", "GET", _path("/api/forum/discutii/smoke-forum-thread"), {200}),
    SmokeCase("createForumThread", "POST", _path("/api/forum/discutii"), {201}, _json({"section": "general", "title": "Created Smoke Thread", "content": "Created smoke thread body"})),
    SmokeCase("createForumReply", "POST", lambda data: f"/api/forum/discutii/{data.forum_thread_id}/raspunsuri", {201}, _json({"content": "Created smoke reply"})),
    SmokeCase("reportForumThread", "POST", lambda data: f"/api/forum/discutii/{data.forum_thread_id}/raportari", {201}, _json({"reason_type": "offensive", "details": "Smoke forum thread report"})),
    SmokeCase("reportForumReply", "POST", lambda data: f"/api/forum/raspunsuri/{data.forum_reply_id}/raportari", {201}, _json({"reason_type": "plagiarism", "evidence_url": "https://example.com/forum"})),
    SmokeCase("deleteForumThread", "DELETE", _path("/api/forum/discutii/999999"), {404}),
    SmokeCase("deleteForumReply", "DELETE", _path("/api/forum/raspunsuri/999999"), {404}),
    SmokeCase("updateForumThreadState", "POST", lambda data: f"/api/forum/discutii/{data.forum_thread_id}/stare", {200}, _json({"action": "lock"})),
    SmokeCase("updateForumReplyState", "POST", lambda data: f"/api/forum/raspunsuri/{data.forum_reply_id}/stare", {200}, _json({"action": "pin"})),
    SmokeCase("fetchAdminForumSections", "GET", _path("/api/admin/forum/sectiuni"), {200}),
    SmokeCase("createAdminForumSection", "POST", _path("/api/admin/forum/sectiuni"), {201}, _json({"name": "Atelier de smoke", "description": "Secțiune creată de smoke test"})),
    SmokeCase("reorderAdminForumSections", "POST", _path("/api/admin/forum/sectiuni/ordine"), {200}, _json({"section_ids": [999999]})),
    SmokeCase("updateAdminForumSection", "PUT", _path("/api/admin/forum/sectiuni/999999"), {404}, _json({"name": "Lipsă"})),
    SmokeCase("deleteAdminForumSection", "DELETE", _path("/api/admin/forum/sectiuni/999999"), {404}),
    SmokeCase("fetchAdminForumThreads", "GET", _path("/api/admin/forum/discutii?status=approved"), {200}),
    SmokeCase("bulkAdminForumThreads", "POST", _path("/api/admin/forum/discutii/actiuni"), {200}, _json({"thread_ids": [999999], "action": "unpin"})),
    SmokeCase("createClub", "POST", _path("/api/cluburi/"), {409}, _json({"title": "Created Smoke Club", "speciality": "poezie", "description": "Created club"})),
    SmokeCase("updateClub", "PUT", lambda data: f"/api/cluburi/{data.club_id}", {200}, _json({"title": "Updated Smoke Club", "speciality": "poezie"})),
    SmokeCase("deleteClub", "DELETE", _path("/api/cluburi/999999"), {404}),
    SmokeCase("applyToClub", "POST", lambda data: f"/api/cluburi/{data.club_id}/inscriere", {409}, _json({})),
    SmokeCase("inviteToClub", "POST", lambda data: f"/api/cluburi/{data.club_id}/invita", {200}, _json({"username": "smokeinvitee"})),
    SmokeCase("fetchClubRequests", "GET", lambda data: f"/api/cluburi/{data.club_id}/cereri", {200}),
    SmokeCase("respondClubRequest", "POST", lambda data: f"/api/cluburi/{data.club_id}/cereri/{data.club_request_id}/raspunde", {200}, _json({"action": "approve"})),
    SmokeCase("removeClubMember", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/membri/{data.peer_id}", {204}),
    SmokeCase("updateClubMemberRole", "PUT", lambda data: f"/api/cluburi/{data.club_id}/membri/{data.peer_id}/rol", {200}, _json({"role": "admin"})),
    SmokeCase("fetchMyClubs", "GET", _path("/api/utilizator/cluburi"), {200}),
    SmokeCase("fetchMyClubInvitations", "GET", _path("/api/utilizator/cluburi/in-asteptare"), {200}),
    SmokeCase("fetchClubBoard", "GET", lambda data: f"/api/cluburi/{data.club_id}/tabla", {200}),
    SmokeCase("createClubBoardMessage", "POST", lambda data: f"/api/cluburi/{data.club_id}/tabla", {201}, _json({"title": "Created board thread", "content": "Created board message"})),
    SmokeCase("deleteClubBoardMessage", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/tabla/{data.board_message_id}", {204}),
    SmokeCase("uploadClubMedia", "POST", lambda data: f"/api/cluburi/{data.club_id}/media/profil", {200}, files=lambda _data: {"file": ("club.png", SMOKE_PNG_BYTES, "image/png")}),
    SmokeCase("deleteClubMedia", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/media/profil", {200}),
    SmokeCase("setClubFeatured", "POST", lambda data: f"/api/cluburi/{data.club_id}/creatia-saptamanii", {200}, lambda data: {"post_id": data.post_id}),
    SmokeCase("clearClubFeatured", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/creatia-saptamanii", {204}),
    SmokeCase("fetchTheatrePlays", "GET", _path("/api/teatru"), {200}),
    SmokeCase("createTheatrePlay", "POST", _path("/api/teatru"), {201}, _json({"title": "Created Smoke Theatre", "description": "Created theatre smoke"})),
    SmokeCase("fetchTheatrePlay", "GET", lambda data: f"/api/teatru/{data.theatre_slug}", {200}),
    SmokeCase("fetchTheatrePdf", "GET", lambda data: f"/api/teatru/{data.theatre_slug}/pdf", {200}),
    SmokeCase("updateTheatrePlay", "PUT", lambda data: f"/api/teatru/{data.theatre_play_id}", {200}, _json({"title": "Updated Smoke Theatre"})),
    SmokeCase("deleteTheatrePlay", "DELETE", _path("/api/teatru/999999"), {404}),
    SmokeCase("deleteTheatreMissing", "DELETE", _path("/api/teatru/999999"), {404}),
    SmokeCase("applyToTheatrePlay", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/cereri", {400, 403, 409}, _json({"note": "smoke apply"})),
    SmokeCase("inviteToTheatrePlay", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/invita", {200}, _json({"username": "smokeinvitee"})),
    SmokeCase("fetchTheatreRequests", "GET", lambda data: f"/api/teatru/{data.theatre_play_id}/cereri", {200}),
    SmokeCase("respondTheatreRequest", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/cereri/{data.theatre_request_id}/raspunde", {200}, _json({"action": "approve"})),
    SmokeCase("createTheatreCharacter", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/personaje", {200, 201}, _json({"name": "Smoke Extra", "description": "extra character"})),
    SmokeCase("deleteTheatreCharacter", "DELETE", lambda data: f"/api/teatru/{data.theatre_play_id}/personaje/999999", {404}),
    SmokeCase("reviewTheatreCharacter", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/personaje/999999/raspunde", {404}, _json({"action": "approve"})),
    SmokeCase("assignTheatreCharacter", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/personaje/{data.theatre_character_id}/atribuie", {200}, _json({"username": "smokeauthor"})),
    SmokeCase("startTheatreScene", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/scene", {201, 400, 409}, lambda data: {"title": "Smoke New Scene", "first_character_id": data.theatre_character_id, "content": "<p>Opening</p>"}),
    SmokeCase("createTheatreReply", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/scene/{data.theatre_scene_id}/replici", {201}, lambda data: {"content": "<p>Reply</p>", "next_character_id": data.theatre_character_id}),
    SmokeCase("createTheatreStageDirection", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/scene/{data.theatre_scene_id}/indicatii", {201}, _json({"content": "<p>Stage direction</p>"})),
    SmokeCase("overrideTheatreTurn", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/rand", {200}, lambda data: {"character_id": data.theatre_character_id}),
    SmokeCase("endTheatreScene", "POST", lambda data: f"/api/teatru/{data.theatre_play_id}/scene/{data.theatre_scene_id}/incheie", {200}, _json({"note": "smoke end"})),
    SmokeCase("fetchMyTheatrePlays", "GET", _path("/api/utilizator/teatru"), {200}),
    SmokeCase("fetchMyTheatreInvitations", "GET", _path("/api/utilizator/teatru/in-asteptare"), {200}),
    SmokeCase("fetchStafetaWorks", "GET", _path("/api/stafeta"), {200}),
    SmokeCase("fetchStafetaParticipation", "GET", _path("/api/stafeta/participare"), {200}),
    SmokeCase("updateStafetaParticipation", "PUT", _path("/api/stafeta/participare"), {200}, _json({"participates": True, "desired_slots": 3})),
    SmokeCase("createStafetaWork", "POST", _path("/api/stafeta"), {201}, _json({"title": "Created Smoke Stafeta", "category": "poezie", "initial_content": "<p>Start</p>", "first_target_mode": "specific", "assigned_username": "smokereader"})),
    SmokeCase("fetchStafetaWork", "GET", lambda data: f"/api/stafeta/{data.stafeta_slug}", {200}),
    SmokeCase("respondStafetaAssignment", "POST", lambda data: f"/api/stafeta/{data.stafeta_work_id}/invitatie/{data.stafeta_assignment_id}/raspunde", {200, 400, 409}, _json({"action": "accept"})),
    SmokeCase("sendStafetaForward", "POST", lambda data: f"/api/stafeta/{data.stafeta_work_id}/trimite", {200}, _json({"content": "<p>Next</p>", "target_mode": "random"})),
    SmokeCase("assignStafetaSpecific", "POST", lambda data: f"/api/stafeta/{data.stafeta_work_id}/atribuie", {200}, _json({"username": "smokereader"})),
    SmokeCase("assignStafetaRandom", "POST", lambda data: f"/api/stafeta/{data.stafeta_work_id}/aleatoriu", {200}),
    SmokeCase("publishStafeta", "POST", lambda data: f"/api/stafeta/{data.stafeta_work_id}/publica", {200}),
    SmokeCase("cancelStafeta", "DELETE", _path("/api/stafeta/999999"), {404}),
    SmokeCase("cancelStafetaMissing", "DELETE", _path("/api/stafeta/999999"), {404}),
    SmokeCase("addSuperLike", "POST", lambda data: f"/api/postari/{data.peer_post_id}/super-aprecieri", {201}, _json({})),
    SmokeCase("removeSuperLike", "DELETE", lambda data: f"/api/postari/{data.super_liked_post_id}/super-aprecieri", {204}),
    SmokeCase("fetchSuperLikeQuota", "GET", _path("/api/utilizatori/eu/super-aprecieri/cota"), {200}),
    SmokeCase("fetchShopItems", "GET", _path("/api/magazin/obiecte"), {200}),
    SmokeCase("fetchShopState", "GET", _path("/api/magazin/eu"), {200}),
    SmokeCase("purchaseShopItem", "POST", lambda data: f"/api/magazin/obiecte/{data.unowned_shop_item_id}/cumpara", {423}, _json({})),
    SmokeCase("equipInventoryItem", "POST", _path("/api/inventar/echipeaza"), {423}, lambda data: {"item_id": data.shop_item_id}),
    SmokeCase("unequipInventorySlot", "DELETE", _path("/api/inventar/echipate/profile_badge"), {423}),
    SmokeCase("fetchAdminShopItems", "GET", _path("/api/moderare/magazin/obiecte"), {200}),
    SmokeCase("fetchAdminGologaniRewards", "GET", _path("/api/moderare/gologani/recompense"), {200}),
    SmokeCase("updateAdminGologaniReward", "PUT", _path("/api/moderare/gologani/recompense/post_approved"), {200}, _json({"amount": 26})),
    SmokeCase("createAdminShopItem", "POST", _path("/api/moderare/magazin/obiecte"), {201}, _json({"slug": "admin-smoke-item", "name": "Admin Smoke Item", "price": 5, "slot": "title"})),
    SmokeCase("updateAdminShopItem", "PUT", lambda data: f"/api/moderare/magazin/obiecte/{data.shop_item_id}", {200}, _json({"name": "Updated Smoke Item"})),
    SmokeCase("fetchAdminOverview", "GET", _path("/api/admin/overview"), {200}),
    SmokeCase("fetchAdminOverviewDateRange", "GET", _path("/api/admin/overview?from=2000-01-01&to=2099-12-31"), {200}),
    SmokeCase("rollupAdminMetrics", "POST", _path("/api/admin/metrics/rollup?date=2026-01-01"), {200}, _json({})),
    SmokeCase("fetchAdminIntegrations", "GET", _path("/api/admin/integrations"), {200}),
    SmokeCase("fetchAdminPerformanceLive", "GET", _path("/api/admin/performance/live"), {200}),
    SmokeCase("fetchAdminPerformanceHistory", "GET", _path("/api/admin/performance/history?hours=24"), {200}),
    SmokeCase("fetchAdminUsers", "GET", _path("/api/admin/users"), {200}),
    SmokeCase("fetchAdminUser", "GET", lambda data: f"/api/admin/users/{data.peer_id}", {200}),
    SmokeCase("updateAdminUserRoles", "PUT", lambda data: f"/api/admin/users/{data.target_id}/roles", {200}, _json({"is_admin": False, "is_moderator": True, "reason": "smoke roles"})),
    SmokeCase("suspendAdminUser", "POST", lambda data: f"/api/admin/users/{data.peer_id}/suspend", {200}, _json({"reason": "smoke suspend"})),
    SmokeCase("reactivateAdminUser", "POST", lambda data: f"/api/admin/users/{data.peer_id}/reactivate", {200}, _json({"reason": "smoke reactivate"})),
    SmokeCase("updateAdminUserPremium", "PUT", lambda data: f"/api/admin/users/{data.target_id}/premium", {200}, _json({"premium_tier": "cronicar", "reason": "smoke premium"})),
    SmokeCase("adjustAdminUserGologani", "POST", lambda data: f"/api/admin/users/{data.target_id}/gologani-adjustments", {200}, _json({"amount": 5, "reason": "smoke gologani"})),
    SmokeCase("deleteAdminUser", "DELETE", _path("/api/admin/users/999999"), {404}, _json({"reason": "smoke missing"})),
    SmokeCase("fetchAdminContent", "GET", _path("/api/admin/content"), {200}),
    SmokeCase("fetchAdminContentDetail", "GET", lambda data: f"/api/admin/content/post/{data.post_id}", {200}),
    SmokeCase("updateAdminContent", "PUT", lambda data: f"/api/admin/content/post/{data.post_id}", {200}, _json({"title": "Admin Smoke Updated", "reason": "smoke content update"})),
    SmokeCase("moderateAdminContent", "POST", lambda data: f"/api/admin/content/post/{data.pending_post_id}/moderate", {200}, _json({"action": "approve", "reason": "smoke moderate"})),
    SmokeCase("deleteAdminContent", "DELETE", _path("/api/admin/content/post/999999"), {404}, _json({"reason": "smoke missing"})),
    SmokeCase("fetchAdminJobs", "GET", _path("/api/admin/jobs"), {200}),
    SmokeCase("retryAdminJob", "POST", _path("/api/admin/jobs/999999/retry"), {404}, _json({"reason": "smoke retry missing"})),
    SmokeCase("cancelAdminJob", "POST", _path("/api/admin/jobs/999999/cancel"), {404}, _json({"reason": "smoke cancel missing"})),
    SmokeCase("fetchAdminAuditLog", "GET", _path("/api/admin/audit-log"), {200}),
    SmokeCase("fetchAdminStorageObjects", "GET", _path("/api/admin/storage/objects?prefix=posts/"), {200}),
    SmokeCase("presignAdminStorageObject", "POST", _path("/api/admin/storage/objects/presign"), {200}, _json({"key": "posts/smoke-admin-object.txt"})),
    SmokeCase("deleteAdminStorageObject", "DELETE", _path("/api/admin/storage/objects"), {200}, _json({"key": "posts/smoke-admin-object.txt", "reason": "smoke storage delete"})),
    SmokeCase("cleanupAdminStorageObject", "POST", _path("/api/admin/storage/objects/cleanup"), {200}, _json({"key": "posts/smoke-admin-object.txt", "reason": "smoke storage cleanup"})),
    SmokeCase("fetchAdminModerationWords", "GET", _path("/api/admin/moderation-words"), {200}),
    SmokeCase("addAdminModerationWord", "POST", _path("/api/admin/moderation-words"), {400}, _json({"word": "?!", "category": "profanity"})),
    SmokeCase("deleteAdminModerationWord", "DELETE", _path("/api/admin/moderation-words/999999"), {404}),
    SmokeCase("fetchAdminPlatformAccess", "GET", _path("/api/admin/platform-access"), {200}),
    SmokeCase("updateAdminPlatformAccess", "PUT", _path("/api/admin/platform-access"), {200}, _json({"open": False})),
    SmokeCase("addAdminPlatformAllowedEmail", "POST", _path("/api/admin/platform-access/emails"), {200}, _json({"email": "allowed-smoke@example.com", "note": "smoke"})),
    SmokeCase("deleteAdminPlatformAllowedEmail", "DELETE", _path("/api/admin/platform-access/emails/999999"), {404}),
    SmokeCase("fetchAdminInvitations", "GET", _path("/api/admin/invitatii"), {200}),
    SmokeCase("createAdminInvitations", "POST", _path("/api/admin/invitatii"), {200}, _json({"emails": ["invite-smoke@example.com"], "premium_tier": "free", "note": "smoke"})),
    SmokeCase("resendAdminInvitation", "POST", _path("/api/admin/invitatii/999999/retrimite"), {404}, _json({})),
    SmokeCase("revokeAdminInvitation", "POST", _path("/api/admin/invitatii/999999/revoca"), {404}, _json({})),
    SmokeCase("previewAdminEmail", "POST", _path("/api/admin/email/preview"), {200}, _json({"audience": {"selected_user_ids": []}})),
    SmokeCase("createAdminEmailCampaign", "POST", _path("/api/admin/email/campaigns"), {200}, _json({"subject": "Smoke campaign", "html_content": "<p>Smoke email body</p>", "audience": {"selected_user_ids": []}})),
    SmokeCase("processAdminEmailOutbox", "POST", _path("/api/admin/email/outbox/process?limit=1"), {200}, _json({})),
    SmokeCase("sendAdminNotificationTestEmail", "POST", _path("/api/admin/email/test-notification"), {200}, _json({})),
    SmokeCase("fetchAdminEmailCampaigns", "GET", _path("/api/admin/email/campaigns"), {200}),
    SmokeCase("createSiteFeedback", "POST", _path("/api/site-feedback"), {201}, _json({"kind": "bug", "message": "Smoke bug report", "page_url": "https://calimara.test/smoke", "client_context": {"viewport": "1200x800"}})),
    SmokeCase("fetchAdminQaReport", "GET", _path("/api/admin/referinta/raport-qa"), {200}),
    SmokeCase("fetchAdminSiteFeedback", "GET", _path("/api/admin/site-feedback?status=all"), {200}),
    SmokeCase("fetchAdminSiteFeedbackThread", "GET", lambda data: f"/api/admin/site-feedback/{data.site_feedback_id}/thread", {200}),
    SmokeCase("replyAdminSiteFeedback", "POST", lambda data: f"/api/admin/site-feedback/{data.site_feedback_id}/reply", {200}, _json({"content": "Smoke support reply"})),
    SmokeCase("updateAdminSiteFeedback", "PUT", lambda data: f"/api/admin/site-feedback/{data.site_feedback_id}", {200}, _json({"status": "closed", "admin_note": "smoke closed"})),
    SmokeCase("fetchPremiumPlans", "GET", _path("/api/premium/planuri"), {200}),
    SmokeCase("fetchMyReferrals", "GET", _path("/api/recomandari/eu"), {200}),
    SmokeCase("startPremiumCheckout", "POST", _path("/api/premium/plata"), {200}, _json({"tier": "trubadur"})),
    SmokeCase("openPremiumPortal", "POST", _path("/api/premium/portal"), {200}, _json({})),
    SmokeCase("fetchCoffeeOffer", "GET", _path("/api/premium/cafea"), {200}),
    SmokeCase("startCoffeeCheckout", "POST", _path("/api/premium/cafea"), {200}, _json({"quantity": 2})),
    SmokeCase("stripeWebhookInvalidSignature", "POST", _path("/api/stripe/notificare"), {400}, _json({})),
    SmokeCase("unsubscribeEmailInvalidToken", "GET", _path("/api/email/dezabonare?token=missing&type=comment"), {400}),
    SmokeCase("fetchAudioConversionQuota", "GET", _path("/api/audio/cota-conversie"), {200}),
    SmokeCase("requestTtsConversions", "POST", _path("/api/audio/cereri-tts"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchSeriesAudioPlaylist", "GET", lambda data: f"/api/audio/serii/{data.series_id}/lista-redare", {200}),
    SmokeCase("fetchRandomAudio", "GET", _path("/api/audio/aleatoriu?category=poezie"), {200}),
    SmokeCase("fetchListeningQuota", "GET", _path("/api/audio/asculta/cota"), {200}),
    SmokeCase("fetchListeningRandomAudio", "GET", _path("/api/audio/asculta/aleatoriu?mode=poezie"), {200}),
    SmokeCase("fetchAuthorListeningRandomAudio", "GET", _path("/api/audio/autori/smokeauthor/aleatoriu?mode=poezie"), {200}),
    SmokeCase("fetchAudioPlaylists", "GET", _path("/api/audio/playlisturi"), {200}),
    SmokeCase("createAudioPlaylist", "POST", _path("/api/audio/playlisturi"), {201}, _json({"title": "Smoke nou"})),
    SmokeCase("fetchAudioPlaylist", "GET", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}", {200}),
    SmokeCase("updateAudioPlaylist", "PUT", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}", {200}, _json({"title": "Smoke redenumit"})),
    SmokeCase("deleteAudioPlaylist", "DELETE", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}", {204}),
    SmokeCase("addPostToAudioPlaylistDuplicate", "POST", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}/postari", {409}, lambda data: {"post_id": data.post_id}),
    SmokeCase("removePostFromAudioPlaylist", "DELETE", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}/postari/{data.post_id}", {204}),
    SmokeCase("fetchAudioPlaylistPlayback", "GET", lambda data: f"/api/audio/playlisturi/{data.audio_playlist_id}/lista-redare", {200}),
    SmokeCase("recordAudioListenSeconds", "POST", _path("/api/audio/asculta/secunde"), {200}, lambda data: {"event_id": "smoke-listen-1", "audio_id": data.audio_id, "seconds": 3, "mode": "poezie"}),
    SmokeCase("uploadPostAudioRecording", "POST", lambda data: f"/api/postari/{data.post_id}/inregistrare-audio", {200}, files=lambda _data: {"file": ("author.mp3", b"ID3 smoke recording", "audio/mpeg")}),
    SmokeCase("audioStreamUrl", "GET", lambda data: f"/api/audio/redare/{data.audio_id}", {200}),
    SmokeCase("audioDownloadUrl", "GET", lambda data: f"/api/audio/descarcare/{data.audio_id}", {200}),
    SmokeCase("deletePostAudio", "DELETE", _path("/api/postari/999999/audio"), {404}),
    SmokeCase(
        "uploadPostAudioRecordingWav",
        "POST",
        lambda data: f"/api/postari/{data.post_id}/inregistrare-audio",
        {200},
        files=lambda _data: {"file": ("smoke.wav", b"RIFFsmoke", "audio/wav")},
    ),
    SmokeCase("fetchModerationStats", "GET", _path("/api/moderare/statistici"), {200}),
    SmokeCase("fetchPendingModerationContent", "GET", _path("/api/moderare/continut/in-asteptare"), {200}),
    SmokeCase("fetchFlaggedModerationContent", "GET", _path("/api/moderare/continut/marcate"), {200}),
    SmokeCase("moderateContent", "POST", lambda data: f"/api/moderare/modereaza/post/{data.pending_post_id}", {200}, _json({"action": "approve", "reason": "smoke"})),
    SmokeCase("searchModerationUsers", "GET", _path("/api/moderare/utilizatori/cauta?q=smoke"), {200}),
    SmokeCase("suspendUser", "POST", lambda data: f"/api/moderare/utilizatori/{data.peer_id}/suspenda", {200}, _json({"reason": "smoke"})),
    SmokeCase("unsuspendUser", "POST", lambda data: f"/api/moderare/utilizatori/{data.peer_id}/reactiveaza", {200}, _json({})),
    SmokeCase("fetchModerationLogs", "GET", _path("/api/moderare/jurnal"), {200}),
    SmokeCase("fetchModerationQueue", "GET", _path("/api/moderare/coada"), {200}),
    SmokeCase("reviewModerationLog", "POST", lambda data: f"/api/moderare/revizie/{data.moderation_log_id}", {200}, _json({"action": "approved", "reason": "smoke"})),
    SmokeCase("fetchPostReports", "GET", _path("/api/moderare/raportari?status=open"), {200}),
    SmokeCase("reviewPostReport", "POST", _path("/api/moderare/raportari/999999/revizie"), {404}, _json({"action": "dismiss", "reason": "smoke missing"})),
    SmokeCase("fetchExtendedModerationStats", "GET", _path("/api/moderare/statistici/extinse"), {200}),
    SmokeCase("registerWithPassword", "POST", _path("/api/autentificare/parola/inregistrare"), {200}, _json({"email": "new-password-smoke@example.com", "password": "long-enough-password"})),
    SmokeCase("fetchInvitation", "GET", _path("/api/invitatii/missing-token"), {404}),
    SmokeCase("loginWithInvitationPassword", "POST", _path("/api/autentificare/invitatie/parola"), {400}, _json({"token": "missing-token-1234567890", "email": "missing@example.com", "password": "wrong"})),
    SmokeCase("addSetupDiacritics", "POST", _path("/api/autentificare/configurare/diacritice"), {400}, _json({"kind": "profile_description", "content": "Descriere fara diacritice"})),
    SmokeCase("activatePasswordSignup", "POST", _path("/api/autentificare/parola/activeaza"), {400}, _json({"email": "new-password-smoke@example.com", "code": "00000000"})),
    SmokeCase("activatePasswordSignupInvalidCode", "POST", _path("/api/autentificare/parola/activeaza"), {400}, _json({"email": "new-password-smoke@example.com", "code": "00000000"})),
    SmokeCase("resendActivationCode", "POST", _path("/api/autentificare/parola/retrimite-cod"), {200, 400, 404}, _json({"email": "new-password-smoke@example.com"})),
    SmokeCase("loginWithPassword", "POST", _path("/api/autentificare/parola/login"), {400}, _json({"email": "smokeauthor@example.com", "password": "wrong"})),
    SmokeCase("loginWithPasswordInvalid", "POST", _path("/api/autentificare/parola/login"), {400}, _json({"email": "smokeauthor@example.com", "password": "wrong"})),
    SmokeCase("requestPasswordReset", "POST", _path("/api/autentificare/parola/resetare"), {200}, _json({"email": "smokeauthor@example.com"})),
    SmokeCase("confirmPasswordReset", "POST", _path("/api/autentificare/parola/resetare/confirma"), {400}, _json({"email": "smokeauthor@example.com", "code": "00000000", "password": "new-long-password"})),
    SmokeCase("confirmPasswordResetInvalidCode", "POST", _path("/api/autentificare/parola/resetare/confirma"), {400}, _json({"email": "smokeauthor@example.com", "code": "00000000", "password": "new-long-password"})),
    SmokeCase("completeAuthSetup", "POST", _path("/api/autentificare/finalizeaza-configurarea"), {400}, _json({"username": "newsmoke", "subtitle": "setup", "avatar_seed": "setup-seed"})),
    SmokeCase("logout", "GET", _path("/api/deconectare"), {200}, headers={"accept": "application/json"}),
]


@pytest.mark.parametrize("case", SMOKE_CASES, ids=lambda case: case.name)
def test_frontend_api_wrappers_do_not_500(smoke_client, case: SmokeCase):
    client, data = smoke_client
    response = client.request(
        case.method,
        case.path(data),
        json=case.json(data) if case.json else None,
        files=case.files(data) if case.files else None,
        headers=case.headers,
    )

    assert response.status_code < 500, (
        f"{case.name} returned {response.status_code}: {response.text}"
    )
    assert response.status_code in case.expected, (
        f"{case.name} returned {response.status_code}, expected "
        f"{sorted(case.expected)}: {response.text}"
    )


def _sample_smoke_data() -> SmokeData:
    values = {}
    for field in fields(SmokeData):
        values[field.name] = "smoke-slug" if field.name.endswith("_slug") else 1
    return SmokeData(**values)


def test_smoke_cases_cover_all_mounted_api_routes():
    sample = _sample_smoke_data()
    case_requests = [
        (case.method.upper(), case.path(sample).split("?", 1)[0], case.name)
        for case in SMOKE_CASES
    ]
    missing = []

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            if not any(
                case_method == method and route.path_regex.fullmatch(path)
                for case_method, path, _case_name in case_requests
            ):
                missing.append(f"{method} {route.path} ({route.name})")

    assert missing == []


def test_static_api_routes_are_not_shadowed_by_earlier_dynamic_routes():
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]
    shadowed = []

    for index, earlier in enumerate(routes):
        if "{" not in earlier.path:
            continue
        earlier_methods = earlier.methods - {"HEAD", "OPTIONS"}
        for later in routes[index + 1:]:
            if "{" in later.path:
                continue
            shared_methods = sorted(earlier_methods & (later.methods - {"HEAD", "OPTIONS"}))
            if shared_methods and earlier.path_regex.fullmatch(later.path):
                shadowed.append(
                    f"{','.join(shared_methods)} {earlier.path} ({earlier.name}) shadows {later.path} ({later.name})"
                )

    assert shadowed == []


def _route_dependency_names(route: APIRoute) -> set[str]:
    return {
        f"{getattr(dependency.call, '__module__', '')}.{getattr(dependency.call, '__name__', repr(dependency.call))}"
        for dependency in route.dependant.dependencies
    }


def test_privileged_api_routes_keep_privileged_dependencies():
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        dependency_names = _route_dependency_names(route)
        if route.path.startswith("/api/admin") and "app.admin.require_admin" not in dependency_names:
            missing.append(f"{','.join(sorted(route.methods - {'HEAD', 'OPTIONS'}))} {route.path} missing require_admin")
        if route.path.startswith("/api/moderare") and not {
            "app.admin.require_admin",
            "app.admin.require_moderator",
        }.intersection(dependency_names):
            missing.append(f"{','.join(sorted(route.methods - {'HEAD', 'OPTIONS'}))} {route.path} missing moderation guard")

    assert missing == []


def test_overview_stats_route_is_admin_only():
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/statistici/ansamblu"
    )

    assert "app.admin.require_admin" in _route_dependency_names(route)


def test_public_or_internally_guarded_mutating_api_routes_are_explicitly_allowlisted():
    protective_dependencies = {
        "app.auth.get_required_user",
        "app.auth.require_audio_user",
        "app.auth.require_author_audio_user",
        "app.auth.require_rapsod_user",
        "app.admin.require_admin",
        "app.admin.require_moderator",
    }
    allowed = {
        ("POST", "/api/autentificare/invitatie/parola"),
        ("POST", "/api/autentificare/parola/inregistrare"),
        ("POST", "/api/autentificare/parola/activeaza"),
        ("POST", "/api/autentificare/parola/retrimite-cod"),
        ("POST", "/api/autentificare/parola/login"),
        ("POST", "/api/autentificare/parola/resetare"),
        ("POST", "/api/autentificare/parola/resetare/confirma"),
        ("POST", "/api/autentificare/configurare/diacritice"),
        ("POST", "/api/autentificare/finalizeaza-configurarea"),
        ("POST", "/api/postari/{post_id}/comentarii"),
        ("POST", "/api/postari/{post_id}/aprecieri"),
        ("DELETE", "/api/postari/{post_id}/aprecieri"),
        ("POST", "/api/postari/{post_id}/super-aprecieri"),
        ("DELETE", "/api/postari/{post_id}/super-aprecieri"),
        ("POST", "/api/premium/plata"),
        ("POST", "/api/premium/portal"),
        ("POST", "/api/premium/cafea"),
        ("POST", "/api/stripe/notificare"),
        ("POST", "/api/audio/asculta/secunde"),
    }
    unguarded = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        methods = route.methods - {"HEAD", "OPTIONS"}
        if not methods.intersection({"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if protective_dependencies.intersection(_route_dependency_names(route)):
            continue
        for method in methods:
            key = (method, route.path)
            if key not in allowed:
                unguarded.append(f"{method} {route.path} ({route.name})")

    assert sorted(unguarded) == []


def _sample_frontend_api_endpoint(value: str) -> str | None:
    if "\n" in value:
        return None

    def replace_template_expression(match: re.Match[str]) -> str:
        expression = match.group(1)
        if any(token in expression for token in ("buildQuery", "params", "query", "URLSearchParams")):
            return ""
        return "sample"

    sampled = re.sub(r"\$\{([^}]*)\}", replace_template_expression, value).split("?", 1)[0]
    return sampled if sampled.startswith("/api/") else None


def test_frontend_api_endpoint_strings_match_mounted_backend_routes():
    frontend_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".js", ".jsx"}
    )
    mounted_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]
    sampled_paths = sorted(
        {
            sampled
            for match in re.finditer(r"([`\"'])(.*?/api/.*?)(?<!\\)\1", frontend_source, flags=re.S)
            if (sampled := _sample_frontend_api_endpoint(match.group(2)))
        }
    )

    missing = [
        path
        for path in sampled_paths
        if not any(route.path_regex.fullmatch(path) for route in mounted_routes)
    ]

    assert missing == []


def test_frontend_api_barrel_exports_all_api_modules():
    api_dir = ROOT / "frontend" / "src" / "api"
    expected_exports = {
        f'export * from "./api/{path.name}";'
        for path in api_dir.glob("*.js")
    }
    barrel_source = (ROOT / "frontend" / "src" / "api.js").read_text(encoding="utf-8")
    missing_exports = sorted(line for line in expected_exports if line not in barrel_source)

    assert missing_exports == []


def test_comment_reaction_frontend_wires_icons_labels_and_api_helpers():
    source = (ROOT / "frontend" / "src" / "app" / "post-actions.jsx").read_text(encoding="utf-8")
    api_source = (ROOT / "frontend" / "src" / "api" / "posts.js").read_text(encoding="utf-8")

    assert 'import { FaFlag, FaHandsHelping, FaHeart, FaRegLaughSquint } from "react-icons/fa";' in source
    assert 'import { TfiThought } from "react-icons/tfi";' in source
    assert '{ type: "helpful", label: "Util", Icon: FaHandsHelping }' in source
    assert '{ type: "funny", label: "Amuzant", Icon: FaRegLaughSquint }' in source
    assert '{ type: "insightful", label: "Profund", Icon: TfiThought }' in source
    assert "Pentru reacții la comentarii trebuie să intri în cont." in source
    assert "Nu poți reacționa la propriul comentariu" in source
    assert "/api/comentarii/${encodeURIComponent(commentId)}/reactii" in api_source


def test_post_action_tools_disables_own_post_reactions():
    source = (ROOT / "frontend" / "src" / "app" / "post-actions.jsx").read_text(encoding="utf-8")

    assert "const ownPost = Boolean(user?.id && postState.user_id" in source
    assert "Nu poți aprecia propria postare." in source
    assert "Nu îți poți super-aprecia propria postare." in source
    assert 'disabled={ownPost || liked || busy === "like"}' in source
    assert 'disabled={ownPost || Boolean(postState.viewer_super_liked) || busy === "super"}' in source


OLD_PUBLIC_PATHS = [
    "/admin",
    "/dashboard",
    "/create-post",
    "/messages",
    "/category/poezie",
    "/colectii/smoke-collection",
    "/collections/smoke-collection",
    "/forum",
    "/forum/new",
    "/forum/smoke-forum-thread",
    "/shop",
    "/inventory",
    "/privacy",
    "/terms",
    "/auth/google",
    "/auth/setup",
    "/auth/callback",
]


OLD_API_GET_PATHS = [
    "/api/user/me",
    "/api/users/search?q=smoke",
    "/api/user/smokeauthor/profile",
    "/api/categories/poezie",
    "/api/blog/smokeauthor",
    "/api/blog/smokeauthor/post/smoke-poem",
    "/api/audio/posts/1",
    "/api/audio/conversion-quota",
    "/api/audio/random",
    "/api/audio/stream/1",
    "/api/writing/diacritics",
    "/api/posts/archive",
    "/api/posts/months",
    "/api/posts/random",
    "/api/messages/conversations",
    "/api/notifications",
    "/api/stats/my",
    "/api/colectii/aleatoriu",
    "/api/utilizator/colectii",
    "/api/collections/random",
    "/api/user/collections",
    "/api/forum/threads",
    "/api/forum/sections",
    "/api/clubs",
    "/api/clubs/random",
    "/api/users/me/super-likes/quota",
    "/api/shop/me",
    "/api/admin/shop/items",
    "/api/moderation/stats",
    "/api/moderation/content/pending",
    "/api/moderation/logs",
    "/api/moderation/queue",
    "/api/auth/complete-setup",
    "/api/stripe/webhook",
    "/api/logout",
]


@pytest.mark.parametrize("path", ["/api/prima-pagina?category=toate", "/api/landing?category=toate"])
def test_landing_api_returns_json_stats(smoke_client, path: str):
    client, _data = smoke_client
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["stats"]["total_posts"] > 0
    assert payload["stats"]["total_authors"] > 0


def test_platform_stats_api_returns_json_totals(smoke_client):
    client, _data = smoke_client
    response = client.get("/api/statistici/platforma")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["total_posts"] > 0
    assert payload["total_authors"] > 0


def test_friend_request_accepts_incoming_request_id_from_friends_state(smoke_client):
    client, _data = smoke_client

    state_response = client.get("/api/prieteni")
    assert state_response.status_code == 200
    state = state_response.json()
    request_id = state["incoming_requests"][0]["id"]
    response = client.post(f"/api/prieteni/cereri/{request_id}/accepta", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "friends"
    assert payload["friendship"]["id"] == request_id


def test_category_page_api_is_removed(smoke_client):
    client, _data = smoke_client
    response = client.get("/api/categorii/poezie?sort_by=newest")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_audio_download_returns_attachment(smoke_client):
    client, data = smoke_client
    response = client.get(f"/api/audio/descarcare/{data.audio_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    content_disposition = response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "smokeauthor-smoke-poem-audio.mp3" in content_disposition


def test_archive_exposes_author_audio_upload_state(smoke_client):
    client, data = smoke_client
    response = client.get("/api/postari/arhiva")
    assert response.status_code == 200
    posts = response.json()["posts"]
    post = next(item for item in posts if item["id"] == data.post_id)
    assert post["author_audio_can_upload"] is True
    assert post["author_audio_status"] == "missing"
    assert "lectură de autor" in post["author_audio_message"]


def test_missing_audio_download_returns_json_404(smoke_client):
    client, _data = smoke_client
    response = client.get("/api/audio/descarcare/999999")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("path", OLD_PUBLIC_PATHS)
def test_old_english_public_paths_do_not_resolve(smoke_client, path: str):
    client, _data = smoke_client
    response = client.get(path)
    assert response.status_code == 404


@pytest.mark.parametrize("path", OLD_API_GET_PATHS)
def test_old_english_api_paths_do_not_resolve(smoke_client, path: str):
    client, _data = smoke_client
    response = client.get(path)
    assert response.status_code == 404
