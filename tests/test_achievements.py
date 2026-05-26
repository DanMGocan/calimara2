import os
import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import crud, models
from app.achievements import AchievementDefinition, AchievementEvent, evaluate_achievements, emit_super_like_created
from app.week_util import utcnow_naive


class AchievementTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def user(self, name, *, premium=False):
        user = models.User(
            username=name,
            email=f"{name}@example.test",
            google_id=f"google-{name}",
        )
        if premium:
            user.premium_until = utcnow_naive() + timedelta(days=30)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def post(self, author, title="Post", *, status="approved", approved_delta=timedelta(minutes=30)):
        now = utcnow_naive()
        post = models.Post(
            user_id=author.id,
            title=title,
            slug=f"{author.username}-{title}".lower(),
            content="content",
            moderation_status=status,
            moderated_at=now - approved_delta if status == "approved" else None,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_hermes_awards_author_for_super_like_inside_first_public_hour(self):
        author = self.user("author")
        reader = self.user("reader")
        post = self.post(author)

        crud.create_super_like(self.db, reader, post.id)

        awards = self.db.query(models.UserAward).all()
        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0].user_id, author.id)
        self.assertEqual(awards[0].achievement_key, "piciorul-lui-hermes")
        self.assertEqual(awards[0].award_title, "Piciorul lui Hermes")
        self.assertEqual(awards[0].dedupe_key, "once")
        self.assertEqual(awards[0].source_type, "super_like")
        self.assertEqual(awards[0].extra_data["post_id"], post.id)

        notification = self.db.query(models.Notification).filter_by(user_id=author.id).one()
        self.assertEqual(notification.type, "achievement_unlocked")
        self.assertIn("Piciorul lui Hermes", notification.title)
        self.assertEqual(notification.link, f"//{author.username}.calimara.ro/{post.slug}")

    def test_hermes_does_not_award_after_first_public_hour(self):
        author = self.user("slow_author")
        reader = self.user("slow_reader")
        post = self.post(author, approved_delta=timedelta(hours=2))

        crud.create_super_like(self.db, reader, post.id)

        self.assertEqual(self.db.query(models.UserAward).count(), 0)
        self.assertEqual(self.db.query(models.Notification).filter_by(type="achievement_unlocked").count(), 0)

    def test_hermes_does_not_award_for_unapproved_post(self):
        author = self.user("pending_author")
        reader = self.user("pending_reader")
        post = self.post(author, status="pending")

        crud.create_super_like(self.db, reader, post.id)

        self.assertEqual(self.db.query(models.UserAward).count(), 0)

    def test_hermes_is_once_per_user(self):
        author = self.user("repeat_author")
        reader = self.user("repeat_reader", premium=True)
        first = self.post(author, "First")
        second = self.post(author, "Second")

        crud.create_super_like(self.db, reader, first.id)
        crud.create_super_like(self.db, reader, second.id)

        awards = self.db.query(models.UserAward).filter_by(achievement_key="piciorul-lui-hermes").all()
        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0].user_id, author.id)

    def test_re_evaluating_same_event_is_idempotent(self):
        author = self.user("idem_author")
        reader = self.user("idem_reader")
        post = self.post(author)
        super_like = crud.create_super_like(self.db, reader, post.id)

        emit_super_like_created(self.db, super_like)

        awards = self.db.query(models.UserAward).filter_by(achievement_key="piciorul-lui-hermes").all()
        self.assertEqual(len(awards), 1)

    def test_broken_definition_does_not_block_other_achievement(self):
        user = self.user("rule_user")
        event = AchievementEvent(event_type="custom_event", occurred_at=utcnow_naive())

        broken = AchievementDefinition(
            key="broken-rule",
            title="Broken",
            description="Broken",
            award_type="special",
            event_type="custom_event",
            awardee_user_id=lambda _db, _event: user.id,
            condition=lambda _db, _event: (_ for _ in ()).throw(RuntimeError("boom")),
            dedupe_key=lambda _db, _event: "once",
        )
        working = AchievementDefinition(
            key="working-rule",
            title="Working",
            description="Working",
            award_type="special",
            event_type="custom_event",
            awardee_user_id=lambda _db, _event: user.id,
            condition=lambda _db, _event: True,
            dedupe_key=lambda _db, _event: "once",
        )

        created = evaluate_achievements(self.db, event, definitions=(broken, working))

        self.assertEqual([award.achievement_key for award in created], ["working-rule"])
        self.assertEqual(self.db.query(models.UserAward).filter_by(achievement_key="working-rule").count(), 1)


if __name__ == "__main__":
    unittest.main()
