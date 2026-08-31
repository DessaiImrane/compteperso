import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel
from app.services.reporting import depenses_par_tag, rapport_mensuel

router = APIRouter()


@router.get("/reporting/mensuel")
def reporting_mensuel(
    request: Request,
    compte_virtuel_id: int | None = None,
    annee: int = datetime.date.today().year,
    mois: int = datetime.date.today().month,
    db: Session = Depends(get_db),
):
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    rapport = None
    if compte_virtuel_id:
        rapport = rapport_mensuel(db, compte_virtuel_id, annee, mois)
    return templates.TemplateResponse(
        request,
        "reporting/mensuel.html",
        {
            "comptes": comptes,
            "compte_virtuel_id": compte_virtuel_id,
            "annee": annee,
            "mois": mois,
            "rapport": rapport,
        },
    )


@router.get("/reporting/tags")
def reporting_tags(
    request: Request,
    date_debut: datetime.date = datetime.date.today().replace(day=1),
    date_fin: datetime.date = datetime.date.today(),
    db: Session = Depends(get_db),
):
    depenses = depenses_par_tag(db, date_debut, date_fin)
    return templates.TemplateResponse(
        request,
        "reporting/tags.html",
        {"depenses": depenses, "date_debut": date_debut, "date_fin": date_fin},
    )
