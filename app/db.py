import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_db_path() -> Path:
    override = os.environ.get("COMPTES_DB_PATH")
    if override:
        return Path(override)
    support_dir = Path.home() / "Library" / "Application Support" / "ComptesApp"
    support_dir.mkdir(parents=True, exist_ok=True)
    return support_dir / "comptes.db"


def make_engine(db_path: Path | None = None):
    path = db_path or get_db_path()
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
