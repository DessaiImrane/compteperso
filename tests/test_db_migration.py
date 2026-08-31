from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect, text

from app.db import ensure_columns


def test_ensure_columns_adds_missing_column_with_default():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE demo (id INTEGER PRIMARY KEY)"))

    metadata = MetaData()
    Table(
        "demo", metadata,
        Column("id", Integer, primary_key=True),
        Column("ordre", Integer, default=0),
    )

    ensure_columns(engine, metadata)

    columns = {c["name"] for c in inspect(engine).get_columns("demo")}
    assert "ordre" in columns


def test_ensure_columns_leaves_existing_column_alone():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE demo (id INTEGER PRIMARY KEY, ordre INTEGER)"))
        conn.execute(text("INSERT INTO demo (id, ordre) VALUES (1, 42)"))

    metadata = MetaData()
    Table(
        "demo", metadata,
        Column("id", Integer, primary_key=True),
        Column("ordre", Integer, default=0),
    )

    ensure_columns(engine, metadata)

    with engine.begin() as conn:
        row = conn.execute(text("SELECT ordre FROM demo WHERE id = 1")).one()
    assert row.ordre == 42


def test_ensure_columns_skips_tables_that_do_not_exist_yet():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    Table("absent", metadata, Column("id", Integer, primary_key=True))

    ensure_columns(engine, metadata)  # must not raise
