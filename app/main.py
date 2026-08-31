import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import Base, SessionLocal, engine
from app.services.creancier_engine import generate_due_echeances


@asynccontextmanager
async def lifespan(app: FastAPI):
    import app.models  # noqa: F401  ensure all tables are registered on Base.metadata

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        generate_due_echeances(db, datetime.date.today())
    finally:
        db.close()
    yield


app = FastAPI(title="Comptes", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
