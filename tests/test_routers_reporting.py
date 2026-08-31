def _compte_avec_transaction(client):
    client.post("/banques", data={"nom": "Hello"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="Hello").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Budget"})
    from app.models import CompteVirtuel
    compte = db.query(CompteVirtuel).filter_by(nom="Budget").first()
    client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-09-05", "montant": "-40.0", "libelle": "Resto", "tags": "resto"},
    )
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Resto").first()
    client.post(f"/transactions/{tx.id}/pointer")
    return compte


def test_reporting_mensuel_shows_totals(client):
    compte = _compte_avec_transaction(client)
    resp = client.get(f"/reporting/mensuel?compte_virtuel_id={compte.id}&annee=2026&mois=9")
    assert resp.status_code == 200
    assert "40.0" in resp.text or "40,0" in resp.text


def test_reporting_tags_shows_chart_data(client):
    _compte_avec_transaction(client)
    resp = client.get("/reporting/tags?date_debut=2026-09-01&date_fin=2026-09-30")
    assert resp.status_code == 200
    assert "resto" in resp.text
    assert "chart" in resp.text.lower()
