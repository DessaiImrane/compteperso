def _banque_et_compte(client, nom="Bourso"):
    client.post("/banques", data={"nom": nom})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom=nom).first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": nom})
    from app.models import CompteVirtuel
    compte = db.query(CompteVirtuel).filter_by(nom=nom).first()
    return banque, compte


def test_coller_sans_mapping_demande_calibrage(client):
    banque, _ = _banque_et_compte(client)
    resp = client.post(f"/rapprochement/{banque.id}/coller", data={"texte": "05/08/2026\tTest\t-10,00"})
    assert resp.status_code == 200
    assert "calibrage" in resp.text.lower() or "mapping" in resp.text.lower()


def test_mapping_puis_coller_affiche_staging(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/coller",
        data={"texte": "05/08/2026\tRestaurant\t-45,90"},
    )
    assert resp.status_code == 200
    assert "Restaurant" in resp.text
    assert "-45.9" in resp.text or "-45,9" in resp.text


def test_valider_ecrit_transactions_non_verrouillees(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/valider",
        data={
            "compte_virtuel_id__0": str(compte.id),
            "date__0": "2026-08-05",
            "libelle__0": "Restaurant",
            "montant__0": "-45.90",
            "tags__0": "resto",
            "verrouille__0": "",
            "row_count": "1",
            "total_banque_pointe": "-45.90",
            "total_banque_a_venir": "0",
        },
    )
    assert resp.status_code in (200, 303)

    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Restaurant").first()
    assert tx is not None
    assert tx.pointe is True


def test_valider_ignore_lignes_verrouillees(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/valider",
        data={
            "compte_virtuel_id__0": str(compte.id),
            "date__0": "2026-08-05",
            "libelle__0": "Doublon",
            "montant__0": "-10.0",
            "tags__0": "",
            "verrouille__0": "on",
            "row_count": "1",
            "total_banque_pointe": "0",
            "total_banque_a_venir": "0",
        },
    )
    assert resp.status_code in (200, 303)

    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    assert db.query(Transaction).filter_by(libelle="Doublon").first() is None
