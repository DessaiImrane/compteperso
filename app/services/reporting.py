import calendar
import datetime
from collections import defaultdict

from app.models import Creancier, Transaction


def rapport_mensuel(db, compte_virtuel_id: int, annee: int, mois: int) -> dict:
    start = datetime.date(annee, mois, 1)
    end = datetime.date(annee, mois, calendar.monthrange(annee, mois)[1])
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.compte_virtuel_id == compte_virtuel_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )
    recurrent = [t for t in txs if t.creancier_id is not None]
    non_recurrent = [t for t in txs if t.creancier_id is None]
    return {
        "recurrent_prevu": round(sum(abs(t.montant) for t in recurrent), 2),
        "recurrent_pointe": round(sum(abs(t.montant) for t in recurrent if t.pointe), 2),
        "non_recurrent_pointe": round(
            sum(abs(t.montant) for t in non_recurrent if t.pointe), 2
        ),
    }


def depenses_par_tag(db, date_debut: datetime.date, date_fin: datetime.date) -> dict[str, float]:
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date >= date_debut,
            Transaction.date <= date_fin,
            Transaction.montant < 0,
        )
        .all()
    )
    agg: dict[str, float] = defaultdict(float)
    for t in txs:
        for tag in t.tags:
            agg[tag.nom] += abs(t.montant)
    return {k: round(v, 2) for k, v in agg.items()}


def _flux(db, source_label, destination_label) -> list[dict]:
    creanciers = db.query(Creancier).filter(Creancier.actif.is_(True)).all()
    agg: dict[tuple[str, str], float] = defaultdict(float)
    for c in creanciers:
        src = source_label(c)
        dst = destination_label(c)
        agg[(src, dst)] += abs(c.montant_defaut)
    return sorted(
        (
            {"source": src, "destination": dst, "total": round(total, 2)}
            for (src, dst), total in agg.items()
        ),
        key=lambda r: (r["source"], r["destination"]),
    )


def flux_creanciers_par_banque(db) -> list[dict]:
    return _flux(
        db,
        source_label=lambda c: c.compte_source.banque.nom,
        destination_label=lambda c: c.compte_destination.banque.nom if c.compte_destination else "Externe",
    )


def flux_creanciers_par_compte(db) -> list[dict]:
    return _flux(
        db,
        source_label=lambda c: f"{c.compte_source.banque.nom} / {c.compte_source.nom}",
        destination_label=lambda c: (
            f"{c.compte_destination.banque.nom} / {c.compte_destination.nom}"
            if c.compte_destination
            else "Externe"
        ),
    )
