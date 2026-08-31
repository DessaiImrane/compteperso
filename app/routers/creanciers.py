import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Creancier

router = APIRouter()


@router.get("/creanciers")
def list_creanciers(request: Request, db: Session = Depends(get_db)):
    creanciers = db.query(Creancier).all()
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    return templates.TemplateResponse(
        request,
        "creanciers/list.html",
        {"creanciers": creanciers, "comptes": comptes, "prefill": None},
    )


@router.post("/creanciers")
def create_creancier(
    nom: str = Form(...),
    montant_defaut: float = Form(...),
    compte_source_id: int = Form(...),
    compte_destination_id: str = Form(""),
    date_prochaine_echeance: datetime.date = Form(...),
    recurrence: str = Form(...),
    intervalle_jours: str = Form(""),
    fin_type: str = Form("jamais"),
    fin_date: str = Form(""),
    fin_occurrences: str = Form(""),
    db: Session = Depends(get_db),
):
    creancier = Creancier(
        nom=nom,
        montant_defaut=montant_defaut,
        compte_source_id=compte_source_id,
        compte_destination_id=int(compte_destination_id) if compte_destination_id else None,
        date_prochaine_echeance=date_prochaine_echeance,
        recurrence=recurrence,
        intervalle_jours=int(intervalle_jours) if intervalle_jours else None,
        fin_type=fin_type,
        fin_date=datetime.date.fromisoformat(fin_date) if fin_date else None,
        fin_occurrences=int(fin_occurrences) if fin_occurrences else None,
        actif=True,
    )
    db.add(creancier)
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)


@router.get("/creanciers/{creancier_id}/dupliquer")
def duplicate_creancier_form(creancier_id: int, request: Request, db: Session = Depends(get_db)):
    source = db.get(Creancier, creancier_id)
    creanciers = db.query(Creancier).all()
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    prefill = {"nom": source.nom, "montant_defaut": source.montant_defaut}
    return templates.TemplateResponse(
        request,
        "creanciers/list.html",
        {"creanciers": creanciers, "comptes": comptes, "prefill": prefill},
    )


@router.post("/creanciers/{creancier_id}/desactiver")
def deactivate_creancier(creancier_id: int, db: Session = Depends(get_db)):
    creancier = db.get(Creancier, creancier_id)
    creancier.actif = False
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)
