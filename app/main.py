import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import Base, SessionLocal, ensure_columns, engine, get_db
from app.models import Banque, CompteVirtuel
from app.services.backup import bump_derniere_ouverture
from app.services.creancier_engine import generate_due_echeances

derniere_ouverture_precedente: datetime.datetime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global derniere_ouverture_precedente
    Base.metadata.create_all(engine)
    ensure_columns(engine, Base.metadata)
    db = SessionLocal()
    try:
        generate_due_echeances(db, datetime.date.today())
        derniere_ouverture_precedente = bump_derniere_ouverture(db, datetime.datetime.now())
    finally:
        db.close()
    yield


def sidebar_context(request):
    # Reuse whatever get_db override is active (e.g. the test client's in-memory
    # session) instead of always hitting the real engine, mirroring FastAPI's
    # own Depends(get_db) resolution.
    override = app.dependency_overrides.get(get_db, get_db)
    gen = override()
    db = next(gen)
    try:
        banques = db.query(Banque).order_by(Banque.nom).all()
        sidebar_banques = [
            {
                "banque": banque,
                "comptes": db.query(CompteVirtuel)
                .filter_by(banque_id=banque.id, actif=True)
                .order_by(CompteVirtuel.ordre)
                .all(),
            }
            for banque in banques
        ]
    finally:
        gen.close()
    return {
        "sidebar_banques": sidebar_banques,
        "derniere_ouverture_precedente": derniere_ouverture_precedente,
    }


app = FastAPI(title="Comptes", lifespan=lifespan)
templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates"), context_processors=[sidebar_context]
)
templates.env.filters["money"] = lambda v: f"{v:.2f}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse("/banques")


from app.routers import banques, creanciers, rapprochement, reporting, settings, transactions  # noqa: E402

app.include_router(banques.router)
app.include_router(transactions.router)
app.include_router(creanciers.router)
app.include_router(rapprochement.router)
app.include_router(reporting.router)
app.include_router(settings.router)
