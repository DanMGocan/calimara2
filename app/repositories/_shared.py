import logging
import os
import re
from datetime import datetime, date as date_type, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import and_, case, desc, extract, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import models, rich_text, schemas
from ..week_util import start_of_iso_week_utc, utcnow_naive

logger = logging.getLogger(__name__)
