import datetime
import pytest
from app.services.creancier_engine import next_date


def test_next_date_mensuelle_handles_end_of_month():
    assert next_date(datetime.date(2026, 1, 31), "mensuelle") == datetime.date(2026, 2, 28)


def test_next_date_hebdomadaire_adds_seven_days():
    assert next_date(datetime.date(2026, 8, 1), "hebdomadaire") == datetime.date(2026, 8, 8)


def test_next_date_custom_uses_intervalle_jours():
    assert next_date(datetime.date(2026, 8, 1), "custom", intervalle_jours=10) == datetime.date(2026, 8, 11)


def test_next_date_custom_without_intervalle_raises():
    with pytest.raises(ValueError):
        next_date(datetime.date(2026, 8, 1), "custom")


def test_next_date_aucune_returns_none():
    assert next_date(datetime.date(2026, 8, 1), "aucune") is None


import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Transaction
from app.services.creancier_engine import generate_due_echeances


def _make_comptes(db_session):
    banque = Banque(nom="Test")
    hello = CompteVirtuel(nom="Hello", banque=banque)
    poste = CompteVirtuel(nom="Poste/Maison", banque=banque)
    db_session.add_all([banque, hello, poste])
    db_session.commit()
    return hello, poste


def test_generate_interne_creates_two_linked_transactions(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Virement loyer",
        montant_defaut=800.0,
        compte_source=hello,
        compte_destination=poste,
        date_prochaine_echeance=dt.date(2026, 9, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2
    debit, credit = created
    assert debit.compte_virtuel_id == hello.id and debit.montant == -800.0
    assert credit.compte_virtuel_id == poste.id and credit.montant == 800.0
    assert debit.transfer_link_id == credit.transfer_link_id
    assert debit.creancier_id == creancier.id
    assert creancier.date_prochaine_echeance == dt.date(2026, 10, 1)
    assert creancier.occurrences_generees == 1


def test_generate_externe_creates_one_transaction(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Prélèvement loyer",
        montant_defaut=800.0,
        compte_source=poste,
        compte_destination=None,
        date_prochaine_echeance=dt.date(2026, 9, 5),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 5))

    assert len(created) == 1
    assert created[0].montant == -800.0
    assert created[0].transfer_link_id is None


def test_generate_catches_up_multiple_missed_months(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Abonnement",
        montant_defaut=10.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 6, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 4  # juin, juillet, août, septembre
    assert [t.date for t in created] == [
        dt.date(2026, 6, 1), dt.date(2026, 7, 1), dt.date(2026, 8, 1), dt.date(2026, 9, 1)
    ]
    assert creancier.date_prochaine_echeance == dt.date(2026, 10, 1)
    assert creancier.occurrences_generees == 4


def test_generate_stops_at_fin_occurrences(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Remboursement",
        montant_defaut=50.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 1, 1),
        recurrence="mensuelle",
        fin_type="occurrences",
        fin_occurrences=2,
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2
    assert creancier.actif is False


def test_generate_stops_at_fin_date(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Assurance temporaire",
        montant_defaut=30.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 7, 1),
        recurrence="mensuelle",
        fin_type="date",
        fin_date=dt.date(2026, 8, 1),
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2  # juillet, août — s'arrête à fin_date incluse
    assert creancier.actif is False


def test_generate_ignores_inactive_creancier(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Archivé",
        montant_defaut=15.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 1, 1),
        recurrence="mensuelle",
        fin_type="jamais",
        actif=False,
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert created == []
