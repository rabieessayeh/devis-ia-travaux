"""Chiffrage déterministe : bibliothèque de prix + lignes proposées -> devis.

Le LLM ne calcule jamais un prix. Il propose des lignes (code de la bibliothèque,
quantité, pièce) ; ce module vérifie chaque ligne, applique le prix unitaire et
la TVA de la bibliothèque, et calcule les totaux. Toute ligne douteuse est
signalée au lieu d'être devinée.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .catalogue import Article

CENT = Decimal("0.01")


def _money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def chiffrer(lignes: list[dict], cat: dict[str, Article], a_chiffrer: list[dict] | None = None,
             questions: list[str] | None = None) -> dict:
    """Transforme les lignes proposées en devis chiffré, avec contrôles."""
    devis_lignes, alertes = [], []
    a_chiffrer = list(a_chiffrer or [])

    for i, ligne in enumerate(lignes, start=1):
        code = str(ligne.get("code", "")).strip().upper()
        art = cat.get(code)
        piece = ligne.get("piece") or ""
        if art is None:
            a_chiffrer.append({"description": ligne.get("description") or code,
                               "raison": f"code « {code} » absent de la bibliothèque"})
            continue
        try:
            qte = Decimal(str(ligne.get("quantite")))
        except Exception:  # noqa: BLE001
            qte = Decimal("0")
        if qte <= 0:
            alertes.append(f"Ligne {i} ({art.libelle}) : quantité manquante ou nulle, à confirmer")
            continue
        if art.unite in ("u", "forfait") and qte != qte.to_integral_value():
            alertes.append(f"Ligne {i} ({art.libelle}) : quantité {qte} non entière "
                           f"pour l'unité « {art.unite} »")
        if art.unite == "forfait" and qte > 1:
            alertes.append(f"Ligne {i} ({art.libelle}) : forfait compté {qte} fois, à vérifier")
        total_ht = _money(qte * art.prix_unitaire_ht)
        devis_lignes.append({
            "source_index": i - 1,
            "code": art.code, "lot": art.lot, "libelle": art.libelle, "piece": piece,
            "quantite": float(qte), "unite": art.unite,
            "prix_unitaire_ht": float(art.prix_unitaire_ht), "tva": float(art.tva),
            "total_ht": float(total_ht), "hypothese": ligne.get("hypothese") or "",
        })

    # Doublons exacts (même code, même pièce) : souvent une erreur d'extraction.
    vus = {}
    for ln in devis_lignes:
        cle = (ln["code"], ln["piece"].lower())
        if cle in vus:
            alertes.append(f"{ln['libelle']} apparaît deux fois pour « {ln['piece'] or 'sans pièce'} »")
        vus[cle] = True

    total_ht = sum((Decimal(str(ln["total_ht"])) for ln in devis_lignes), Decimal("0"))
    tva_par_taux: dict[str, Decimal] = {}
    for ln in devis_lignes:
        taux = Decimal(str(ln["tva"]))
        cle = format(taux, "f").rstrip("0").rstrip(".")
        tva_par_taux[cle] = tva_par_taux.get(cle, Decimal("0")) + \
            Decimal(str(ln["total_ht"])) * taux / 100
    tva = {k: float(_money(v)) for k, v in sorted(tva_par_taux.items())}
    total_tva = _money(sum(tva_par_taux.values(), Decimal("0")))

    lots: dict[str, float] = {}
    for ln in devis_lignes:
        lots[ln["lot"]] = round(lots.get(ln["lot"], 0.0) + ln["total_ht"], 2)

    return {
        "lignes": devis_lignes,
        "sous_totaux_par_lot": lots,
        "total_ht": float(_money(total_ht)),
        "tva_par_taux": tva,
        "total_tva": float(total_tva),
        "total_ttc": float(_money(total_ht + total_tva)),
        "a_chiffrer_manuellement": a_chiffrer,
        "questions_a_poser": list(questions or []),
        "alertes": alertes,
    }
