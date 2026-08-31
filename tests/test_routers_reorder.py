def test_reorder_comptes_persists_new_order(client):
    client.post("/banques", data={"nom": "LaPoste"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="LaPoste").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Economie"})
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Maison"})
    from app.models import CompteVirtuel
    economie = db.query(CompteVirtuel).filter_by(nom="Economie").first()
    maison = db.query(CompteVirtuel).filter_by(nom="Maison").first()
    assert economie.ordre == 0
    assert maison.ordre == 1

    resp = client.post(
        f"/banques/{banque.id}/comptes/ordre",
        json={"ordre": [maison.id, economie.id]},
    )
    assert resp.status_code == 200

    db.refresh(economie)
    db.refresh(maison)
    assert maison.ordre == 0
    assert economie.ordre == 1
