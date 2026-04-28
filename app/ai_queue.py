import hashlib
import logging
import socket
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from . import ai_critic, audio_service, category_classifier, crud, models, moderation, theme_analysis

logger = logging.getLogger(__name__)

JOB_POST_PUBLISH = "post_publish"
JOB_COMMENT_MODERATION = "comment_moderation"
JOB_FORUM_THREAD_MODERATION = "forum_thread_moderation"
JOB_FORUM_REPLY_MODERATION = "forum_reply_moderation"
JOB_TTS_AUDIO = "tts_audio_generation"
JOB_AUTHOR_AUDIO = "author_audio_moderation"
JOB_THEME_ANALYSIS = "post_theme_analysis"
JOB_AI_CRITIC = "post_ai_critic"


def worker_id() -> str:
    return f"{socket.gethostname()}-{uuid4().hex[:8]}"


def _content_hash(*parts: str | None) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update((part or "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _post_hash(post: models.Post) -> str:
    return _content_hash(post.title, post.content)


def _post_matches_job(post: models.Post, job: models.AIJob) -> bool:
    expected = (job.payload or {}).get("content_hash")
    return not expected or expected == _post_hash(post)


def enqueue_post_publish_job(
    db: Session,
    post: models.Post,
    *,
    ai_critic_requested: bool | None = None,
) -> models.AIJob:
    if ai_critic_requested is not None:
        post.ai_critic_requested = bool(ai_critic_requested)
        db.commit()
        db.refresh(post)
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_POST_PUBLISH,
        target_type="post",
        target_id=post.id,
        payload={"content_hash": _post_hash(post)},
        max_attempts=3,
        dedupe=False,
    )


def enqueue_comment_moderation_job(db: Session, comment: models.Comment) -> models.AIJob:
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_COMMENT_MODERATION,
        target_type="comment",
        target_id=comment.id,
        payload={"content_hash": _content_hash(comment.content)},
        max_attempts=3,
    )


def enqueue_forum_thread_moderation_job(db: Session, thread: models.ForumThread) -> models.AIJob:
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_FORUM_THREAD_MODERATION,
        target_type="forum_thread",
        target_id=thread.id,
        payload={"content_hash": _content_hash(thread.title, thread.content)},
        max_attempts=3,
    )


def enqueue_forum_reply_moderation_job(db: Session, reply: models.ForumReply) -> models.AIJob:
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_FORUM_REPLY_MODERATION,
        target_type="forum_reply",
        target_id=reply.id,
        payload={"content_hash": _content_hash(reply.content)},
        max_attempts=3,
    )


def enqueue_tts_audio_job(db: Session, audio: models.PostAudio) -> models.AIJob:
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_TTS_AUDIO,
        target_type="audio",
        target_id=audio.id,
        payload={},
        max_attempts=2,
    )


def enqueue_author_audio_moderation_job(db: Session, audio: models.PostAudio) -> models.AIJob:
    return crud.enqueue_ai_job(
        db,
        job_type=JOB_AUTHOR_AUDIO,
        target_type="audio",
        target_id=audio.id,
        payload={},
        max_attempts=3,
    )


def enqueue_post_approval_jobs(db: Session, post: models.Post) -> None:
    if post.moderation_status != "approved":
        return
    crud.enqueue_ai_job(
        db,
        job_type=JOB_THEME_ANALYSIS,
        target_type="post",
        target_id=post.id,
        payload={"content_hash": _post_hash(post)},
        max_attempts=2,
    )
    if post.ai_critic_requested:
        crud.enqueue_ai_job(
            db,
            job_type=JOB_AI_CRITIC,
            target_type="post",
            target_id=post.id,
            payload={"content_hash": _post_hash(post)},
            max_attempts=2,
        )

def process_ai_jobs(db: Session, *, limit: int = 10, worker: str | None = None) -> int:
    claimed = crud.claim_pending_ai_jobs(db, limit=limit, worker_id=worker or worker_id())
    for job in claimed:
        process_claimed_job(db, job)
    return len(claimed)


def process_claimed_job(db: Session, job: models.AIJob) -> None:
    try:
        handler = _HANDLERS[job.job_type]
    except KeyError:
        crud.fail_ai_job(db, job, f"Unknown AI job type: {job.job_type}", retry=False)
        return

    try:
        handler(db, job)
        crud.complete_ai_job(db, job)
    except Exception as exc:
        logger.exception("AI job %s (%s) failed", job.id, job.job_type)
        job_id = job.id
        final_attempt = int(job.attempts or 0) >= int(job.max_attempts or 1)
        try:
            db.rollback()
        except Exception:
            logger.exception("Rollback failed after AI job error")
        job = db.query(models.AIJob).filter(models.AIJob.id == job_id).first()
        if not job:
            return
        if final_attempt:
            _finalize_moderation_failure(db, job, exc)
            crud.fail_ai_job(db, job, str(exc), retry=False)
        else:
            crud.fail_ai_job(db, job, str(exc), retry=True)


