"""Stored media files are deleted from the server when the platform stops using them."""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import media_cleanup, models


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    audio = tmp_path / "audio"
    photos = tmp_path / "profile-media"
    audio.mkdir()
    photos.mkdir()
    monkeypatch.setenv("AUDIO_LOCAL_DIR", str(audio))
    monkeypatch.setenv("PROFILE_MEDIA_LOCAL_DIR", str(photos))
    return audio, photos


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _file(root: Path, key: str, body: bytes = b"data") -> Path:
    path = root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _user(db, name="ana", **photos):
    user = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}", **photos)
    db.add(user)
    db.commit()
    return user


def _post_with_audio(db, user, audio_root, key="posts/1/audio/tts-a.mp3"):
    post = models.Post(user_id=user.id, title="T", slug=f"{user.username}-t-{key[-6:]}", content="c")
    db.add(post)
    db.flush()
    audio = models.PostAudio(post_id=post.id, source="tts", status="ready", storage_backend="local", storage_key=key)
    db.add(audio)
    db.commit()
    return post, audio, _file(audio_root, key)


def test_deleting_a_post_deletes_its_audio_file(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    post, _, path = _post_with_audio(db, user, audio_root)

    db.delete(post)
    db.commit()

    assert not path.exists()
    assert not (audio_root / "posts").exists()  # empty folders are pruned too


def test_rollback_keeps_the_file(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    post, _, path = _post_with_audio(db, user, audio_root)

    db.delete(post)
    db.flush()
    db.rollback()
    db.commit()

    assert path.exists()


def test_deleting_an_audio_row_deletes_its_file(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    _, audio, path = _post_with_audio(db, user, audio_root)

    db.delete(audio)
    db.commit()

    assert not path.exists()


def test_replacing_audio_deletes_only_the_old_file(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    _, audio, old_path = _post_with_audio(db, user, audio_root)
    new_path = _file(audio_root, "posts/1/audio/tts-b.mp3")

    audio.storage_key = "posts/1/audio/tts-b.mp3"
    db.commit()

    assert not old_path.exists()
    assert new_path.exists()


def test_clearing_audio_storage_deletes_the_file(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    _, audio, path = _post_with_audio(db, user, audio_root)

    audio.storage_backend = None
    audio.storage_key = None
    db.commit()

    assert not path.exists()


def test_file_still_used_by_another_row_is_kept(db, dirs):
    audio_root, _ = dirs
    user = _user(db)
    post, audio, path = _post_with_audio(db, user, audio_root)
    other = models.Post(user_id=user.id, title="U", slug="ana-u", content="c")
    db.add(other)
    db.flush()
    db.add(models.PostAudio(post_id=other.id, source="tts", status="ready", storage_backend="local", storage_key=audio.storage_key))
    db.commit()

    db.delete(post)
    db.commit()

    assert path.exists()


def test_replacing_or_deleting_photos_deletes_old_files(db, dirs):
    _, photo_root = dirs
    avatar = _file(photo_root, "users/1/profile-old.webp")
    cover = _file(photo_root, "clubs/1/cover.webp")
    user = _user(db, profile_photo_storage_backend="local", profile_photo_storage_key="users/1/profile-old.webp")
    club = models.Club(owner_id=user.id, title="Club", slug="club", speciality="poezie",
                       cover_photo_storage_backend="local", cover_photo_storage_key="clubs/1/cover.webp")
    db.add(club)
    db.commit()

    new_avatar = _file(photo_root, "users/1/profile-new.webp")
    user.profile_photo_storage_key = "users/1/profile-new.webp"
    db.commit()
    assert not avatar.exists() and new_avatar.exists()

    db.delete(club)
    db.commit()
    assert not cover.exists()


def test_bulk_user_delete_with_mark_user_media(db, dirs):
    audio_root, photo_root = dirs
    avatar = _file(photo_root, "users/1/profile.webp")
    user = _user(db, profile_photo_storage_backend="local", profile_photo_storage_key="users/1/profile.webp")
    _, _, audio_path = _post_with_audio(db, user, audio_root)
    club_cover = _file(photo_root, "clubs/9/cover.webp")
    db.add(models.Club(owner_id=user.id, title="C", slug="c", speciality="poezie",
                       cover_photo_storage_backend="local", cover_photo_storage_key="clubs/9/cover.webp"))
    db.commit()
    user_id = user.id
    db.expunge_all()

    media_cleanup.mark_user_media(db, user_id)
    db.query(models.User).filter(models.User.id == user_id).delete(synchronize_session=False)
    db.commit()

    assert not avatar.exists()
    assert not audio_path.exists()
    assert not club_cover.exists()


def test_other_users_files_are_untouched(db, dirs):
    audio_root, _ = dirs
    ana = _user(db, "ana")
    ion = _user(db, "ion")
    ana_post, _, ana_path = _post_with_audio(db, ana, audio_root, "posts/1/audio/a.mp3")
    _, _, ion_path = _post_with_audio(db, ion, audio_root, "posts/2/audio/b.mp3")

    db.delete(ana_post)
    db.commit()

    assert not ana_path.exists()
    assert ion_path.exists()


def test_keys_escaping_the_media_folder_are_refused(dirs, tmp_path):
    outside = tmp_path / "keep.txt"
    outside.write_text("x")

    assert media_cleanup.delete_file("audio", "local", "../keep.txt") is False
    assert outside.exists()


def _age(path: Path, hours: float) -> None:
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def test_sweep_deletes_only_old_unreferenced_files(dirs):
    audio_root, photo_root = dirs
    used = _file(audio_root, "posts/1/used.mp3")
    old_orphan = _file(audio_root, "posts/2/orphan.mp3")
    new_orphan = _file(audio_root, "posts/3/fresh.mp3")
    keep = [_file(audio_root, f"posts/{i}/keep.mp3") for i in range(10, 14)]
    for path in (used, old_orphan, *keep):
        _age(path, 48)
    _age(new_orphan, 1)
    referenced = {"audio": {"posts/1/used.mp3", *(f"posts/{i}/keep.mp3" for i in range(10, 14))}, "profile-media": set()}

    report = media_cleanup.sweep_unreferenced_local_files(
        referenced, {"audio": audio_root, "profile-media": photo_root}
    )

    assert report["deleted"] == 1 and report["skipped_folders"] == []
    assert used.exists() and new_orphan.exists() and not old_orphan.exists()
    assert all(path.exists() for path in keep)


def test_sweep_refuses_to_empty_a_folder(dirs):
    audio_root, photo_root = dirs
    files = [_file(audio_root, f"posts/{i}/a.mp3") for i in range(10)]
    for path in files:
        _age(path, 48)

    report = media_cleanup.sweep_unreferenced_local_files(
        {"audio": set(), "profile-media": set()}, {"audio": audio_root, "profile-media": photo_root}
    )

    assert report["deleted"] == 0
    assert report["skipped_folders"] == ["audio: 10 of 10 files unreferenced"]
    assert all(path.exists() for path in files)


def test_referenced_media_keys(db, dirs):
    user = _user(db, profile_photo_storage_backend="local", profile_photo_storage_key="users/1/p.webp",
                 cover_photo_storage_backend="s3", cover_photo_storage_key="users/1/c.webp")
    post = models.Post(user_id=user.id, title="T", slug="t", content="c")
    db.add(post)
    db.flush()
    db.add(models.PostAudio(post_id=post.id, source="tts", status="ready", storage_backend="local", storage_key="posts/1/a.mp3"))
    db.commit()

    keys = media_cleanup.referenced_media_keys(db)

    assert keys == {"audio": {"posts/1/a.mp3"}, "profile-media": {"users/1/p.webp"}}
