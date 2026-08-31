def test_reglages_shows_default_backup_dir(client):
    resp = client.get("/reglages")
    assert resp.status_code == 200
    assert "ComptesAppBackups" in resp.text


def test_save_reglages_persists_backup_dir(client):
    resp = client.post("/reglages", data={"backup_dir": "/tmp/mon-dossier"})
    assert resp.status_code in (200, 303)

    resp = client.get("/reglages")
    assert "/tmp/mon-dossier" in resp.text
