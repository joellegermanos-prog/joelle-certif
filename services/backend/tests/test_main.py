import sys
from pathlib import Path
from types import SimpleNamespace

for module_name in ("app.main", "app.middleware", "app.schemas", "app"):
    sys.modules.pop(module_name, None)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from fastapi.testclient import TestClient

VALID_APPLICATION = {
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

    def test_score_persists_session_and_history(monkeypatch):
        async def fake_post(self, url, json, headers=None):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "prediction": 0,
                    "prediction_label": "Retour rapide",
                    "probabilities": {"0": 0.8, "1": 0.1, "2": 0.1},
                    "model_version": "v-history",
                    "request_id": headers["X-Request-ID"],
                },
                text="ok",
            )

        monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
        client = TestClient(app)
        response = client.post(
            "/score",
            json={
                **VALID_APPLICATION,
                "usager_id": "user-history",
                "session_id": "session-history",
            },
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == "session-history"
        history = client.get("/history?session_id=session-history")
        assert history.status_code == 200
        assert history.json()[0]["usager_id"] == "user-history"


def test_train_validates_minimum_records():
    response = TestClient(app).post(
        "/train",
        json={"records": [VALID_APPLICATION]},
    )
    assert response.status_code == 422


def _register_prediction(request_id: str = "req-feedback") -> None:
    import os
    import sqlite3
    from pathlib import Path

    db_path = Path(
        os.environ.get("FEEDBACK_DB", str(Path.cwd() / "data" / "feedbacks.db"))
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS predictions (
                request_id TEXT PRIMARY KEY,
                input_json TEXT NOT NULL,
                prediction INTEGER NOT NULL,
                probabilities_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS feedbacks (
                request_id TEXT PRIMARY KEY,
                prediction INTEGER NOT NULL,
                true_label INTEGER NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL,
                used_for_training INTEGER NOT NULL DEFAULT 0
            )"""
        )
        connection.execute(
            """INSERT OR REPLACE INTO predictions
            (request_id, input_json, prediction, probabilities_json,
             model_version, created_at)
            VALUES (?, '{}', 1, '{"0": 0.2, "1": 0.8, "2": 0.0}', 'test', 'now')""",
            (request_id,),
        )


def test_feedback_requires_known_prediction():
    response = TestClient(app).post(
        "/feedback",
        json={"request_id": "missing", "prediction": 1, "true_label": 1},
    )
    assert response.status_code == 404


def test_feedback_is_idempotent_and_rejects_conflict():
    _register_prediction()
    client = TestClient(app)
    payload = {"request_id": "req-feedback", "prediction": 1, "true_label": 2}

    first = client.post("/feedback", json=payload)
    second = client.post("/feedback", json=payload)
    conflict = client.post(
        "/feedback",
        json={**payload, "true_label": 0},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["status"] == "already_registered"
    assert conflict.status_code == 409
    assert client.get("/feedback/count").json()["new"] == 1
