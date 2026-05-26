from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import auth, data_portability, models, schemas
from ..database import get_db


router = APIRouter(tags=["portabilitate"])


@router.get("/api/portabilitate/export")
def export_current_user_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    payload = data_portability.export_user_data(db, current_user)
    date_stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"calimara-export-{current_user.username}-{date_stamp}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/portabilitate/import", response_model=schemas.DataImportReport, status_code=status.HTTP_200_OK)
def import_current_user_data(
    manifest: schemas.DataExportManifest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        return data_portability.import_user_data(db, current_user, manifest)
    except data_portability.DataImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
