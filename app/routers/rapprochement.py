import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import Banque, CompteVirtuel, MappingParsing, RapprochementSession, Tag, Transaction
from app.services.dedup import is_duplicate
from app.services.parsing import parse_pasted_text, split_preview_rows
from app.services.tag_learning import record_learning, suggest_tags
from app.services.totals import calcule_ecart, total_pointe_banque

router = APIRouter()

_SEPARATEURS = {"tab": "\t", ";": ";", ",": ","}
_ROLES = {"date": "colonne_date", "libelle": "colonne_libelle", "montant": "colonne_montant"}


@router.get("/rapprochement")
def rapprochement_home(request: Request, banque_id: int | None = None, db: Session = Depends(get_db)):
    banques = db.query(Banque).all()
    banque = db.get(Banque, banque_id) if banque_id else None
    mapping = (
        db.query(MappingParsing).filter_by(banque_id=banque_id).first() if banque_id else None
    )
    return templates.TemplateResponse(
        request,
        "rapprochement/paste.html",
        {"banques": banques, "banque": banque, "mapping": mapping},
    )


@router.post("/rapprochement/{banque_id}/mapping/apercu")
def mapping_apercu(
    banque_id: int,
    request: Request,
    texte: str = Form(...),
    separateur: str = Form(...),
    db: Session = Depends(get_db),
):
    banque = db.get(Banque, banque_id)
    rows = split_preview_rows(texte, _SEPARATEURS[separateur])
    col_count = max((len(r) for r in rows), default=0)
    return templates.TemplateResponse(
        request,
        "rapprochement/mapping_apercu.html",
        {
            "banque": banque,
            "texte": texte,
            "separateur": separateur,
            "rows": rows[:5],
            "columns": range(col_count),
            "selected_roles": {},
            "erreur": None,
        },
    )


@router.post("/rapprochement/{banque_id}/mapping/valider")
async def mapping_valider(banque_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    texte = form["texte"]
    separateur = form["separateur"]
    sep = _SEPARATEURS[separateur]
    rows = split_preview_rows(texte, sep)
    col_count = max((len(r) for r in rows), default=0)

    colonnes = {}
    selected_roles = {}
    for i in range(col_count):
        role = form.get(f"role__{i}", "ignore")
        selected_roles[i] = role
        if role in _ROLES:
            colonnes[_ROLES[role]] = i

    if not all(key in colonnes for key in _ROLES.values()):
        banque = db.get(Banque, banque_id)
        return templates.TemplateResponse(
            request,
            "rapprochement/mapping_apercu.html",
            {
                "banque": banque,
                "texte": texte,
                "separateur": separateur,
                "rows": rows[:5],
                "columns": range(col_count),
                "selected_roles": selected_roles,
                "erreur": "Choisis une colonne pour Date, Libellé et Montant.",
            },
        )

    mapping = MappingParsing(banque_id=banque_id, separateur=sep, **colonnes)
    db.add(mapping)
    db.commit()
    return RedirectResponse(f"/rapprochement?banque_id={banque_id}", status_code=303)


@router.post("/rapprochement/{banque_id}/coller")
def parse_and_stage(
    banque_id: int, request: Request, texte: str = Form(...), db: Session = Depends(get_db)
):
    banque = db.get(Banque, banque_id)
    mapping = db.query(MappingParsing).filter_by(banque_id=banque_id).first()
    if not mapping:
        return templates.TemplateResponse(
            request,
            "rapprochement/paste.html",
            {"banques": db.query(Banque).all(), "banque": banque, "mapping": None},
        )

    comptes = db.query(CompteVirtuel).filter_by(banque_id=banque_id, actif=True).all()
    parsed = parse_pasted_text(texte, mapping)
    rows = []
    for entry in parsed:
        doublon = any(
            is_duplicate(db, compte.id, entry["date"], entry["montant"], entry["libelle"])
            for compte in comptes
        )
        tags = suggest_tags(db, entry["libelle"])
        rows.append(
            {
                "date": entry["date"].isoformat(),
                "libelle": entry["libelle"],
                "montant": entry["montant"],
                "doublon": doublon,
                "tags_suggeres": ", ".join(t.nom for t in tags),
            }
        )
    return templates.TemplateResponse(
        request,
        "rapprochement/staging.html",
        {"banque": banque, "comptes": comptes, "rows": rows},
    )


@router.post("/rapprochement/{banque_id}/valider")
async def validate_staging(banque_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    row_count = int(form["row_count"])
    banque = db.get(Banque, banque_id)

    for i in range(row_count):
        if form.get(f"verrouille__{i}"):
            continue
        libelle = form[f"libelle__{i}"]
        tags_csv = form.get(f"tags__{i}", "")
        tag_names = [t.strip() for t in tags_csv.split(",") if t.strip()]

        tags = []
        for name in tag_names:
            tag = db.query(Tag).filter_by(nom=name).first()
            if not tag:
                tag = Tag(nom=name)
                db.add(tag)
                db.flush()
            tags.append(tag)

        tx = Transaction(
            date=datetime.date.fromisoformat(form[f"date__{i}"]),
            compte_virtuel_id=int(form[f"compte_virtuel_id__{i}"]),
            montant=float(form[f"montant__{i}"]),
            libelle=libelle,
            pointe=True,
        )
        tx.tags = tags
        db.add(tx)
        if tags:
            record_learning(db, libelle, tags)
    db.commit()

    total_banque_pointe = float(form["total_banque_pointe"])
    total_banque_a_venir = float(form["total_banque_a_venir"])
    total_calcule = total_pointe_banque(db, banque_id)
    ecart = calcule_ecart(total_banque_pointe, total_calcule)

    db.add(
        RapprochementSession(
            banque_id=banque_id,
            date=datetime.date.today(),
            total_banque_pointe=total_banque_pointe,
            total_banque_a_venir=total_banque_a_venir,
            total_pointe_calcule=total_calcule,
            ecart=ecart,
        )
    )
    db.commit()

    return RedirectResponse(f"/banques/{banque_id}", status_code=303)
