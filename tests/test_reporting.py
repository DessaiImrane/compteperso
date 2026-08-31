import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Tag, Transaction
from app.services.reporting import (
    rapport_mensuel,
    depenses_par_tag,
    flux_creanciers_par_banque,
    flux_creanciers_par_compte,
)


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
        "reliquat_debut_mois": -10.0,
        "recurrent_prevu": 800.0,
        "recurrent_pointe": 800.0,
        "non_recurrent_pointe": 60.0,
    }


def test_rapport_mensuel_reliquat_sums_all_prior_transactions(db_session):
    compte = _compte(db_session)
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 7, 15), compte_virtuel=compte, montant=1500.0,
                        libelle="Salaire", pointe=True),
            Transaction(date=dt.date(2026, 8, 20), compte_virtuel=compte, montant=-1450.0,
                        libelle="Depenses aout", pointe=True),
            Transaction(date=dt.date(2026, 8, 25), compte_virtuel=compte, montant=-30.0,
                        libelle="Pas encore passe", pointe=False),
            Transaction(date=dt.date(2026, 9, 5), compte_virtuel=compte, montant=-20.0,
                        libelle="Deja en septembre", pointe=True),
        ]
    )
    db_session.commit()

    rapport = rapport_mensuel(db_session, compte.id, 2026, 9)

    assert rapport["reliquat_debut_mois"] == 20.0  # 1500 - 1450 - 30


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


def _flux_setup(db_session):
    hello_banque = Banque(nom="HelloBank")
    poste_banque = Banque(nom="LaPoste")
    argent_mois = CompteVirtuel(nom="ArgentMois", banque=hello_banque)
    eco = CompteVirtuel(nom="Eco", banque=poste_banque)
    maison = CompteVirtuel(nom="Maison", banque=poste_banque)
    db_session.add_all([hello_banque, poste_banque, argent_mois, eco, maison])
    db_session.commit()
    db_session.add_all(
        [
            Creancier(
                nom="Economie", montant_defaut=250.0, compte_source=argent_mois,
                compte_destination=eco, date_prochaine_echeance=dt.date(2026, 9, 1),
                recurrence="mensuelle", fin_type="jamais", actif=True,
            ),
            Creancier(
                nom="Loyer virement", montant_defaut=800.0, compte_source=argent_mois,
                compte_destination=maison, date_prochaine_echeance=dt.date(2026, 9, 1),
                recurrence="mensuelle", fin_type="jamais", actif=True,
            ),
            Creancier(
                nom="Prelevement loyer", montant_defaut=-800.0, compte_source=maison,
                compte_destination=None, date_prochaine_echeance=dt.date(2026, 9, 1),
                recurrence="mensuelle", fin_type="jamais", actif=True,
            ),
            Creancier(
                nom="Inactif", montant_defaut=999.0, compte_source=argent_mois,
                compte_destination=eco, date_prochaine_echeance=dt.date(2026, 9, 1),
                recurrence="mensuelle", fin_type="jamais", actif=False,
            ),
        ]
    )
    db_session.commit()
    return hello_banque, poste_banque, argent_mois, eco, maison


def test_flux_creanciers_par_banque_aggregates_active_only(db_session):
    _flux_setup(db_session)

    flux = flux_creanciers_par_banque(db_session)

    assert flux == [
        {"source": "HelloBank", "destination": "LaPoste", "total": 1050.0},
        {"source": "LaPoste", "destination": "Externe", "total": 800.0},
    ]


def test_flux_creanciers_par_compte_keeps_comptes_separate(db_session):
    _flux_setup(db_session)

    flux = flux_creanciers_par_compte(db_session)

    assert flux == [
        {"source": "HelloBank / ArgentMois", "destination": "LaPoste / Eco", "total": 250.0},
        {"source": "HelloBank / ArgentMois", "destination": "LaPoste / Maison", "total": 800.0},
        {"source": "LaPoste / Maison", "destination": "Externe", "total": 800.0},
    ]
