def _compte(client, nom="Hello"):
    client.post("/banques", data={"nom": nom})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom=nom).first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": nom})
    from app.models import CompteVirtuel
    return db.query(CompteVirtuel).filter_by(nom=nom).first()


def test_create_creancier(client):
    compte = _compte(client)
    resp = client.post(
        "/creanciers",
        data={
            "nom": "Loyer", "montant_defaut": "800", "compte_source_id": str(compte.id),
            "compte_destination_id": "", "date_prochaine_echeance": "2026-09-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )
    assert resp.status_code in (200, 303)

    resp = client.get("/creanciers")
    assert "Loyer" in resp.text


def test_creanciers_page_shows_flux_totals(client):
    compte = _compte(client, nom="Hello")
    dest = _compte(client, nom="LaPoste")
    client.post(
        "/creanciers",
        data={
            "nom": "Virement", "montant_defaut": "250", "compte_source_id": str(compte.id),
            "compte_destination_id": str(dest.id), "date_prochaine_echeance": "2026-09-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )

    resp = client.get("/creanciers")

    assert "Flux" in resp.text
    assert "Hello" in resp.text and "LaPoste" in resp.text
    assert "250.00" in resp.text


def test_duplicate_creancier_prefills_form(client):
    compte = _compte(client)
    client.post(
        "/creanciers",
        data={
            "nom": "Abonnement", "montant_defaut": "10", "compte_source_id": str(compte.id),
            "compte_destination_id": "", "date_prochaine_echeance": "2026-09-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Creancier
    creancier = db.query(Creancier).filter_by(nom="Abonnement").first()

    resp = client.get(f"/creanciers/{creancier.id}/dupliquer")
    assert resp.status_code == 200
    assert "Abonnement" in resp.text


def test_edit_creancier_form_prefills_and_updates(client):
    compte = _compte(client)
    client.post(
        "/creanciers",
        data={
            "nom": "Avant", "montant_defaut": "10", "compte_source_id": str(compte.id),
            "compte_destination_id": "", "date_prochaine_echeance": "2026-09-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Creancier
    creancier = db.query(Creancier).filter_by(nom="Avant").first()

    resp = client.get(f"/creanciers/{creancier.id}/modifier")
    assert resp.status_code == 200
    assert "Avant" in resp.text

    resp = client.post(
        f"/creanciers/{creancier.id}/modifier",
        data={
            "nom": "Après", "montant_defaut": "20", "compte_source_id": str(compte.id),
            "compte_destination_id": "", "date_prochaine_echeance": "2026-10-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )
    assert resp.status_code in (200, 303)

    db.refresh(creancier)
    assert creancier.nom == "Après"
    assert creancier.montant_defaut == 20.0


def test_desactiver_creancier(client):
    compte = _compte(client)
    client.post(
        "/creanciers",
        data={
            "nom": "Test", "montant_defaut": "5", "compte_source_id": str(compte.id),
            "compte_destination_id": "", "date_prochaine_echeance": "2026-09-01",
            "recurrence": "mensuelle", "fin_type": "jamais",
        },
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Creancier
    creancier = db.query(Creancier).filter_by(nom="Test").first()

    resp = client.post(f"/creanciers/{creancier.id}/desactiver")
    assert resp.status_code in (200, 303)
    db.refresh(creancier)
    assert creancier.actif is False
