# App Comptes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI+HTMX+SQLite app that replaces BankPerfect and the Excel budget file — accounts, transactions, recurring "créanciers", copy-paste bank reconciliation, and reporting.

**Architecture:** Single FastAPI process serving server-rendered HTMX pages, backed by SQLAlchemy models over a local SQLite file. Business logic (créancier generation, parsing, dedup, totals, reporting) lives in plain functions under `app/services/`, independent of FastAPI, so it's unit-testable without HTTP. Routers in `app/routers/` are thin — they call services and render Jinja2 templates. A `launcher.py` starts uvicorn in a background thread and opens a chrome-less `pywebview` window; closing the window stops the server and triggers a DB backup copy.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, HTMX (CDN), Chart.js (CDN), SQLAlchemy 2.0, SQLite, pywebview, pytest, httpx (TestClient).

**Spec:** `docs/superpowers/specs/2026-08-30-app-comptes-design.md`

## Global Constraints

- No bank API integration — all bank data enters via copy-pasted text, parsed with a per-banque calibrated mapping.
- No import of legacy BankPerfect/Excel data — app starts with an empty database, seeded by the user through the UI.
- Comptes virtuels are freely created/renamed/archived per banque from the UI — never hardcoded.
- Tags are free-form, created on the fly — no predefined tag list/screen.
- SQLite database file lives outside any cloud-synced folder (`~/Library/Application Support/ComptesApp/comptes.db`); only the post-shutdown backup copy targets a (configurable) synced folder.
- No e2e test suite required for V1 — pytest covers service-layer logic; UI/launcher verified manually.

---

## File Structure

```
app/
  __init__.py
  main.py                    # FastAPI app, mounts routers, Jinja2Templates
  db.py                      # Base, engine/session factory, get_db_path(), get_db() dependency
  models.py                  # Banque, CompteVirtuel, Tag, Transaction, transaction_tags, Creancier,
                              # RapprochementSession, MappingParsing, TagLearning
  services/
    __init__.py
    creancier_engine.py       # next_date(), generate_due_echeances()
    parsing.py                 # parse_pasted_text(), parse_date_fr(), parse_montant_fr()
    dedup.py                   # is_duplicate()
    tag_learning.py            # normalize_libelle(), suggest_tags(), record_learning()
    totals.py                  # total_pointe(), total_a_venir(), calcule_ecart()
    reporting.py                # rapport_mensuel(), depenses_par_tag()
    backup.py                   # backup_database()
  routers/
    __init__.py
    banques.py                  # CRUD banque + comptes virtuels, dashboard drill-down
    transactions.py              # list/add/duplicate transaction, tag assignment
    creanciers.py                 # CRUD créancier, duplicate
    rapprochement.py               # paste -> staging -> validate -> totals/écart
    reporting.py                    # monthly créancier report + tag chart screens
  templates/
    base.html
    banques/{list,detail}.html
    transactions/{list,form}.html
    creanciers/{list,form}.html
    rapprochement/{paste,staging}.html
    reporting/{mensuel,tags}.html
launcher.py                       # pywebview window + uvicorn thread + shutdown backup
scripts/ComptesApp.command         # double-clickable launcher script for /Applications
tests/
  conftest.py                       # db_session fixture, TestClient fixture
  test_models.py
  test_creancier_engine.py
  test_parsing.py
  test_dedup_tag_learning.py
  test_totals.py
  test_reporting.py
  test_backup.py
  test_routers_banques.py
  test_routers_transactions.py
  test_routers_creanciers.py
  test_routers_rapprochement.py
  test_routers_reporting.py
pyproject.toml
```

---

### Task 1: Project scaffolding & DB session

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/db.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Produces: `app.db.Base` (SQLAlchemy `DeclarativeBase`), `app.db.get_db_path() -> Path`, `app.db.make_engine(db_path: Path | None = None) -> Engine`, `app.db.SessionLocal` (sessionmaker bound to the default engine), `app.db.get_db() -> Generator[Session, None, None]` (FastAPI dependency), `app.main.app` (FastAPI instance).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "comptes-app"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "pywebview>=5.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: install completes without error.

- [ ] **Step 3: Write `app/db.py`**

```python
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
```

- [ ] **Step 4: Write `app/main.py`**

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Comptes")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Write `tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Write `tests/test_main.py`**

```python
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_main.py -v`
Expected: PASS (1 test)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml app/__init__.py app/db.py app/main.py tests/__init__.py tests/conftest.py tests/test_main.py
git commit -m "feat: scaffold FastAPI app with SQLite session plumbing"
```

---

### Task 2: Core models — Banque, CompteVirtuel, Tag, Transaction

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `app.db.Base` (Task 1).
- Produces: `Banque(id, nom)`, `CompteVirtuel(id, banque_id, nom, actif)`, `Tag(id, nom)`, `transaction_tags` (association table), `Transaction(id, date, compte_virtuel_id, montant, libelle, pointe, creancier_id, transfer_link_id, tags)`. `Transaction.creancier_id` is a plain FK column here (no relationship yet — `Creancier` model arrives in Task 3); tests in this task pass `creancier_id=None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import datetime
from app.models import Banque, CompteVirtuel, Tag, Transaction


def test_create_banque_compte_and_transaction_with_tags(db_session):
    banque = Banque(nom="LaPoste")
    compte = CompteVirtuel(nom="Maison", banque=banque, actif=True)
    tag_resto = Tag(nom="resto")
    tx = Transaction(
        date=datetime.date(2026, 8, 1),
        compte_virtuel=compte,
        montant=-42.5,
        libelle="Restaurant Le Bon Coin",
        pointe=True,
        tags=[tag_resto],
    )
    db_session.add_all([banque, compte, tag_resto, tx])
    db_session.commit()

    saved = db_session.query(Transaction).one()
    assert saved.montant == -42.5
    assert saved.compte_virtuel.nom == "Maison"
    assert saved.compte_virtuel.banque.nom == "LaPoste"
    assert [t.nom for t in saved.tags] == ["resto"]
    assert saved.creancier_id is None
    assert saved.transfer_link_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write `app/models.py`**

```python
from __future__ import annotations

import datetime

from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

transaction_tags = Table(
    "transaction_tags",
    Base.metadata,
    Column("transaction_id", ForeignKey("transactions.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Banque(Base):
    __tablename__ = "banques"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(unique=True)

    comptes: Mapped[list["CompteVirtuel"]] = relationship(back_populates="banque")


class CompteVirtuel(Base):
    __tablename__ = "comptes_virtuels"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"))
    nom: Mapped[str]
    actif: Mapped[bool] = mapped_column(default=True)

    banque: Mapped["Banque"] = relationship(back_populates="comptes")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(unique=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date]
    compte_virtuel_id: Mapped[int] = mapped_column(ForeignKey("comptes_virtuels.id"))
    montant: Mapped[float]
    libelle: Mapped[str]
    pointe: Mapped[bool] = mapped_column(default=False)
    creancier_id: Mapped[int | None] = mapped_column(ForeignKey("creanciers.id"), nullable=True)
    transfer_link_id: Mapped[str | None] = mapped_column(nullable=True)

    compte_virtuel: Mapped["CompteVirtuel"] = relationship()
    tags: Mapped[list["Tag"]] = relationship(secondary=transaction_tags)
```

