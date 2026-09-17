import json
import sys
from pathlib import Path

import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_model import (
    compute_metrics,
    check_thresholds,
    load_baseline,
    load_reference_set,
)

MODEL_PATH = ROOT / "services" / "model" / "models" / "pyrenex_risk_v2.joblib"
META_PATH = ROOT / "services" / "model" / "models" / "pyrenex_risk_v2.json"

def test_reference_baseline_matches_current_model():
    model = joblib.load(MODEL_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    df = load_reference_set()

    metrics = compute_metrics(model, df, meta)
    baseline = load_baseline()

    for name in ["f1_macro", "f1_default", "roc_auc", "recall_default"]:
        assert abs(metrics[name] - baseline["metrics"][name]) < 1e-12

def test_thresholds_detect_degradation():
    baseline = {
        "metrics": {
            "f1_macro": 0.5951,
            "f1_default": 0.4211,
            "roc_auc": 0.7247,
            "recall_default": 0.6593,
        }
    }
    metrics = {
        "f1_macro": 0.45,
        "f1_default": 0.21,
        "roc_auc": 0.47,
        "recall_default": 0.33,
    }

    violations = check_thresholds(metrics, baseline)
    assert len(violations) > 0

def test_mlflow_params_are_loaded_from_model_metadata():
    from scripts.evaluate_model import build_mlflow_params

    meta = {
        "model_version": "v2.0.0",
        "dataset_sha256": "abc123",
        "hyperparameters": {"n_estimators": 200, "max_depth": 10},
        "target_column": "loan_status",
    }

    params = build_mlflow_params(meta, "v2.0.0", 512)

    assert params["model_version"] == "v2.0.0"
    assert params["dataset_sha256"] == "abc123"
    assert params["hyperparameters.n_estimators"] == 200
    assert params["hyperparameters.max_depth"] == 10
    assert params["n_reference"] == 512

def test_release_gate_blocks_on_violation():
    baseline = {
        "metrics": {
            "f1_macro": 0.5951,
            "f1_default": 0.4211,
            "roc_auc": 0.7247,
            "recall_default": 0.6593,
        }
    }
    metrics = {
        "f1_macro": 0.45,
        "f1_default": 0.21,
        "roc_auc": 0.47,
        "recall_default": 0.33,
    }

    violations = check_thresholds(metrics, baseline)
    assert violations