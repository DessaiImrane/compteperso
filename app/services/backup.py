import shutil
from pathlib import Path

from app.models import Settings

DEFAULT_BACKUP_DIR = Path.home() / "Google Drive" / "ComptesAppBackups"


def backup_database(db_path: Path, backup_dir: Path, timestamp: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"comptes_{timestamp}.db"
    shutil.copy2(db_path, destination)
    return destination


def get_backup_dir(db) -> Path:
    settings = db.query(Settings).first()
    if settings and settings.backup_dir:
        return Path(settings.backup_dir)
    return DEFAULT_BACKUP_DIR


def set_backup_dir(db, backup_dir: str) -> None:
    settings = db.query(Settings).first()
    if settings:
        settings.backup_dir = backup_dir
    else:
        db.add(Settings(backup_dir=backup_dir))
    db.commit()
