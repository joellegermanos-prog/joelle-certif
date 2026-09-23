"""Tests API + contract test du modèle — service model (fourni)."""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd

MODELS_DIR = Path(__file__).parent.parent / "models"
sys.path.insert(0, str(MODELS_DIR.parent))

from preprocess import create_features

# --- Tests API --------------------------------------------------------------

def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_predict_valid_returns_class_and_proba(client, valid_payload):
    resp = client.post("/predict", json=valid_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["prediction"] in (0, 1, 2)
    assert set(body["probabilities"]) == {"0", "1", "2"}
    assert abs(sum(body["probabilities"].values()) - 1.0) < 0.001
    assert body["model_version"] == "v1.0.0"


def test_predict_invalid_returns_422(client, valid_payload):
    bad = dict(valid_payload)
    bad["age"] = 999  # hors bornes (16-100)
    resp = client.post("/predict", json=bad)
    assert resp.status_code == 422


def test_train_requires_at_least_ten_records(client, valid_payload):
    record = dict(valid_payload)
    record["classe_retour_emploi"] = 0
    resp = client.post("/train", json={"records": [record] * 9})
    assert resp.status_code == 422


def test_train_rejects_invalid_token(client, valid_payload, monkeypatch):
    monkeypatch.setenv("TRAIN_API_TOKEN", "secret")
    record = dict(valid_payload)
    record["classe_retour_emploi"] = 0
    resp = client.post("/train", json={"records": [record] * 10})
    assert resp.status_code == 403


def test_train_returns_mlflow_run(client, valid_payload, monkeypatch, tmp_path):
    monkeypatch.delenv("TRAIN_API_TOKEN", raising=False)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file:{tmp_path / 'mlruns'}")
    records = []
    for index in range(12):
        record = dict(valid_payload)
        record["age"] = 25 + index
        record["classe_retour_emploi"] = index % 3
        records.append(record)

    resp = client.post("/train", json={"records": records})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "trained"
    assert body["rows"] == 12
    assert body["mlflow_run_id"]


def test_metrics_endpoint_exposes_prometheus(client, valid_payload):
    client.post("/predict", json=valid_payload)  # génère au moins 1 observation
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "pyrenex_predictions_total" in resp.text
    assert "cisia_model_info" in resp.text


# --- Contract test du modèle (bloque la release en CI) ----------------------

def test_model_contract_features_and_output():
    """Le pipeline CISIA accepte le schéma emploi et sort trois probabilités."""
    model = joblib.load(
        MODELS_DIR / "cisia_emploi_xgboost_multimodal_complet_balanced.joblib"
    )
    row = {
        "age": 35,
        "niveau_diplome": "Bac+2",
        "anciennete_poste_ans": 3.0,
        "code_rome_vise": "M1805",
        "code_insee_commune": "75056",
        "est_allocataire": 0,
        "nationalite_hors_ue": 0,
        "synthese_entretien": (
            "Recherche un emploi stable dans le domaine informatique."
        ),
    }
    X = create_features(pd.DataFrame([row]))
    probabilities = model.predict_proba(X)[0]
    assert int(model.predict(X)[0]) in (0, 1, 2)
    assert len(probabilities) == 3
    assert abs(float(probabilities.sum()) - 1.0) < 0.001
