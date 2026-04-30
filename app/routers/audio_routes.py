import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from .. import audio_service, audio_storage, auth, crud, models, schemas
from ..categories import CATEGORIES
from ..database import get_db

router = APIRouter(tags=["audio"])

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/webm",
    "audio/mp4",
    "audio/x-m4a",
}


@router.get("/api/audio/postari/{post_id}", response_model=schemas.PostAudioStatus)
def get_post_audio_status(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    return audio_service.post_audio_status_payload(db, post_id, current_user)


@router.get("/api/audio/cota-conversie", response_model=schemas.AudioConversionQuota)
def get_audio_conversion_quota(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return audio_service.audio_quota_payload(db, current_user)


@router.post("/api/audio/cereri-tts", response_model=schemas.TTSConversionResponse)
def request_tts_audio(
    body: schemas.TTSConversionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        return audio_service.request_tts_for_posts(db, current_user, body.post_ids)
    except audio_service.TTSQuotaExceeded as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Limita lunară de caractere ar fi depășită. "
                f"Disponibil: {exc.remaining}, cerut: {exc.requested}."
            ),
        )
    except audio_service.TTSRequestForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except audio_service.TTSRequestInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/audio/redare/{audio_id}")
def stream_local_audio(
    audio_id: int,
    db: Session = Depends(get_db),
):
    audio = (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post))
        .filter(models.PostAudio.id == audio_id)
        .first()
    )
    if not audio or audio.status != "ready" or not audio.post or audio.post.moderation_status != "approved":
        raise HTTPException(status_code=404, detail="Audio indisponibil")
    if audio.storage_backend == "s3":
        return RedirectResponse(audio_storage.playback_url(audio))
    if audio.storage_backend != "local" or not audio.storage_key:
        raise HTTPException(status_code=404, detail="Audio indisponibil")
    path = audio_storage.local_path_for_key(audio.storage_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fișierul audio nu există")
    return FileResponse(path, media_type=audio.content_type or "audio/mpeg")


@router.get("/api/audio/colectii/{collection_id}/lista-redare", response_model=schemas.CollectionAudioPlaylist)
def get_collection_audio_playlist(
    collection_id: int,
    db: Session = Depends(get_db),
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")
    entries = crud.get_collection_entries(db, collection_id, status="accepted")
    tracks = []
    for entry in entries:
        audio = crud.get_best_audio_for_post(db, entry.post_id)
        if audio:
            db.refresh(audio)
            tracks.append(audio_service.audio_track_payload(audio))
    return {
        "collection_id": collection.id,
        "title": collection.title,
        "tracks": tracks,
    }


@router.get("/api/audio/aleatoriu", response_model=schemas.AudioTrack)
def get_random_audio(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if category and category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Categorie invalidă")
    audio = crud.get_random_ready_audio(db, category=category)
    if not audio:
        raise HTTPException(status_code=404, detail="Nu există audio disponibil")
    audio = (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        .filter(models.PostAudio.id == audio.id)
        .first()
    )
    return audio_service.audio_track_payload(audio)


@router.post("/api/postari/{post_id}/inregistrare-audio", response_model=schemas.PostAudioStatus)
async def upload_author_recording(
    post_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_author_audio_user),
):
    post = crud.get_post(db, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    if post.moderation_status != "approved":
        raise HTTPException(status_code=400, detail="Postarea trebuie aprobată înainte de încărcarea audio")

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail="Format audio neacceptat")

    max_mb = int(os.getenv("AUDIO_UPLOAD_MAX_MB", "25"))
    max_bytes = max_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Fișierul audio depășește {max_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="Fișierul audio este gol")

    audio = audio_service.create_author_recording(db, post, content, content_type)
    return audio_service.post_audio_status_payload(db, post_id, current_user)
