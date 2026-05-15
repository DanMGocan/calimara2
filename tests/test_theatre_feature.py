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

from app import crud, models, pdf_exporter
from app.schemas.theatre import (
    TheatreInvite,
    TheatreCharacterCreate,
    TheatreJoinApply,
    TheatrePlayCreate,
    TheatreSceneCreate,
    TheatreReplyCreate,
)


APPROVED = SimpleNamespace(status="approved", toxicity_score=0.0, reason="test approved")


class TheatreFeatureTests(unittest.TestCase):
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

    def test_schema_allows_theatre_entry_moderation_logs(self):
        schema = (Path(__file__).resolve().parents[1] / "schema.sql").read_text()
        moderation_table = schema.split("CREATE TABLE moderation_logs", 1)[1].split("CREATE INDEX idx_modlog_content", 1)[0]
        self.assertIn("'theatre_entry'", moderation_table)
        self.assertIn("uq_theatre_character_assigned_user", schema)
        self.assertIn("uq_theatre_join_requests_pending_character", schema)
        self.assertIn("fk_theatre_plays_current_scene", schema)
        self.assertIn("fk_theatre_plays_current_character", schema)
        self.assertIn("fk_theatre_plays_current_actor", schema)
        self.assertNotIn("uq_theatre_join_requests_pending ON theatre_join_requests(play_id, user_id)", schema)

    def test_invitation_requires_invited_user_approval_before_assignment(self):
        creator = self.make_user("regizor")
        actor = self.make_user("actor")
        play = crud.create_theatre_play(
            self.db,
            creator,
            TheatrePlayCreate(
                title="Piesa test",
                characters=[
                    {
                        "name": "Hamlet",
                        "description": "Prințul ezitant",
                        "assigned_username": actor.username,
                    }
                ],
            ),
        )

        character = crud.list_theatre_characters(self.db, play.id)[0]
        self.assertIsNone(character.assigned_user_id)
        self.assertIsNone(crud.get_theatre_membership(self.db, play.id, actor.id))

        request = crud.get_user_pending_theatre_request(self.db, play.id, actor.id)
        self.assertIsNotNone(request)
        updated, error = crud.respond_to_theatre_request(self.db, request, actor, "approve")

        self.assertIsNone(error)
        self.assertEqual(updated.status, "approved")
        self.db.refresh(character)
        self.assertEqual(character.assigned_user_id, actor.id)
        self.assertIsNotNone(crud.get_theatre_membership(self.db, play.id, actor.id))

    def test_user_can_accept_only_one_character_assignment(self):
        creator = self.make_user("regizor")
        actor = self.make_user("actor")
        play = crud.create_theatre_play(
            self.db,
            creator,
            TheatrePlayCreate(
                title="Două roluri",
                characters=[
                    {"name": "Primul", "description": "Un rol", "assigned_username": actor.username},
                    {"name": "Al doilea", "description": "Alt rol", "assigned_username": actor.username},
                ],
            ),
        )

        requests = crud.list_theatre_pending_requests(self.db, play.id)
        self.assertEqual(len(requests), 2)
        first, second = requests
        approved, error = crud.respond_to_theatre_request(self.db, first, actor, "approve")
        self.assertIsNone(error)
        self.assertEqual(approved.status, "approved")

        rejected, error = crud.respond_to_theatre_request(self.db, second, actor, "approve")
        self.assertIsNone(rejected)
        self.assertEqual(error, "user_already_assigned")

    def test_delete_theatre_character_allows_unused_and_blocks_used(self):
        creator = self.make_user("autor")
        play = crud.create_theatre_play(self.db, creator, TheatrePlayCreate(title="Ștergeri"))
        unused, error = crud.create_theatre_character(
            self.db,
            creator,
            play,
            TheatreCharacterCreate(name="Umbra", description="Apare târziu"),
        )
        self.assertIsNone(error)
        ok, error = crud.delete_theatre_character(self.db, creator, unused)
        self.assertTrue(ok)
        self.assertIsNone(error)

        used, error = crud.create_theatre_character(
            self.db,
            creator,
            play,
            TheatreCharacterCreate(name="Narator", description="Deschide scena"),
        )
        self.assertIsNone(error)
        used.assigned_user_id = creator.id
        self.db.commit()
        scene, error = crud.start_theatre_scene(
            self.db,
            creator,
            play,
            TheatreSceneCreate(
                title="Actul 1",
                first_character_id=used.id,
                content="<p>Decorul.</p>",
            ),
        )
        self.assertIsNone(error)
        self.assertIsNotNone(scene)

        ok, error = crud.delete_theatre_character(self.db, creator, used)
        self.assertFalse(ok)
        self.assertEqual(error, "character_in_use")

    def test_application_with_proposed_character_approves_character_and_membership(self):
        creator = self.make_user("autor")
        applicant = self.make_user("actrita")
        play = crud.create_theatre_play(self.db, creator, TheatrePlayCreate(title="Comedia"))

        request, error = crud.apply_to_theatre_play(
            self.db,
            applicant,
            play,
            TheatreJoinApply(
                proposed_character={"name": "Bufonul", "description": "Observă totul"},
                note="Vreau să intru în piesă.",
            ),
        )

        self.assertIsNone(error)
        self.assertEqual(request.character.status, "pending")
        updated, error = crud.respond_to_theatre_request(self.db, request, creator, "approve")

        self.assertIsNone(error)
        self.assertEqual(updated.status, "approved")
        character = crud.get_theatre_character(self.db, request.character_id)
        self.assertEqual(character.status, "approved")
        self.assertEqual(character.assigned_user_id, applicant.id)
        self.assertIsNotNone(crud.get_theatre_membership(self.db, play.id, applicant.id))

    def test_turn_advances_only_after_entry_approval(self):
        creator = self.make_user("creator")
        alice = self.make_user("alice")
        bob = self.make_user("bob")
        play = crud.create_theatre_play(
            self.db,
            creator,
            TheatrePlayCreate(
                title="Rânduri",
                characters=[
                    {"name": "A", "description": "Primul", "assigned_username": alice.username},
                    {"name": "B", "description": "Al doilea", "assigned_username": bob.username},
                ],
            ),
        )
        for user in (alice, bob):
            request = crud.get_user_pending_theatre_request(self.db, play.id, user.id)
            crud.respond_to_theatre_request(self.db, request, user, "approve")
        characters = crud.list_theatre_characters(self.db, play.id)
        first = next(character for character in characters if character.name == "A")
        second = next(character for character in characters if character.name == "B")

        scene, error = crud.start_theatre_scene(
            self.db,
            creator,
            play,
            TheatreSceneCreate(
                title="Scena întâi",
                first_character_id=first.id,
                content="<p>Decorul e pregătit.</p>",
            ),
        )
        self.assertIsNone(error)
        self.db.refresh(play)
        self.assertIsNone(play.current_actor_user_id)

        opening = scene.entries[0]
        crud.apply_theatre_entry_moderation_result(self.db, opening, APPROVED)
        self.db.refresh(play)
        self.assertEqual(play.current_actor_user_id, alice.id)
        self.assertEqual(play.current_character_id, first.id)

        reply, error = crud.create_theatre_reply(
            self.db,
            alice,
            play,
            scene,
            TheatreReplyCreate(content="<p>Replica mea.</p>", next_character_id=second.id),
        )
        self.assertIsNone(error)
        self.db.refresh(play)
        self.assertEqual(play.current_actor_user_id, alice.id)

        crud.apply_theatre_entry_moderation_result(self.db, reply, APPROVED)
        self.db.refresh(play)
        self.assertEqual(play.current_actor_user_id, bob.id)
        self.assertEqual(play.current_character_id, second.id)

    def test_theatre_pdf_exports_only_approved_entries(self):
        creator = self.make_user("pdfautor")
        play = crud.create_theatre_play(self.db, creator, TheatrePlayCreate(title="Export"))
        character, _ = crud.create_theatre_character(
            self.db,
            creator,
            play,
            TheatreCharacterCreate(name="Narator", description="Spune povestea"),
        )
        character.assigned_user_id = creator.id
        self.db.commit()
        scene, _ = crud.start_theatre_scene(
            self.db,
            creator,
            play,
            TheatreSceneCreate(
                title="Scena PDF",
                first_character_id=character.id,
                content="<p>Text aprobat.</p>",
            ),
        )
        approved = scene.entries[0]
        approved.moderation_status = "approved"
        pending = models.TheatreEntry(
            play_id=play.id,
            scene_id=scene.id,
            author_id=creator.id,
            entry_type="stage_direction",
            content="<p>Text ascuns.</p>",
            position=2,
            moderation_status="pending",
        )
        self.db.add(pending)
        self.db.commit()
        self.db.refresh(scene)

        with patch.object(pdf_exporter, "render_html_to_pdf", return_value=b"%PDF-theatre") as renderer:
            pdf = pdf_exporter.render_theatre_pdf(
                play=play,
                creator=creator,
                scenes=[scene],
                page_url="https://calimara.ro/teatru/export",
            )

        html = renderer.call_args.args[0]
        self.assertEqual(pdf, b"%PDF-theatre")
        self.assertIn("Text aprobat", html)
        self.assertIn('<span class="theatre-paren">(</span>', html)
        self.assertIn('<span class="theatre-paren">)</span>', html)
        self.assertNotIn("Text ascuns", html)


if __name__ == "__main__":
    unittest.main()
