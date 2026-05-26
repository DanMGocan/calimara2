from ._shared import *
from ..utils import author_public_url, post_public_url


REPORT_TARGET_PREFIXES = {
    "forum_thread": "Discuție forum",
    "forum_reply": "Răspuns forum",
    "message": "Mesaj privat",
}


def _target_key(content_type: str, content_id: int) -> str:
    return f"{content_type}:{int(content_id)}"


def _target_snapshot(content_type: str, content_id: int, target_url: Optional[str] = None) -> str:
    key = _target_key(content_type, content_id)
    return f"{key}|{target_url[:240]}" if target_url else key


def _append_report_context(
    details: Optional[str],
    *,
    reported_content: Optional[str] = None,
    target_url: Optional[str] = None,
) -> Optional[str]:
    parts: list[str] = []
    if details:
        parts.append(details.strip())
    plain_content = rich_text.rich_text_to_plain_text(reported_content or "").strip()
    context: list[str] = []
    if plain_content:
        context.append(f"Conținut raportat: {plain_content[:1000]}")
    if target_url:
        context.append(f"Link conținut: {target_url}")
    if context:
        parts.extend(context)
    return "\n\n".join(parts) or None


def _parse_report_target(report: models.PostReport) -> tuple[str, Optional[int], Optional[str], Optional[str]]:
    if report.post_id:
        return "post", report.post_id, None, report.post_slug_snapshot
    snapshot = report.post_slug_snapshot or ""
    key, _, target_url = snapshot.partition("|")
    if ":" not in key:
        return "post", None, None, key or None
    content_type, raw_id = key.split(":", 1)
    if content_type not in REPORT_TARGET_PREFIXES:
        return "post", None, None, key
    try:
        return content_type, int(raw_id), target_url or None, key
    except (TypeError, ValueError):
        return content_type, None, target_url or None, key


def post_report_payload(report: models.PostReport) -> dict:
    post = report.post
    target_type, target_id, target_url, target_key = _parse_report_target(report)
    post_url = post_public_url(post.owner, post.slug) if post and post.owner else None
    post_author_url = (
        author_public_url(post.owner)
        if post and post.owner
        else author_public_url(report.post_author_username_snapshot)
        if report.post_author_username_snapshot
        else None
    )
    return {
        "id": report.id,
        "post_id": report.post_id,
        "target_type": target_type,
        "target_id": target_id,
        "target_label": REPORT_TARGET_PREFIXES.get(target_type, "Postare"),
        "target_url": target_url or post_url,
        "reporter_user_id": report.reporter_user_id,
        "reason_type": report.reason_type,
        "details": report.details,
        "evidence_url": report.evidence_url,
        "post_title": post.title if post else report.post_title_snapshot,
        "post_slug": post.slug if post else target_key,
        "post_url": post_url,
        "post_author": post.owner.username if post and post.owner else report.post_author_username_snapshot,
        "post_author_id": post.user_id if post else None,
        "post_author_url": post_author_url,
        "reporter_username": report.reporter.username if report.reporter else None,
        "reporter_url": author_public_url(report.reporter) if report.reporter else None,
        "status": report.status,
        "reviewed_by": report.reviewed_by,
        "reviewer_username": report.reviewer.username if report.reviewer else None,
        "reviewer_url": author_public_url(report.reviewer) if report.reviewer else None,
        "reviewed_at": report.reviewed_at,
        "review_note": report.review_note,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def get_post_report(db: Session, report_id: int):
    return (
        db.query(models.PostReport)
        .options(
            joinedload(models.PostReport.post).joinedload(models.Post.owner),
            joinedload(models.PostReport.reporter),
            joinedload(models.PostReport.reviewer),
        )
        .filter(models.PostReport.id == report_id)
        .first()
    )


def list_post_reports(
    db: Session,
    *,
    status_filter: str = "open",
    skip: int = 0,
    limit: int = 50,
):
    query = db.query(models.PostReport).options(
        joinedload(models.PostReport.post).joinedload(models.Post.owner),
        joinedload(models.PostReport.reporter),
        joinedload(models.PostReport.reviewer),
    )
    if status_filter != "all":
        query = query.filter(models.PostReport.status == status_filter)
    return (
        query.order_by(models.PostReport.created_at.desc(), models.PostReport.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_post_report(
    db: Session,
    *,
    post: models.Post,
    reporter_user_id: int,
    report: schemas.PostReportCreate,
):
    db_report = models.PostReport(
        post_id=post.id,
        reporter_user_id=reporter_user_id,
        reason_type=report.reason_type,
        details=report.details,
        evidence_url=report.evidence_url,
        post_title_snapshot=post.title,
        post_slug_snapshot=post.slug,
        post_author_username_snapshot=post.owner.username if post.owner else None,
        status="open",
    )
    db.add(db_report)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(db_report)
    return get_post_report(db, db_report.id)


def create_content_report(
    db: Session,
    *,
    content_type: str,
    content_id: int,
    title: str,
    author_username: Optional[str],
    reporter_user_id: int,
    report: schemas.PostReportCreate,
    reported_content: Optional[str] = None,
    target_url: Optional[str] = None,
):
    if content_type not in REPORT_TARGET_PREFIXES:
        raise ValueError("invalid_report_target")
    key = _target_key(content_type, content_id)
    snapshot = _target_snapshot(content_type, content_id, target_url)
    existing = (
        db.query(models.PostReport)
        .filter(
            models.PostReport.post_id.is_(None),
            or_(
                models.PostReport.post_slug_snapshot == key,
                models.PostReport.post_slug_snapshot.like(f"{key}|%"),
            ),
            models.PostReport.reporter_user_id == reporter_user_id,
            models.PostReport.reason_type == report.reason_type,
        )
        .first()
    )
    if existing:
        return None
    db_report = models.PostReport(
        post_id=None,
        reporter_user_id=reporter_user_id,
        reason_type=report.reason_type,
        details=_append_report_context(report.details, reported_content=reported_content, target_url=target_url),
        evidence_url=report.evidence_url,
        post_title_snapshot=title[:255],
        post_slug_snapshot=snapshot,
        post_author_username_snapshot=author_username,
        status="open",
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return get_post_report(db, db_report.id)


def update_post_report_review(
    db: Session,
    report: models.PostReport,
    *,
    status: str,
    reviewer_id: int,
    note: str,
):
    report.status = status
    report.reviewed_by = reviewer_id
    report.reviewed_at = utcnow_naive()
    report.review_note = note
    db.commit()
    db.refresh(report)
    return get_post_report(db, report.id)


def resolve_open_post_reports_for_post(
    db: Session,
    *,
    post_id: int,
    reviewer_id: int,
    note: str,
):
    reports = (
        db.query(models.PostReport)
        .filter(models.PostReport.post_id == post_id, models.PostReport.status == "open")
        .all()
    )
    now = utcnow_naive()
    for report in reports:
        report.status = "resolved"
        report.reviewed_by = reviewer_id
        report.reviewed_at = now
        report.review_note = note
    db.commit()
    return reports
