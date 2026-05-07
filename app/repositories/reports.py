from ._shared import *


def post_report_payload(report: models.PostReport) -> dict:
    post = report.post
    return {
        "id": report.id,
        "post_id": report.post_id,
        "reporter_user_id": report.reporter_user_id,
        "reason_type": report.reason_type,
        "details": report.details,
        "evidence_url": report.evidence_url,
        "post_title": post.title if post else report.post_title_snapshot,
        "post_slug": post.slug if post else report.post_slug_snapshot,
        "post_author": post.owner.username if post and post.owner else report.post_author_username_snapshot,
        "post_author_id": post.user_id if post else None,
        "reporter_username": report.reporter.username if report.reporter else None,
        "status": report.status,
        "reviewed_by": report.reviewed_by,
        "reviewer_username": report.reviewer.username if report.reviewer else None,
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
