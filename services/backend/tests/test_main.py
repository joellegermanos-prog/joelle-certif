from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


VALID_APPLICATION = {
    "age": 35,
    "niveau_diplome": "Bac+2",
    "anciennete_poste_ans": 3.0,
    "code_rome_vise": "M1805",
    "code_insee_commune": "75056",
    "synthese_entretien": "Recherche un emploi stable.",
}


def test_score_calls_model_and_returns_prediction(monkeypatch):
    async def fake_post(self, url, json, headers=None):
        assert url.endswith("/predict")
        assert headers["X-Request-ID"]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "prediction": 1,
                "prediction_label": "Retour moyen",
                "probabilities": {"0": 0.20, "1": 0.42, "2": 0.38},
                "model_version": "v1.2.3",
                "request_id": headers["X-Request-ID"],
            },
            text="ok",
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = TestClient(app)
    response = client.post("/score", json=VALID_APPLICATION, headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction"] == 1
    assert payload["probabilities"]["1"] == 0.42
    assert payload["request_id"] == "req-123"
