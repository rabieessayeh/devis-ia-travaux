"""Interface Streamlit : notes de visite -> devis chiffré.

Usage :
    streamlit run app.py

Clé LLM : fichier .env en local, ou *Secrets* de l'app sur Streamlit Community Cloud
(voir .env.example et .streamlit/secrets.toml.example).
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque

import pandas as pd
import streamlit as st

from devis_travaux import EXAMPLES_DIR, llm
from devis_travaux.catalogue import load_catalogue
from devis_travaux.chiffrage import chiffrer
from devis_travaux.export import to_csv

GITHUB_URL = "https://github.com/rabieessayeh/devis-ia-travaux"

st.set_page_config(page_title="Devis Travaux Assistant", page_icon="🧱", layout="wide")


# --- Configuration : .env (local) ou secrets Streamlit (Cloud) ------------------------------------
try:
    _secrets = dict(st.secrets)
except Exception:  # noqa: BLE001  (aucun secrets.toml)
    _secrets = {}
llm.load_config(_secrets)
LLM_OK = llm.is_configured()
RATE_LIMIT = int(llm.get("RATE_LIMIT_PER_HOUR"))


# --- Ressources mises en cache (une seule fois par processus) -------------------------------------
@st.cache_resource
def catalogue() -> dict:
    return load_catalogue()


@st.cache_data
def exemple() -> tuple[str, dict]:
    notes = (EXAMPLES_DIR / "notes_t2.txt").read_text(encoding="utf-8")
    prop = json.loads((EXAMPLES_DIR / "proposition_t2.json").read_text(encoding="utf-8"))
    return notes, prop


@st.cache_resource
def _hits() -> dict[str, deque]:
    """Compteur d'appels LLM partagé entre sessions (protège le quota de la clé)."""
    return defaultdict(deque)


def _rate_ok() -> bool:
    ip = getattr(st.context, "ip_address", None) or "local"
    now, win = time.time(), _hits()[ip]
    while win and now - win[0] > 3600:
        win.popleft()
    if len(win) >= RATE_LIMIT:
        return False
    win.append(now)
    return True


CAT = catalogue()

# --- État de session ------------------------------------------------------------------------------
ss = st.session_state
if "notes" not in ss:
    ss.notes = exemple()[0]
ss.setdefault("proposition", None)
ss.setdefault("version", 0)  # change à chaque nouvelle proposition -> réinitialise l'éditeur


def _set_proposition(prop: dict) -> None:
    ss.proposition = prop
    ss.version += 1


def _charger_exemple() -> None:
    notes, prop = exemple()
    ss.notes = notes
    _set_proposition(prop)


# --- Interface ------------------------------------------------------------------------------------
st.title("Devis Travaux Assistant")
st.caption("Notes de visite en texte libre → devis chiffré. Le LLM propose les lignes ; "
           "**les prix, la TVA et les totaux sont calculés par du code déterministe**. "
           f"[Code source]({GITHUB_URL})")

with st.sidebar:
    st.subheader("Bibliothèque de prix")
    st.caption(f"{len(CAT)} articles — prix indicatifs de démonstration")
    st.dataframe(
        pd.DataFrame([{"Code": a.code, "Libellé": a.libelle, "Unité": a.unite,
                       "PU HT": float(a.prix_unitaire_ht), "TVA %": float(a.tva)} for a in CAT.values()]),
        hide_index=True, height=420,
    )
    st.caption(f"Modèle : `{llm.get('LLM_MODEL')}`" if LLM_OK
               else "Aucune clé LLM configurée : seul l'exemple est disponible.")

col_in, col_out = st.columns([2, 3], gap="large")

with col_in:
    st.subheader("Notes de visite")
    st.text_area("Notes", key="notes", height=320, max_chars=4000, label_visibility="collapsed")
    b1, b2 = st.columns(2)
    generer = b1.button("Générer le devis", type="primary", width="stretch", disabled=not LLM_OK,
                        help=None if LLM_OK else "Ajoutez LLM_API_KEY dans les secrets de l'app.")
    b2.button("Exemple sans LLM", width="stretch", on_click=_charger_exemple,
              help="Charge une proposition enregistrée : fonctionne sans clé API.")

    if generer:
        notes = ss.notes.strip()
        if len(notes) < 10:
            st.warning("Notes trop courtes.")
        elif not _rate_ok():
            st.error("Limite horaire atteinte, réessayez plus tard.")
        else:
            from devis_travaux.extraction import extraire

            with st.spinner("Lecture des notes par le modèle…"):
                try:
                    _set_proposition(extraire(notes, CAT))
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Le modèle n'a pas pu être joint ({type(exc).__name__}).")

with col_out:
    prop = ss.proposition
    if prop is None:
        st.info("Collez des notes puis **Générer le devis**, ou cliquez sur **Exemple sans LLM**.")
        st.stop()

    st.subheader("Lignes proposées — modifiables")
    df = pd.DataFrame(prop["lignes"]).reindex(columns=["piece", "code", "quantite", "hypothese"])
    edited = st.data_editor(
        df, key=f"editor_{ss.version}", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "piece": st.column_config.TextColumn("Pièce"),
            "code": st.column_config.SelectboxColumn("Code", options=sorted(CAT), required=True),
            "quantite": st.column_config.NumberColumn("Quantité", min_value=0, step=0.5),
            "hypothese": st.column_config.TextColumn("Hypothèse", width="large"),
        },
    )
    lignes = [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
              for r in edited.to_dict("records") if r.get("code")]  # ignore les lignes vides ajoutées
    devis = chiffrer(lignes, CAT, prop.get("a_chiffrer"), prop.get("questions"))

    m1, m2, m3 = st.columns(3)
    eur = lambda x: f"{x:,.2f} €".replace(",", " ").replace(".", ",")  # noqa: E731
    m1.metric("Total HT", eur(devis["total_ht"]))
    m2.metric("TVA", eur(devis["total_tva"]),
              help=" · ".join(f"{t} % : {eur(v)}" for t, v in devis["tva_par_taux"].items()))
    m3.metric("Total TTC", eur(devis["total_ttc"]))

    st.subheader("Devis chiffré")
    if devis["lignes"]:
        st.dataframe(
            pd.DataFrame(devis["lignes"])[["lot", "piece", "libelle", "quantite", "unite",
                                           "prix_unitaire_ht", "tva", "total_ht"]],
            hide_index=True, width="stretch",
            column_config={
                "lot": "Lot", "piece": "Pièce", "libelle": "Désignation", "quantite": "Qté",
                "unite": "Unité", "tva": "TVA %",
                "prix_unitaire_ht": st.column_config.NumberColumn("PU HT", format="%.2f €"),
                "total_ht": st.column_config.NumberColumn("Total HT", format="%.2f €"),
            },
        )
        st.bar_chart(pd.Series(devis["sous_totaux_par_lot"], name="Total HT (€)"), horizontal=True)

    for titre, items, show in (
        ("À chiffrer manuellement", [f"**{x.get('description', '')}** — {x.get('raison', '')}"
                                     for x in devis["a_chiffrer_manuellement"]], st.warning),
        ("Questions à poser", devis["questions_a_poser"], st.info),
        ("Points de contrôle", devis["alertes"], st.error),
    ):
        if items:
            show(f"**{titre}**\n\n" + "\n".join(f"- {x}" for x in items))

    st.download_button("Export CSV (Excel / Sheets)", data=("﻿" + to_csv(devis)).encode("utf-8"),
                       file_name="devis.csv", mime="text/csv", width="stretch")
