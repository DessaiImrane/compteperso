import shutil
from pathlib import Path


def backup_database(db_path: Path, backup_dir: Path, timestamp: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"comptes_{timestamp}.db"
    shutil.copy2(db_path, destination)
    return destination