Note: `creanciers.id` is referenced before `Creancier` exists — Task 3 defines that table in the same `app/models.py` file (SQLAlchemy resolves the FK string lazily at `create_all()` time, so column order across the file doesn't matter as long as both classes are defined in the same module before metadata creation).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `creanciers` table doesn't exist yet (Task 3 adds it). This is expected at this point; proceed to Task 3 before this test can pass. Note it in the commit message as WIP if needed, or fold Steps 3-4 together with Task 3's model addition before committing. **Do this instead:** add a minimal placeholder `Creancier` model now (just enough to satisfy the FK), and let Task 3 replace it with the full definition.

- [ ] **Step 3b: Add minimal `Creancier` placeholder to `app/models.py`**

```python
class Creancier(Base):
    __tablename__ = "creanciers"

    id: Mapped[int] = mapped_column(primary_key=True)
```

- [ ] **Step 4b: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add Banque, CompteVirtuel, Tag, Transaction models"
```

---

### Task 3: Créancier model + date-advance helper

**Files:**
- Modify: `app/models.py` (replace the `Creancier` placeholder from Task 2 with the full model)
- Create: `app/services/__init__.py`
- Create: `app/services/creancier_engine.py` (this task: only `next_date`; `generate_due_echeances` comes in Task 4)
- Test: `tests/test_creancier_engine.py`

**Interfaces:**
- Consumes: `Transaction`, `CompteVirtuel` (Task 2).
- Produces: `Creancier(id, nom, montant_defaut, compte_source_id, compte_destination_id, date_prochaine_echeance, recurrence, intervalle_jours, fin_type, fin_date, fin_occurrences, occurrences_generees, actif)`. `next_date(current: date, recurrence: str, intervalle_jours: int | None = None) -> date | None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_creancier_engine.py
import datetime
import pytest
from app.services.creancier_engine import next_date


def test_next_date_mensuelle_handles_end_of_month():
    assert next_date(datetime.date(2026, 1, 31), "mensuelle") == datetime.date(2026, 2, 28)


def test_next_date_hebdomadaire_adds_seven_days():
    assert next_date(datetime.date(2026, 8, 1), "hebdomadaire") == datetime.date(2026, 8, 8)


def test_next_date_custom_uses_intervalle_jours():
    assert next_date(datetime.date(2026, 8, 1), "custom", intervalle_jours=10) == datetime.date(2026, 8, 11)


def test_next_date_custom_without_intervalle_raises():
    with pytest.raises(ValueError):
        next_date(datetime.date(2026, 8, 1), "custom")


def test_next_date_aucune_returns_none():
    assert next_date(datetime.date(2026, 8, 1), "aucune") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_creancier_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: Write `app/services/creancier_engine.py`**

```python
import datetime

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _add_months(d: datetime.date, months: int) -> datetime.date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    max_day = _DAYS_IN_MONTH[month - 1]
    if month == 2 and _is_leap(year):
        max_day = 29
    return datetime.date(year, month, min(d.day, max_day))


def next_date(
    current: datetime.date, recurrence: str, intervalle_jours: int | None = None
) -> datetime.date | None:
    if recurrence == "mensuelle":
        return _add_months(current, 1)
    if recurrence == "hebdomadaire":
        return current + datetime.timedelta(days=7)
    if recurrence == "custom":
        if not intervalle_jours:
            raise ValueError("intervalle_jours requis pour une récurrence custom")
        return current + datetime.timedelta(days=intervalle_jours)
    if recurrence == "aucune":
        return None
    raise ValueError(f"récurrence inconnue: {recurrence}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_creancier_engine.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Replace the `Creancier` placeholder in `app/models.py`**

```python
class Creancier(Base):
    __tablename__ = "creanciers"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str]
    montant_defaut: Mapped[float]
    compte_source_id: Mapped[int] = mapped_column(ForeignKey("comptes_virtuels.id"))
    compte_destination_id: Mapped[int | None] = mapped_column(
        ForeignKey("comptes_virtuels.id"), nullable=True
    )
    date_prochaine_echeance: Mapped[datetime.date | None]
    recurrence: Mapped[str]
    intervalle_jours: Mapped[int | None] = mapped_column(nullable=True)
    fin_type: Mapped[str] = mapped_column(default="jamais")
    fin_date: Mapped[datetime.date | None] = mapped_column(nullable=True)
    fin_occurrences: Mapped[int | None] = mapped_column(nullable=True)
    occurrences_generees: Mapped[int] = mapped_column(default=0)
    actif: Mapped[bool] = mapped_column(default=True)

    compte_source: Mapped["CompteVirtuel"] = relationship(foreign_keys=[compte_source_id])
    compte_destination: Mapped["CompteVirtuel | None"] = relationship(
        foreign_keys=[compte_destination_id]
    )
```

- [ ] **Step 6: Write a model-level test for `Creancier`, run it, confirm pass**

```python
# append to tests/test_models.py
import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier


