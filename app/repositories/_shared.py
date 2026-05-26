import logging
import os
import re
from datetime import datetime, date as date_type, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import and_, case, desc, exists, extract, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from .. import models, rich_text, schemas
from ..week_util import start_of_iso_week_utc, utcnow_naive

logger = logging.getLogger(__name__)


def not_human_rejected_condition(content_type: str, content_id_column):
    return ~exists().where(
        and_(
            models.ModerationLog.content_type == content_type,
            models.ModerationLog.content_id == content_id_column,
            models.ModerationLog.human_decision == "rejected",
        )
    )


def content_has_human_rejection(db: Session, content_type: str, content_id: int) -> bool:
    return db.query(models.ModerationLog.id).filter(
        models.ModerationLog.content_type == content_type,
        models.ModerationLog.content_id == content_id,
        models.ModerationLog.human_decision == "rejected",
    ).first() is not None
