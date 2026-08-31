import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Tag, Transaction
from app.services.totals import total_a_venir, total_pointe

router = APIRouter()


def _get_or_create_tags(db: Session, tags_csv: str) -> list[Tag]:
    names = [t.strip() for t in tags_csv.split(",") if t.strip()]
    tags = []
    for name in names:
        tag = db.query(Tag).filter_by(nom=name).first()
        if not tag:
            tag = Tag(nom=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _render_compte(request, db, compte, prefill, form_action):
    transactions = (
        db.query(Transaction)
        .filter_by(compte_virtuel_id=compte.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    pointe = total_pointe(db, compte.id)
    a_venir = total_a_venir(db, compte.id)
    return templates.TemplateResponse(
        request,
        "transactions/list.html",
        {
            "compte": compte,
            "transactions": transactions,
            "prefill": prefill,
            "form_action": form_action,
            "today": datetime.date.today().isoformat(),
            "pointe": pointe,
            "a_venir": a_venir,
            "solde": round(pointe + a_venir, 2),
        },
    )


@router.get("/comptes/{compte_id}/transactions")
def list_transactions(compte_id: int, request: Request, db: Session = Depends(get_db)):
    compte = db.get(CompteVirtuel, compte_id)
    return _render_compte(request, db, compte, None, f"/comptes/{compte_id}/transactions")


@router.post("/comptes/{compte_id}/transactions")
def add_transaction(
    compte_id: int,
    date: datetime.date = Form(...),
    libelle: str = Form(...),
    montant: float = Form(...),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    tx = Transaction(
        date=date, compte_virtuel_id=compte_id, montant=montant, libelle=libelle, pointe=False
    )
    tx.tags = _get_or_create_tags(db, tags)
    db.add(tx)
    db.commit()
    return RedirectResponse(f"/comptes/{compte_id}/transactions", status_code=303)


@router.post("/transactions/{transaction_id}/pointer")
def toggle_pointer(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    tx.pointe = not tx.pointe
    db.commit()
    return RedirectResponse(f"/comptes/{tx.compte_virtuel_id}/transactions", status_code=303)


@router.get("/transactions/{transaction_id}/dupliquer")
def duplicate_transaction_form(transaction_id: int, request: Request, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    compte = db.get(CompteVirtuel, tx.compte_virtuel_id)
    prefill = {
        "date": datetime.date.today().isoformat(),
        "libelle": tx.libelle,
        "montant": tx.montant,
        "tags": ", ".join(t.nom for t in tx.tags),
    }
    return _render_compte(request, db, compte, prefill, f"/comptes/{compte.id}/transactions")


@router.get("/transactions/{transaction_id}/modifier")
def edit_transaction_form(transaction_id: int, request: Request, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    compte = db.get(CompteVirtuel, tx.compte_virtuel_id)
    prefill = {
        "date": tx.date.isoformat(),
        "libelle": tx.libelle,
        "montant": tx.montant,
        "tags": ", ".join(t.nom for t in tx.tags),
    }
    return _render_compte(request, db, compte, prefill, f"/transactions/{transaction_id}/modifier")


@router.post("/transactions/{transaction_id}/modifier")
def update_transaction(
    transaction_id: int,
    date: datetime.date = Form(...),
    libelle: str = Form(...),
    montant: float = Form(...),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    tx = db.get(Transaction, transaction_id)
    tx.date = date
    tx.libelle = libelle
    tx.montant = montant
    tx.tags = _get_or_create_tags(db, tags)
    db.commit()
    return RedirectResponse(f"/comptes/{tx.compte_virtuel_id}/transactions", status_code=303)
