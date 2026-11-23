"""L'interface Streamlit se charge et chiffre l'exemple sans LLM."""

from streamlit.testing.v1 import AppTest


def test_exemple_sans_llm(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    at = AppTest.from_file("../streamlit_app.py", default_timeout=30).run()
    assert not at.exception
    assert at.button[0].disabled  # pas de clé -> génération LLM désactivée
    at.button[1].click().run()
    assert not at.exception
    assert at.metric[0].value.endswith("€") and at.metric[0].value != "0,00 €"
    assert len(at.dataframe) >= 2
