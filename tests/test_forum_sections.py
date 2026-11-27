import os
import unittest
from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import crud, models, moderation, schemas
from app.routers import forum_admin_routes, forum_routes


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1234)})


class ForumSectionsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)()
        self.approved = SimpleNamespace(status=moderation.ModerationStatus.APPROVED, toxicity_score=0.0, reason="ok")
        self.member = self.user("membru")
        self.other = self.user("cititor")
        self.mod = self.user("moderator", is_moderator=True)
        self.admin = self.user("admin", is_admin=True)

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # helpers -------------------------------------------------------------

    def user(self, name, *, is_admin=False, is_moderator=False):
        user = models.User(
            username=name,
            email=f"{name}@example.com",
            google_id=f"google-{name}",
            is_admin=is_admin,
            is_moderator=is_moderator,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def thread(self, author=None, section="general", title="Discuție", approve=True):
        thread = crud.create_forum_thread(
            self.db,
            author or self.member,
            schemas.ForumThreadCreate(section=section, title=title, content="<p>Conținut</p>"),
        )
        if approve:
            crud.apply_forum_thread_moderation_result(self.db, thread, self.approved)
        return thread

    def reply(self, thread, author=None, approve=True):
        reply, error = crud.create_forum_reply(
            self.db, author or self.other, thread, schemas.ForumReplyCreate(content="<p>Răspuns</p>")
        )
        self.assertIsNone(error)
        if approve:
            crud.apply_forum_reply_moderation_result(self.db, reply, self.approved)
        return reply

    # sections ------------------------------------------------------------

    def test_default_sections_are_seeded_in_order_with_rules(self):
        sections = crud.list_forum_sections(self.db)
        self.assertEqual([s.slug for s in sections], ["anunturi", "general", "poezie", "proza_scurta"])
        announcements = sections[0]
        self.assertTrue(announcements.staff_only)
        self.assertTrue(announcements.is_featured)
        # Seeding is idempotent.
        crud.ensure_default_forum_sections(self.db)
        self.assertEqual(self.db.query(models.ForumSection).count(), 4)

    def test_sections_api_reports_counts_last_post_and_permissions(self):
        thread = self.thread(title="Prima")
        reply = self.reply(thread)
        payload = forum_routes.list_forum_sections_api(db=self.db, current_user=self.member)
        by_key = {item["key"]: item for item in payload["sections"]}
        self.assertEqual(by_key["general"]["thread_count"], 1)
        self.assertEqual(by_key["general"]["reply_count"], 1)
        self.assertEqual(by_key["general"]["last_thread"]["slug"], thread.slug)
        self.assertEqual(by_key["general"]["last_thread"]["last_post"]["reply_id"], reply.id)
        self.assertEqual(by_key["general"]["last_thread"]["last_post"]["author"]["username"], "cititor")
        self.assertTrue(by_key["general"]["can_post"])
        self.assertFalse(by_key["anunturi"]["can_post"])
        self.assertIsNone(by_key["poezie"]["last_thread"])
        mod_payload = forum_routes.list_forum_sections_api(db=self.db, current_user=self.mod)
        self.assertTrue({item["key"]: item for item in mod_payload["sections"]}["anunturi"]["can_post"])

    def test_create_section_generates_unique_slug_and_rejects_taken_slug(self):
        first, error = crud.create_forum_section(self.db, self.admin, schemas.ForumSectionCreate(name="Atelier de proză"))
        self.assertIsNone(error)
        self.assertEqual(first.slug, "atelier-de-proza")
        self.assertEqual(first.position, 4)
        second, error = crud.create_forum_section(self.db, self.admin, schemas.ForumSectionCreate(name="Atelier de proză"))
        self.assertIsNone(error)
        self.assertEqual(second.slug, "atelier-de-proza-2")
        _, error = crud.create_forum_section(self.db, self.admin, schemas.ForumSectionCreate(name="Altul", slug="general"))
        self.assertEqual(error, "slug_taken")

    def test_section_schema_rejects_bad_slug(self):
        with self.assertRaises(ValueError):
            schemas.ForumSectionCreate(name="Ok", slug="Nu e bun!")
        with self.assertRaises(ValueError):
            schemas.ForumSectionCreate(name="   ")

    def test_renaming_section_slug_moves_its_threads(self):
        thread = self.thread(section="poezie")
        section = crud.get_forum_section_by_slug(self.db, "poezie")
        updated, error = crud.update_forum_section(
            self.db, section, schemas.ForumSectionUpdate(slug="versuri", name="Versuri", description="")
        )
        self.assertIsNone(error)
        self.assertEqual(updated.slug, "versuri")
        self.assertIsNone(updated.description)
        self.db.refresh(thread)
        self.assertEqual(thread.section, "versuri")
        _, error = crud.update_forum_section(self.db, updated, schemas.ForumSectionUpdate(slug="general"))
        self.assertEqual(error, "slug_taken")

    def test_reorder_puts_listed_sections_first(self):
        sections = crud.list_forum_sections(self.db)
        ids = {s.slug: s.id for s in sections}
        reordered = crud.reorder_forum_sections(self.db, [ids["poezie"], ids["anunturi"], 999999])
        self.assertEqual([s.slug for s in reordered], ["poezie", "anunturi", "general", "proza_scurta"])

    def test_staff_only_section_blocks_members_from_new_threads_but_not_replies(self):
        with self.assertRaises(crud.ForumSectionError) as raised:
            self.thread(author=self.member, section="anunturi")
        self.assertEqual(raised.exception.code, "staff_only")
        announcement = self.thread(author=self.mod, section="anunturi")
        self.reply(announcement, author=self.member)

    def test_archived_section_blocks_members_but_not_moderators(self):
        thread = self.thread(section="poezie")
        section = crud.get_forum_section_by_slug(self.db, "poezie")
        crud.update_forum_section(self.db, section, schemas.ForumSectionUpdate(is_archived=True))
        with self.assertRaises(crud.ForumSectionError) as raised:
            self.thread(section="poezie")
        self.assertEqual(raised.exception.code, "archived")
        _, error = crud.create_forum_reply(self.db, self.other, thread, schemas.ForumReplyCreate(content="<p>Nu</p>"))
        self.assertEqual(error, "archived")
        _, error = crud.create_forum_reply(self.db, self.mod, thread, schemas.ForumReplyCreate(content="<p>Da</p>"))
        self.assertIsNone(error)

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(crud.ForumSectionError) as raised:
            self.thread(section="nu-exista")
        self.assertEqual(raised.exception.code, "invalid_section")

    def test_delete_section_requires_target_when_not_empty_and_keeps_last_section(self):
        thread = self.thread(section="poezie")
        poezie = crud.get_forum_section_by_slug(self.db, "poezie")
        general = crud.get_forum_section_by_slug(self.db, "general")
        self.assertEqual(crud.delete_forum_section(self.db, poezie), (0, "not_empty"))
        self.assertEqual(crud.delete_forum_section(self.db, poezie, poezie), (0, "same_section"))
        self.assertEqual(crud.delete_forum_section(self.db, poezie, general), (1, None))
        self.db.refresh(thread)
        self.assertEqual(thread.section, "general")
        self.assertIsNone(crud.get_forum_section_by_slug(self.db, "poezie"))
        for slug in ("anunturi", "proza_scurta"):
            self.assertEqual(crud.delete_forum_section(self.db, crud.get_forum_section_by_slug(self.db, slug)), (0, None))
        self.assertEqual(crud.delete_forum_section(self.db, general), (0, "last_section"))

    # thread & reply moderation ------------------------------------------

    def test_pin_lock_move_record_who_and_when(self):
        thread = self.thread()
        _, error = crud.update_forum_thread_state(self.db, self.member, thread, "pin")
        self.assertEqual(error, "not_allowed")
        updated, error = crud.update_forum_thread_state(self.db, self.mod, thread, "pin")
        self.assertIsNone(error)
        self.assertTrue(updated.is_pinned)
        self.assertEqual(updated.pinned_by, self.mod.id)
        self.assertIsNotNone(updated.pinned_at)
        updated, _ = crud.update_forum_thread_state(self.db, self.mod, thread, "lock")
        self.assertEqual(updated.locked_by, self.mod.id)
        updated, _ = crud.update_forum_thread_state(self.db, self.mod, thread, "unpin")
        self.assertFalse(updated.is_pinned)
        self.assertIsNone(updated.pinned_by)
        _, error = crud.update_forum_thread_state(self.db, self.mod, thread, "move", "nu-exista")
        self.assertEqual(error, "invalid_section")
        updated, error = crud.update_forum_thread_state(self.db, self.mod, thread, "move", "poezie")
        self.assertIsNone(error)
        self.assertEqual(updated.section, "poezie")

    def test_move_via_route_and_bad_section_is_400(self):
        thread = self.thread()
        payload = forum_routes.update_forum_thread_state_api(
            thread.id, schemas.ForumThreadModerationAction(action="move", section="proza_scurta"), db=self.db, current_user=self.mod
        )
        self.assertEqual(payload["section"], "proza_scurta")
        self.assertEqual(payload["section_label"], "Proză scurtă")
        with self.assertRaises(HTTPException) as raised:
            forum_routes.update_forum_thread_state_api(
                thread.id, schemas.ForumThreadModerationAction(action="move", section="lipsa"), db=self.db, current_user=self.mod
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_reply_pinning_requires_moderator_and_approved_reply(self):
        thread = self.thread()
        pending = self.reply(thread, approve=False)
        approved = self.reply(thread)
        self.assertEqual(crud.update_forum_reply_state(self.db, self.member, approved, "pin")[1], "not_allowed")
        self.assertEqual(crud.update_forum_reply_state(self.db, self.mod, pending, "pin")[1], "not_approved")
        payload = forum_routes.update_forum_reply_state_api(
            approved.id, schemas.ForumReplyModerationAction(action="pin"), db=self.db, current_user=self.mod
        )
        self.assertTrue(payload["is_pinned"])
        detail = forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)
        self.assertEqual([item["id"] for item in detail["pinned_replies"]], [approved.id])
        self.assertTrue(detail["replies"][1]["is_pinned"])
        self.assertFalse(detail["can_moderate"])
        self.assertTrue(detail["can_reply"])

    def test_admin_bulk_actions(self):
        a = self.thread(title="A")
        b = self.thread(title="B")
        self.assertEqual(crud.bulk_update_forum_threads(self.db, self.member, [a.id], "pin"), (0, "not_allowed"))
        self.assertEqual(crud.bulk_update_forum_threads(self.db, self.admin, [a.id, b.id, 999], "lock"), (2, None))
        self.assertEqual(crud.bulk_update_forum_threads(self.db, self.admin, [a.id], "move", "lipsa"), (0, "invalid_section"))
        self.assertEqual(crud.bulk_update_forum_threads(self.db, self.admin, [a.id, b.id], "move", "poezie"), (2, None))
        self.db.refresh(a)
        self.assertTrue(a.is_locked)
        self.assertEqual(a.section, "poezie")
        self.assertEqual(crud.bulk_update_forum_threads(self.db, self.admin, [a.id], "delete"), (1, None))
        self.assertIsNone(crud.get_forum_thread(self.db, a.id))

    # listing, pagination, reads ------------------------------------------

    def test_section_listing_splits_pinned_and_paginates(self):
        threads = [self.thread(title=f"Fir {index}") for index in range(5)]
        crud.update_forum_thread_state(self.db, self.mod, threads[0], "pin")
        self.thread(section="poezie", title="Altă secțiune")
        listing = forum_routes.list_forum_threads_api(section="general", per_page=2, page=1, db=self.db, current_user=self.member)
        self.assertEqual([item["id"] for item in listing["pinned"]], [threads[0].id])
        self.assertEqual(listing["total"], 4)
        self.assertEqual(listing["pages"], 2)
        self.assertEqual(len(listing["threads"]), 2)
        self.assertNotIn(threads[0].id, [item["id"] for item in listing["threads"]])
        self.assertEqual(listing["section"]["key"], "general")
        page_two = forum_routes.list_forum_threads_api(section="general", per_page=2, page=9, db=self.db, current_user=self.member)
        self.assertEqual(page_two["page"], 2)
        # The cross-section feed is a single list, not split by pins.
        feed = forum_routes.list_forum_threads_api(db=self.db, current_user=self.member)
        self.assertEqual(feed["pinned"], [])
        self.assertEqual(feed["total"], 6)
        with self.assertRaises(HTTPException):
            forum_routes.list_forum_threads_api(section="lipsa", db=self.db, current_user=self.member)

    def test_sort_by_replies(self):
        quiet = self.thread(title="Liniștit")
        busy = self.thread(title="Animat")
        self.reply(busy)
        self.reply(busy)
        listing = forum_routes.list_forum_threads_api(section="general", sort="replies", db=self.db, current_user=self.member)
        self.assertEqual([item["id"] for item in listing["threads"]], [busy.id, quiet.id])
        self.assertEqual(listing["threads"][0]["reply_count"], 2)

    def test_thread_detail_paginates_numbers_and_jumps_to_reply(self):
        thread = self.thread()
        replies = [self.reply(thread) for _ in range(forum_routes.REPLIES_PER_PAGE + 3)]
        first = forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)
        self.assertEqual(first["reply_total"], len(replies))
        self.assertEqual(first["reply_pages"], 2)
        self.assertEqual(first["reply_page"], 1)
        self.assertEqual(first["replies"][0]["number"], 1)
        jumped = forum_routes.get_forum_thread_api(thread.slug, reply=replies[-1].id, db=self.db, current_user=self.member)
        self.assertEqual(jumped["reply_page"], 2)
        self.assertEqual(jumped["replies"][-1]["id"], replies[-1].id)
        self.assertEqual(jumped["replies"][-1]["number"], len(replies))
        clamped = forum_routes.get_forum_thread_api(thread.slug, page=50, db=self.db, current_user=self.member)
        self.assertEqual(clamped["reply_page"], 2)

    def test_views_count_unique_readers_and_new_replies_are_flagged(self):
        thread = self.thread(author=self.member)
        forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)
        self.db.refresh(thread)
        self.assertEqual(thread.view_count, 0)  # the author's own visits do not count
        detail = forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.other)
        self.assertEqual(detail["view_count"], 1)
        forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.other)
        self.db.refresh(thread)
        self.assertEqual(thread.view_count, 1)
        self.assertEqual(self.db.query(models.ForumThreadRead).count(), 2)

        listing = forum_routes.list_forum_threads_api(section="general", db=self.db, current_user=self.member)
        self.assertFalse(listing["threads"][0]["has_new_replies"])
        # New activity after the member's last visit.
        self.reply(thread, author=self.other)
        thread.last_activity_at = thread.last_activity_at + timedelta(minutes=5)
        self.db.commit()
        listing = forum_routes.list_forum_threads_api(section="general", db=self.db, current_user=self.member)
        self.assertTrue(listing["threads"][0]["has_new_replies"])
        forum_routes.get_forum_thread_api(thread.slug, db=self.db, current_user=self.member)
        listing = forum_routes.list_forum_threads_api(section="general", db=self.db, current_user=self.member)
        self.assertFalse(listing["threads"][0]["has_new_replies"])

    # admin routes ----------------------------------------------------------

    def test_admin_section_routes_and_audit_log(self):
        created = forum_admin_routes.admin_create_forum_section(
            schemas.ForumSectionCreate(name="Traduceri", description="Despre traduceri", staff_only=True),
            _request(),
            db=self.db,
            current_user=self.admin,
        )
        self.assertEqual(created["key"], "traduceri")
        self.assertTrue(created["staff_only"])
        with self.assertRaises(HTTPException) as raised:
            forum_admin_routes.admin_create_forum_section(
                schemas.ForumSectionCreate(name="Dublură", slug="traduceri"), _request(), db=self.db, current_user=self.admin
            )
        self.assertEqual(raised.exception.status_code, 409)

        updated = forum_admin_routes.admin_update_forum_section(
            created["id"], schemas.ForumSectionUpdate(is_archived=True), _request(), db=self.db, current_user=self.admin
        )
        self.assertTrue(updated["is_archived"])

        self.thread(section="poezie")
        poezie = crud.get_forum_section_by_slug(self.db, "poezie")
        with self.assertRaises(HTTPException) as raised:
            forum_admin_routes.admin_delete_forum_section(poezie.id, _request(), move_to=None, db=self.db, current_user=self.admin)
        self.assertEqual(raised.exception.status_code, 409)
        result = forum_admin_routes.admin_delete_forum_section(
            poezie.id, _request(), move_to="general", db=self.db, current_user=self.admin
        )
        self.assertEqual(result["moved_threads"], 1)
        self.assertNotIn("poezie", [item["key"] for item in result["sections"]])

        listing = forum_admin_routes.admin_list_forum_sections(db=self.db, current_user=self.admin)
        general = next(item for item in listing["sections"] if item["key"] == "general")
        self.assertEqual(general["total_thread_count"], 1)

        actions = [row.action for row in self.db.query(models.AdminAuditLog).all()]
        self.assertIn("forum_section_create", actions)
        self.assertIn("forum_section_update", actions)
        self.assertIn("forum_section_delete", actions)

    def test_admin_thread_listing_filters_and_bulk_route(self):
        visible = self.thread(title="Vizibil")
        pending = self.thread(title="În așteptare", approve=False)
        listing = forum_admin_routes.admin_list_forum_threads(status="pending", db=self.db, current_user=self.admin)
        self.assertEqual([item["id"] for item in listing["threads"]], [pending.id])
        result = forum_admin_routes.admin_bulk_forum_thread_action(
            schemas.AdminForumThreadBulkAction(thread_ids=[visible.id], action="pin"), _request(), db=self.db, current_user=self.admin
        )
        self.assertEqual(result["affected"], 1)
        pinned = forum_admin_routes.admin_list_forum_threads(pinned=True, db=self.db, current_user=self.admin)
        self.assertEqual([item["id"] for item in pinned["threads"]], [visible.id])
        with self.assertRaises(HTTPException):
            forum_admin_routes.admin_list_forum_threads(status="nimic", db=self.db, current_user=self.admin)


if __name__ == "__main__":
    unittest.main()
