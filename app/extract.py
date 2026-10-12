"""Extraction par LLM : notes de visite (texte libre) -> lignes structurées.

Le LLM est forcé à répondre via un seul outil `proposer_lignes`, dont le schéma
impose des codes de la bibliothèque, des quantités et des hypothèses explicites.
Fonctionne avec toute API compatible OpenAI (Groq, OpenAI, Mistral, Ollama...).
"""

from __future__ import annotations

import json
import os
import time

from openai import OpenAI, RateLimitError

from .devis import Article, catalogue_for_prompt

SYSTEM = """Tu es l'assistant du pôle travaux d'une société d'investissement locatif.
À partir des notes de visite d'un conducteur de travaux, tu proposes les lignes d'un devis.
Règles :
- Utilise UNIQUEMENT les codes de la bibliothèque ci-dessous. Ne donne jamais de prix.
- Quantités : reprends celles des notes. Si une surface doit être déduite (ex. murs d'une pièce),
  calcule-la simplement et écris le calcul dans "hypothese". Si une quantité est impossible à
  déduire, ne l'invente pas : ajoute une question dans "questions".
- Un travail sans code correspondant va dans "a_chiffrer" avec une courte description.
- Une ligne par code et par pièce.
Bibliothèque (code | lot | libellé | unité) :
{catalogue}"""

TOOL = {
    "type": "function",
    "function": {
        "name": "proposer_lignes",
        "description": "Propose les lignes du devis à partir des notes de visite.",
        "parameters": {
            "type": "object",
            "properties": {
                "lignes": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "piece": {"type": "string"},
                        "quantite": {"type": "number"},
                        "hypothese": {"type": "string"},
                    },
                    "required": ["code", "quantite"],
                }},
                "a_chiffrer": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"description": {"type": "string"}, "raison": {"type": "string"}},
                    "required": ["description"],
                }},
                "questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["lignes"],
        },
    },
}


def _client() -> OpenAI:
    return OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                  api_key=os.getenv("LLM_API_KEY", "ollama"))


def extraire(notes: str, cat: dict[str, Article], client: OpenAI | None = None) -> dict:
    """Retourne {'lignes': [...], 'a_chiffrer': [...], 'questions': [...]}."""
    client = client or _client()
    kwargs = dict(
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        temperature=0,
        messages=[{"role": "system", "content": SYSTEM.format(catalogue=catalogue_for_prompt(cat))},
                  {"role": "user", "content": notes}],
        tools=[TOOL],
        tool_choice={"type": "function", "function": {"name": "proposer_lignes"}},
    )
    for attempt in range(4):
        try:
            msg = client.chat.completions.create(**kwargs).choices[0].message
            break
        except RateLimitError:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    if not msg.tool_calls:
        raise ValueError("Le modèle n'a pas proposé de lignes.")
    data = json.loads(msg.tool_calls[0].function.arguments or "{}")
    return {"lignes": data.get("lignes", []), "a_chiffrer": data.get("a_chiffrer", []),
            "questions": data.get("questions", [])}
