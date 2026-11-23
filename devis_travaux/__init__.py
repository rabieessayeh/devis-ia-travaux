"""Devis Travaux Assistant : notes de visite -> devis chiffré.

Modules :
    catalogue   bibliothèque de prix (data/bibliotheque_prix.csv)
    chiffrage   chiffrage déterministe, TVA, totaux et contrôles
    export      export CSV du devis
    llm         configuration et client LLM (API compatible OpenAI)
    extraction  notes de visite -> lignes proposées par le LLM
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EXAMPLES_DIR = ROOT / "examples"
