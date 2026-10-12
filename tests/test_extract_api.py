"""Extraction et API avec un faux client LLM : pas de réseau, pas de clé."""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import api, extract
from app.devis import load_catalogue


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
    out = extract.extraire("Changer le WC", load_catalogue(), client=fake)
    assert out["lignes"][0]["code"] == "WC" and out["questions"] == ["Surface ?"]
    assert fake.kwargs["tool_choice"]["function"]["name"] == "proposer_lignes"
    system = fake.kwargs["messages"][0]["content"]
    assert "WC" in system and "380" not in system  # le LLM ne voit pas les prix


client = TestClient(api.app)


def test_health_and_index():
    assert client.get("/health").json()["articles"] > 20
    assert client.get("/").status_code == 200
    assert client.get("/static/notes_t2.txt").status_code == 200


def test_devis_endpoint_with_fake_llm(monkeypatch):
    monkeypatch.setattr(extract, "extraire",
                        lambda notes, cat: {"lignes": [{"code": "PRISE", "quantite": 3}],
                                            "a_chiffrer": [], "questions": []})
    api._hits.clear()
    r = client.post("/devis", json={"notes": "Changer trois prises dans la chambre"})
    assert r.status_code == 200 and r.json()["devis"]["total_ht"] == 135.0


def test_llm_failure_and_rate_limit(monkeypatch):
    def boom(notes, cat):
        raise ConnectionError
    monkeypatch.setattr(extract, "extraire", boom)
    monkeypatch.setattr(api, "RATE_LIMIT", 1)
    api._hits.clear()
    assert client.post("/devis", json={"notes": "notes de visite"}).status_code == 502
    assert client.post("/devis", json={"notes": "notes de visite"}).status_code == 429
