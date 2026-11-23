"""Extraction avec un faux client LLM : pas de réseau, pas de clé."""

import json
from types import SimpleNamespace

from devis_travaux.catalogue import load_catalogue
from devis_travaux.extraction import extraire


class FakeClient:
    def __init__(self, payload):
        self.payload, self.kwargs = payload, None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(self.payload)))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))])


def test_extraction_forces_tool_and_hides_prices():
    fake = FakeClient({"lignes": [{"code": "WC", "quantite": 1}], "questions": ["Surface ?"]})
    out = extraire("Changer le WC", load_catalogue(), client=fake)
    assert out["lignes"][0]["code"] == "WC" and out["questions"] == ["Surface ?"]
    assert out["a_chiffrer"] == []
    assert fake.kwargs["tool_choice"]["function"]["name"] == "proposer_lignes"
    system = fake.kwargs["messages"][0]["content"]
    assert "WC" in system and "380" not in system  # le LLM ne voit pas les prix
