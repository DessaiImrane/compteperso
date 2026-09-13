import datetime
from pathlib import Path
from app.services.backup import (
    DEFAULT_BACKUP_DIR,
    backup_database,
    get_backup_dir,
    set_backup_dir,
    bump_derniere_ouverture,
)


def test_backup_database_copies_file_with_timestamped_name(tmp_path):
    db_path = tmp_path / "comptes.db"
    db_path.write_bytes(b"fake-sqlite-content")
    backup_dir = tmp_path / "backups"

    result = backup_database(db_path, backup_dir, timestamp="2026-08-30T12-00-00")

    assert result == backup_dir / "comptes_2026-08-30T12-00-00.db"
    assert result.read_bytes() == b"fake-sqlite-content"


def test_backup_database_creates_backup_dir_if_missing(tmp_path):
    db_path = tmp_path / "comptes.db"
    db_path.write_bytes(b"x")
    backup_dir = tmp_path / "nested" / "backups"

    backup_database(db_path, backup_dir, timestamp="t")

    assert backup_dir.exists()


def test_get_backup_dir_defaults_when_unset(db_session):
    assert get_backup_dir(db_session) == DEFAULT_BACKUP_DIR


def test_set_then_get_backup_dir_returns_saved_value(db_session):
    set_backup_dir(db_session, "/tmp/mon-dossier-backup")
    assert get_backup_dir(db_session) == Path("/tmp/mon-dossier-backup")


def test_set_backup_dir_twice_overwrites_previous_value(db_session):
    set_backup_dir(db_session, "/tmp/premier")
    set_backup_dir(db_session, "/tmp/second")
    assert get_backup_dir(db_session) == Path("/tmp/second")


def test_bump_derniere_ouverture_returns_none_on_first_ever_open(db_session):
    now = datetime.datetime(2026, 9, 13, 8, 0)
    previous = bump_derniere_ouverture(db_session, now)
    assert previous is None


def test_bump_derniere_ouverture_returns_previous_value_and_stores_new_one(db_session):
    first = datetime.datetime(2026, 9, 6, 8, 0)
    second = datetime.datetime(2026, 9, 13, 9, 30)

    bump_derniere_ouverture(db_session, first)
    previous = bump_derniere_ouverture(db_session, second)

    assert previous == first
    from app.models import Settings
    assert db_session.query(Settings).first().derniere_ouverture == second
