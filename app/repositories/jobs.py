from ._shared import *

AI_JOB_ACTIVE_STATUSES = ("pending", "processing")

def enqueue_ai_job(
    db: Session,
    *,
    job_type: str,
    target_type: str,
    target_id: int,
    payload: Optional[dict] = None,
    max_attempts: int = 3,
    dedupe: bool = True,
) -> models.AIJob:
    if dedupe:
        existing = (
            db.query(models.AIJob)
            .filter(
                models.AIJob.job_type == job_type,
                models.AIJob.target_type == target_type,
                models.AIJob.target_id == target_id,
                models.AIJob.status.in_(AI_JOB_ACTIVE_STATUSES),
            )
            .order_by(models.AIJob.id.desc())
            .first()
        )
        if existing:
            return existing
    job = models.AIJob(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        max_attempts=max_attempts,
        status="pending",
        run_after=utcnow_naive(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def claim_pending_ai_jobs(
    db: Session,
    *,
    limit: int = 10,
    worker_id: Optional[str] = None,
) -> List[models.AIJob]:
    now = utcnow_naive()
    query = (
        db.query(models.AIJob)
        .filter(
            models.AIJob.status == "pending",
            models.AIJob.run_after <= now,
        )
        .order_by(models.AIJob.run_after.asc(), models.AIJob.id.asc())
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    jobs = query.limit(max(1, limit)).all()
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id
        job.attempts = int(job.attempts or 0) + 1
        job.error_message = None
    if jobs:
        db.commit()
        for job in jobs:
            db.refresh(job)
    return jobs

def complete_ai_job(db: Session, job: models.AIJob) -> models.AIJob:
    job.status = "completed"
    job.locked_at = None
    job.locked_by = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job

def ai_job_retry_delay_seconds(job: models.AIJob) -> int:
    attempts = int(job.attempts or 1)
    if job.job_type == "tts_audio_generation" and attempts == 2:
        return max(0, int(os.getenv("TTS_THIRD_ATTEMPT_DELAY_SECONDS", "900")))
    return min(300, 10 * (2 ** max(0, attempts - 1)))

def fail_ai_job(
    db: Session,
    job: models.AIJob,
    error_message: str,
    *,
    retry: bool = True,
) -> models.AIJob:
    message = error_message[:2000] if error_message else "AI job failed"
    if retry and int(job.attempts or 0) < int(job.max_attempts or 1):
        delay_seconds = ai_job_retry_delay_seconds(job)
        job.status = "pending"
        job.run_after = utcnow_naive() + timedelta(seconds=delay_seconds)
    else:
        job.status = "failed"
    job.locked_at = None
    job.locked_by = None
    job.error_message = message
    db.commit()
    db.refresh(job)
    return job
