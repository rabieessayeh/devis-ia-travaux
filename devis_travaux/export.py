"""Export du devis chiffré en CSV (séparateur « ; », lisible par Excel et Google Sheets)."""

from __future__ import annotations

import csv
import io


def to_csv(devis: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Lot", "Pièce", "Code", "Désignation", "Quantité", "Unité", "PU HT", "TVA %", "Total HT"])
    for ln in devis["lignes"]:
        w.writerow([ln["lot"], ln["piece"], ln["code"], ln["libelle"], ln["quantite"], ln["unite"],
                    f"{ln['prix_unitaire_ht']:.2f}", ln["tva"], f"{ln['total_ht']:.2f}"])
    w.writerow([])
    w.writerow(["", "", "", "Total HT", "", "", "", "", f"{devis['total_ht']:.2f}"])
    for taux, montant in devis["tva_par_taux"].items():
        w.writerow(["", "", "", f"TVA {taux} %", "", "", "", "", f"{montant:.2f}"])
    w.writerow(["", "", "", "Total TTC", "", "", "", "", f"{devis['total_ttc']:.2f}"])
    return out.getvalue()