def test_create_creancier(db_session):
    banque = Banque(nom="HelloBank")
    source = CompteVirtuel(nom="Budget famille", banque=banque)
    creancier = Creancier(
        nom="Loyer",
        montant_defaut=800.0,
        compte_source=source,
        date_prochaine_echeance=dt.date(2026, 9, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add_all([banque, source, creancier])
    db_session.commit()

    saved = db_session.query(Creancier).one()
    assert saved.montant_defaut == 800.0
    assert saved.compte_destination is None
    assert saved.occurrences_generees == 0
```

Run: `pytest tests/test_models.py tests/test_creancier_engine.py -v`
Expected: PASS (7 tests)

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/services/__init__.py app/services/creancier_engine.py tests/test_models.py tests/test_creancier_engine.py
git commit -m "feat: add Creancier model and next_date recurrence helper"
```

---

### Task 4: Créancier generation engine

**Files:**
- Modify: `app/services/creancier_engine.py` (add `generate_due_echeances`)
- Test: `tests/test_creancier_engine.py`

**Interfaces:**
- Consumes: `next_date` (Task 3), `Creancier`, `Transaction`, `CompteVirtuel` (Tasks 2-3), `sqlalchemy.orm.Session`.
- Produces: `generate_due_echeances(db: Session, today: datetime.date) -> list[Transaction]`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_creancier_engine.py
import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Transaction
from app.services.creancier_engine import generate_due_echeances


def _make_comptes(db_session):
    banque = Banque(nom="Test")
    hello = CompteVirtuel(nom="Hello", banque=banque)
    poste = CompteVirtuel(nom="Poste/Maison", banque=banque)
    db_session.add_all([banque, hello, poste])
    db_session.commit()
    return hello, poste


def test_generate_interne_creates_two_linked_transactions(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Virement loyer",
        montant_defaut=800.0,
        compte_source=hello,
        compte_destination=poste,
        date_prochaine_echeance=dt.date(2026, 9, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2
    debit, credit = created
    assert debit.compte_virtuel_id == hello.id and debit.montant == -800.0
    assert credit.compte_virtuel_id == poste.id and credit.montant == 800.0
    assert debit.transfer_link_id == credit.transfer_link_id
    assert debit.creancier_id == creancier.id
    assert creancier.date_prochaine_echeance == dt.date(2026, 10, 1)
    assert creancier.occurrences_generees == 1


def test_generate_externe_creates_one_transaction(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Prélèvement loyer",
        montant_defaut=800.0,
        compte_source=poste,
        compte_destination=None,
        date_prochaine_echeance=dt.date(2026, 9, 5),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 5))

    assert len(created) == 1
    assert created[0].montant == -800.0
    assert created[0].transfer_link_id is None


def test_generate_catches_up_multiple_missed_months(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Abonnement",
        montant_defaut=10.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 6, 1),
        recurrence="mensuelle",
        fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 4  # juin, juillet, août, septembre
    assert [t.date for t in created] == [
        dt.date(2026, 6, 1), dt.date(2026, 7, 1), dt.date(2026, 8, 1), dt.date(2026, 9, 1)
    ]
    assert creancier.date_prochaine_echeance == dt.date(2026, 10, 1)
    assert creancier.occurrences_generees == 4


def test_generate_stops_at_fin_occurrences(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Remboursement",
        montant_defaut=50.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 1, 1),
        recurrence="mensuelle",
        fin_type="occurrences",
        fin_occurrences=2,
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2
    assert creancier.actif is False


def test_generate_stops_at_fin_date(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Assurance temporaire",
        montant_defaut=30.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 7, 1),
        recurrence="mensuelle",
        fin_type="date",
        fin_date=dt.date(2026, 8, 1),
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert len(created) == 2  # juillet, août — s'arrête à fin_date incluse
    assert creancier.actif is False


def test_generate_ignores_inactive_creancier(db_session):
    hello, poste = _make_comptes(db_session)
    creancier = Creancier(
        nom="Archivé",
        montant_defaut=15.0,
        compte_source=hello,
        date_prochaine_echeance=dt.date(2026, 1, 1),
        recurrence="mensuelle",
        fin_type="jamais",
        actif=False,
    )
    db_session.add(creancier)
    db_session.commit()

    created = generate_due_echeances(db_session, dt.date(2026, 9, 1))

    assert created == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_creancier_engine.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_due_echeances'`

- [ ] **Step 3: Add `generate_due_echeances` to `app/services/creancier_engine.py`**

```python
import uuid

from sqlalchemy.orm import Session

from app.models import Creancier, Transaction


def generate_due_echeances(db: Session, today) -> list[Transaction]:
    created: list[Transaction] = []
    creanciers = db.query(Creancier).filter(Creancier.actif.is_(True)).all()

    for creancier in creanciers:
        while (
            creancier.date_prochaine_echeance is not None
            and creancier.date_prochaine_echeance <= today
        ):
            echeance_date = creancier.date_prochaine_echeance

            if creancier.compte_destination_id is not None:
                transfer_id = str(uuid.uuid4())
                debit = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_source_id,
                    montant=-abs(creancier.montant_defaut),
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                    transfer_link_id=transfer_id,
                )
                credit = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_destination_id,
                    montant=abs(creancier.montant_defaut),
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                    transfer_link_id=transfer_id,
                )
                db.add_all([debit, credit])
                created.extend([debit, credit])
            else:
                debit = Transaction(
                    date=echeance_date,
                    compte_virtuel_id=creancier.compte_source_id,
                    montant=-abs(creancier.montant_defaut),
                    libelle=creancier.nom,
                    pointe=False,
                    creancier_id=creancier.id,
                )
                db.add(debit)
                created.append(debit)

            creancier.occurrences_generees += 1

            stop = False
            if creancier.fin_type == "occurrences" and creancier.fin_occurrences is not None:
                if creancier.occurrences_generees >= creancier.fin_occurrences:
                    stop = True
            if creancier.fin_type == "date" and creancier.fin_date is not None:
                if echeance_date >= creancier.fin_date:
                    stop = True
            if creancier.recurrence == "aucune":
                stop = True

            if stop:
                creancier.actif = False
                creancier.date_prochaine_echeance = None
                break

            creancier.date_prochaine_echeance = next_date(
                echeance_date, creancier.recurrence, creancier.intervalle_jours
            )

    db.commit()
    return created
```

Add the missing import at the top of the file: `import datetime` stays, plus this function relies on `next_date` already defined below/above in the same module — keep both functions in `app/services/creancier_engine.py`, `next_date` first, `generate_due_echeances` second, sharing the module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_creancier_engine.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/creancier_engine.py tests/test_creancier_engine.py
git commit -m "feat: generate due creancier echeances with catch-up loop"
```

---

### Task 5: Parsing service

**Files:**
- Create: `app/services/parsing.py`
- Modify: `app/models.py` (add `MappingParsing`)
- Test: `tests/test_parsing.py`

**Interfaces:**
- Produces: `MappingParsing(id, banque_id, colonne_date, colonne_libelle, colonne_montant, separateur)`, `parse_date_fr(s: str) -> date`, `parse_montant_fr(s: str) -> float`, `parse_pasted_text(text: str, mapping: MappingParsing) -> list[dict]` (each dict: `{"date": date, "libelle": str, "montant": float}`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_parsing.py
import datetime
import pytest
from app.services.parsing import parse_date_fr, parse_montant_fr, parse_pasted_text


class FakeMapping:
    def __init__(self, colonne_date=0, colonne_libelle=1, colonne_montant=2, separateur="\t"):
        self.colonne_date = colonne_date
        self.colonne_libelle = colonne_libelle
        self.colonne_montant = colonne_montant
        self.separateur = separateur


def test_parse_date_fr():
    assert parse_date_fr("05/08/2026") == datetime.date(2026, 8, 5)


def test_parse_montant_fr_negative_with_comma():
    assert parse_montant_fr("-45,90 €") == -45.90


def test_parse_montant_fr_positive_with_thousands_separator():
    assert parse_montant_fr("1 234,56") == 1234.56


def test_parse_pasted_text_splits_columns_by_mapping():
    text = "05/08/2026\tRestaurant Le Bon Coin\t-45,90\n06/08/2026\tSalaire\t1 500,00"
    mapping = FakeMapping()
    rows = parse_pasted_text(text, mapping)
    assert rows == [
        {"date": datetime.date(2026, 8, 5), "libelle": "Restaurant Le Bon Coin", "montant": -45.90},
        {"date": datetime.date(2026, 8, 6), "libelle": "Salaire", "montant": 1500.00},
    ]


def test_parse_pasted_text_skips_blank_and_short_lines():
    text = "05/08/2026\tRestaurant\t-45,90\n\nligne incomplete"
    mapping = FakeMapping()
    rows = parse_pasted_text(text, mapping)
    assert len(rows) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_parsing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.parsing'`

- [ ] **Step 3: Add `MappingParsing` to `app/models.py`**

```python
class MappingParsing(Base):
    __tablename__ = "mappings_parsing"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"), unique=True)
    colonne_date: Mapped[int]
    colonne_libelle: Mapped[int]
    colonne_montant: Mapped[int]
    separateur: Mapped[str] = mapped_column(default="\t")
```

- [ ] **Step 4: Write `app/services/parsing.py`**

```python
import datetime


def parse_date_fr(s: str) -> datetime.date:
    day, month, year = s.strip().split("/")
    return datetime.date(int(year), int(month), int(day))


def parse_montant_fr(s: str) -> float:
    cleaned = s.strip().replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    return float(cleaned)


def parse_pasted_text(text: str, mapping) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        cols = line.split(mapping.separateur)
        needed = max(mapping.colonne_date, mapping.colonne_libelle, mapping.colonne_montant)
        if len(cols) <= needed:
            continue
        rows.append(
            {
                "date": parse_date_fr(cols[mapping.colonne_date]),
                "libelle": cols[mapping.colonne_libelle].strip(),
                "montant": parse_montant_fr(cols[mapping.colonne_montant]),
            }
        )
    return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_parsing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/services/parsing.py tests/test_parsing.py
git commit -m "feat: parse pasted bank text via per-banque column mapping"
```

---

### Task 6: Dedup + TagLearning services

**Files:**
- Create: `app/services/dedup.py`
- Create: `app/services/tag_learning.py`
- Modify: `app/models.py` (add `TagLearning`)
- Test: `tests/test_dedup_tag_learning.py`

**Interfaces:**
- Consumes: `Transaction`, `Tag` (Task 2).
- Produces: `TagLearning(id, libelle_pattern, tag_id)`, `is_duplicate(db, compte_virtuel_id, date, montant, libelle) -> bool`, `normalize_libelle(s: str) -> str`, `suggest_tags(db, libelle: str) -> list[Tag]`, `record_learning(db, libelle: str, tags: list[Tag]) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dedup_tag_learning.py
import datetime as dt
from app.models import Banque, CompteVirtuel, Tag, Transaction
from app.services.dedup import is_duplicate
from app.services.tag_learning import normalize_libelle, suggest_tags, record_learning


def _compte(db_session):
    banque = Banque(nom="Bourso")
    compte = CompteVirtuel(nom="Bourso", banque=banque)
    db_session.add_all([banque, compte])
    db_session.commit()
    return compte


def test_is_duplicate_true_for_exact_match(db_session):
    compte = _compte(db_session)
    tx = Transaction(
        date=dt.date(2026, 8, 5), compte_virtuel=compte, montant=-45.9, libelle="Restaurant"
    )
    db_session.add(tx)
    db_session.commit()

    assert is_duplicate(db_session, compte.id, dt.date(2026, 8, 5), -45.9, "Restaurant") is True


def test_is_duplicate_false_when_no_match(db_session):
    compte = _compte(db_session)
    assert is_duplicate(db_session, compte.id, dt.date(2026, 8, 5), -45.9, "Restaurant") is False


def test_normalize_libelle_lowercases_and_strips():
    assert normalize_libelle("  Restaurant Le Bon Coin  ") == "restaurant le bon coin"


def test_record_and_suggest_tags(db_session):
    tag = Tag(nom="resto")
    db_session.add(tag)
    db_session.commit()

    record_learning(db_session, "Restaurant Le Bon Coin", [tag])
    suggestions = suggest_tags(db_session, "restaurant le bon coin")

    assert [t.nom for t in suggestions] == ["resto"]


def test_suggest_tags_empty_when_unknown(db_session):
    assert suggest_tags(db_session, "Inconnu") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup_tag_learning.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add `TagLearning` to `app/models.py`**

```python
class TagLearning(Base):
    __tablename__ = "tag_learning"

    id: Mapped[int] = mapped_column(primary_key=True)
    libelle_pattern: Mapped[str]
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"))

    tag: Mapped["Tag"] = relationship()
```

- [ ] **Step 4: Write `app/services/dedup.py`**

```python
from app.models import Transaction


def is_duplicate(db, compte_virtuel_id: int, date, montant: float, libelle: str) -> bool:
    return (
        db.query(Transaction)
        .filter_by(
            compte_virtuel_id=compte_virtuel_id, date=date, montant=montant, libelle=libelle
        )
        .first()
        is not None
    )
```

- [ ] **Step 5: Write `app/services/tag_learning.py`**

```python
from app.models import Tag, TagLearning


def normalize_libelle(s: str) -> str:
    return s.strip().lower()


def suggest_tags(db, libelle: str) -> list[Tag]:
    key = normalize_libelle(libelle)
    learnings = db.query(TagLearning).filter_by(libelle_pattern=key).all()
    return [learning.tag for learning in learnings]


def record_learning(db, libelle: str, tags: list[Tag]) -> None:
    key = normalize_libelle(libelle)
    for tag in tags:
        exists = (
            db.query(TagLearning).filter_by(libelle_pattern=key, tag_id=tag.id).first()
        )
        if not exists:
            db.add(TagLearning(libelle_pattern=key, tag_id=tag.id))
    db.commit()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_dedup_tag_learning.py -v`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/services/dedup.py app/services/tag_learning.py tests/test_dedup_tag_learning.py
git commit -m "feat: dedup check and learned libelle-to-tag suggestions"
```

---

### Task 7: Totals & écart service + RapprochementSession

**Files:**
- Create: `app/services/totals.py`
- Modify: `app/models.py` (add `RapprochementSession`)
- Test: `tests/test_totals.py`

**Interfaces:**
- Consumes: `Transaction`, `CompteVirtuel`, `Banque` (Task 2).
- Produces: `RapprochementSession(id, banque_id, date, total_banque_pointe, total_banque_a_venir, total_pointe_calcule, ecart)`, `total_pointe(db, compte_virtuel_id) -> float`, `total_a_venir(db, compte_virtuel_id) -> float`, `total_pointe_banque(db, banque_id) -> float` (sums across all comptes virtuels of that banque), `calcule_ecart(total_banque: float, total_calcule: float) -> float`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_totals.py
import datetime as dt
from app.models import Banque, CompteVirtuel, Transaction
from app.services.totals import total_pointe, total_a_venir, total_pointe_banque, calcule_ecart


def _setup(db_session):
    banque = Banque(nom="LaPoste")
    economie = CompteVirtuel(nom="Economie", banque=banque)
    maison = CompteVirtuel(nom="Maison", banque=banque)
    db_session.add_all([banque, economie, maison])
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 8, 1), compte_virtuel=economie, montant=100.0, libelle="a", pointe=True),
            Transaction(date=dt.date(2026, 8, 2), compte_virtuel=economie, montant=-20.0, libelle="b", pointe=False),
            Transaction(date=dt.date(2026, 8, 3), compte_virtuel=maison, montant=-30.0, libelle="c", pointe=True),
        ]
    )
    db_session.commit()
    return banque, economie, maison


