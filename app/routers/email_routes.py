from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import email_service
from ..database import get_db

router = APIRouter(tags=["email"])


@router.get("/api/email/dezabonare", response_class=HTMLResponse)
def unsubscribe_email(
    token: str = Query(...),
    type: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        user, email_type = email_service.apply_unsubscribe_token(db, token, requested_type=type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Linkul de dezabonare nu este valid.")
    labels = {
        "comment": "comentarii noi",
        "mention": "mențiuni",
        "analytics": "Analitice avansate",
        "admin": "anunțuri administrative",
    }
    label = labels.get(email_type, "emailuri")
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ro">
  <head><meta charset="utf-8"><title>Dezabonare</title></head>
  <body style="font-family:Georgia,'Times New Roman',serif;background:#f7f3ea;color:#1f1d1b;padding:32px;">
    <main style="max-width:680px;margin:0 auto;">
      <div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#7a7168;">călimara.ro</div>
      <h1 style="font-weight:500;">Ai fost dezabonat</h1>
      <p>{user.username}, nu vei mai primi emailuri pentru {label}.</p>
      <p>Poți reactiva preferința oricând din profilul tău.</p>
    </main>
  </body>
</html>"""
    )
