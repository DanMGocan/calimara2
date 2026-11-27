from datetime import datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import ai_queue, data_portability, models, schemas


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

    def publish_jobs(self, post_id=None):
        query = self.db.query(models.AIJob).filter(
            models.AIJob.job_type == ai_queue.JOB_POST_PUBLISH,
            models.AIJob.target_type == "post",
        )
        if post_id is not None:
            query = query.filter(models.AIJob.target_id == post_id)
        return query.all()

    def test_export_includes_profile_and_approved_posts_without_metrics_audio_or_media(self):
        author = self.user(
            "portable",
            subtitle="<p>Bio</p>",
            location="Bucuresti",
            youtube_playlist_url="https://youtube.com/playlist?list=abc",
        )
        approved = self.post(author, "Approved poem", slug="approved-poem", view_count=42)
        self.post(author, "Pending poem", slug="pending-poem", status="pending")
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
        assert "media" not in payload
        assert len(payload["posts"]) == 1
        exported = payload["posts"][0]
        assert exported["title"] == "Approved poem"
        assert "metrics" not in exported
        assert "audio" not in exported

    def test_import_creates_new_pending_posts_queued_for_moderation_and_skips_duplicates(self):
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
        assert "moderare" in first.message
        assert imported.moderation_status == "pending"
        assert imported.view_count == 0
        assert imported.ai_critic_requested is False
        assert imported.created_at != datetime(2026, 5, 20, 10, 0, 0)
        assert imported.slug != post.slug
        jobs = self.publish_jobs(imported.id)
        assert len(jobs) == 1
        assert jobs[0].status == "pending"
        assert jobs[0].payload["imported"] is True
        assert snapshot.imported_view_count == 0
        assert snapshot.imported_likes_count == 0
        assert snapshot.imported_super_likes_count == 0
        assert snapshot.audio_playback_url is None
        assert snapshot.audio_download_url is None
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
        assert len(self.publish_jobs()) == 1

    def test_import_ignores_metrics_audio_and_media_from_crafted_or_old_files(self):
        target = self.user("crafted")
        manifest = schemas.DataExportManifest.model_validate(
            {
                "format": data_portability.EXPORT_FORMAT,
                "version": data_portability.EXPORT_VERSION,
                "export_id": "crafted-1",
                "exported_at": "2026-11-27T00:00:00Z",
                "media": {"profile_photo_url": "https://evil.example/p.png"},
                "posts": [
                    {
                        "stable_id": "crafted-post",
                        "title": "Crafted",
                        "slug": "crafted",
                        "content": "<p>Text</p>",
                        "created_at": "2031-01-01T00:00:00",
                        "metrics": {"view_count": 99999999, "likes_count": 5, "super_likes_count": 5},
                        "audio": {"playback_url": "https://evil.example/a.mp3"},
                    }
                ],
            }
        )

        report = data_portability.import_user_data(self.db, target, manifest)

        imported = self.db.query(models.Post).filter(models.Post.user_id == target.id).one()
        record = self.db.query(models.UserDataImport).filter_by(user_id=target.id).one()
        assert report.posts_created == 1
        assert imported.moderation_status == "pending"
        assert imported.view_count == 0
        assert imported.created_at.year < 2031
        assert record.media_snapshot == {}
        assert len(self.publish_jobs(imported.id)) == 1

    def test_import_keeps_profile_fields_missing_from_the_file(self):
        target = self.user("keeper", subtitle="<p>My bio</p>", location="Cluj")
        manifest = schemas.DataExportManifest.model_validate(
            {
                "export_id": "partial-1",
                "exported_at": "2026-11-27T00:00:00Z",
                "profile": {"location": "Iasi"},
            }
        )

        report = data_portability.import_user_data(self.db, target, manifest)

        self.db.refresh(target)
        assert report.profile_updated is True
        assert target.location == "Iasi"
        assert target.subtitle == "<p>My bio</p>"
        assert target.avatar_seed == "keeper-avatar"

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
        assert self.publish_jobs() == []

    def test_failed_post_is_rolled_back_without_leaving_a_pending_orphan(self):
        target = self.user("partial")
        manifest = schemas.DataExportManifest.model_validate(
            {
                "export_id": "partial-posts",
                "exported_at": "2026-11-27T00:00:00Z",
                "posts": [
                    {"stable_id": "ok-1", "title": "Bun", "content": "<p>Unu</p>"},
                    {"stable_id": "bad-2", "title": "Stricat", "content": "<p>Doi</p>"},
                    {"stable_id": "ok-3", "title": "Tot bun", "content": "<p>Trei</p>"},
                ],
            }
        )
        real_snapshot = data_portability._add_import_snapshot

        def flaky_snapshot(db, **kwargs):
            if kwargs["stable_id"] == "bad-2":
                raise RuntimeError("boom")
            return real_snapshot(db, **kwargs)

        with patch.object(data_portability, "_add_import_snapshot", side_effect=flaky_snapshot):
            report = data_portability.import_user_data(self.db, target, manifest)

        titles = sorted(p.title for p in self.db.query(models.Post).filter_by(user_id=target.id))
        assert report.posts_created == 2
        assert report.posts_failed == 1
        assert titles == ["Bun", "Tot bun"]
        assert len(self.publish_jobs()) == 2
        assert self.db.query(models.ImportedPostSnapshot).filter_by(user_id=target.id).count() == 2

    def test_manifest_rejects_more_posts_than_the_import_cap(self):
        from app.schemas.portability import MAX_IMPORT_POSTS

        posts = [
            {"stable_id": f"p-{i}", "title": f"T{i}", "content": "<p>x</p>"}
            for i in range(MAX_IMPORT_POSTS + 1)
        ]
        with pytest.raises(ValidationError, match="cel mult"):
            schemas.DataExportManifest.model_validate(
                {"export_id": "big", "exported_at": "2026-11-27T00:00:00Z", "posts": posts}
            )
        ok = schemas.DataExportManifest.model_validate(
            {"export_id": "max", "exported_at": "2026-11-27T00:00:00Z", "posts": posts[:MAX_IMPORT_POSTS]}
        )
        assert len(ok.posts) == MAX_IMPORT_POSTS
