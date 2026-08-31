import datetime
import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Tag, Transaction


def test_create_banque_compte_and_transaction_with_tags(db_session):
    banque = Banque(nom="LaPoste")
    compte = CompteVirtuel(nom="Maison", banque=banque, actif=True)
    tag_resto = Tag(nom="resto")
    tx = Transaction(
        date=datetime.date(2026, 8, 1),
        compte_virtuel=compte,
        montant=-42.5,
        libelle="Restaurant Le Bon Coin",
        pointe=True,
        tags=[tag_resto],
    )
    db_session.add_all([banque, compte, tag_resto, tx])
    db_session.commit()

    saved = db_session.query(Transaction).one()
    assert saved.montant == -42.5
    assert saved.compte_virtuel.nom == "Maison"
    assert saved.compte_virtuel.banque.nom == "LaPoste"
    assert [t.nom for t in saved.tags] == ["resto"]
    assert saved.creancier_id is None
    assert saved.transfer_link_id is None


def test_create_creancier(db_session):
    banque = Banque(nom="HelloBank")
    source = CompteVirtuel(nom="Budget famille", banque=banque)
    creancier = Creancier(
        nom="Loyer",
        montant_defaut=800.0,
        compte_source=source,
        date_prochaine_echeance=dt.date(2026, 9, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add_all([banque, source, creancier])
    db_session.commit()

    saved = db_session.query(Creancier).one()
    assert saved.montant_defaut == 800.0
    assert saved.compte_destination is None
    assert saved.occurrences_generees == 0