def test_total_pointe_sums_only_pointed(db_session):
    _, economie, _ = _setup(db_session)
    assert total_pointe(db_session, economie.id) == 100.0


def test_total_a_venir_sums_only_unpointed(db_session):
    _, economie, _ = _setup(db_session)
    assert total_a_venir(db_session, economie.id) == -20.0


def test_total_pointe_banque_sums_across_comptes(db_session):
    banque, _, _ = _setup(db_session)
    assert total_pointe_banque(db_session, banque.id) == 70.0  # 100 + (-30)


def test_calcule_ecart_rounds_to_cents():
    assert calcule_ecart(70.001, 70.0) == 0.0
    assert calcule_ecart(70.5, 70.0) == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_totals.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add `RapprochementSession` to `app/models.py`**

```python
class RapprochementSession(Base):
    __tablename__ = "rapprochement_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    banque_id: Mapped[int] = mapped_column(ForeignKey("banques.id"))
    date: Mapped[datetime.date]
    total_banque_pointe: Mapped[float]
    total_banque_a_venir: Mapped[float]
    total_pointe_calcule: Mapped[float]
    ecart: Mapped[float]
```

- [ ] **Step 4: Write `app/services/totals.py`**

```python
from app.models import CompteVirtuel, Transaction


def total_pointe(db, compte_virtuel_id: int) -> float:
    rows = (
        db.query(Transaction.montant)
        .filter_by(compte_virtuel_id=compte_virtuel_id, pointe=True)
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def total_a_venir(db, compte_virtuel_id: int) -> float:
    rows = (
        db.query(Transaction.montant)
        .filter_by(compte_virtuel_id=compte_virtuel_id, pointe=False)
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def total_pointe_banque(db, banque_id: int) -> float:
    compte_ids = [c.id for c in db.query(CompteVirtuel).filter_by(banque_id=banque_id).all()]
    if not compte_ids:
        return 0.0
    rows = (
        db.query(Transaction.montant)
        .filter(Transaction.compte_virtuel_id.in_(compte_ids), Transaction.pointe.is_(True))
        .all()
    )
    return round(sum(r[0] for r in rows), 2)


def calcule_ecart(total_banque: float, total_calcule: float) -> float:
    return round(total_banque - total_calcule, 2)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_totals.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/services/totals.py tests/test_totals.py
git commit -m "feat: pointed/upcoming totals and banque-vs-app ecart calculation"
```

---

### Task 8: Reporting service

**Files:**
- Create: `app/services/reporting.py`
- Test: `tests/test_reporting.py`

**Interfaces:**
- Consumes: `Transaction`, `Tag` (Task 2).
- Produces: `rapport_mensuel(db, compte_virtuel_id, annee, mois) -> dict` (keys: `recurrent_prevu`, `recurrent_pointe`, `non_recurrent_pointe`), `depenses_par_tag(db, date_debut, date_fin) -> dict[str, float]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reporting.py
import datetime as dt
from app.models import Banque, CompteVirtuel, Creancier, Tag, Transaction
from app.services.reporting import rapport_mensuel, depenses_par_tag


def _compte(db_session):
    banque = Banque(nom="Hello")
    compte = CompteVirtuel(nom="Budget famille", banque=banque)
    db_session.add_all([banque, compte])
    db_session.commit()
    return compte


def test_rapport_mensuel_splits_recurrent_and_non_recurrent(db_session):
    compte = _compte(db_session)
    creancier = Creancier(
        nom="Loyer", montant_defaut=800.0, compte_source=compte,
        date_prochaine_echeance=dt.date(2026, 9, 1), recurrence="mensuelle", fin_type="jamais",
    )
    db_session.add(creancier)
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 9, 1), compte_virtuel=compte, montant=-800.0,
                        libelle="Loyer", pointe=True, creancier_id=creancier.id),
            Transaction(date=dt.date(2026, 9, 3), compte_virtuel=compte, montant=-60.0,
                        libelle="Courses", pointe=True),
            Transaction(date=dt.date(2026, 9, 4), compte_virtuel=compte, montant=-25.0,
                        libelle="Courses", pointe=False),
            Transaction(date=dt.date(2026, 8, 31), compte_virtuel=compte, montant=-10.0,
                        libelle="Hors periode", pointe=True),
        ]
    )
    db_session.commit()

    rapport = rapport_mensuel(db_session, compte.id, 2026, 9)

    assert rapport == {
        "recurrent_prevu": 800.0,
        "recurrent_pointe": 800.0,
        "non_recurrent_pointe": 60.0,
    }


def test_depenses_par_tag_aggregates_negative_amounts(db_session):
    compte = _compte(db_session)
    resto = Tag(nom="resto")
    courses = Tag(nom="courses")
    db_session.add_all([resto, courses])
    db_session.commit()
    db_session.add_all(
        [
            Transaction(date=dt.date(2026, 9, 1), compte_virtuel=compte, montant=-40.0,
                        libelle="a", tags=[resto]),
            Transaction(date=dt.date(2026, 9, 2), compte_virtuel=compte, montant=-15.0,
                        libelle="b", tags=[resto]),
            Transaction(date=dt.date(2026, 9, 3), compte_virtuel=compte, montant=-60.0,
                        libelle="c", tags=[courses]),
            Transaction(date=dt.date(2026, 9, 4), compte_virtuel=compte, montant=1500.0,
                        libelle="salaire", tags=[]),
        ]
    )
    db_session.commit()

    result = depenses_par_tag(db_session, dt.date(2026, 9, 1), dt.date(2026, 9, 30))

    assert result == {"resto": 55.0, "courses": 60.0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reporting.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `app/services/reporting.py`**

```python
import calendar
import datetime
from collections import defaultdict

from app.models import Transaction


def rapport_mensuel(db, compte_virtuel_id: int, annee: int, mois: int) -> dict:
    start = datetime.date(annee, mois, 1)
    end = datetime.date(annee, mois, calendar.monthrange(annee, mois)[1])
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.compte_virtuel_id == compte_virtuel_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .all()
    )
    recurrent = [t for t in txs if t.creancier_id is not None]
    non_recurrent = [t for t in txs if t.creancier_id is None]
    return {
        "recurrent_prevu": round(sum(abs(t.montant) for t in recurrent), 2),
        "recurrent_pointe": round(sum(abs(t.montant) for t in recurrent if t.pointe), 2),
        "non_recurrent_pointe": round(
            sum(abs(t.montant) for t in non_recurrent if t.pointe), 2
        ),
    }


