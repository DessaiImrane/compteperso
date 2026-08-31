import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Creancier
from app.services.reporting import flux_creanciers_par_banque, flux_creanciers_par_compte

router = APIRouter()


def _prefill(c: Creancier) -> dict:
    return {
        "nom": c.nom,
        "montant_defaut": c.montant_defaut,
        "compte_source_id": c.compte_source_id,
        "compte_destination_id": c.compte_destination_id or "",
        "date_prochaine_echeance": c.date_prochaine_echeance.isoformat()
        if c.date_prochaine_echeance
        else "",
        "recurrence": c.recurrence,
        "intervalle_jours": c.intervalle_jours or "",
        "fin_type": c.fin_type,
        "fin_date": c.fin_date.isoformat() if c.fin_date else "",
        "fin_occurrences": c.fin_occurrences or "",
    }


def _render(request, db: Session, prefill, form_action: str):
    creanciers = db.query(Creancier).order_by(Creancier.nom).all()
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    return templates.TemplateResponse(
        request,
        "creanciers/list.html",
        {
            "creanciers": creanciers,
            "comptes": comptes,
            "prefill": prefill,
            "form_action": form_action,
            "flux_banque": flux_creanciers_par_banque(db),
            "flux_compte": flux_creanciers_par_compte(db),
        },
    )


@router.get("/creanciers")
def list_creanciers(request: Request, db: Session = Depends(get_db)):
    return _render(request, db, None, "/creanciers")


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
    return _render(request, db, _prefill(source), "/creanciers")


@router.get("/creanciers/{creancier_id}/modifier")
def edit_creancier_form(creancier_id: int, request: Request, db: Session = Depends(get_db)):
    creancier = db.get(Creancier, creancier_id)
    return _render(request, db, _prefill(creancier), f"/creanciers/{creancier_id}/modifier")


@router.post("/creanciers/{creancier_id}/modifier")
def update_creancier(
    creancier_id: int,
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
    creancier = db.get(Creancier, creancier_id)
    creancier.nom = nom
    creancier.montant_defaut = montant_defaut
    creancier.compte_source_id = compte_source_id
    creancier.compte_destination_id = int(compte_destination_id) if compte_destination_id else None
    creancier.date_prochaine_echeance = date_prochaine_echeance
    creancier.recurrence = recurrence
    creancier.intervalle_jours = int(intervalle_jours) if intervalle_jours else None
    creancier.fin_type = fin_type
    creancier.fin_date = datetime.date.fromisoformat(fin_date) if fin_date else None
    creancier.fin_occurrences = int(fin_occurrences) if fin_occurrences else None
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)


@router.post("/creanciers/{creancier_id}/desactiver")
def deactivate_creancier(creancier_id: int, db: Session = Depends(get_db)):
    creancier = db.get(Creancier, creancier_id)
    creancier.actif = False
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)
