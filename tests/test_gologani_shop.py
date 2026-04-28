import os
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import admin, crud, models, moderation, schemas


class GologaniShopTests(unittest.TestCase):
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

    def user(self, name, *, admin_user=False):
        user = models.User(
            username=name,
            email=f"{name}@example.com",
            google_id=f"google-{name}",
            is_admin=admin_user,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def post(self, user, title="Post"):
        post = models.Post(
            user_id=user.id,
            title=title,
            slug=f"{user.username}-{title}".lower(),
            content="content",
            moderation_status="pending",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def shop_item(self, slug="test-item", price=50, slot="profile_badge"):
        return crud.create_shop_item(
            self.db,
            schemas.ShopItemCreate(
                slug=slug,
                name="Test item",
                description="Test description",
                price=price,
                slot=slot,
                sort_order=1,
            ),
        )

    def test_content_reward_is_idempotent(self):
        author = self.user("author")
        post = self.post(author)
        post.moderation_status = "approved"
        self.db.commit()
        self.db.refresh(post)

        crud.award_content_approved(self.db, "post", post)
        crud.award_content_approved(self.db, "post", post)
        self.db.refresh(author)

        self.assertEqual(author.gologani_balance, 25)
        self.assertEqual(self.db.query(models.GologaniTransaction).count(), 1)

    def test_forum_reward_uses_approval_transition(self):
        author = self.user("forum_author")
        approved = SimpleNamespace(
            status=moderation.ModerationStatus.APPROVED,
            toxicity_score=0.0,
            reason="ok",
        )
        thread = crud.create_forum_thread(
            self.db,
            author,
            schemas.ForumThreadCreate(section="general", title="Atelier", content="Salut"),
        )

        crud.apply_forum_thread_moderation_result(self.db, thread, approved)
        crud.apply_forum_thread_moderation_result(self.db, thread, approved)
        self.db.refresh(author)

        self.assertEqual(author.gologani_balance, 15)
        self.assertEqual(self.db.query(models.GologaniTransaction).count(), 1)

    def test_like_and_super_like_rewards_exclude_self_and_anonymous(self):
        author = self.user("author")
        reader = self.user("reader")
        post = self.post(author)
        post.moderation_status = "approved"
        self.db.commit()

        crud.create_like(self.db, post.id, user_id=reader.id)
        crud.create_like(self.db, post.id, ip_address="127.0.0.1")
        self_like_post = self.post(author, "Self")
        self_like_post.moderation_status = "approved"
        self.db.commit()
        crud.create_like(self.db, self_like_post.id, user_id=author.id)
        crud.create_super_like(self.db, reader, post.id)

        self.db.refresh(author)
        self.db.refresh(reader)
        self.assertEqual(author.gologani_balance, 17)
        self.assertEqual(reader.gologani_balance, 6)

    def test_purchase_equip_and_unequip_flow(self):
        buyer = self.user("buyer")
        item = self.shop_item(price=120, slot="costume")
        crud.grant_gologani(
            self.db,
            user_id=buyer.id,
            amount=200,
            event_type="test_grant",
            idempotency_key="test-grant-buyer",
        )

        inventory_item = crud.purchase_shop_item(self.db, buyer, item.id)
        self.db.refresh(buyer)
        self.assertEqual(inventory_item.item_id, item.id)
        self.assertEqual(buyer.gologani_balance, 80)

        with self.assertRaises(crud.InventoryDuplicateError):
            crud.purchase_shop_item(self.db, buyer, item.id)

        equipped = crud.equip_inventory_item(self.db, buyer, item.id)
        self.assertEqual(equipped.slot, "costume")
        self.assertTrue(crud.unequip_slot(self.db, buyer, "costume"))
        self.assertFalse(crud.unequip_slot(self.db, buyer, "costume"))

    def test_purchase_rejects_insufficient_balance(self):
        buyer = self.user("buyer")
        item = self.shop_item(price=120)

        with self.assertRaises(crud.InsufficientGologaniError):
            crud.purchase_shop_item(self.db, buyer, item.id)

    def test_admin_gate_and_catalog_duplicate_slug(self):
        normal = self.user("normal")
        superuser = self.user("superuser", admin_user=True)

        with self.assertRaises(HTTPException):
            admin.require_admin(current_user=normal)
        self.assertEqual(admin.require_admin(current_user=superuser).id, superuser.id)

        self.shop_item(slug="unique-item")
        with self.assertRaises(crud.ShopItemDuplicateSlugError):
            self.shop_item(slug="unique-item")


if __name__ == "__main__":
    unittest.main()