def _classify_post(post: models.Post) -> str:
    try:
        return category_classifier.classify_post(post.title, post.content)
    except Exception as exc:
        logger.error("Category classification failed for post %s: %s", post.id, exc)
        return post.category or "proza_scurta"


def _handle_post_publish(db: Session, job: models.AIJob) -> None:
    post = crud.get_post(db, job.target_id)
    if not post or not _post_matches_job(post, job):
        return
    if post.moderation_status != "pending":
        if post.moderation_status == "approved":
            enqueue_post_approval_jobs(db, post)
        return

    post.category = _classify_post(post)
    result = moderation.moderate_post_with_logging(
        post.title, post.content, post.id, post.user_id, db
    )
    post.moderation_status = result.status.value
    post.toxicity_score = result.toxicity_score
    post.moderation_reason = result.reason
    db.commit()
    db.refresh(post)

    if post.moderation_status == "flagged":
        crud.create_notification(
            db=db,
            user_id=post.user_id,
            notif_type="moderation_queue",
            title="Postare în curs de moderare",
            message=f"Postarea '{post.title}' a fost trimisă pentru revizuire manuală.",
            link=None,
        )
    elif post.moderation_status == "approved":
        crud.award_content_approved(db, "post", post)
        enqueue_post_approval_jobs(db, post)


def _handle_comment_moderation(db: Session, job: models.AIJob) -> None:
    comment = (
        db.query(models.Comment)
        .options(joinedload(models.Comment.post))
        .filter(models.Comment.id == job.target_id)
        .first()
    )
    if not comment or comment.moderation_status != "pending":
        return
    result = moderation.moderate_comment_with_logging(
        comment.content, comment.id, comment.user_id, db
    )
    comment.moderation_status = result.status.value
    comment.toxicity_score = result.toxicity_score
    comment.moderation_reason = result.reason
    comment.approved = result.status.value == "approved"
    db.commit()
    db.refresh(comment)

    if comment.moderation_status == "flagged" and comment.user_id:
        crud.create_notification(
            db=db,
            user_id=comment.user_id,
            notif_type="moderation_queue",
            title="Comentariu în curs de moderare",
            message=f"Comentariul tău la postarea '{comment.post.title if comment.post else ''}' a fost trimis pentru revizuire manuală.",
            link=f"/piese/{comment.post.slug}" if comment.post else None,
        )
    elif comment.moderation_status == "approved":
        crud.award_content_approved(db, "comment", comment)


def _handle_forum_thread_moderation(db: Session, job: models.AIJob) -> None:
    thread = crud.get_forum_thread(db, job.target_id)
    if not thread or thread.moderation_status != "pending":
        return
    result = moderation.moderate_forum_thread_with_logging(
        thread.title, thread.content, thread.id, thread.author_id, db
    )
    thread = crud.apply_forum_thread_moderation_result(db, thread, result)
    if thread.moderation_status == "flagged":
        crud.create_notification(
            db=db,
            user_id=thread.author_id,
            notif_type="moderation_queue",
            title="Discuție în curs de moderare",
            message=f"Discuția „{thread.title}\" a fost trimisă pentru revizuire manuală.",
            link=None,
            extra_data={"thread_id": thread.id},
        )


def _handle_forum_reply_moderation(db: Session, job: models.AIJob) -> None:
    reply = (
        db.query(models.ForumReply)
        .options(joinedload(models.ForumReply.thread))
        .filter(models.ForumReply.id == job.target_id)
        .first()
    )
    if not reply or reply.moderation_status != "pending":
        return
    result = moderation.moderate_forum_reply_with_logging(
        reply.content, reply.id, reply.author_id, db
    )
    reply = crud.apply_forum_reply_moderation_result(db, reply, result)
    if reply.moderation_status == "flagged":
        crud.create_notification(
            db=db,
            user_id=reply.author_id,
            notif_type="moderation_queue",
            title="Răspuns în curs de moderare",
            message=f"Răspunsul tău în „{reply.thread.title if reply.thread else ''}\" a fost trimis pentru revizuire manuală.",
            link=None,
            extra_data={"thread_id": reply.thread_id, "reply_id": reply.id},
        )


