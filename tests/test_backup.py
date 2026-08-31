from pathlib import Path
from app.services.backup import backup_database


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
