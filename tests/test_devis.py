import json
from pathlib import Path

from app.devis import chiffrer, load_catalogue, to_csv

CAT = load_catalogue()
EX = json.loads((Path(__file__).resolve().parents[1] / "examples" / "proposition_t2.json").read_text())


def test_catalogue_loaded():
    assert "PEINT-MUR" in CAT and CAT["VMC"].tva == 5.5


def test_example_totals_are_consistent():
    d = chiffrer(EX["lignes"], CAT, EX["a_chiffrer"], EX["questions"])
    assert len(d["lignes"]) == len(EX["lignes"])
    assert round(sum(ln["total_ht"] for ln in d["lignes"]), 2) == d["total_ht"]
    assert round(d["total_ht"] + d["total_tva"], 2) == d["total_ttc"]
    assert set(d["tva_par_taux"]) == {"10", "5.5"}
    assert round(sum(d["sous_totaux_par_lot"].values()), 2) == d["total_ht"]
    assert d["a_chiffrer_manuellement"] and d["questions_a_poser"]


def test_price_comes_from_catalogue_not_from_input():
    d = chiffrer([{"code": "PEINT-MUR", "quantite": 10, "prix_unitaire_ht": 1}], CAT)
    assert d["lignes"][0]["total_ht"] == 180.0


def test_unknown_code_goes_to_manual_pricing():
    d = chiffrer([{"code": "PISCINE", "quantite": 1, "description": "Piscine"}], CAT)
    assert not d["lignes"] and d["a_chiffrer_manuellement"][0]["description"] == "Piscine"


def test_controls_missing_quantity_forfait_and_duplicates():
    d = chiffrer([
        {"code": "PRISE", "quantite": 0},
        {"code": "EVAC", "quantite": 2},
        {"code": "WC", "quantite": 1.5},
        {"code": "PEINT-MUR", "quantite": 10, "piece": "Séjour"},
        {"code": "PEINT-MUR", "quantite": 12, "piece": "séjour"},
    ], CAT)
    text = " ".join(d["alertes"])
    assert "quantité manquante" in text
    assert "forfait compté" in text
    assert "non entière" in text
    assert "deux fois" in text


def test_source_index_points_to_input_line():
    d = chiffrer([{"code": "XXX", "quantite": 1}, {"code": "WC", "quantite": 1}], CAT)
    assert d["lignes"][0]["source_index"] == 1


def test_csv_export():
    csv_text = to_csv(chiffrer(EX["lignes"], CAT))
    assert csv_text.splitlines()[0].startswith("Lot;Pièce;Code")
    assert "Total TTC" in csv_text
