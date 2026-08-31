import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Tag, Transaction
from app.services.reporting import rapport_mensuel, depenses_par_tag


def _compte(db_session):
    banque = Banque(nom="Hello")
    compte = CompteVirtuel(nom="Budget famille", banque=banque)
    db_session.add_all([banque, compte])
    db_session.commit()
    return compte


def test_rapport_mensuel_splits_recurrent_and_non_recurrent(db_session):
    compte = _compte(db_session)
    creancier = Creancier(
        nom="Loyer", montant_defaut=800.0, compte_source=compte,
        date_prochaine_echeance=dt.date(2026, 9, 1), recurrence="mensuelle", fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 9, 1), compte_virtuel=compte, montant=-800.0,
                        libelle="Loyer", pointe=True, creancier_id=creancier.id),
            Transaction(date=dt.date(2026, 9, 3), compte_virtuel=compte, montant=-60.0,
                        libelle="Courses", pointe=True),
            Transaction(date=dt.date(2026, 9, 4), compte_virtuel=compte, montant=-25.0,
                        libelle="Courses", pointe=False),
            Transaction(date=dt.date(2026, 8, 31), compte_virtuel=compte, montant=-10.0,
                        libelle="Hors periode", pointe=True),
        ]
    )
    db_session.commit()

    rapport = rapport_mensuel(db_session, compte.id, 2026, 9)

    assert rapport == {
        "recurrent_prevu": 800.0,
        "recurrent_pointe": 800.0,
        "non_recurrent_pointe": 60.0,
    }


def test_depenses_par_tag_aggregates_negative_amounts(db_session):
    compte = _compte(db_session)
    resto = Tag(nom="resto")
    courses = Tag(nom="courses")
    db_session.add_all([resto, courses])
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 9, 1), compte_virtuel=compte, montant=-40.0,
                        libelle="a", tags=[resto]),
            Transaction(date=dt.date(2026, 9, 2), compte_virtuel=compte, montant=-15.0,
                        libelle="b", tags=[resto]),
            Transaction(date=dt.date(2026, 9, 3), compte_virtuel=compte, montant=-60.0,
                        libelle="c", tags=[courses]),
            Transaction(date=dt.date(2026, 9, 4), compte_virtuel=compte, montant=1500.0,
                        libelle="salaire", tags=[]),
        ]
    )
    db_session.commit()

    result = depenses_par_tag(db_session, dt.date(2026, 9, 1), dt.date(2026, 9, 30))

    assert result == {"resto": 55.0, "courses": 60.0}
