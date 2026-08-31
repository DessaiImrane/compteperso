def _create_compte(client):
    client.post("/banques", data={"nom": "Bourso"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="Bourso").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Bourso"})
    from app.models import CompteVirtuel
    return db.query(CompteVirtuel).filter_by(nom="Bourso").first()


def test_add_transaction_manually(client):
    compte = _create_compte(client)
    resp = client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-45.90", "libelle": "Restaurant", "tags": "resto"},
    )
    assert resp.status_code in (200, 303)

    resp = client.get(f"/comptes/{compte.id}/transactions")
    assert "Restaurant" in resp.text


def test_pointer_transaction(client):
    compte = _create_compte(client)
    client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-10.0", "libelle": "Test", "tags": ""},
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Test").first()
    assert tx.pointe is False

    resp = client.post(f"/transactions/{tx.id}/pointer")
    assert resp.status_code in (200, 303)
    db.refresh(tx)
    assert tx.pointe is True


def test_duplicate_transaction_prefills_form(client):
    compte = _create_compte(client)
    client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-10.0", "libelle": "Abonnement", "tags": ""},
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Abonnement").first()

    resp = client.get(f"/transactions/{tx.id}/dupliquer")
    assert resp.status_code == 200
    assert "Abonnement" in resp.text
    assert "-10.0" in resp.text or "-10" in resp.text
