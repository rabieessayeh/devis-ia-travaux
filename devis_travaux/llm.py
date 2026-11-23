"""Configuration et client LLM (API compatible OpenAI : Groq, OpenAI, Mistral, Ollama...).

Variables : LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, RATE_LIMIT_PER_HOUR.
Lues dans l'environnement, le fichier .env (local) puis les secrets Streamlit (Cloud).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from . import ROOT

CONFIG_VARS = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "RATE_LIMIT_PER_HOUR")
DEFAULTS = {"LLM_BASE_URL": "https://api.groq.com/openai/v1", "LLM_MODEL": "openai/gpt-oss-120b",
            "RATE_LIMIT_PER_HOUR": "30"}


def load_config(secrets: dict | None = None) -> None:
    """Complète os.environ depuis .env puis `secrets` (st.secrets), sans écraser l'existant."""
    load_dotenv(ROOT / ".env")
    for key in CONFIG_VARS:
        if not os.getenv(key) and secrets and secrets.get(key):
            os.environ[key] = str(secrets[key])


def get(key: str) -> str:
    return os.getenv(key) or DEFAULTS.get(key, "")


def is_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY"))


def client() -> OpenAI:
    return OpenAI(base_url=get("LLM_BASE_URL"), api_key=get("LLM_API_KEY"))
