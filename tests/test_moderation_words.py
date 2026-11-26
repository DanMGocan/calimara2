import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import local_auth, models, moderation, schemas
from app.routers import admin_routes
from app.week_util import utcnow_naive

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "20261126_moderation_words.sql"

CATEGORIES = [
    "sexual", "hate_and_discrimination", "violence_and_threats", "dangerous",
    "criminal", "selfharm", "health", "financial", "law", "pii", "jailbreaking",
]


def clean_classifier_client(test_case):
    """Mistral stub: the classifier finds nothing, and the LLM review must not run."""
    response = SimpleNamespace(
        results=[
            SimpleNamespace(
                category_scores={name: 0.0 for name in CATEGORIES},
                categories={name: False for name in CATEGORIES},
            )
        ]
    )
    return SimpleNamespace(
        classifiers=SimpleNamespace(moderate=lambda **kwargs: response),
        chat=SimpleNamespace(complete=lambda **kwargs: test_case.fail("LLM review should not run for clean text")),
    )


def seeded_words(sql: str) -> dict:
    lists = {"profanity": [], "hate_speech": []}
    for word, category in re.findall(r"\('([^']+)', '(profanity|hate_speech)'\)", sql):
        lists[category].append(word)
    return lists


class ModerationWordListTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()
        self.admin_user = models.User(
            username="admin",
            email="admin@example.com",
            password_hash=local_auth.password_hash("long-enough-password"),
            email_verified_at=utcnow_naive(),
            is_admin=True,
        )
        self.db.add(self.admin_user)
        self.db.commit()
        self.db.refresh(self.admin_user)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def seed_defaults(self):
        for category, words in moderation.default_wordlists().items():
            for word in words:
                self.db.add(models.ModerationWord(word=word, category=category))
        self.db.commit()

    def moderate(self, text):
        with patch.object(moderation, "MODERATION_ENABLED", True), patch.object(
            moderation, "client", clean_classifier_client(self)
        ):
            return moderation.moderate_post("Titlu", text, self.db)

    def add(self, word, category="profanity"):
        return admin_routes.add_moderation_word(
            schemas.AdminModerationWordCreate(word=word, category=category),
            request=None,
            db=self.db,
            current_user=self.admin_user,
        )

    def test_without_db_the_built_in_list_is_used(self):
        self.assertEqual(moderation.load_wordlists(None), moderation.default_wordlists())

    def test_seed_data_matches_built_in_list(self):
        defaults = moderation.default_wordlists()
        migration = MIGRATION.read_text(encoding="utf-8")
        self.assertEqual(seeded_words(migration[migration.index("INSERT INTO moderation_words"):]), defaults)
        schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
        schema_block = schema[schema.index("INSERT INTO moderation_words"):]
        schema_block = schema_block[:schema_block.index(";")]
        self.assertEqual(seeded_words(schema_block), defaults)

    def test_migration_is_idempotent_and_additive(self):
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS moderation_words", sql)
        self.assertIn("WHERE NOT EXISTS (SELECT 1 FROM moderation_words)", sql)
        self.assertIn("ON CONFLICT (word) DO NOTHING", sql)
        self.assertNotRegex(sql, r"(?im)^\s*(DROP|DELETE|TRUNCATE|ALTER|UPDATE)\b")

    def test_added_word_sends_clean_text_to_manual_review(self):
        self.seed_defaults()
        self.assertEqual(self.moderate("O dimineață cu ceață peste lac.").status, moderation.ModerationStatus.APPROVED)

        payload = self.add("  CEAȚĂ  ")
        self.assertIn("ceață", [item["word"] for item in payload["words"]])

        result = self.moderate("O dimineață cu Ceață peste lac.")
        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)
        self.assertTrue(result.details["romanian_signals"]["profanity_detected"])

    def test_hate_speech_category_is_used(self):
        self.add("cuvânt interzis", category="hate_speech")
        result = self.moderate("Aici apare un cuvânt interzis.")
        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)
        self.assertTrue(result.details["romanian_signals"]["hate_speech_detected"])
        self.assertFalse(result.details["romanian_signals"]["profanity_detected"])

    def test_removed_word_no_longer_flags(self):
        self.seed_defaults()
        self.assertEqual(self.moderate("Dumnezeu din poezie.").status, moderation.ModerationStatus.FLAGGED)

        word = self.db.query(models.ModerationWord).filter_by(word="dumnezeu").one()
        payload = admin_routes.delete_moderation_word(word.id, request=None, db=self.db, current_user=self.admin_user)
        self.assertNotIn("dumnezeu", [item["word"] for item in payload["words"]])

        self.assertEqual(self.moderate("Dumnezeu din poezie.").status, moderation.ModerationStatus.APPROVED)

    def test_empty_table_flags_nothing(self):
        self.assertEqual(self.moderate("Ești un idiot prost.").status, moderation.ModerationStatus.APPROVED)

    def test_add_rejects_duplicates_and_empty_words(self):
        self.add("ceață")
        with self.assertRaises(HTTPException) as duplicate:
            self.add("Ceață")
        self.assertEqual(duplicate.exception.status_code, 400)
        with self.assertRaises(HTTPException) as empty:
            self.add("  ?!  ")
        self.assertEqual(empty.exception.status_code, 400)

    def test_phrase_matches_across_line_breaks_and_extra_spaces(self):
        self.add("cuvânt   interzis", category="hate_speech")
        self.assertEqual(
            [item["word"] for item in admin_routes.get_moderation_words(db=self.db, current_user=self.admin_user)["words"]],
            ["cuvânt interzis"],
        )
        result = self.moderate("Un cuvânt\n  interzis aici.")
        self.assertEqual(result.status, moderation.ModerationStatus.FLAGGED)

    def test_cedilla_and_comma_below_letters_match_each_other(self):
        self.add("țigan")  # comma-below ț
        self.assertEqual(self.moderate("Un ţigan aici.").status, moderation.ModerationStatus.FLAGGED)  # cedilla ţ
        with self.assertRaises(HTTPException):
            self.add("ţigan")  # same word once normalized

    def test_concurrent_duplicate_insert_returns_400_not_500(self):
        self.add("ceață")
        with patch("sqlalchemy.orm.Query.first", return_value=None):
            with self.assertRaises(HTTPException) as duplicate:
                self.add("ceață")
        self.assertEqual(duplicate.exception.status_code, 400)
        self.assertEqual(self.db.query(models.ModerationWord).count(), 1)

    def test_delete_missing_word_is_404(self):
        with self.assertRaises(HTTPException) as missing:
            admin_routes.delete_moderation_word(999, request=None, db=self.db, current_user=self.admin_user)
        self.assertEqual(missing.exception.status_code, 404)

    def test_changes_are_audited(self):
        payload = self.add("ceață")
        admin_routes.delete_moderation_word(payload["words"][0]["id"], request=None, db=self.db, current_user=self.admin_user)
        actions = [row.action for row in self.db.query(models.AdminAuditLog).order_by(models.AdminAuditLog.id).all()]
        self.assertEqual(actions, ["moderation_word_create", "moderation_word_delete"])

    def test_missing_table_falls_back_to_built_in_list(self):
        models.ModerationWord.__table__.drop(self.engine)
        self.assertEqual(moderation.load_wordlists(self.db), moderation.default_wordlists())
        payload = admin_routes.get_moderation_words(db=self.db, current_user=self.admin_user)
        self.assertFalse(payload["available"])
        self.assertEqual(payload["words"], [])
        self.assertEqual(self.moderate("Ești un idiot.").status, moderation.ModerationStatus.FLAGGED)
        models.ModerationWord.__table__.create(self.engine)


if __name__ == "__main__":
    unittest.main()