def _handle_tts_audio(db: Session, job: models.AIJob) -> None:
    audio = db.query(models.PostAudio).filter(models.PostAudio.id == job.target_id).first()
    if not audio or audio.status in ("ready", "flagged", "rejected", "cancelled"):
        return
    if audio.requester_user_id is None:
        audio_service.generate_tts_audio(db, audio)
        return
    audio_service.generate_tts_audio(db, audio)


def _handle_author_audio(db: Session, job: models.AIJob) -> None:
    audio = db.query(models.PostAudio).filter(models.PostAudio.id == job.target_id).first()
    if not audio or audio.status in ("ready", "flagged", "rejected"):
        return
    audio_service.process_author_recording(db, audio)


def _handle_theme_analysis(db: Session, job: models.AIJob) -> None:
    post = crud.get_post(db, job.target_id)
    if not post or post.moderation_status != "approved" or not _post_matches_job(post, job):
        return
    try:
        analysis = theme_analysis.analyze_post_themes(post.title, post.content, db)
        if analysis.success:
            crud.update_post_theme_analysis(db, post.id, analysis.themes, analysis.feelings, "completed")
        else:
            crud.update_post_theme_analysis(db, post.id, [], [], "failed")
    except Exception as exc:
        logger.error("Theme analysis failed for post %s: %s", post.id, exc)
        crud.update_post_theme_analysis(db, post.id, [], [], "failed")


def _handle_ai_critic(db: Session, job: models.AIJob) -> None:
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == job.target_id)
        .first()
    )
    if (
        not post
        or post.moderation_status != "approved"
        or not post.ai_critic_requested
        or not _post_matches_job(post, job)
    ):
        return
    existing = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post.id, models.Comment.is_robot == True)
        .first()
    )
    if existing:
        return
    critique = ai_critic.generate_critique(
        post.title, post.content, bool(post.owner and post.owner.is_premium)
    )
    if critique:
        crud.create_robot_comment(db, post_id=post.id, content=critique)


def _finalize_moderation_failure(db: Session, job: models.AIJob, exc: Exception) -> None:
    reason = f"Auto-approved due to queued AI job failure: {exc}"
    approved = SimpleNamespace(
        status=moderation.ModerationStatus.APPROVED,
        toxicity_score=0.0,
        reason=reason,
    )
    if job.job_type == JOB_POST_PUBLISH:
        post = crud.get_post(db, job.target_id)
        if post and post.moderation_status == "pending" and _post_matches_job(post, job):
            post.category = post.category or "proza_scurta"
            post.moderation_status = "approved"
            post.toxicity_score = 0.0
            post.moderation_reason = reason
            db.commit()
            db.refresh(post)
            crud.award_content_approved(db, "post", post)
            enqueue_post_approval_jobs(db, post)
    elif job.job_type == JOB_COMMENT_MODERATION:
        comment = db.query(models.Comment).filter(models.Comment.id == job.target_id).first()
        if comment and comment.moderation_status == "pending":
            comment.moderation_status = "approved"
            comment.approved = True
            comment.toxicity_score = 0.0
            comment.moderation_reason = reason
            db.commit()
            db.refresh(comment)
            crud.award_content_approved(db, "comment", comment)
    elif job.job_type == JOB_FORUM_THREAD_MODERATION:
        thread = crud.get_forum_thread(db, job.target_id)
        if thread and thread.moderation_status == "pending":
            crud.apply_forum_thread_moderation_result(db, thread, approved)
    elif job.job_type == JOB_FORUM_REPLY_MODERATION:
        reply = (
            db.query(models.ForumReply)
            .options(joinedload(models.ForumReply.thread), joinedload(models.ForumReply.author))
            .filter(models.ForumReply.id == job.target_id)
            .first()
        )
        if reply and reply.moderation_status == "pending":
            crud.apply_forum_reply_moderation_result(db, reply, approved)


_HANDLERS = {
    JOB_POST_PUBLISH: _handle_post_publish,
    JOB_COMMENT_MODERATION: _handle_comment_moderation,
    JOB_FORUM_THREAD_MODERATION: _handle_forum_thread_moderation,
    JOB_FORUM_REPLY_MODERATION: _handle_forum_reply_moderation,
    JOB_TTS_AUDIO: _handle_tts_audio,
    JOB_AUTHOR_AUDIO: _handle_author_audio,
    JOB_THEME_ANALYSIS: _handle_theme_analysis,
    JOB_AI_CRITIC: _handle_ai_critic,
}
