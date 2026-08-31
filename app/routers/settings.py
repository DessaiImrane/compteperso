from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.services.backup import get_backup_dir, set_backup_dir

router = APIRouter()


@router.get("/reglages")
def reglages_form(request: Request, saved: bool = False, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "settings/form.html", {"backup_dir": str(get_backup_dir(db)), "saved": saved}
    )


@router.post("/reglages")
def save_reglages(backup_dir: str = Form(...), db: Session = Depends(get_db)):
    set_backup_dir(db, backup_dir)
    return RedirectResponse("/reglages?saved=1", status_code=303)
