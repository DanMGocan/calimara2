from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import data_portability, models, schemas


class TestDataPortability:
    def setup_method(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def teardown_method(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def user(self, username, **fields):
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            avatar_seed=f"{username}-avatar",
            cover_seed=f"{username}-cover",
            **fields,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def post(self, user, title, *, slug, status="approved", view_count=0):
        post = models.Post(
            user_id=user.id,
            title=title,
            slug=slug,
            content=f"<p>{title} content</p>",
            category="poezie",
            moderation_status=status,
            view_count=view_count,
            created_at=datetime(2026, 5, 20, 10, 0, 0),
            updated_at=datetime(2026, 5, 20, 11, 0, 0),
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def test_export_includes_profile_approved_posts_metrics_and_audio_links(self):
        author = self.user(
            "portable",
            subtitle="<p>Bio</p>",
            location="Bucuresti",
            youtube_playlist_url="https://youtube.com/playlist?list=abc",
        )
        approved = self.post(author, "Approved poem", slug="approved-poem", view_count=42)
        self.post(author, "Pending poem", slug="pending-poem", status="pending")
        liker = self.user("liker")
        self.db.add(models.Like(post_id=approved.id, user_id=liker.id))
        self.db.add(models.SuperLike(post_id=approved.id, user_id=liker.id))
        self.db.add(
            models.PostAudio(
                post_id=approved.id,
                source="tts",
                status="ready",
                storage_backend="local",
                storage_key="portable/audio.mp3",
                content_type="audio/mpeg",
            )
        )
        self.db.commit()

        payload = data_portability.export_user_data(self.db, author)

        assert payload["format"] == data_portability.EXPORT_FORMAT
        assert payload["profile"]["subtitle"] == "<p>Bio</p>"
        assert len(payload["posts"]) == 1
        exported = payload["posts"][0]
        assert exported["title"] == "Approved poem"
        assert exported["metrics"]["view_count"] == 42
        assert exported["metrics"]["likes_count"] == 1
        assert exported["metrics"]["super_likes_count"] == 1
        assert exported["audio"]["playback_url"].startswith("/api/audio/redare/")

    def test_import_creates_approved_posts_preserves_snapshots_and_skips_duplicates(self):
        source = self.user("source", subtitle="<p>Source bio</p>", instagram_url="https://instagram.com/source")
        post = self.post(source, "Portable poem", slug="portable-poem", view_count=7)
        liker = self.user("source_liker")
        self.db.add(models.Like(post_id=post.id, user_id=liker.id))
        self.db.add(models.SuperLike(post_id=post.id, user_id=liker.id))
        self.db.commit()
        payload = data_portability.export_user_data(self.db, source)
        manifest = schemas.DataExportManifest.model_validate(payload)
        target = self.user("target", is_admin=True, premium_tier="free")

        first = data_portability.import_user_data(self.db, target, manifest)
        imported = self.db.query(models.Post).filter(models.Post.user_id == target.id).one()
        snapshot = self.db.query(models.ImportedPostSnapshot).filter_by(post_id=imported.id).one()

        assert first.posts_created == 1
        assert first.posts_skipped == 0
        assert imported.moderation_status == "approved"
        assert imported.view_count == 7
        assert imported.created_at == datetime(2026, 5, 20, 10, 0, 0)
        assert snapshot.imported_likes_count == 1
        assert snapshot.imported_super_likes_count == 1
        assert self.db.query(models.Like).filter(models.Like.post_id == imported.id).count() == 0
        assert self.db.query(models.SuperLike).filter(models.SuperLike.post_id == imported.id).count() == 0
        self.db.refresh(target)
        assert target.subtitle == "<p>Source bio</p>"
        assert target.instagram_url == "https://instagram.com/source"
        assert target.is_admin is True
        assert target.premium_tier == "free"

        second = data_portability.import_user_data(self.db, target, manifest)

        assert second.posts_created == 0
        assert second.posts_skipped == 1
        assert self.db.query(models.Post).filter(models.Post.user_id == target.id).count() == 1

    def test_import_own_export_skips_existing_posts_without_creating_copies(self):
        author = self.user("ownportable", subtitle="<p>Bio</p>")
        existing = self.post(author, "Existing poem", slug="existing-poem", view_count=3)
        payload = data_portability.export_user_data(self.db, author)
        manifest = schemas.DataExportManifest.model_validate(payload)

        report = data_portability.import_user_data(self.db, author, manifest)

        assert report.posts_created == 0
        assert report.posts_skipped == 1
        assert self.db.query(models.Post).filter(models.Post.user_id == author.id).count() == 1
        snapshot = self.db.query(models.ImportedPostSnapshot).filter_by(user_id=author.id).one()
        assert snapshot.post_id == existing.id
