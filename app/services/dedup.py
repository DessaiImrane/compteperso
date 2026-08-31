from app.models import Transaction


def is_duplicate(db, compte_virtuel_id: int, date, montant: float, libelle: str) -> bool:
    return (
        db.query(Transaction)
        .filter_by(
            compte_virtuel_id=compte_virtuel_id, date=date, montant=montant, libelle=libelle
        )
        .first()
        is not None
    )