def depenses_par_tag(db, date_debut: datetime.date, date_fin: datetime.date) -> dict[str, float]:
    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date >= date_debut,
            Transaction.date <= date_fin,
            Transaction.montant < 0,
        )
        .all()
    )
    agg: dict[str, float] = defaultdict(float)
    for t in txs:
        for tag in t.tags:
            agg[tag.nom] += abs(t.montant)
    return {k: round(v, 2) for k, v in agg.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reporting.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/reporting.py tests/test_reporting.py
git commit -m "feat: monthly creancier report and spend-by-tag aggregation"
```

---

### Task 9: Backup service

**Files:**
- Create: `app/services/backup.py`
- Test: `tests/test_backup.py`

**Interfaces:**
- Produces: `backup_database(db_path: Path, backup_dir: Path, timestamp: str) -> Path` (returns the path of the created copy).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backup.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backup.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `app/services/backup.py`**

```python
import shutil
from pathlib import Path


def backup_database(db_path: Path, backup_dir: Path, timestamp: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"comptes_{timestamp}.db"
    shutil.copy2(db_path, destination)
    return destination
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_backup.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/backup.py tests/test_backup.py
git commit -m "feat: post-shutdown timestamped database backup copy"
```

---

### Task 10: Banques & comptes virtuels UI (CRUD + drill-down dashboard)

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/banques/list.html`
- Create: `app/templates/banques/detail.html`
- Create: `app/routers/__init__.py`
- Create: `app/routers/banques.py`
- Modify: `app/main.py` (mount router, wire templates dir already present)
- Test: `tests/test_routers_banques.py`

**Interfaces:**
- Consumes: `Banque`, `CompteVirtuel` (Task 2), `total_pointe`, `total_a_venir`, `total_pointe_banque` (Task 7), `get_db` (Task 1).
- Produces: routes `GET /banques`, `POST /banques`, `GET /banques/{id}`, `POST /banques/{id}/comptes`, `POST /comptes/{id}/archiver`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routers_banques.py
def test_create_and_list_banque(client):
    resp = client.post("/banques", data={"nom": "Bourso"})
    assert resp.status_code in (200, 303)

    resp = client.get("/banques")
    assert resp.status_code == 200
    assert "Bourso" in resp.text


def test_add_compte_virtuel_to_banque(client):
    client.post("/banques", data={"nom": "LaPoste"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="LaPoste").first()

    resp = client.post(f"/banques/{banque.id}/comptes", data={"nom": "Maison"})
    assert resp.status_code in (200, 303)

    resp = client.get(f"/banques/{banque.id}")
    assert resp.status_code == 200
    assert "Maison" in resp.text


def test_archiver_compte_virtuel(client):
    client.post("/banques", data={"nom": "LaPoste"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque, CompteVirtuel
    banque = db.query(Banque).filter_by(nom="LaPoste").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Vacances"})
    compte = db.query(CompteVirtuel).filter_by(nom="Vacances").first()

    resp = client.post(f"/comptes/{compte.id}/archiver")
    assert resp.status_code in (200, 303)

    db.refresh(compte)
    assert compte.actif is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routers_banques.py -v`
Expected: FAIL — 404 (no routes registered yet)

- [ ] **Step 3: Write `app/templates/base.html`**

```html
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Comptes</title>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
</head>
<body>
  <nav>
    <a href="/banques">Banques</a>
    <a href="/rapprochement">Rapprochement</a>
    <a href="/reporting/mensuel">Rapport mensuel</a>
    <a href="/reporting/tags">Dépenses par tag</a>
  </nav>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Write `app/templates/banques/list.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Banques</h1>
<form method="post" action="/banques">
  <input type="text" name="nom" placeholder="Nom de la banque" required>
  <button type="submit">Ajouter</button>
</form>
<ul>
  {% for banque in banques %}
    <li><a href="/banques/{{ banque.id }}">{{ banque.nom }}</a></li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 5: Write `app/templates/banques/detail.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ banque.nom }}</h1>
<p>Total pointé banque : {{ total_banque }}</p>
<form method="post" action="/banques/{{ banque.id }}/comptes">
  <input type="text" name="nom" placeholder="Nouveau compte virtuel" required>
  <button type="submit">Ajouter</button>
</form>
<table>
  <tr><th>Compte</th><th>Pointé</th><th>À venir</th><th></th></tr>
  {% for compte, pointe, a_venir in comptes %}
    <tr>
      <td>{{ compte.nom }}{% if not compte.actif %} (archivé){% endif %}</td>
      <td>{{ pointe }}</td>
      <td>{{ a_venir }}</td>
      <td>
        {% if compte.actif %}
        <form method="post" action="/comptes/{{ compte.id }}/archiver">
          <button type="submit">Archiver</button>
        </form>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 6: Write `app/routers/banques.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import Banque, CompteVirtuel
from app.services.totals import total_a_venir, total_pointe, total_pointe_banque

router = APIRouter()


@router.get("/banques")
def list_banques(request: Request, db: Session = Depends(get_db)):
    banques = db.query(Banque).all()
    return templates.TemplateResponse(
        "banques/list.html", {"request": request, "banques": banques}
    )


@router.post("/banques")
def create_banque(nom: str = Form(...), db: Session = Depends(get_db)):
    db.add(Banque(nom=nom))
    db.commit()
    return RedirectResponse("/banques", status_code=303)


@router.get("/banques/{banque_id}")
def banque_detail(banque_id: int, request: Request, db: Session = Depends(get_db)):
    banque = db.get(Banque, banque_id)
    comptes = db.query(CompteVirtuel).filter_by(banque_id=banque_id).all()
    rows = [(c, total_pointe(db, c.id), total_a_venir(db, c.id)) for c in comptes]
    return templates.TemplateResponse(
        "banques/detail.html",
        {
            "request": request,
            "banque": banque,
            "comptes": rows,
            "total_banque": total_pointe_banque(db, banque_id),
        },
    )


@router.post("/banques/{banque_id}/comptes")
def create_compte(banque_id: int, nom: str = Form(...), db: Session = Depends(get_db)):
    db.add(CompteVirtuel(nom=nom, banque_id=banque_id, actif=True))
    db.commit()
    return RedirectResponse(f"/banques/{banque_id}", status_code=303)


@router.post("/comptes/{compte_id}/archiver")
def archiver_compte(compte_id: int, db: Session = Depends(get_db)):
    compte = db.get(CompteVirtuel, compte_id)
    compte.actif = False
    db.commit()
    return RedirectResponse(f"/banques/{compte.banque_id}", status_code=303)
```

- [ ] **Step 7: Mount the router in `app/main.py`**

```python
from app.routers import banques

app.include_router(banques.router)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_routers_banques.py -v`
Expected: PASS (3 tests)

- [ ] **Step 9: Commit**

```bash
git add app/templates app/routers/__init__.py app/routers/banques.py app/main.py tests/test_routers_banques.py
git commit -m "feat: banques and comptes virtuels CRUD screens with drill-down totals"
```

---

### Task 11: Transactions UI (list, manual add, duplicate)

**Files:**
- Create: `app/templates/transactions/list.html`
- Create: `app/routers/transactions.py`
- Modify: `app/main.py` (mount router)
- Modify: `app/templates/banques/detail.html` (link each compte to its transaction list)
- Test: `tests/test_routers_transactions.py`

**Interfaces:**
- Consumes: `Transaction`, `Tag`, `CompteVirtuel` (Task 2), `get_db` (Task 1).
- Produces: routes `GET /comptes/{id}/transactions`, `POST /comptes/{id}/transactions`, `POST /transactions/{id}/pointer`, `GET /transactions/{id}/dupliquer`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routers_transactions.py
def _create_compte(client):
    client.post("/banques", data={"nom": "Bourso"})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom="Bourso").first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": "Bourso"})
    from app.models import CompteVirtuel
    return db.query(CompteVirtuel).filter_by(nom="Bourso").first()


def test_add_transaction_manually(client):
    compte = _create_compte(client)
    resp = client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-45.90", "libelle": "Restaurant", "tags": "resto"},
    )
    assert resp.status_code in (200, 303)

    resp = client.get(f"/comptes/{compte.id}/transactions")
    assert "Restaurant" in resp.text


def test_pointer_transaction(client):
    compte = _create_compte(client)
    client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-10.0", "libelle": "Test", "tags": ""},
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Test").first()
    assert tx.pointe is False

    resp = client.post(f"/transactions/{tx.id}/pointer")
    assert resp.status_code in (200, 303)
    db.refresh(tx)
    assert tx.pointe is True


def test_duplicate_transaction_prefills_form(client):
    compte = _create_compte(client)
    client.post(
        f"/comptes/{compte.id}/transactions",
        data={"date": "2026-08-30", "montant": "-10.0", "libelle": "Abonnement", "tags": ""},
    )
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Abonnement").first()

    resp = client.get(f"/transactions/{tx.id}/dupliquer")
    assert resp.status_code == 200
    assert "Abonnement" in resp.text
    assert "-10.0" in resp.text or "-10" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routers_transactions.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Write `app/templates/transactions/list.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ compte.nom }} — transactions</h1>
<form method="post" action="/comptes/{{ compte.id }}/transactions">
  <input type="date" name="date" value="{{ prefill.date if prefill else '' }}" required>
  <input type="text" name="libelle" placeholder="Libellé" value="{{ prefill.libelle if prefill else '' }}" required>
  <input type="number" step="0.01" name="montant" placeholder="Montant" value="{{ prefill.montant if prefill else '' }}" required>
  <input type="text" name="tags" placeholder="tags séparés par virgule" value="{{ prefill.tags if prefill else '' }}">
  <button type="submit">Ajouter</button>
</form>
<table>
  <tr><th>Date</th><th>Libellé</th><th>Montant</th><th>Tags</th><th>Pointé</th><th></th></tr>
  {% for tx in transactions %}
    <tr>
      <td>{{ tx.date }}</td>
      <td>{{ tx.libelle }}</td>
      <td>{{ tx.montant }}</td>
      <td>{{ tx.tags | map(attribute="nom") | join(", ") }}</td>
      <td>
        {% if not tx.pointe %}
        <form method="post" action="/transactions/{{ tx.id }}/pointer">
          <button type="submit">Pointer</button>
        </form>
        {% else %}Oui{% endif %}
      </td>
      <td><a href="/transactions/{{ tx.id }}/dupliquer">Dupliquer</a></td>
    </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 4: Write `app/routers/transactions.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Tag, Transaction

router = APIRouter()


def _get_or_create_tags(db: Session, tags_csv: str) -> list[Tag]:
    names = [t.strip() for t in tags_csv.split(",") if t.strip()]
    tags = []
    for name in names:
        tag = db.query(Tag).filter_by(nom=name).first()
        if not tag:
            tag = Tag(nom=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


@router.get("/comptes/{compte_id}/transactions")
def list_transactions(compte_id: int, request: Request, db: Session = Depends(get_db)):
    compte = db.get(CompteVirtuel, compte_id)
    transactions = (
        db.query(Transaction)
        .filter_by(compte_virtuel_id=compte_id)
        .order_by(Transaction.date.desc())
        .all()
    )
    return templates.TemplateResponse(
        "transactions/list.html",
        {"request": request, "compte": compte, "transactions": transactions, "prefill": None},
    )


@router.post("/comptes/{compte_id}/transactions")
def add_transaction(
    compte_id: int,
    date: datetime.date = Form(...),
    libelle: str = Form(...),
    montant: float = Form(...),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    tx = Transaction(
        date=date, compte_virtuel_id=compte_id, montant=montant, libelle=libelle, pointe=False
    )
    tx.tags = _get_or_create_tags(db, tags)
    db.add(tx)
    db.commit()
    return RedirectResponse(f"/comptes/{compte_id}/transactions", status_code=303)


@router.post("/transactions/{transaction_id}/pointer")
def pointer_transaction(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    tx.pointe = True
    db.commit()
    return RedirectResponse(f"/comptes/{tx.compte_virtuel_id}/transactions", status_code=303)


@router.get("/transactions/{transaction_id}/dupliquer")
def duplicate_transaction_form(transaction_id: int, request: Request, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    compte = db.get(CompteVirtuel, tx.compte_virtuel_id)
    transactions = (
        db.query(Transaction)
        .filter_by(compte_virtuel_id=compte.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    prefill = {
        "date": datetime.date.today().isoformat(),
        "libelle": tx.libelle,
        "montant": tx.montant,
        "tags": ", ".join(t.nom for t in tx.tags),
    }
    return templates.TemplateResponse(
        "transactions/list.html",
        {"request": request, "compte": compte, "transactions": transactions, "prefill": prefill},
    )
```

- [ ] **Step 5: Mount router in `app/main.py`**

```python
from app.routers import banques, transactions

app.include_router(banques.router)
app.include_router(transactions.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_routers_transactions.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add app/templates/transactions app/routers/transactions.py app/main.py tests/test_routers_transactions.py
git commit -m "feat: transaction list, manual add, pointing, and duplication screens"
```

---

### Task 12: Créanciers UI (CRUD, duplicate, échéance generation trigger)

**Files:**
- Create: `app/templates/creanciers/list.html`
- Create: `app/routers/creanciers.py`
- Modify: `app/main.py` (mount router; call `generate_due_echeances` on startup)
- Test: `tests/test_routers_creanciers.py`

**Interfaces:**
- Consumes: `Creancier`, `CompteVirtuel` (Tasks 2-3), `generate_due_echeances` (Task 4), `get_db` (Task 1).
- Produces: routes `GET /creanciers`, `POST /creanciers`, `GET /creanciers/{id}/dupliquer`, `POST /creanciers/{id}/desactiver`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routers_creanciers.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routers_creanciers.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Write `app/templates/creanciers/list.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Créanciers</h1>
<form method="post" action="/creanciers">
  <input type="text" name="nom" placeholder="Nom" value="{{ prefill.nom if prefill else '' }}" required>
  <input type="number" step="0.01" name="montant_defaut" placeholder="Montant" value="{{ prefill.montant_defaut if prefill else '' }}" required>
  <select name="compte_source_id" required>
    {% for compte in comptes %}
      <option value="{{ compte.id }}">{{ compte.banque.nom }} / {{ compte.nom }}</option>
    {% endfor %}
  </select>
  <select name="compte_destination_id">
    <option value="">— externe —</option>
    {% for compte in comptes %}
      <option value="{{ compte.id }}">{{ compte.banque.nom }} / {{ compte.nom }}</option>
    {% endfor %}
  </select>
  <input type="date" name="date_prochaine_echeance" required>
  <select name="recurrence">
    <option value="mensuelle">Mensuelle</option>
    <option value="hebdomadaire">Hebdomadaire</option>
    <option value="custom">Custom</option>
    <option value="aucune">Aucune (ponctuelle)</option>
  </select>
  <input type="number" name="intervalle_jours" placeholder="jours (si custom)">
  <select name="fin_type">
    <option value="jamais">Jamais</option>
    <option value="date">Date de fin</option>
    <option value="occurrences">Nombre d'occurrences</option>
  </select>
  <input type="date" name="fin_date">
  <input type="number" name="fin_occurrences">
  <button type="submit">Enregistrer</button>
</form>
<table>
  <tr><th>Nom</th><th>Montant</th><th>Source</th><th>Destination</th><th>Prochaine échéance</th><th></th></tr>
  {% for c in creanciers %}
    <tr>
      <td>{{ c.nom }}{% if not c.actif %} (inactif){% endif %}</td>
      <td>{{ c.montant_defaut }}</td>
      <td>{{ c.compte_source.nom }}</td>
      <td>{{ c.compte_destination.nom if c.compte_destination else "externe" }}</td>
      <td>{{ c.date_prochaine_echeance }}</td>
      <td>
        <a href="/creanciers/{{ c.id }}/dupliquer">Dupliquer</a>
        {% if c.actif %}
        <form method="post" action="/creanciers/{{ c.id }}/desactiver" style="display:inline">
          <button type="submit">Désactiver</button>
        </form>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
</table>
{% endblock %}
```

- [ ] **Step 4: Write `app/routers/creanciers.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel, Creancier

router = APIRouter()


@router.get("/creanciers")
def list_creanciers(request: Request, db: Session = Depends(get_db)):
    creanciers = db.query(Creancier).all()
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    return templates.TemplateResponse(
        "creanciers/list.html",
        {"request": request, "creanciers": creanciers, "comptes": comptes, "prefill": None},
    )


@router.post("/creanciers")
def create_creancier(
    nom: str = Form(...),
    montant_defaut: float = Form(...),
    compte_source_id: int = Form(...),
    compte_destination_id: str = Form(""),
    date_prochaine_echeance: datetime.date = Form(...),
    recurrence: str = Form(...),
    intervalle_jours: str = Form(""),
    fin_type: str = Form("jamais"),
    fin_date: str = Form(""),
    fin_occurrences: str = Form(""),
    db: Session = Depends(get_db),
):
    creancier = Creancier(
        nom=nom,
        montant_defaut=montant_defaut,
        compte_source_id=compte_source_id,
        compte_destination_id=int(compte_destination_id) if compte_destination_id else None,
        date_prochaine_echeance=date_prochaine_echeance,
        recurrence=recurrence,
        intervalle_jours=int(intervalle_jours) if intervalle_jours else None,
        fin_type=fin_type,
        fin_date=datetime.date.fromisoformat(fin_date) if fin_date else None,
        fin_occurrences=int(fin_occurrences) if fin_occurrences else None,
        actif=True,
    )
    db.add(creancier)
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)


@router.get("/creanciers/{creancier_id}/dupliquer")
def duplicate_creancier_form(creancier_id: int, request: Request, db: Session = Depends(get_db)):
    source = db.get(Creancier, creancier_id)
    creanciers = db.query(Creancier).all()
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    prefill = {"nom": source.nom, "montant_defaut": source.montant_defaut}
    return templates.TemplateResponse(
        "creanciers/list.html",
        {"request": request, "creanciers": creanciers, "comptes": comptes, "prefill": prefill},
    )


@router.post("/creanciers/{creancier_id}/desactiver")
def deactivate_creancier(creancier_id: int, db: Session = Depends(get_db)):
    creancier = db.get(Creancier, creancier_id)
    creancier.actif = False
    db.commit()
    return RedirectResponse("/creanciers", status_code=303)
```

- [ ] **Step 5: Mount router and wire startup generation in `app/main.py`**

```python
from app.routers import banques, creanciers, transactions
from app.db import SessionLocal
from app.services.creancier_engine import generate_due_echeances
import datetime

app.include_router(banques.router)
app.include_router(transactions.router)
app.include_router(creanciers.router)


@app.on_event("startup")
def generate_echeances_on_startup():
    db = SessionLocal()
    try:
        generate_due_echeances(db, datetime.date.today())
    finally:
        db.close()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_routers_creanciers.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add app/templates/creanciers app/routers/creanciers.py app/main.py tests/test_routers_creanciers.py
git commit -m "feat: creanciers CRUD screen, duplication, startup echeance generation"
```

---

### Task 13: Rapprochement UI (paste, staging, dedup lock, validate, écart)

**Files:**
- Create: `app/templates/rapprochement/paste.html`
- Create: `app/templates/rapprochement/staging.html`
- Create: `app/routers/rapprochement.py`
- Modify: `app/main.py` (mount router)
- Test: `tests/test_routers_rapprochement.py`

**Interfaces:**
- Consumes: `parse_pasted_text`, `MappingParsing` (Task 5), `is_duplicate`, `suggest_tags`, `record_learning` (Task 6), `total_pointe_banque`, `calcule_ecart`, `RapprochementSession` (Task 7), `get_db` (Task 1).
- Produces: routes `GET /rapprochement`, `POST /rapprochement/{banque_id}/coller` (returns staging screen), `POST /rapprochement/{banque_id}/valider`, `POST /rapprochement/{banque_id}/mapping` (calibration, only if no `MappingParsing` exists yet for that banque).

Design note for the staging step: since HTML forms are stateless, parsed rows are round-tripped through hidden form fields (one row = one set of hidden inputs) rather than kept server-side between the paste and validate requests — this avoids adding a session/cache layer for a short-lived screen.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routers_rapprochement.py
def _banque_et_compte(client, nom="Bourso"):
    client.post("/banques", data={"nom": nom})
    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Banque
    banque = db.query(Banque).filter_by(nom=nom).first()
    client.post(f"/banques/{banque.id}/comptes", data={"nom": nom})
    from app.models import CompteVirtuel
    compte = db.query(CompteVirtuel).filter_by(nom=nom).first()
    return banque, compte


def test_coller_sans_mapping_demande_calibrage(client):
    banque, _ = _banque_et_compte(client)
    resp = client.post(f"/rapprochement/{banque.id}/coller", data={"texte": "05/08/2026\tTest\t-10,00"})
    assert resp.status_code == 200
    assert "calibrage" in resp.text.lower() or "mapping" in resp.text.lower()


def test_mapping_puis_coller_affiche_staging(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/coller",
        data={"texte": "05/08/2026\tRestaurant\t-45,90"},
    )
    assert resp.status_code == 200
    assert "Restaurant" in resp.text
    assert "-45.9" in resp.text or "-45,9" in resp.text


def test_valider_ecrit_transactions_non_verrouillees(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/valider",
        data={
            "compte_virtuel_id__0": str(compte.id),
            "date__0": "2026-08-05",
            "libelle__0": "Restaurant",
            "montant__0": "-45.90",
            "tags__0": "resto",
            "verrouille__0": "",
            "row_count": "1",
            "total_banque_pointe": "-45.90",
            "total_banque_a_venir": "0",
        },
    )
    assert resp.status_code in (200, 303)

    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    tx = db.query(Transaction).filter_by(libelle="Restaurant").first()
    assert tx is not None
    assert tx.pointe is True


def test_valider_ignore_lignes_verrouillees(client):
    banque, compte = _banque_et_compte(client)
    client.post(
        f"/rapprochement/{banque.id}/mapping",
        data={"colonne_date": "0", "colonne_libelle": "1", "colonne_montant": "2", "separateur": "tab"},
    )
    resp = client.post(
        f"/rapprochement/{banque.id}/valider",
        data={
            "compte_virtuel_id__0": str(compte.id),
            "date__0": "2026-08-05",
            "libelle__0": "Doublon",
            "montant__0": "-10.0",
            "tags__0": "",
            "verrouille__0": "on",
            "row_count": "1",
            "total_banque_pointe": "0",
            "total_banque_a_venir": "0",
        },
    )
    assert resp.status_code in (200, 303)

    from app.db import get_db
    from app.main import app
    db = next(app.dependency_overrides[get_db]())
    from app.models import Transaction
    assert db.query(Transaction).filter_by(libelle="Doublon").first() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routers_rapprochement.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Write `app/templates/rapprochement/paste.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Rapprochement</h1>
<ul>
  {% for banque in banques %}<li><a href="/rapprochement?banque_id={{ banque.id }}">{{ banque.nom }}</a></li>{% endfor %}
</ul>

{% if banque %}
<h2>{{ banque.nom }}</h2>

{% if not mapping %}
<h3>Calibrage (1re utilisation pour cette banque)</h3>
<form method="post" action="/rapprochement/{{ banque.id }}/mapping">
  <label>Colonne date (index depuis 0) <input type="number" name="colonne_date" required></label>
  <label>Colonne libellé <input type="number" name="colonne_libelle" required></label>
  <label>Colonne montant <input type="number" name="colonne_montant" required></label>
  <label>Séparateur
    <select name="separateur">
      <option value="tab">Tabulation</option>
      <option value=";">Point-virgule</option>
      <option value=",">Virgule</option>
    </select>
  </label>
  <button type="submit">Enregistrer le calibrage</button>
</form>
{% else %}
<form method="post" action="/rapprochement/{{ banque.id }}/coller">
  <textarea name="texte" rows="10" cols="80" placeholder="Colle ici le texte copié depuis le site de la banque"></textarea>
  <button type="submit">Analyser</button>
</form>
{% endif %}
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Write `app/templates/rapprochement/staging.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ banque.nom }} — contrôle avant écriture</h1>
<form method="post" action="/rapprochement/{{ banque.id }}/valider">
  <input type="hidden" name="row_count" value="{{ rows|length }}">
  <table>
    <tr><th>Verrouillé (doublon)</th><th>Date</th><th>Libellé</th><th>Montant</th><th>Compte</th><th>Tags</th></tr>
    {% for row in rows %}
    <tr>
      <td><input type="checkbox" name="verrouille__{{ loop.index0 }}" {% if row.doublon %}checked{% endif %}></td>
      <td><input type="date" name="date__{{ loop.index0 }}" value="{{ row.date }}"></td>
      <td><input type="text" name="libelle__{{ loop.index0 }}" value="{{ row.libelle }}"></td>
      <td><input type="number" step="0.01" name="montant__{{ loop.index0 }}" value="{{ row.montant }}"></td>
      <td>
        <select name="compte_virtuel_id__{{ loop.index0 }}">
          {% for compte in comptes %}
            <option value="{{ compte.id }}">{{ compte.nom }}</option>
          {% endfor %}
        </select>
      </td>
      <td><input type="text" name="tags__{{ loop.index0 }}" value="{{ row.tags_suggeres }}"></td>
    </tr>
    {% endfor %}
  </table>
  <label>Total pointé affiché par la banque <input type="number" step="0.01" name="total_banque_pointe" required></label>
  <label>Total à venir affiché par la banque <input type="number" step="0.01" name="total_banque_a_venir" required></label>
  <button type="submit">Valider</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Write `app/routers/rapprochement.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import Banque, CompteVirtuel, MappingParsing, RapprochementSession, Transaction
from app.services.dedup import is_duplicate
from app.services.parsing import parse_pasted_text
from app.services.tag_learning import record_learning, suggest_tags
from app.services.totals import calcule_ecart, total_pointe_banque

router = APIRouter()

_SEPARATEURS = {"tab": "\t", ";": ";", ",": ","}


@router.get("/rapprochement")
def rapprochement_home(request: Request, banque_id: int | None = None, db: Session = Depends(get_db)):
    banques = db.query(Banque).all()
    banque = db.get(Banque, banque_id) if banque_id else None
    mapping = (
        db.query(MappingParsing).filter_by(banque_id=banque_id).first() if banque_id else None
    )
    return templates.TemplateResponse(
        "rapprochement/paste.html",
        {"request": request, "banques": banques, "banque": banque, "mapping": mapping},
    )


@router.post("/rapprochement/{banque_id}/mapping")
def save_mapping(
    banque_id: int,
    colonne_date: int = Form(...),
    colonne_libelle: int = Form(...),
    colonne_montant: int = Form(...),
    separateur: str = Form(...),
    db: Session = Depends(get_db),
):
    mapping = MappingParsing(
        banque_id=banque_id,
        colonne_date=colonne_date,
        colonne_libelle=colonne_libelle,
        colonne_montant=colonne_montant,
        separateur=_SEPARATEURS[separateur],
    )
    db.add(mapping)
    db.commit()
    return RedirectResponse(f"/rapprochement?banque_id={banque_id}", status_code=303)


@router.post("/rapprochement/{banque_id}/coller")
def parse_and_stage(
    banque_id: int, request: Request, texte: str = Form(...), db: Session = Depends(get_db)
):
    banque = db.get(Banque, banque_id)
    mapping = db.query(MappingParsing).filter_by(banque_id=banque_id).first()
    if not mapping:
        return templates.TemplateResponse(
            "rapprochement/paste.html",
            {
                "request": request,
                "banques": db.query(Banque).all(),
                "banque": banque,
                "mapping": None,
            },
        )

    comptes = db.query(CompteVirtuel).filter_by(banque_id=banque_id, actif=True).all()
    parsed = parse_pasted_text(texte, mapping)
    rows = []
    for entry in parsed:
        doublon = any(
            is_duplicate(db, compte.id, entry["date"], entry["montant"], entry["libelle"])
            for compte in comptes
        )
        tags = suggest_tags(db, entry["libelle"])
        rows.append(
            {
                "date": entry["date"].isoformat(),
                "libelle": entry["libelle"],
                "montant": entry["montant"],
                "doublon": doublon,
                "tags_suggeres": ", ".join(t.nom for t in tags),
            }
        )
    return templates.TemplateResponse(
        "rapprochement/staging.html",
        {"request": request, "banque": banque, "comptes": comptes, "rows": rows},
    )


@router.post("/rapprochement/{banque_id}/valider")
async def validate_staging(banque_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    row_count = int(form["row_count"])
    banque = db.get(Banque, banque_id)

    for i in range(row_count):
        if form.get(f"verrouille__{i}"):
            continue
        libelle = form[f"libelle__{i}"]
        tags_csv = form.get(f"tags__{i}", "")
        tag_names = [t.strip() for t in tags_csv.split(",") if t.strip()]
        from app.models import Tag

        tags = []
        for name in tag_names:
            tag = db.query(Tag).filter_by(nom=name).first()
            if not tag:
                tag = Tag(nom=name)
                db.add(tag)
                db.flush()
            tags.append(tag)

        tx = Transaction(
            date=datetime.date.fromisoformat(form[f"date__{i}"]),
            compte_virtuel_id=int(form[f"compte_virtuel_id__{i}"]),
            montant=float(form[f"montant__{i}"]),
            libelle=libelle,
            pointe=True,
        )
        tx.tags = tags
        db.add(tx)
        if tags:
            record_learning(db, libelle, tags)
    db.commit()

    total_banque_pointe = float(form["total_banque_pointe"])
    total_banque_a_venir = float(form["total_banque_a_venir"])
    total_calcule = total_pointe_banque(db, banque_id)
    ecart = calcule_ecart(total_banque_pointe, total_calcule)

    db.add(
        RapprochementSession(
            banque_id=banque_id,
            date=datetime.date.today(),
            total_banque_pointe=total_banque_pointe,
            total_banque_a_venir=total_banque_a_venir,
            total_pointe_calcule=total_calcule,
            ecart=ecart,
        )
    )
    db.commit()

    return RedirectResponse(f"/banques/{banque_id}", status_code=303)
```

- [ ] **Step 6: Mount router in `app/main.py`**

```python
from app.routers import banques, creanciers, rapprochement, transactions

app.include_router(banques.router)
app.include_router(transactions.router)
app.include_router(creanciers.router)
app.include_router(rapprochement.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_routers_rapprochement.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add app/templates/rapprochement app/routers/rapprochement.py app/main.py tests/test_routers_rapprochement.py
git commit -m "feat: rapprochement paste-parse-stage-validate flow with dedup lock and ecart"
```

---

### Task 14: Reporting UI (monthly créanciers view + tag chart)

**Files:**
- Create: `app/templates/reporting/mensuel.html`
- Create: `app/templates/reporting/tags.html`
- Create: `app/routers/reporting.py`
- Modify: `app/main.py` (mount router)
- Test: `tests/test_routers_reporting.py`

**Interfaces:**
- Consumes: `rapport_mensuel`, `depenses_par_tag` (Task 8), `CompteVirtuel` (Task 2), `get_db` (Task 1).
- Produces: routes `GET /reporting/mensuel`, `GET /reporting/tags`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routers_reporting.py
import datetime as dt


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_routers_reporting.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Write `app/templates/reporting/mensuel.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Rapport mensuel</h1>
<form method="get" action="/reporting/mensuel">
  <select name="compte_virtuel_id">
    {% for compte in comptes %}
      <option value="{{ compte.id }}" {% if compte.id == compte_virtuel_id %}selected{% endif %}>{{ compte.nom }}</option>
    {% endfor %}
  </select>
  <input type="number" name="annee" value="{{ annee }}">
  <input type="number" name="mois" value="{{ mois }}">
  <button type="submit">Afficher</button>
</form>
{% if rapport %}
<ul>
  <li>Récurrent prévu : {{ rapport.recurrent_prevu }}</li>
  <li>Récurrent pointé : {{ rapport.recurrent_pointe }}</li>
  <li>Récurrent reste à passer : {{ (rapport.recurrent_prevu - rapport.recurrent_pointe) | round(2) }}</li>
  <li>Non récurrent pointé : {{ rapport.non_recurrent_pointe }}</li>
</ul>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Write `app/templates/reporting/tags.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Dépenses par tag</h1>
<form method="get" action="/reporting/tags">
  <input type="date" name="date_debut" value="{{ date_debut }}">
  <input type="date" name="date_fin" value="{{ date_fin }}">
  <button type="submit">Afficher</button>
</form>
<ul>
  {% for tag, montant in depenses.items() %}<li>{{ tag }} : {{ montant }}</li>{% endfor %}
</ul>
<canvas id="chart-tags" width="400" height="200"></canvas>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<script>
new Chart(document.getElementById('chart-tags'), {
  type: 'bar',
  data: {
    labels: {{ depenses.keys() | list | tojson }},
    datasets: [{ label: 'Dépenses par tag', data: {{ depenses.values() | list | tojson }} }]
  }
});
</script>
{% endblock %}
```

- [ ] **Step 5: Write `app/routers/reporting.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import templates
from app.models import CompteVirtuel
from app.services.reporting import depenses_par_tag, rapport_mensuel

router = APIRouter()


@router.get("/reporting/mensuel")
def reporting_mensuel(
    request: Request,
    compte_virtuel_id: int | None = None,
    annee: int = datetime.date.today().year,
    mois: int = datetime.date.today().month,
    db: Session = Depends(get_db),
):
    comptes = db.query(CompteVirtuel).filter_by(actif=True).all()
    rapport = None
    if compte_virtuel_id:
        rapport = rapport_mensuel(db, compte_virtuel_id, annee, mois)
    return templates.TemplateResponse(
        "reporting/mensuel.html",
        {
            "request": request,
            "comptes": comptes,
            "compte_virtuel_id": compte_virtuel_id,
            "annee": annee,
            "mois": mois,
            "rapport": rapport,
        },
    )


@router.get("/reporting/tags")
def reporting_tags(
    request: Request,
    date_debut: datetime.date = datetime.date.today().replace(day=1),
    date_fin: datetime.date = datetime.date.today(),
    db: Session = Depends(get_db),
):
    depenses = depenses_par_tag(db, date_debut, date_fin)
    return templates.TemplateResponse(
        "reporting/tags.html",
        {"request": request, "depenses": depenses, "date_debut": date_debut, "date_fin": date_fin},
    )
```

- [ ] **Step 6: Mount router in `app/main.py`**

```python
from app.routers import banques, creanciers, rapprochement, reporting, transactions

app.include_router(banques.router)
app.include_router(transactions.router)
app.include_router(creanciers.router)
app.include_router(rapprochement.router)
app.include_router(reporting.router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_routers_reporting.py -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add app/templates/reporting app/routers/reporting.py app/main.py tests/test_routers_reporting.py
git commit -m "feat: monthly creancier report and tag spend chart screens"
```

---

### Task 15: Launcher (pywebview + uvicorn) and packaging script

**Files:**
- Create: `launcher.py`
- Create: `scripts/ComptesApp.command`

**Interfaces:**
- Consumes: `app.main.app` (Task 1), `app.db.get_db_path` (Task 1), `app.services.backup.backup_database` (Task 9).
- Produces: `launcher.main()` — no automated test (pywebview requires a real display; per spec, no e2e suite for V1). Verified manually per Step 4 below.

- [ ] **Step 1: Write `launcher.py`**

```python
import datetime
import threading
import time
from pathlib import Path

import uvicorn
import webview

from app.db import get_db_path
from app.main import app
from app.services.backup import backup_database

PORT = 8731
BACKUP_DIR_ENV_DEFAULT = Path.home() / "Google Drive" / "ComptesAppBackups"


def _run_server(server: uvicorn.Server) -> None:
    server.run()


def main() -> None:
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    thread.start()

    while not server.started:
        time.sleep(0.05)

    webview.create_window("Comptes", f"http://127.0.0.1:{PORT}", width=1280, height=850)
    webview.start()

    server.should_exit = True
    thread.join(timeout=5)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_database(get_db_path(), BACKUP_DIR_ENV_DEFAULT, timestamp)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `scripts/ComptesApp.command`**

```bash
#!/bin/bash
cd "$(dirname "$0")/.."
python3 launcher.py
```

- [ ] **Step 3: Make the launcher script executable**

Run: `chmod +x scripts/ComptesApp.command`

- [ ] **Step 4: Manual verification**

Run: `python3 launcher.py`
Expected: a chrome-less window opens showing the "Banques" nav (no address bar); closing the window returns control to the terminal within a few seconds, and a file named `comptes_<timestamp>.db` appears under `~/Google Drive/ComptesAppBackups/`.

- [ ] **Step 5: Commit**

```bash
git add launcher.py scripts/ComptesApp.command
git commit -m "feat: pywebview launcher with clean shutdown and DB backup"
```

- [ ] **Step 6: (User action, not scripted) Place a shortcut in /Applications**

Create an alias/symlink to `scripts/ComptesApp.command` inside `/Applications`, or wrap it into a minimal `.app` bundle with Platypus if a Dock icon is wanted — this step is manual, outside the scope of this repo's automation.

---

## Self-Review Notes

- **Spec coverage:** stack/packaging → Tasks 1, 15. Data model → Tasks 2-3, 5, 7. Rapprochement workflow (paste/calibrage/staging/dedup/tags appris/manuel/validation/écart/historique) → Tasks 5, 6, 7, 13. Créancier engine (catch-up loop, interne/externe, montant ajustable, désactivation) → Tasks 3, 4, 12. Duplication (transaction + créancier) → Tasks 11, 12. Reporting (drill-down banque→compte, vue mensuelle, vue par tag + graphique) → Tasks 10, 14. Backup à la fermeture → Tasks 9, 15. Tests ciblés sur la logique sensible → Tasks 3, 4, 5, 6, 7, 8, 9 (services), Tasks 10-14 (routers via TestClient).
- **Placeholder scan:** no TBD/TODO; every step carries runnable code.
- **Type consistency checked:** `Transaction.montant`/`Creancier.montant_defaut` are `float` throughout; `is_duplicate`, `suggest_tags`, `record_learning`, `total_pointe`/`total_a_venir`/`total_pointe_banque`, `calcule_ecart`, `rapport_mensuel`, `depenses_par_tag`, `parse_pasted_text`, `next_date`, `generate_due_echeances`, `backup_database` are called with the same names/signatures in every task that consumes them.
- **Scope check:** one cohesive pipeline (accounts → transactions → créanciers → rapprochement → reporting) sharing a single data model — not independent subsystems, so a single plan is appropriate rather than a decomposition into separate specs.
