import os
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

import pytest
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

from app import auth, crud, diacritics, models, schemas, statistics, stripe_service
from app.database import get_db
from app.main import app


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
    notification_id: int
    series_id: int
    series_slug: str
    club_id: int
    club_slug: str
    club_request_id: int
    board_message_id: int
    forum_thread_id: int
    forum_thread_slug: str
    forum_reply_id: int
    shop_item_id: int
    unowned_shop_item_id: int
    super_liked_post_id: int
    audio_id: int
    moderation_log_id: int


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
        theme_analysis_status="completed",
        themes=["dor"],
        feelings=["bucurie"],
    )
    db.add(post)
    db.flush()
    return post


def _seed_smoke_data(db: Session, audio_dir) -> SmokeData:
    user = _create_user(
        db,
        "smokeauthor",
        is_admin=True,
        is_moderator=True,
        premium=True,
        balance=500,
    )
    peer = _create_user(db, "smokereader", premium=True, balance=50)
    target = _create_user(db, "smoketarget")
    invitee = _create_user(db, "smokeinvitee")

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
        content="Pending smoke comment",
        approved=False,
        moderation_status="pending",
    )
    db.add(comment)

    conversation = models.Conversation(user1_id=user.id, user2_id=peer.id)
    db.add(conversation)
    db.flush()
    db.add(
        models.Message(
            conversation_id=conversation.id,
            sender_id=peer.id,
            content="Smoke message",
            is_read=False,
        )
    )

    notification = models.Notification(
        user_id=user.id,
        type="smoke",
        title="Smoke notification",
        message="Verification notification",
        link="/panou",
    )
    db.add(notification)

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
    db.add(models.SuperLike(user_id=user.id, post_id=super_liked_post.id))

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
        notification,
        series,
        club,
        club_request,
        board_message,
        forum_thread,
        forum_reply,
        owned_item,
        unowned_item,
        audio,
        moderation_log,
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
        notification_id=notification.id,
        series_id=series.id,
        series_slug=series.slug,
        club_id=club.id,
        club_slug=club.slug,
        club_request_id=club_request.id,
        board_message_id=board_message.id,
        forum_thread_id=forum_thread.id,
        forum_thread_slug=forum_thread.slug,
        forum_reply_id=forum_reply.id,
        shop_item_id=owned_item.id,
        unowned_shop_item_id=unowned_item.id,
        super_liked_post_id=super_liked_post.id,
        audio_id=audio.id,
        moderation_log_id=moderation_log.id,
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
        "list_premium_plans",
        lambda: [
            {
                "key": "trubadur",
                "name": "Trubadur",
                "eyebrow": "Premium",
                "price": "3,99 €",
                "cadence": "/ lună",
                "summary": "Smoke premium plan",
                "benefits": ["Smoke benefit"],
                "available": True,
            }
        ],
    )
    monkeypatch.setattr(
        diacritics,
        "add_diacritics",
        lambda **kwargs: {
            "title": "Orașul" if kwargs.get("title") is not None else None,
            "content": "Șapte țări",
            "changed": True,
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
    SmokeCase("uploadProfileMedia", "POST", _path("/api/utilizator/media/profil"), {200}, files=lambda _data: {"file": ("profile.png", SMOKE_PNG_BYTES, "image/png")}),
    SmokeCase("uploadCoverMedia", "POST", _path("/api/utilizator/media/coperta"), {200}, files=lambda _data: {"file": ("cover.png", SMOKE_PNG_BYTES, "image/png")}),
    SmokeCase("deleteProfileMedia", "DELETE", _path("/api/utilizator/media/profil"), {200}),
    SmokeCase("updateBestFriends", "PUT", _path("/api/utilizator/prieteni-apropiati"), {200}, _json({"friends": ["smokereader"]})),
    SmokeCase("searchUsers", "GET", _path("/api/utilizatori/cauta?q=smoke"), {200}),
    SmokeCase("fetchPublicProfile", "GET", _path("/api/utilizator/smokeauthor/profil"), {200}),
    SmokeCase("updateFeaturedPosts", "PUT", _path("/api/utilizator/postari-recomandate"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchLanding", "GET", _path("/api/prima-pagina?category=toate"), {200}),
    SmokeCase("fetchCategory", "GET", _path("/api/categorii/poezie?sort_by=newest"), {200}),
    SmokeCase("fetchBlog", "GET", _path("/api/bloguri/smokeauthor"), {200}),
    SmokeCase("fetchPostDetail", "GET", _path("/api/bloguri/smokeauthor/postari/smoke-poem"), {200}),
    SmokeCase("fetchPostAudioStatus", "GET", lambda data: f"/api/audio/postari/{data.post_id}", {200}),
    SmokeCase("fetchRandomUser", "GET", _path("/api/utilizatori/aleatoriu"), {200}),
    SmokeCase("fetchClubs", "GET", _path("/api/cluburi?limit=50"), {200}),
    SmokeCase("fetchRandomClub", "GET", _path("/api/cluburi/aleatoriu"), {200}),
    SmokeCase("fetchClub", "GET", _path("/api/cluburi/smoke-club"), {200}),
    SmokeCase("fetchArchive", "GET", _path("/api/postari/arhiva"), {200}),
    SmokeCase("fetchPostDrafts", "GET", _path("/api/postari/ciorne"), {200}),
    SmokeCase("fetchPostDraft", "GET", lambda data: f"/api/postari/ciorne/{data.draft_id}", {200}),
    SmokeCase("createPostDraft", "POST", _path("/api/postari/ciorne"), {201}, _json({"title": "Smoke Draft New", "content": "<p>Draft body</p>", "category": "poezie"})),
    SmokeCase("updatePostDraft", "PUT", lambda data: f"/api/postari/ciorne/{data.draft_id}", {200}, _json({"title": "Smoke Draft Updated", "content": "<p>Updated draft body</p>", "category": "proza_scurta"})),
    SmokeCase("deletePostDraft", "DELETE", lambda data: f"/api/postari/ciorne/{data.draft_id}", {204}),
    SmokeCase("fetchPostMonths", "GET", _path("/api/postari/luni"), {200}),
    SmokeCase("fetchRandomPosts", "GET", _path("/api/postari/aleatoriu?category=poezie"), {200}),
    SmokeCase("createPost", "POST", _path("/api/postari/"), {200}, _json({"title": "Smoke Created Post", "content": "Created smoke body", "category": "proza_scurta", "ai_critic": False})),
    SmokeCase("addDiacritics", "POST", _path("/api/scriere/diacritice"), {200}, _json({"kind": "forum_thread", "title": "Orasul", "content": "Sapte tari"})),
    SmokeCase("updatePost", "PUT", lambda data: f"/api/postari/{data.post_id}", {200}, _json({"title": "Smoke Poem Updated", "content": "Updated smoke body", "category": "poezie"})),
    SmokeCase("deletePost", "DELETE", _path("/api/postari/999999"), {404}),
    SmokeCase("createComment", "POST", lambda data: f"/api/postari/{data.post_id}/comentarii", {200}, _json({"content": "Smoke authenticated comment"})),
    SmokeCase("approveComment", "PUT", lambda data: f"/api/comentarii/{data.comment_id}/aproba", {200}, _json({})),
    SmokeCase("deleteComment", "DELETE", lambda data: f"/api/comentarii/{data.comment_id}", {204}),
    SmokeCase("likePost", "POST", lambda data: f"/api/postari/{data.peer_post_id}/aprecieri", {200}, _json({})),
    SmokeCase("fetchLikeCount", "GET", lambda data: f"/api/postari/{data.post_id}/aprecieri/numar", {200}),
    SmokeCase("fetchConversations", "GET", _path("/api/mesaje/conversatii"), {200}),
    SmokeCase("fetchConversation", "GET", lambda data: f"/api/mesaje/conversatii/{data.conversation_id}", {200}),
    SmokeCase("sendConversationMessage", "POST", lambda data: f"/api/mesaje/conversatii/{data.conversation_id}", {200}, _json({"content": "Smoke reply"})),
    SmokeCase("sendMessage", "POST", _path("/api/mesaje/trimite"), {200}, _json({"username": "smokereader", "content": "Smoke direct message"})),
    SmokeCase("fetchUnreadMessageCount", "GET", _path("/api/mesaje/necitite"), {200}),
    SmokeCase("deleteConversation", "DELETE", _path("/api/mesaje/conversatii/999999"), {404}),
    SmokeCase("searchConversations", "GET", _path("/api/mesaje/cauta?q=smoke"), {200}),
    SmokeCase("fetchNotifications", "GET", _path("/api/notificari"), {200}),
    SmokeCase("fetchUnreadNotificationCount", "GET", _path("/api/notificari/necitite"), {200}),
    SmokeCase("markNotificationRead", "PUT", lambda data: f"/api/notificari/{data.notification_id}/citita", {200}, _json({})),
    SmokeCase("markAllNotificationsRead", "PUT", _path("/api/notificari/citeste-toate"), {200}, _json({})),
    SmokeCase("fetchPostStats", "GET", lambda data: f"/api/statistici/postare/{data.post_id}", {200}),
    SmokeCase("fetchAuthorStats", "GET", _path("/api/statistici/autor/smokeauthor"), {200}),
    SmokeCase("fetchCategoryStats", "GET", _path("/api/statistici/categorie/poezie"), {200}),
    SmokeCase("fetchOverviewStats", "GET", _path("/api/statistici/ansamblu"), {200}),
    SmokeCase("fetchMyStats", "GET", _path("/api/statistici/ale-mele"), {200}),
    SmokeCase("createSeries", "POST", _path("/api/serii/"), {201}, _json({"title": "Created Series", "description": "Created through smoke"})),
    SmokeCase("fetchRandomSeries", "GET", _path("/api/serii/aleatoriu"), {200}),
    SmokeCase("fetchSeries", "GET", _path("/api/serii/smoke-series"), {200}),
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
    SmokeCase("deleteForumThread", "DELETE", _path("/api/forum/discutii/999999"), {404}),
    SmokeCase("deleteForumReply", "DELETE", _path("/api/forum/raspunsuri/999999"), {404}),
    SmokeCase("updateForumThreadState", "POST", lambda data: f"/api/forum/discutii/{data.forum_thread_id}/stare", {200}, _json({"action": "lock"})),
    SmokeCase("createClub", "POST", _path("/api/cluburi/"), {201}, _json({"title": "Created Smoke Club", "speciality": "poezie", "description": "Created club"})),
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
    SmokeCase("createClubBoardMessage", "POST", lambda data: f"/api/cluburi/{data.club_id}/tabla", {201}, _json({"content": "Created board message"})),
    SmokeCase("deleteClubBoardMessage", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/tabla/{data.board_message_id}", {204}),
    SmokeCase("setClubFeatured", "POST", lambda data: f"/api/cluburi/{data.club_id}/creatia-saptamanii", {200}, lambda data: {"post_id": data.post_id}),
    SmokeCase("clearClubFeatured", "DELETE", lambda data: f"/api/cluburi/{data.club_id}/creatia-saptamanii", {204}),
    SmokeCase("addSuperLike", "POST", lambda data: f"/api/postari/{data.peer_post_id}/super-aprecieri", {201}, _json({})),
    SmokeCase("removeSuperLike", "DELETE", lambda data: f"/api/postari/{data.super_liked_post_id}/super-aprecieri", {204}),
    SmokeCase("fetchSuperLikeQuota", "GET", _path("/api/utilizatori/eu/super-aprecieri/cota"), {200}),
    SmokeCase("fetchShopState", "GET", _path("/api/magazin/eu"), {200}),
    SmokeCase("purchaseShopItem", "POST", lambda data: f"/api/magazin/obiecte/{data.unowned_shop_item_id}/cumpara", {200}, _json({})),
    SmokeCase("equipInventoryItem", "POST", _path("/api/inventar/echipeaza"), {200}, lambda data: {"item_id": data.shop_item_id}),
    SmokeCase("unequipInventorySlot", "DELETE", _path("/api/inventar/echipate/profile_badge"), {200}),
    SmokeCase("fetchAdminShopItems", "GET", _path("/api/moderare/magazin/obiecte"), {200}),
    SmokeCase("createAdminShopItem", "POST", _path("/api/moderare/magazin/obiecte"), {201}, _json({"slug": "admin-smoke-item", "name": "Admin Smoke Item", "price": 5, "slot": "title"})),
    SmokeCase("updateAdminShopItem", "PUT", lambda data: f"/api/moderare/magazin/obiecte/{data.shop_item_id}", {200}, _json({"name": "Updated Smoke Item"})),
    SmokeCase("fetchAdminOverview", "GET", _path("/api/admin/overview"), {200}),
    SmokeCase("fetchAdminOverviewDateRange", "GET", _path("/api/admin/overview?from=2000-01-01&to=2099-12-31"), {200}),
    SmokeCase("rollupAdminMetrics", "POST", _path("/api/admin/metrics/rollup?date=2026-01-01"), {200}, _json({})),
    SmokeCase("fetchAdminUsers", "GET", _path("/api/admin/users"), {200}),
    SmokeCase("fetchAdminContent", "GET", _path("/api/admin/content"), {200}),
    SmokeCase("fetchAdminJobs", "GET", _path("/api/admin/jobs"), {200}),
    SmokeCase("fetchAdminAuditLog", "GET", _path("/api/admin/audit-log"), {200}),
    SmokeCase("fetchPremiumPlans", "GET", _path("/api/premium/planuri"), {200}),
    SmokeCase("startPremiumCheckout", "POST", _path("/api/premium/plata"), {200}, _json({"tier": "trubadur"})),
    SmokeCase("openPremiumPortal", "POST", _path("/api/premium/portal"), {200}, _json({})),
    SmokeCase("fetchAudioConversionQuota", "GET", _path("/api/audio/cota-conversie"), {200}),
    SmokeCase("requestTtsConversions", "POST", _path("/api/audio/cereri-tts"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchSeriesAudioPlaylist", "GET", lambda data: f"/api/audio/serii/{data.series_id}/lista-redare", {200}),
    SmokeCase("fetchRandomAudio", "GET", _path("/api/audio/aleatoriu?category=poezie"), {200}),
    SmokeCase("fetchListeningRandomAudio", "GET", _path("/api/audio/asculta/aleatoriu?mode=poezie"), {200}),
    SmokeCase("recordAudioListenSeconds", "POST", _path("/api/audio/asculta/secunde"), {200}, lambda data: {"event_id": "smoke-listen-1", "audio_id": data.audio_id, "seconds": 3, "mode": "poezie"}),
    SmokeCase("audioStreamUrl", "GET", lambda data: f"/api/audio/redare/{data.audio_id}", {200}),
    SmokeCase("audioDownloadUrl", "GET", lambda data: f"/api/audio/descarcare/{data.audio_id}", {200}),
    SmokeCase(
        "uploadPostAudioRecording",
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
    SmokeCase("fetchExtendedModerationStats", "GET", _path("/api/moderare/statistici/extinse"), {200}),
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


def test_audio_download_returns_attachment(smoke_client):
    client, data = smoke_client
    response = client.get(f"/api/audio/descarcare/{data.audio_id}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    content_disposition = response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "smokeauthor-smoke-poem-audio.mp3" in content_disposition


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
