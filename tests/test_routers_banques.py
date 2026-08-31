def test_create_and_list_banque(client):
    resp = client.post("/banques", data={"nom": "Bourso"})
    assert resp.status_code in (200, 303)

    resp = client.get("/banques")
    assert resp.status_code == 200
    assert "Bourso" in resp.text


def test_add_compte_virtuel_to_banque(client):
    client.post("/banques", data={"nom": "LaPoste"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="LaPoste").first()

    resp = client.post(f"/banques/{banque.id}/comptes", data={"nom": "Maison"})
    assert resp.status_code in (200, 303)

    resp = client.get(f"/banques/{banque.id}")
    assert resp.status_code == 200
    assert "Maison" in resp.text


def test_archiver_compte_virtuel(client):
    client.post("/banques", data={"nom": "LaPoste"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque, CompteVirtuel
    banque = db.query(Banque).filter_by(nom="LaPoste").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Vacances"})
    compte = db.query(CompteVirtuel).filter_by(nom="Vacances").first()

    resp = client.post(f"/comptes/{compte.id}/archiver")
    assert resp.status_code in (200, 303)

    db.refresh(compte)
    assert compte.actif is False
