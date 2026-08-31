from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import Banque, CompteVirtuel
from app.services.totals import (
    total_a_venir,
    total_a_venir_banque,
    total_pointe,
    total_pointe_banque,
)

router = APIRouter()


def _compte_totaux(db, compte):
    pointe = total_pointe(db, compte.id)
    a_venir = total_a_venir(db, compte.id)
    return {"compte": compte, "pointe": pointe, "a_venir": a_venir, "solde": round(pointe + a_venir, 2)}


@router.get("/banques")
def list_banques(request: Request, db: Session = Depends(get_db)):
    banques = db.query(Banque).all()
    rows = []
    for banque in banques:
        comptes = (
            db.query(CompteVirtuel)
            .filter_by(banque_id=banque.id, actif=True)
            .order_by(CompteVirtuel.ordre)
            .all()
        )
        comptes_totaux = [_compte_totaux(db, c) for c in comptes]
        pointe = total_pointe_banque(db, banque.id)
        a_venir = total_a_venir_banque(db, banque.id)
        rows.append(
            {
                "banque": banque,
                "comptes": comptes_totaux,
                "pointe": pointe,
                "a_venir": a_venir,
                "solde": round(pointe + a_venir, 2),
            }
        )
    return templates.TemplateResponse(request, "banques/list.html", {"rows": rows})


@router.post("/banques")
def create_banque(nom: str = Form(...), db: Session = Depends(get_db)):
    db.add(Banque(nom=nom))
    db.commit()
    return RedirectResponse("/banques", status_code=303)


@router.get("/banques/{banque_id}")
def banque_detail(banque_id: int, request: Request, db: Session = Depends(get_db)):
    banque = db.get(Banque, banque_id)
    comptes = (
        db.query(CompteVirtuel).filter_by(banque_id=banque_id).order_by(CompteVirtuel.ordre).all()
    )
    rows = [_compte_totaux(db, c) for c in comptes]
    pointe = total_pointe_banque(db, banque_id)
    a_venir = total_a_venir_banque(db, banque_id)
    return templates.TemplateResponse(
        request,
        "banques/detail.html",
        {
            "banque": banque,
            "comptes": rows,
            "total_pointe": pointe,
            "total_a_venir": a_venir,
            "total_solde": round(pointe + a_venir, 2),
        },
    )


@router.post("/banques/{banque_id}/comptes")
def create_compte(banque_id: int, nom: str = Form(...), db: Session = Depends(get_db)):
    max_ordre = (
        db.query(CompteVirtuel).filter_by(banque_id=banque_id).count()
    )
    db.add(CompteVirtuel(nom=nom, banque_id=banque_id, actif=True, ordre=max_ordre))
    db.commit()
    return RedirectResponse(f"/banques/{banque_id}", status_code=303)


@router.post("/comptes/{compte_id}/archiver")
def archiver_compte(compte_id: int, db: Session = Depends(get_db)):
    compte = db.get(CompteVirtuel, compte_id)
    compte.actif = False
    db.commit()
    return RedirectResponse(f"/banques/{compte.banque_id}", status_code=303)


@router.post("/banques/{banque_id}/comptes/ordre")
async def reorder_comptes(banque_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    for index, compte_id in enumerate(body["ordre"]):
        compte = db.get(CompteVirtuel, compte_id)
        if compte and compte.banque_id == banque_id:
            compte.ordre = index
    db.commit()
    return {"status": "ok"}
