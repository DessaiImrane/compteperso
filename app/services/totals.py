from app.models import CompteVirtuel, Transaction


def total_pointe(db, compte_virtuel_id: int) -> float:
    rows = (
        db.query(Transaction.montant)
        .filter_by(compte_virtuel_id=compte_virtuel_id, pointe=True)
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def total_a_venir(db, compte_virtuel_id: int) -> float:
    rows = (
        db.query(Transaction.montant)
        .filter_by(compte_virtuel_id=compte_virtuel_id, pointe=False)
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def total_pointe_banque(db, banque_id: int) -> float:
    compte_ids = [c.id for c in db.query(CompteVirtuel).filter_by(banque_id=banque_id).all()]
    if not compte_ids:
        return 0.0
    rows = (
        db.query(Transaction.montant)
        .filter(Transaction.compte_virtuel_id.in_(compte_ids), Transaction.pointe.is_(True))
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def total_a_venir_banque(db, banque_id: int) -> float:
    compte_ids = [c.id for c in db.query(CompteVirtuel).filter_by(banque_id=banque_id).all()]
    if not compte_ids:
        return 0.0
    rows = (
        db.query(Transaction.montant)
        .filter(Transaction.compte_virtuel_id.in_(compte_ids), Transaction.pointe.is_(False))
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def calcule_ecart(total_banque: float, total_calcule: float) -> float:
    return round(total_banque - total_calcule, 2)
