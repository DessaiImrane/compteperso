import os
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, MetaData, create_engine, inspect, text
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


def ensure_columns(engine: Engine, metadata: MetaData) -> None:
    """Add columns that exist on the models but not yet on an existing SQLite
    table (no ALTER on new tables — create_all already made those). No
    migration framework: this is a single-developer local app whose schema
    changes fast, and SQLite's ADD COLUMN is enough for that."""
    inspector = inspect(engine)
    for table in metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(engine.dialect)
            default_sql = ""
            if column.default is not None and column.default.is_scalar:
                arg = column.default.arg
                default_sql = f" DEFAULT '{arg}'" if isinstance(arg, str) else f" DEFAULT {arg}"
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_sql}')
                )
