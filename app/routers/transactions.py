import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Tag, Transaction

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


@router.get("/comptes/{compte_id}/transactions")
def list_transactions(compte_id: int, request: Request, db: Session = Depends(get_db)):
    compte = db.get(CompteVirtuel, compte_id)
    transactions = (
        db.query(Transaction)
        .filter_by(compte_virtuel_id=compte_id)
        .order_by(Transaction.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "transactions/list.html",
        {"compte": compte, "transactions": transactions, "prefill": None},
    )


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
def pointer_transaction(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    tx.pointe = True
    db.commit()
    return RedirectResponse(f"/comptes/{tx.compte_virtuel_id}/transactions", status_code=303)


@router.get("/transactions/{transaction_id}/dupliquer")
def duplicate_transaction_form(transaction_id: int, request: Request, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    compte = db.get(CompteVirtuel, tx.compte_virtuel_id)
    transactions = (
        db.query(Transaction)
        .filter_by(compte_virtuel_id=compte.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    prefill = {
        "date": datetime.date.today().isoformat(),
        "libelle": tx.libelle,
        "montant": tx.montant,
        "tags": ", ".join(t.nom for t in tx.tags),
    }
    return templates.TemplateResponse(
        request,
        "transactions/list.html",
        {"compte": compte, "transactions": transactions, "prefill": prefill},
    )
