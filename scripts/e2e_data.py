#!/usr/bin/env python3
"""Seed and clean deterministic browser-test data.

The E2E suite intentionally uses the configured development database. To avoid
clobbering normal dev data, every row created here uses stable e2e-prefixed
identities and is removed before and after the browser run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import delete
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import local_auth, models
from app.database import SessionLocal


PASSWORD = "e2e-password-123"
USERNAMES = [
    "e2e_author",
    "e2e_reader",
    "e2e_participant",
    "e2e_target",
    "e2e_suspended",
]
USER_EMAILS = [f"{username}@example.com" for username in USERNAMES]
POST_SLUGS = ["e2e-poem", "e2e-story", "e2e-pending"]
SHOP_SLUGS = ["e2e-badge", "e2e-costume"]


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def e2e_audio_dir() -> Path:
    return Path(os.getenv("AUDIO_LOCAL_DIR", "temp/e2e/audio"))


def delete_where_in(db: Session, model, column, values: Iterable[str]) -> None:
    db.execute(delete(model).where(column.in_(list(values))))


def cleanup(db: Session) -> None:
    delete_where_in(db, models.ShopItem, models.ShopItem.slug, SHOP_SLUGS)
    delete_where_in(db, models.ForumThread, models.ForumThread.slug, ["e2e-forum-thread"])
    delete_where_in(db, models.Club, models.Club.slug, ["e2e-club"])
    delete_where_in(db, models.Series, models.Series.slug, ["e2e-series"])
    delete_where_in(db, models.TheatrePlay, models.TheatrePlay.slug, ["e2e-teatru"])
    delete_where_in(db, models.StafetaWork, models.StafetaWork.slug, ["e2e-stafeta"])
    delete_where_in(db, models.Post, models.Post.slug, POST_SLUGS)
    db.execute(delete(models.SiteFeedback).where(models.SiteFeedback.username_snapshot.like("e2e\\_%", escape="\\")))
    db.execute(delete(models.EmailOutbox).where(models.EmailOutbox.recipient_email.like("e2e\\_%@example.com", escape="\\")))
    db.execute(delete(models.EmailCampaign).where(models.EmailCampaign.subject.like("E2E%")))
    delete_where_in(db, models.PlatformAllowedEmail, models.PlatformAllowedEmail.email, USER_EMAILS)
    delete_where_in(db, models.User, models.User.username, USERNAMES)
    db.commit()

    audio_root = e2e_audio_dir()
    if audio_root.parts and "e2e" in audio_root.parts:
        shutil.rmtree(audio_root, ignore_errors=True)


def make_user(
    db: Session,
    username: str,
    *,
    is_admin: bool = False,
    is_moderator: bool = False,
    premium: bool = False,
    suspended: bool = False,
    balance: int = 0,
) -> models.User:
    now = utcnow_naive()
    user = models.User(
        username=username,
        email=f"{username}@example.com",
        google_id=f"e2e-google-{username}",
        password_hash=local_auth.password_hash(PASSWORD),
        email_verified_at=now,
        password_updated_at=now,
        subtitle=f"Profil E2E pentru {username}",
        avatar_seed=f"{username}-avatar",
        cover_seed=f"{username}-cover",
        is_admin=is_admin,
        is_moderator=is_moderator,
        is_suspended=suspended,
        suspension_reason="suspendat pentru test" if suspended else None,
        suspended_at=now if suspended else None,
        premium_tier="rapsod" if premium else "free",
        premium_period_start=now - timedelta(days=1) if premium else None,
        premium_until=now + timedelta(days=30) if premium else None,
        stripe_customer_id=f"cus_{username}" if premium else None,
        gologani_balance=balance,
        location="București",
        instagram_url=f"https://instagram.com/{username}",
        paypal_url=f"https://paypal.me/{username}",
    )
    db.add(user)
    db.add(models.PlatformAllowedEmail(email=user.email, note="e2e"))
    db.flush()
    return user


def make_post(
    db: Session,
    owner: models.User,
    slug: str,
    title: str,
    *,
    category: str = "poezie",
    moderation_status: str = "approved",
) -> models.Post:
    post = models.Post(
        user_id=owner.id,
        title=title,
        slug=slug,
        content=f"<p>Text E2E pentru {title}. Acesta verifică afișarea și fluxurile principale.</p>",
        explanatory_note="Notă E2E",
        category=category,
        moderation_status=moderation_status,
        moderated_at=utcnow_naive() if moderation_status == "approved" else None,
        view_count=3,
    )
    db.add(post)
    db.flush()
    return post


def seed(db: Session) -> None:
    cleanup(db)
    now = utcnow_naive()

    author = make_user(db, "e2e_author", is_admin=True, is_moderator=True, premium=True, balance=500)
    reader = make_user(db, "e2e_reader", premium=True, balance=120)
    participant = make_user(db, "e2e_participant", balance=80)
    target = make_user(db, "e2e_target", balance=40)
    suspended = make_user(db, "e2e_suspended", suspended=True)

    poem = make_post(db, author, "e2e-poem", "E2E Poem", category="poezie")
    story = make_post(db, reader, "e2e-story", "E2E Story", category="proza_scurta")
    pending = make_post(db, author, "e2e-pending", "E2E Pending", moderation_status="pending")

    draft = models.PostDraft(
        user_id=author.id,
        title="E2E Draft",
        content="<p>Ciornă E2E pregătită pentru editare.</p>",
        category="poezie",
    )
    db.add(draft)

    db.add_all(
        [
            models.Comment(post_id=poem.id, user_id=reader.id, content="Comentariu E2E aprobat", approved=True, moderation_status="approved"),
            models.Comment(post_id=poem.id, user_id=target.id, content="Comentariu E2E în moderare", approved=False, moderation_status="pending"),
            models.Like(post_id=poem.id, user_id=reader.id),
            models.SuperLike(post_id=story.id, user_id=author.id),
            models.PostReport(
                post_id=story.id,
                reporter_user_id=author.id,
                reason_type="offensive",
                details="Raport E2E",
                post_title_snapshot=story.title,
                post_slug_snapshot=story.slug,
                post_author_username_snapshot=reader.username,
            ),
        ]
    )

    audio_dir = e2e_audio_dir()
    audio_key = "e2e/e2e-poem.mp3"
    audio_path = audio_dir / audio_key
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"ID3 e2e audio")
    db.add(
        models.PostAudio(
            post_id=poem.id,
            requester_user_id=author.id,
            source="author",
            status="ready",
            storage_backend="local",
            storage_key=audio_key,
            content_type="audio/mpeg",
            byte_size=13,
            duration_seconds=4,
            moderation_status="approved",
        )
    )

    first_id, second_id = sorted([author.id, reader.id])
    db.add(
        models.Friendship(
            user1_id=first_id,
            user2_id=second_id,
            requested_by_id=reader.id,
            status="pending",
        )
    )
    first_id, second_id = sorted([author.id, target.id])
    db.add(
        models.Friendship(
            user1_id=first_id,
            user2_id=second_id,
            requested_by_id=author.id,
            status="accepted",
            responded_at=now,
        )
    )
    db.add_all(
        [
            models.UserFollow(follower_id=author.id, followed_id=target.id),
            models.UserFollow(follower_id=reader.id, followed_id=author.id),
            models.BestFriend(user_id=author.id, friend_user_id=target.id, position=1),
            models.FeaturedPost(user_id=author.id, post_id=poem.id, position=1),
        ]
    )

    conversation = models.Conversation(user1_id=author.id, user2_id=reader.id)
    db.add(conversation)
    db.flush()
    db.add(models.Message(conversation_id=conversation.id, sender_id=reader.id, content="Mesaj E2E necitit", is_read=False))
    db.add(
        models.Notification(
            user_id=author.id,
            type="e2e",
            title="Notificare E2E",
            message="Aceasta este o notificare de test.",
            link="/panou",
        )
    )

    series = models.Series(owner_id=author.id, title="E2E Series", slug="e2e-series", description="Serie E2E")
    db.add(series)
    db.flush()
    db.add(models.SeriesPost(series_id=series.id, post_id=poem.id, position=1))

    club = models.Club(
        owner_id=author.id,
        title="E2E Club",
        slug="e2e-club",
        description="Club E2E pentru teste",
        speciality="poezie",
        join_policy="private",
        featured_post_id=poem.id,
        featured_until=now + timedelta(days=7),
    )
    db.add(club)
    db.flush()
    db.add_all(
        [
            models.ClubMember(club_id=club.id, user_id=author.id, role="owner"),
            models.ClubMember(club_id=club.id, user_id=reader.id, role="member"),
            models.ClubJoinRequest(club_id=club.id, user_id=participant.id, direction="application", status="pending", initiator_id=participant.id),
            models.ClubBoardMessage(club_id=club.id, author_id=author.id, title="Anunț E2E", content="Mesaj de tablă E2E."),
        ]
    )

    forum_thread = models.ForumThread(
        author_id=author.id,
        section="general",
        title="E2E Forum Thread",
        slug="e2e-forum-thread",
        content="Discuție E2E",
        moderation_status="approved",
        moderated_at=now,
    )
    db.add(forum_thread)
    db.flush()
    db.add(models.ForumReply(thread_id=forum_thread.id, author_id=reader.id, content="Răspuns E2E", moderation_status="approved", moderated_at=now))

    badge = models.ShopItem(slug="e2e-badge", name="Insignă E2E", description="Obiect E2E", price=10, slot="profile_badge", sort_order=900)
    costume = models.ShopItem(slug="e2e-costume", name="Costum E2E", description="Obiect E2E necumpărat", price=30, slot="costume", sort_order=901)
    db.add_all([badge, costume])
    db.flush()
    db.add_all(
        [
            models.UserInventoryItem(user_id=author.id, item_id=badge.id),
            models.UserEquippedItem(user_id=author.id, item_id=badge.id, slot=badge.slot),
        ]
    )

    play = models.TheatrePlay(
        creator_id=author.id,
        title="E2E Teatru",
        slug="e2e-teatru",
        description="Piesă E2E",
        status="active",
    )
    db.add(play)
    db.flush()
    narrator = models.TheatreCharacter(
        play_id=play.id,
        name="Narator",
        description="Deschide scena",
        status="approved",
        approved_by=author.id,
        approved_at=now,
        assigned_user_id=author.id,
    )
    actor = models.TheatreCharacter(
        play_id=play.id,
        name="Actor",
        description="Continuă scena",
        status="approved",
        approved_by=author.id,
        approved_at=now,
        assigned_user_id=reader.id,
    )
    db.add_all([narrator, actor])
    db.flush()
    scene = models.TheatreScene(play_id=play.id, scene_number=1, title="Scena E2E", opened_by=author.id)
    db.add(scene)
    db.flush()
    play.current_scene_id = scene.id
    play.current_character_id = actor.id
    play.current_actor_user_id = reader.id
    db.add_all(
        [
            models.TheatreMember(play_id=play.id, user_id=author.id, role="creator"),
            models.TheatreMember(play_id=play.id, user_id=reader.id, role="actor"),
            models.TheatreEntry(
                play_id=play.id,
                scene_id=scene.id,
                author_id=author.id,
                character_id=narrator.id,
                content="<p>Decor E2E.</p>",
                entry_type="line",
                position=1,
                next_character_id=actor.id,
                moderation_status="approved",
                moderated_at=now,
            ),
            models.TheatreJoinRequest(play_id=play.id, user_id=participant.id, direction="application", status="pending", initiator_id=participant.id),
        ]
    )

    for user in (reader, participant):
        db.add(models.StafetaParticipant(user_id=user.id, is_active=True, desired_slots=3))
    work = models.StafetaWork(
        creator_id=author.id,
        title="E2E Ștafeta",
        slug="e2e-stafeta",
        category="poezie",
        status="active",
        deadline_days=1,
        max_characters=400,
        current_holder_user_id=author.id,
    )
    db.add(work)
    db.flush()
    assignment = models.StafetaAssignment(
        work_id=work.id,
        user_id=author.id,
        assigned_by_id=author.id,
        source="creator",
        status="active",
        due_at=now + timedelta(days=1),
        responded_at=now,
    )
    db.add(assignment)
    db.flush()
    work.current_assignment_id = assignment.id
    db.add(
        models.StafetaSegment(
            work_id=work.id,
            assignment_id=assignment.id,
            author_id=author.id,
            content="<p>Început E2E pentru Ștafeta.</p>",
            position=1,
            next_target_mode="random",
            moderation_status="approved",
            moderated_at=now,
        )
    )

    db.add(
        models.ModerationLog(
            content_type="post",
            content_id=pending.id,
            user_id=author.id,
            ai_decision="flagged",
            toxicity_score=0.20,
            ai_reason="E2E moderation",
            human_decision="pending",
        )
    )

    # Keep the suspended user reachable by name in directory/moderation checks.
    suspended.suspended_by = author.id
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "cleanup"])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "seed":
            seed(db)
        else:
            cleanup(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
