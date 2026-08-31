import datetime as dt
from app.models import Banque, CompteVirtuel, Tag, Transaction
from app.services.dedup import is_duplicate
from app.services.tag_learning import normalize_libelle, suggest_tags, record_learning


def _compte(db_session):
    banque = Banque(nom="Bourso")
    compte = CompteVirtuel(nom="Bourso", banque=banque)
    db_session.add_all([banque, compte])
    db_session.commit()
    return compte


def test_is_duplicate_true_for_exact_match(db_session):
    compte = _compte(db_session)
    tx = Transaction(
        date=dt.date(2026, 8, 5), compte_virtuel=compte, montant=-45.9, libelle="Restaurant"
    )
    db_session.add(tx)
    db_session.commit()

    assert is_duplicate(db_session, compte.id, dt.date(2026, 8, 5), -45.9, "Restaurant") is True


def test_is_duplicate_false_when_no_match(db_session):
    compte = _compte(db_session)
    assert is_duplicate(db_session, compte.id, dt.date(2026, 8, 5), -45.9, "Restaurant") is False


def test_normalize_libelle_lowercases_and_strips():
    assert normalize_libelle("  Restaurant Le Bon Coin  ") == "restaurant le bon coin"


def test_record_and_suggest_tags(db_session):
    tag = Tag(nom="resto")
    db_session.add(tag)
    db_session.commit()

    record_learning(db_session, "Restaurant Le Bon Coin", [tag])
    suggestions = suggest_tags(db_session, "restaurant le bon coin")

    assert [t.nom for t in suggestions] == ["resto"]


def test_suggest_tags_empty_when_unknown(db_session):
    assert suggest_tags(db_session, "Inconnu") == []
