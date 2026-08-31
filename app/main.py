from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Comptes")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/health")
def health():
    return {"status": "ok"}


from app.routers import banques  # noqa: E402

app.include_router(banques.router)
