import datetime as dt
from app.models import Banque, CompteVirtuel, Transaction
from app.services.totals import (
    total_pointe,
    total_a_venir,
    total_pointe_banque,
    total_a_venir_banque,
    calcule_ecart,
)


def _setup(db_session):
    banque = Banque(nom="LaPoste")
    economie = CompteVirtuel(nom="Economie", banque=banque)
    maison = CompteVirtuel(nom="Maison", banque=banque)
    db_session.add_all([banque, economie, maison])
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 8, 1), compte_virtuel=economie, montant=100.0, libelle="a", pointe=True),
            Transaction(date=dt.date(2026, 8, 2), compte_virtuel=economie, montant=-20.0, libelle="b", pointe=False),
            Transaction(date=dt.date(2026, 8, 3), compte_virtuel=maison, montant=-30.0, libelle="c", pointe=True),
        ]
    )
    db_session.commit()
    return banque, economie, maison


def test_total_pointe_sums_only_pointed(db_session):
    _, economie, _ = _setup(db_session)
    assert total_pointe(db_session, economie.id) == 100.0


def test_total_a_venir_sums_only_unpointed(db_session):
    _, economie, _ = _setup(db_session)
    assert total_a_venir(db_session, economie.id) == -20.0


def test_total_pointe_banque_sums_across_comptes(db_session):
    banque, _, _ = _setup(db_session)
    assert total_pointe_banque(db_session, banque.id) == 70.0  # 100 + (-30)


def test_total_a_venir_banque_sums_across_comptes(db_session):
    banque, _, _ = _setup(db_session)
    assert total_a_venir_banque(db_session, banque.id) == -20.0


def test_calcule_ecart_rounds_to_cents():
    assert calcule_ecart(70.001, 70.0) == 0.0
    assert calcule_ecart(70.5, 70.0) == 0.5
