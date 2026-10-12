"""API FastAPI : notes de visite -> devis chiffré (JSON ou CSV) + interface web.

Lancer en local :  uvicorn app.api:app --reload
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .devis import chiffrer, load_catalogue, to_csv

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = load_catalogue()
app = FastAPI(title="Devis Travaux Assistant", version="0.1.0")

RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "30"))
TRUST_FORWARDED_FOR = os.getenv("TRUST_FORWARDED_FOR", "0") == "1"
_hits: dict[str, deque] = defaultdict(deque)


def _check_rate(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if TRUST_FORWARDED_FOR and request.headers.get("x-forwarded-for"):
        ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    now, win = time.time(), _hits[ip]
    while win and now - win[0] > 3600:
        win.popleft()
    if len(win) >= RATE_LIMIT:
        raise HTTPException(429, "Limite horaire atteinte, réessayez plus tard.")
    win.append(now)


class Notes(BaseModel):
    notes: str = Field(..., min_length=10, max_length=4000)


class Lignes(BaseModel):
    lignes: list[dict]
    a_chiffrer: list[dict] = []
    questions: list[str] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "articles": len(CATALOGUE)}


@app.get("/catalogue")
def catalogue() -> list[dict]:
    return [{"code": a.code, "lot": a.lot, "libelle": a.libelle, "unite": a.unite,
             "prix_unitaire_ht": float(a.prix_unitaire_ht), "tva": float(a.tva)}
            for a in CATALOGUE.values()]


@app.post("/chiffrer")
def chiffrer_lignes(body: Lignes) -> dict:
    """Chiffrage seul, sans LLM (lignes déjà structurées, ex. depuis n8n ou un formulaire)."""
    return chiffrer(body.lignes, CATALOGUE, body.a_chiffrer, body.questions)


@app.post("/devis")
def devis(body: Notes, request: Request) -> dict:
    """Notes de visite -> extraction LLM -> chiffrage déterministe."""
    from .extract import extraire

    _check_rate(request)
    try:
        proposition = extraire(body.notes, CATALOGUE)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Le modèle n'a pas pu être joint ({type(exc).__name__}).") from exc
    return {"proposition": proposition,
            "devis": chiffrer(proposition["lignes"], CATALOGUE, proposition["a_chiffrer"],
                              proposition["questions"])}


@app.post("/devis.csv", response_class=PlainTextResponse)
def devis_csv(body: Lignes) -> str:
    return to_csv(chiffrer(body.lignes, CATALOGUE, body.a_chiffrer, body.questions))


app.mount("/static", StaticFiles(directory=ROOT / "examples"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")
