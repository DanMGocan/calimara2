import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import crud, models
from app.schemas.stafeta import StafetaCreate, StafetaSend


APPROVED = SimpleNamespace(status="approved", toxicity_score=0.0, reason="test approved")


class StafetaFeatureTests(unittest.TestCase):
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

    def make_user(self, username):
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_schema_contains_stafeta_tables_and_moderation_type(self):
        schema = (Path(__file__).resolve().parents[1] / "schema.sql").read_text()
        self.assertIn("CREATE TABLE stafeta_works", schema)
        self.assertIn("CREATE TABLE stafeta_assignments", schema)
        self.assertIn("CREATE TABLE stafeta_segments", schema)
        self.assertIn("'stafeta_segment'", schema)
        self.assertIn("CHECK (deadline_days IN (1, 3, 7))", schema)
        self.assertIn("max_characters INT DEFAULT 400 NOT NULL", schema)
        self.assertIn("fk_stafeta_works_current_assignment", schema)

    def test_random_assignment_uses_opted_in_user_and_avoids_creator(self):
        creator = self.make_user("creator")
        participant = self.make_user("participant")
        crud.set_stafeta_participation(self.db, participant, True)

        work, error = crud.create_stafeta_work(
            self.db,
            creator,
            StafetaCreate(
                title="Lanțul",
                category="poezie",
                initial_content="<p>Începutul.</p>",
                first_target_mode="random",
            ),
        )

        self.assertIsNone(error)
        self.assertEqual(work.current_holder_user_id, participant.id)
        assignment = crud.get_current_stafeta_assignment(self.db, work)
        self.assertEqual(assignment.status, "active")
        self.assertEqual(assignment.source, "random")

    def test_specific_assignment_can_be_refused_back_to_creator(self):
        creator = self.make_user("creator")
        target = self.make_user("target")
        work, error = crud.create_stafeta_work(
            self.db,
            creator,
            StafetaCreate(
                title="Invitație",
                category="proza_scurta",
                initial_content="<p>O ușă se deschide.</p>",
                first_target_mode="specific",
                assigned_username=target.username,
            ),
        )
        self.assertIsNone(error)
        assignment = crud.get_current_stafeta_assignment(self.db, work)
        self.assertEqual(assignment.status, "pending")

        updated, error = crud.respond_to_stafeta_assignment(self.db, assignment, target, "refuse")

        self.assertIsNone(error)
        self.assertEqual(updated.status, "refused")
        self.db.refresh(work)
        creator_assignment = crud.get_current_stafeta_assignment(self.db, work)
        self.assertEqual(creator_assignment.user_id, creator.id)
        self.assertEqual(creator_assignment.status, "active")

    def test_turn_advances_only_after_approved_segment(self):
        creator = self.make_user("creator")
        first = self.make_user("first")
        second = self.make_user("second")
        for user in (first, second):
            crud.set_stafeta_participation(self.db, user, True)
        work, error = crud.create_stafeta_work(
            self.db,
            creator,
            StafetaCreate(
                title="Rânduri",
                category="poezie",
                initial_content="<p>Start.</p>",
                first_target_mode="specific",
                assigned_username=first.username,
                max_characters=400,
            ),
        )
        self.assertIsNone(error)
        pending = crud.get_current_stafeta_assignment(self.db, work)
        crud.respond_to_stafeta_assignment(self.db, pending, first, "accept")
        self.db.refresh(work)

        with patch("app.repositories.stafeta.choose_random_stafeta_recipient", return_value=second):
            segment, error = crud.send_stafeta_forward(
                self.db,
                work,
                first,
                StafetaSend(content="<p>Continuare.</p>", target_mode="random"),
            )
            self.assertIsNone(error)
            self.db.refresh(work)
            self.assertEqual(work.current_holder_user_id, first.id)

            crud.apply_stafeta_segment_moderation_result(self.db, segment, APPROVED)
            self.db.refresh(work)
            self.assertEqual(work.current_holder_user_id, second.id)
            next_assignment = crud.get_current_stafeta_assignment(self.db, work)
            self.assertEqual(next_assignment.status, "active")

    def test_empty_handoff_goes_random_without_segment(self):
        creator = self.make_user("creator")
        first = self.make_user("first")
        second = self.make_user("second")
        crud.set_stafeta_participation(self.db, second, True)
        work, _ = crud.create_stafeta_work(
            self.db,
            creator,
            StafetaCreate(
                title="Fără text",
                category="poezie",
                initial_content="<p>Start.</p>",
                first_target_mode="specific",
                assigned_username=first.username,
            ),
        )
        pending = crud.get_current_stafeta_assignment(self.db, work)
        crud.respond_to_stafeta_assignment(self.db, pending, first, "accept")
        self.db.refresh(work)

        with patch("app.repositories.stafeta.choose_random_stafeta_recipient", return_value=second):
            assignment, error = crud.send_stafeta_forward(
                self.db,
                work,
                first,
                StafetaSend(content=None, target_mode="creator"),
            )

        self.assertIsNone(error)
        self.assertEqual(assignment.user_id, second.id)
        self.assertEqual(crud.count_stafeta_segments(self.db, work.id, approved_only=False), 1)

    def test_publish_creates_normal_pending_post(self):
        creator = self.make_user("creator")
        participant = self.make_user("participant")
        work, _ = crud.create_stafeta_work(
            self.db,
            creator,
            StafetaCreate(
                title="Publicare",
                category="poezie",
                initial_content="<p>Start.</p>",
                first_target_mode="specific",
                assigned_username=participant.username,
            ),
        )
        segment = models.StafetaSegment(
            work_id=work.id,
            author_id=participant.id,
            content="<p>Final.</p>",
            position=2,
            next_target_mode="creator",
            moderation_status="approved",
        )
        self.db.add(segment)
        self.db.commit()

        post, error = crud.publish_stafeta_work(self.db, work, creator)

        self.assertIsNone(error)
        self.assertEqual(post.user_id, creator.id)
        self.assertEqual(post.moderation_status, "pending")
        self.assertIn("Start", post.content)
        self.assertIn("Final", post.content)
        self.db.refresh(work)
        self.assertEqual(work.status, "published")
        self.assertEqual(work.published_post_id, post.id)


if __name__ == "__main__":
    unittest.main()
