import os
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import crud, models, schemas
from app.routers import club_routes


class ClubFeatureTests(unittest.TestCase):
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

    def make_user(self, username: str, *, admin: bool = False, premium_tier: str = "free") -> models.User:
        is_premium = premium_tier != "free"
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            google_id=f"google-{username}",
            avatar_seed=f"{username}-seed",
            is_admin=admin,
            premium_tier=premium_tier,
            premium_period_start=(
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
            ) if is_premium else None,
            premium_until=(
                datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
            ) if is_premium else None,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def make_club(self, owner: models.User, title: str, *, join_policy: str = "private") -> models.Club:
        payload = schemas.ClubCreate(
            title=title,
            speciality="poezie",
            description=f"Descriere {title}",
            theme="atelier",
            join_policy=join_policy,
        )
        club = crud.create_club(self.db, owner, payload)
        self.db.refresh(club)
        return club

    def make_post(self, owner: models.User, club: models.Club) -> models.Post:
        post = models.Post(
            user_id=owner.id,
            title="Poem de atelier",
            slug="poem-de-atelier",
            content="versuri",
            category=club.speciality,
            moderation_status="approved",
            theme_analysis_status="completed",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_create_one_club_per_user_and_searches_description(self):
        owner = self.make_user("owner")
        club = club_routes.create_club_api(
            schemas.ClubCreate(
                title="Atelierul Umbrelor",
                speciality="poezie",
                description="feedback pe sonete lungi",
                join_policy="closed",
            ),
            db=self.db,
            current_user=owner,
        )

        self.assertEqual(club["join_policy"], "closed")
        self.assertEqual(club["my_role"], "owner")
        self.assertIn("api.dicebear.com/7.x/shapes/svg", club["avatar_url"])
        self.assertIn("api.dicebear.com/7.x/shapes/svg", club["cover_url"])

        with self.assertRaises(HTTPException) as duplicate:
            club_routes.create_club_api(
                schemas.ClubCreate(title="Al doilea club", speciality="poezie"),
                db=self.db,
                current_user=owner,
            )
        self.assertEqual(duplicate.exception.status_code, 409)

        result = club_routes.list_clubs_api(q="sonete", db=self.db, current_user=owner)
        self.assertEqual([item["title"] for item in result["clubs"]], ["Atelierul Umbrelor"])

    def test_join_policies_and_member_only_detail(self):
        private_owner = self.make_user("privateowner")
        open_owner = self.make_user("openowner")
        closed_owner = self.make_user("closedowner")
        applicant = self.make_user("applicant")
        private_club = self.make_club(private_owner, "Club Privat", join_policy="private")
        open_club = self.make_club(open_owner, "Club Deschis", join_policy="open")
        closed_club = self.make_club(closed_owner, "Club Închis", join_policy="closed")

        with self.assertRaises(HTTPException) as private_detail:
            club_routes.get_club_api(private_club.slug, db=self.db, current_user=applicant)
        self.assertEqual(private_detail.exception.status_code, 403)

        with self.assertRaises(HTTPException) as missing_text:
            club_routes.apply_to_club_api(
                private_club.id,
                schemas.ClubJoinApplyRequest(application_text=""),
                db=self.db,
                current_user=applicant,
            )
        self.assertEqual(missing_text.exception.status_code, 422)

        request_payload = club_routes.apply_to_club_api(
            private_club.id,
            schemas.ClubJoinApplyRequest(application_text="Vreau feedback pe poeme."),
            db=self.db,
            current_user=applicant,
        )
        self.assertEqual(request_payload["application_text"], "Vreau feedback pe poeme.")

        request = crud.get_club_join_request(self.db, request_payload["id"])
        club_routes.respond_club_request_api(
            private_club.id,
            request.id,
            schemas.ClubJoinRespondRequest(action="approve"),
            db=self.db,
            current_user=private_owner,
        )
        detail = club_routes.get_club_api(private_club.slug, db=self.db, current_user=applicant)
        self.assertEqual(detail["my_role"], "member")

        open_join = club_routes.apply_to_club_api(
            open_club.id,
            schemas.ClubJoinApplyRequest(),
            db=self.db,
            current_user=applicant,
        )
        self.assertEqual(open_join["status"], "joined")

        with self.assertRaises(HTTPException) as closed_join:
            club_routes.apply_to_club_api(
                closed_club.id,
                schemas.ClubJoinApplyRequest(application_text="Invită-mă."),
                db=self.db,
                current_user=applicant,
            )
        self.assertEqual(closed_join.exception.status_code, 403)

    def test_board_threads_admin_visibility_notifications_and_achievements(self):
        owner = self.make_user("boardowner")
        member = self.make_user("boardmember")
        admin = self.make_user("siteadmin", admin=True)
        club = self.make_club(owner, "Tabla Poeților", join_policy="private")
        self.db.add(models.ClubMember(club_id=club.id, user_id=member.id, role="member"))
        self.db.commit()

        first = club_routes.post_club_board_message_api(
            club.id,
            schemas.ClubBoardMessageCreate(title="Primul atelier", content="Textul de lucru"),
            db=self.db,
            current_user=owner,
        )
        self.assertEqual(first["title"], "Primul atelier")
        self.assertIsNotNone(crud.get_notifications_for_user(self.db, member.id)[0])
        self.assertTrue(
            any(item.key == "atelier_deschis" for item in crud.list_club_achievements(self.db, club.id))
        )

        for index in range(24):
            club_routes.post_club_board_message_api(
                club.id,
                schemas.ClubBoardMessageCreate(parent_id=first["id"], content=f"Răspuns {index}"),
                db=self.db,
                current_user=member if index % 2 else owner,
            )
        self.assertTrue(
            any(item.key == "dialog_viu" for item in crud.list_club_achievements(self.db, club.id))
        )

        admin_detail = club_routes.get_club_api(club.slug, db=self.db, current_user=admin)
        self.assertTrue(admin_detail["viewer_is_site_admin"])
        self.assertFalse(admin_detail["can_post"])
        board = club_routes.list_club_board_api(club.id, db=self.db, current_user=admin)
        self.assertEqual(board["messages"][0]["title"], "Primul atelier")

        with self.assertRaises(HTTPException) as admin_post:
            club_routes.post_club_board_message_api(
                club.id,
                schemas.ClubBoardMessageCreate(title="Admin", content="Nu sunt membru"),
                db=self.db,
                current_user=admin,
            )
        self.assertEqual(admin_post.exception.status_code, 403)

        club_routes.delete_club_board_message_api(
            club.id,
            first["id"],
            db=self.db,
            current_user=admin,
        )
        self.assertEqual(crud.count_club_board_messages(self.db, club.id), 0)

    def test_featured_work_unlocks_club_achievement(self):
        owner = self.make_user("featuredowner")
        club = self.make_club(owner, "Creații", join_policy="private")
        post = self.make_post(owner, club)

        featured = club_routes.set_club_featured_api(
            club.id,
            schemas.ClubFeaturedSetRequest(post_id=post.id),
            db=self.db,
            current_user=owner,
        )

        self.assertEqual(featured["post_id"], post.id)
        self.assertTrue(
            any(item.key == "creatia_saptamanii" for item in crud.list_club_achievements(self.db, club.id))
        )
