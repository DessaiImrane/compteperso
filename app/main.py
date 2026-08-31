import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.services.creancier_engine import generate_due_echeances


@asynccontextmanager
async def lifespan(app: FastAPI):
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


from app.routers import banques, creanciers, rapprochement, transactions  # noqa: E402

app.include_router(banques.router)
app.include_router(transactions.router)
app.include_router(creanciers.router)
app.include_router(rapprochement.router)
