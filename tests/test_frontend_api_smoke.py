import os
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

from app import auth, crud, models, schemas, statistics, stripe_service
from app.database import get_db
from app.main import app


@dataclass(frozen=True)
class SmokeData:
    user_id: int
    peer_id: int
    target_id: int
    invitee_id: int
    post_id: int
    peer_post_id: int
    pending_post_id: int
    comment_id: int
    conversation_id: int
    notification_id: int
    collection_id: int
    collection_slug: str
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
        premium_tier="author_audio" if premium else "free",
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
        link="/dashboard",
    )
    db.add(notification)

    collection = models.Collection(
        owner_id=user.id,
        title="Smoke Collection",
        slug="smoke-collection",
        description="Smoke collection description",
    )
    db.add(collection)
    db.flush()
    db.add(
        models.CollectionPost(
            collection_id=collection.id,
            post_id=peer_post.id,
            initiator_id=user.id,
            status="accepted",
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
        comment,
        conversation,
        notification,
        collection,
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
        comment_id=comment.id,
        conversation_id=conversation.id,
        notification_id=notification.id,
        collection_id=collection.id,
        collection_slug=collection.slug,
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
    monkeypatch.setenv("AUDIO_LOCAL_DIR", str(audio_dir))
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
    SmokeCase("fetchMe", "GET", _path("/api/user/me"), {200}),
    SmokeCase("updateMe", "PUT", _path("/api/user/me"), {200}, _json({"subtitle": "Updated smoke profile", "avatar_seed": "updated-seed"})),
    SmokeCase("updateSocialLinks", "PUT", _path("/api/user/social-links"), {200}, _json({"instagram_url": "https://instagram.com/smokeauthor"})),
    SmokeCase("updateBestFriends", "PUT", _path("/api/user/best-friends"), {200}, _json({"friends": ["smokereader"]})),
    SmokeCase("searchUsers", "GET", _path("/api/users/search?q=smoke"), {200}),
    SmokeCase("fetchPublicProfile", "GET", _path("/api/user/smokeauthor/profile"), {200}),
    SmokeCase("updateFeaturedPosts", "PUT", _path("/api/user/featured-posts"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchLanding", "GET", _path("/api/landing?category=toate"), {200}),
    SmokeCase("fetchCategory", "GET", _path("/api/categories/poezie?sort_by=newest"), {200}),
    SmokeCase("fetchBlog", "GET", _path("/api/blog/smokeauthor"), {200}),
    SmokeCase("fetchPostDetail", "GET", _path("/api/blog/smokeauthor/post/smoke-poem"), {200}),
    SmokeCase("fetchPostAudioStatus", "GET", lambda data: f"/api/audio/posts/{data.post_id}", {200}),
    SmokeCase("fetchRandomUser", "GET", _path("/api/users/random"), {200}),
    SmokeCase("fetchClubs", "GET", _path("/api/clubs?limit=50"), {200}),
    SmokeCase("fetchRandomClub", "GET", _path("/api/clubs/random"), {200}),
    SmokeCase("fetchClub", "GET", _path("/api/clubs/smoke-club"), {200}),
    SmokeCase("fetchArchive", "GET", _path("/api/posts/archive"), {200}),
    SmokeCase("fetchPostMonths", "GET", _path("/api/posts/months"), {200}),
    SmokeCase("fetchRandomPosts", "GET", _path("/api/posts/random?category=poezie"), {200}),
    SmokeCase("createPost", "POST", _path("/api/posts/"), {200}, _json({"title": "Smoke Created Post", "content": "Created smoke body", "ai_critic": False})),
    SmokeCase("updatePost", "PUT", lambda data: f"/api/posts/{data.post_id}", {200}, _json({"title": "Smoke Poem Updated", "content": "Updated smoke body"})),
    SmokeCase("deletePost", "DELETE", _path("/api/posts/999999"), {404}),
    SmokeCase("createComment", "POST", lambda data: f"/api/posts/{data.post_id}/comments", {200}, _json({"content": "Smoke authenticated comment"})),
    SmokeCase("approveComment", "PUT", lambda data: f"/api/comments/{data.comment_id}/approve", {200}, _json({})),
    SmokeCase("deleteComment", "DELETE", lambda data: f"/api/comments/{data.comment_id}", {204}),
    SmokeCase("likePost", "POST", lambda data: f"/api/posts/{data.peer_post_id}/likes", {200}, _json({})),
    SmokeCase("fetchLikeCount", "GET", lambda data: f"/api/posts/{data.post_id}/likes/count", {200}),
    SmokeCase("fetchConversations", "GET", _path("/api/messages/conversations"), {200}),
    SmokeCase("fetchConversation", "GET", lambda data: f"/api/messages/conversations/{data.conversation_id}", {200}),
    SmokeCase("sendConversationMessage", "POST", lambda data: f"/api/messages/conversations/{data.conversation_id}", {200}, _json({"content": "Smoke reply"})),
    SmokeCase("sendMessage", "POST", _path("/api/messages/send"), {200}, _json({"username": "smokereader", "content": "Smoke direct message"})),
    SmokeCase("fetchUnreadMessageCount", "GET", _path("/api/messages/unread-count"), {200}),
    SmokeCase("deleteConversation", "DELETE", _path("/api/messages/conversations/999999"), {404}),
    SmokeCase("searchConversations", "GET", _path("/api/messages/search?q=smoke"), {200}),
    SmokeCase("fetchNotifications", "GET", _path("/api/notifications"), {200}),
    SmokeCase("fetchUnreadNotificationCount", "GET", _path("/api/notifications/unread-count"), {200}),
    SmokeCase("markNotificationRead", "PUT", lambda data: f"/api/notifications/{data.notification_id}/read", {200}, _json({})),
    SmokeCase("markAllNotificationsRead", "PUT", _path("/api/notifications/read-all"), {200}, _json({})),
    SmokeCase("fetchPostStats", "GET", lambda data: f"/api/stats/post/{data.post_id}", {200}),
    SmokeCase("fetchAuthorStats", "GET", _path("/api/stats/author/smokeauthor"), {200}),
    SmokeCase("fetchCategoryStats", "GET", _path("/api/stats/category/poezie"), {200}),
    SmokeCase("fetchOverviewStats", "GET", _path("/api/stats/overview"), {200}),
    SmokeCase("fetchMyStats", "GET", _path("/api/stats/my"), {200}),
    SmokeCase("createCollection", "POST", _path("/api/collections/"), {201}, _json({"title": "Created Collection", "description": "Created through smoke"})),
    SmokeCase("fetchRandomCollection", "GET", _path("/api/collections/random"), {200}),
    SmokeCase("fetchCollection", "GET", _path("/api/collections/smoke-collection"), {200}),
    SmokeCase("fetchUserCollections", "GET", _path("/api/users/smokeauthor/collections"), {200}),
    SmokeCase("updateCollection", "PUT", lambda data: f"/api/collections/{data.collection_id}", {200}, _json({"title": "Updated Smoke Collection"})),
    SmokeCase("deleteCollection", "DELETE", _path("/api/collections/999999"), {404}),
    SmokeCase("addPostToCollection", "POST", lambda data: f"/api/collections/{data.collection_id}/posts", {409}, lambda data: {"post_id": data.peer_post_id}),
    SmokeCase("respondCollectionEntry", "POST", lambda data: f"/api/collections/{data.collection_id}/posts/{data.peer_post_id}/respond", {409}, _json({"action": "accept"})),
    SmokeCase("removeCollectionEntry", "DELETE", lambda data: f"/api/collections/{data.collection_id}/posts/{data.peer_post_id}", {204}),
    SmokeCase("fetchMyCollections", "GET", _path("/api/user/collections"), {200}),
    SmokeCase("fetchManagedCollection", "GET", lambda data: f"/api/user/collections/{data.collection_id}/manage", {200}),
    SmokeCase("fetchPendingCollectionApprovals", "GET", _path("/api/user/collections/pending"), {200}),
    SmokeCase("fetchPostCollections", "GET", lambda data: f"/api/posts/{data.peer_post_id}/collections", {200}),
    SmokeCase("fetchForumThreads", "GET", _path("/api/forum/threads?section=general"), {200}),
    SmokeCase("fetchForumSections", "GET", _path("/api/forum/sections"), {200}),
    SmokeCase("fetchForumThread", "GET", _path("/api/forum/threads/smoke-forum-thread"), {200}),
    SmokeCase("createForumThread", "POST", _path("/api/forum/threads"), {201}, _json({"section": "general", "title": "Created Smoke Thread", "content": "Created smoke thread body"})),
    SmokeCase("createForumReply", "POST", lambda data: f"/api/forum/threads/{data.forum_thread_id}/replies", {201}, _json({"content": "Created smoke reply"})),
    SmokeCase("deleteForumThread", "DELETE", _path("/api/forum/threads/999999"), {404}),
    SmokeCase("deleteForumReply", "DELETE", _path("/api/forum/replies/999999"), {404}),
    SmokeCase("updateForumThreadState", "POST", lambda data: f"/api/forum/threads/{data.forum_thread_id}/state", {200}, _json({"action": "lock"})),
    SmokeCase("createClub", "POST", _path("/api/clubs/"), {201}, _json({"title": "Created Smoke Club", "speciality": "poezie", "description": "Created club"})),
    SmokeCase("updateClub", "PUT", lambda data: f"/api/clubs/{data.club_id}", {200}, _json({"title": "Updated Smoke Club", "speciality": "poezie"})),
    SmokeCase("deleteClub", "DELETE", _path("/api/clubs/999999"), {404}),
    SmokeCase("applyToClub", "POST", lambda data: f"/api/clubs/{data.club_id}/apply", {409}, _json({})),
    SmokeCase("inviteToClub", "POST", lambda data: f"/api/clubs/{data.club_id}/invite", {200}, _json({"username": "smokeinvitee"})),
    SmokeCase("fetchClubRequests", "GET", lambda data: f"/api/clubs/{data.club_id}/requests", {200}),
    SmokeCase("respondClubRequest", "POST", lambda data: f"/api/clubs/{data.club_id}/requests/{data.club_request_id}/respond", {200}, _json({"action": "approve"})),
    SmokeCase("removeClubMember", "DELETE", lambda data: f"/api/clubs/{data.club_id}/members/{data.peer_id}", {204}),
    SmokeCase("updateClubMemberRole", "PUT", lambda data: f"/api/clubs/{data.club_id}/members/{data.peer_id}/role", {200}, _json({"role": "admin"})),
    SmokeCase("fetchMyClubs", "GET", _path("/api/user/clubs"), {200}),
    SmokeCase("fetchMyClubInvitations", "GET", _path("/api/user/clubs/pending"), {200}),
    SmokeCase("fetchClubBoard", "GET", lambda data: f"/api/clubs/{data.club_id}/board", {200}),
    SmokeCase("createClubBoardMessage", "POST", lambda data: f"/api/clubs/{data.club_id}/board", {201}, _json({"content": "Created board message"})),
    SmokeCase("deleteClubBoardMessage", "DELETE", lambda data: f"/api/clubs/{data.club_id}/board/{data.board_message_id}", {204}),
    SmokeCase("setClubFeatured", "POST", lambda data: f"/api/clubs/{data.club_id}/featured", {200}, lambda data: {"post_id": data.post_id}),
    SmokeCase("clearClubFeatured", "DELETE", lambda data: f"/api/clubs/{data.club_id}/featured", {204}),
    SmokeCase("addSuperLike", "POST", lambda data: f"/api/posts/{data.peer_post_id}/super-likes", {201}, _json({})),
    SmokeCase("removeSuperLike", "DELETE", lambda data: f"/api/posts/{data.super_liked_post_id}/super-likes", {204}),
    SmokeCase("fetchSuperLikeQuota", "GET", _path("/api/users/me/super-likes/quota"), {200}),
    SmokeCase("fetchShopState", "GET", _path("/api/shop/me"), {200}),
    SmokeCase("purchaseShopItem", "POST", lambda data: f"/api/shop/items/{data.unowned_shop_item_id}/purchase", {200}, _json({})),
    SmokeCase("equipInventoryItem", "POST", _path("/api/inventory/equip"), {200}, lambda data: {"item_id": data.shop_item_id}),
    SmokeCase("unequipInventorySlot", "DELETE", _path("/api/inventory/equipped/profile_badge"), {200}),
    SmokeCase("fetchAdminShopItems", "GET", _path("/api/admin/shop/items"), {200}),
    SmokeCase("createAdminShopItem", "POST", _path("/api/admin/shop/items"), {201}, _json({"slug": "admin-smoke-item", "name": "Admin Smoke Item", "price": 5, "slot": "title"})),
    SmokeCase("updateAdminShopItem", "PUT", lambda data: f"/api/admin/shop/items/{data.shop_item_id}", {200}, _json({"name": "Updated Smoke Item"})),
    SmokeCase("startPremiumCheckout", "POST", _path("/api/premium/checkout"), {200}, _json({"tier": "premium"})),
    SmokeCase("openPremiumPortal", "POST", _path("/api/premium/portal"), {200}, _json({})),
    SmokeCase("fetchAudioConversionQuota", "GET", _path("/api/audio/conversion-quota"), {200}),
    SmokeCase("requestTtsConversions", "POST", _path("/api/audio/tts-requests"), {200}, lambda data: {"post_ids": [data.post_id]}),
    SmokeCase("fetchCollectionAudioPlaylist", "GET", lambda data: f"/api/audio/collections/{data.collection_id}/playlist", {200}),
    SmokeCase("fetchRandomAudio", "GET", _path("/api/audio/random?category=poezie"), {200}),
    SmokeCase("audioStreamUrl", "GET", lambda data: f"/api/audio/stream/{data.audio_id}", {200}),
    SmokeCase(
        "uploadPostAudioRecording",
        "POST",
        lambda data: f"/api/posts/{data.post_id}/audio-recording",
        {200},
        files=lambda _data: {"file": ("smoke.wav", b"RIFFsmoke", "audio/wav")},
    ),
    SmokeCase("fetchModerationStats", "GET", _path("/api/moderation/stats"), {200}),
    SmokeCase("fetchPendingModerationContent", "GET", _path("/api/moderation/content/pending"), {200}),
    SmokeCase("fetchFlaggedModerationContent", "GET", _path("/api/moderation/content/flagged"), {200}),
    SmokeCase("moderateContent", "POST", lambda data: f"/api/moderation/moderate/post/{data.pending_post_id}", {200}, _json({"action": "approve", "reason": "smoke"})),
    SmokeCase("searchModerationUsers", "GET", _path("/api/moderation/users/search?q=smoke"), {200}),
    SmokeCase("suspendUser", "POST", lambda data: f"/api/moderation/users/{data.peer_id}/suspend", {200}, _json({"reason": "smoke"})),
    SmokeCase("unsuspendUser", "POST", lambda data: f"/api/moderation/users/{data.peer_id}/unsuspend", {200}, _json({})),
    SmokeCase("fetchModerationLogs", "GET", _path("/api/moderation/logs"), {200}),
    SmokeCase("fetchModerationQueue", "GET", _path("/api/moderation/queue"), {200}),
    SmokeCase("reviewModerationLog", "POST", lambda data: f"/api/moderation/review/{data.moderation_log_id}", {200}, _json({"action": "approved", "reason": "smoke"})),
    SmokeCase("fetchExtendedModerationStats", "GET", _path("/api/moderation/stats/extended"), {200}),
    SmokeCase("completeAuthSetup", "POST", _path("/api/auth/complete-setup"), {400}, _json({"username": "newsmoke", "subtitle": "setup", "avatar_seed": "setup-seed"})),
    SmokeCase("logout", "GET", _path("/api/logout"), {200}, headers={"accept": "application/json"}),
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
