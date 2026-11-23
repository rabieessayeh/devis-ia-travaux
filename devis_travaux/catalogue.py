"""Bibliothèque de prix : chargement et version compacte pour le LLM (sans les prix)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import DATA_DIR

CATALOGUE_PATH = DATA_DIR / "bibliotheque_prix.csv"


@dataclass(frozen=True)
class Article:
    code: str
    lot: str
    libelle: str
    unite: str
    prix_unitaire_ht: Decimal
    tva: Decimal  # en %


def load_catalogue(path: Path = CATALOGUE_PATH) -> dict[str, Article]:
    with open(path, encoding="utf-8") as f:
        return {
            row["code"]: Article(
                code=row["code"], lot=row["lot"], libelle=row["libelle"], unite=row["unite"],
                prix_unitaire_ht=Decimal(row["prix_unitaire_ht"]), tva=Decimal(row["tva"]),
            )
            for row in csv.DictReader(f)
        }


def catalogue_for_prompt(cat: dict[str, Article]) -> str:
    """Liste compacte envoyée au LLM : codes, libellés et unités (pas les prix)."""
    return "\n".join(f"{a.code} | {a.lot} | {a.libelle} | {a.unite}" for a in cat.values())
