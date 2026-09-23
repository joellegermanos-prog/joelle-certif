"""Train a CISIA multiclass candidate from validated production feedbacks.

The script deliberately creates a candidate artifact only. Promotion and
replacement of the serving model remain separate release-gate decisions.

Usage:
    python scripts/retrain.py --min-feedback 200
    python scripts/retrain.py --min-feedback 1
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "model"
DATA = ROOT / "data"
MODELS = SERVICE_ROOT / "models"
SOURCE_DATASET = DATA / "dataset_trajectoire_emploi.csv"
CANDIDATE_PATH = MODELS / "cisia_emploi_candidate.joblib"
CANDIDATE_METADATA_PATH = MODELS / "cisia_emploi_candidate.json"
PROMOTED_PATH = MODELS / "cisia_emploi_promoted.joblib"
PROMOTED_METADATA_PATH = MODELS / "cisia_emploi_promoted.json"
DECISION_LOG = ROOT / "decisions_log.jsonl"
PRODUCTION_PATH = MODELS / "cisia_emploi_xgboost_multimodal_complet_balanced.joblib"
PRODUCTION_METADATA_PATH = MODELS / "cisia_emploi_xgboost_multimodal_complet_balanced.json"
REFERENCE_SET = DATA / "reference_set.csv"

sys.path.insert(0, str(SERVICE_ROOT))
from preprocess import (  # noqa: E402
    TARGET_COLUMN,
    build_preprocessor,
    create_features,
    load_dataset,
)
try:  # Supports both `python scripts/retrain.py` and pytest imports.
    from promotion import decide_promotion  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - import-mode compatibility
    from scripts.promotion import decide_promotion  # noqa: E402

# The previous M6 reference implementation used RandomForestClassifier here.
# It is intentionally left as a comment for traceability; M5 production uses
# the CISIA XGBoost multiclass pipeline below.
# from sklearn.ensemble import RandomForestClassifier
# candidate = Pipeline([("preprocessor", build_preprocessor()),
#                       ("classifier", RandomForestClassifier(...))])

XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,
    "n_estimators": 400,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 2.0,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "eval_metric": "mlogloss",
    "random_state": 42,
    "n_jobs": -1,
    "verbosity": 0,
}


def feedback_db_path() -> Path:
    return Path(os.environ.get("FEEDBACK_DB", str(DATA / "feedbacks.db")))


def should_retrain(feedback_count: int, min_feedback: int) -> bool:
    """Return whether the number of new feedbacks reaches the trigger."""
    return feedback_count >= min_feedback


def load_unconsumed_feedbacks() -> pd.DataFrame:
    """Return raw production inputs joined with their validated labels."""
    db_path = feedback_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    with sqlite3.connect(db_path) as connection:
        feedbacks = pd.read_sql_query(
            """SELECT p.request_id, p.input_json, f.true_label
               FROM predictions AS p
               JOIN feedbacks AS f ON f.request_id = p.request_id
               WHERE f.used_for_training = 0""",
            connection,
        )

    if feedbacks.empty:
        return feedbacks

    inputs = pd.json_normalize(feedbacks["input_json"].map(json.loads))
    rows = pd.concat(
        [feedbacks[["request_id", "true_label"]].reset_index(drop=True), inputs],
        axis=1,
    )
    rows = rows.rename(columns={"request_id": "usager_id", "true_label": TARGET_COLUMN})
    return rows


def build_training_data(feedbacks: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Append labelled production rows to the historical CISIA training set."""
    historical_X, historical_y = load_dataset(SOURCE_DATASET)
    if feedbacks.empty:
        return historical_X, historical_y

    required_feedback_columns = {
        "age",
        "niveau_diplome",
        "anciennete_poste_ans",
        "code_rome_vise",
        "code_insee_commune",
        "synthese_entretien",
        TARGET_COLUMN,
    }
    missing_columns = sorted(required_feedback_columns - set(feedbacks.columns))
    if missing_columns:
        raise ValueError(
            "Feedback registry contains incomplete prediction inputs; "
            f"missing columns: {missing_columns}"
        )

    feedback_frame = create_features(feedbacks)
    feedback_features = feedback_frame[historical_X.columns].copy()
    feedback_target = pd.to_numeric(feedback_frame[TARGET_COLUMN], errors="raise").astype(int)
    if not set(feedback_target.unique()).issubset({0, 1, 2}):
        raise ValueError("Feedback labels must be limited to CISIA classes 0, 1 and 2")

    return (
        pd.concat([historical_X, feedback_features], ignore_index=True),
        pd.concat([historical_y, feedback_target], ignore_index=True),
    )


def build_candidate() -> Pipeline:
    """Build the same multimodal preprocessing/model family as M5 production."""
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor(include_sensitive=True, include_text=True)),
            ("classifier", XGBClassifier(**XGB_PARAMS)),
        ]
    )


def write_candidate_metadata(candidate: Pipeline, rows: int, feedback_count: int, metrics: dict[str, float]) -> None:
    payload = {
        "model_name": "cisia_emploi",
        "model_type": "xgboost",
        "model_version": f"candidate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training": {
            "rows": rows,
            "new_feedbacks": feedback_count,
            "metrics_train": metrics,
        },
        "target": {
            "column": TARGET_COLUMN,
            "expected_values": [0, 1, 2],
        },
        "configuration": {"model_parameters": XGB_PARAMS},
    }
    CANDIDATE_METADATA_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def mark_feedbacks_consumed() -> None:
    """Mark only feedbacks used by the successfully built candidate."""
    db_path = feedback_db_path()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE feedbacks SET used_for_training = 1 WHERE used_for_training = 0"
        )


def evaluate_on_reference(model: Pipeline) -> dict[str, float]:
    """Evaluate a model on the frozen CISIA reference set."""
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    if not REFERENCE_SET.exists():
        raise FileNotFoundError(f"Reference set not found: {REFERENCE_SET}")
    reference = pd.read_csv(REFERENCE_SET)
    target = reference[TARGET_COLUMN].astype(int)
    features = create_features(reference.drop(columns=[TARGET_COLUMN]))
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)
    return {
        "accuracy": float(accuracy_score(target, predictions)),
        "f1_macro": float(f1_score(target, predictions, average="macro", zero_division=0)),
        "f1_classe_2": float(
            f1_score(target, predictions, labels=[2], average=None, zero_division=0)[0]
        ),
        "recall_classe_2": float(
            recall_score(target, predictions, labels=[2], average=None, zero_division=0)[0]
        ),
        "precision_classe_2": float(
            precision_score(target, predictions, labels=[2], average=None, zero_division=0)[0]
        ),
        "roc_auc_ovr_macro": float(
            roc_auc_score(target, probabilities, multi_class="ovr", average="macro")
        ),
    }


def log_decision(candidate_metrics: dict[str, float], production_metrics: dict[str, float], decision) -> None:
    """Append every promotion decision, including rejected candidates."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_metrics": candidate_metrics,
        "production_metrics": production_metrics,
        "promote": decision.promote,
        "reason": decision.reason,
        "reference_set": str(REFERENCE_SET.relative_to(ROOT)),
    }
    with DECISION_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_promoted_metadata(candidate_metrics: dict[str, float], feedback_count: int) -> None:
    """Persist promotion metadata without changing the production artifact."""
    metadata = json.loads(PRODUCTION_METADATA_PATH.read_text(encoding="utf-8"))
    candidate_metadata = json.loads(CANDIDATE_METADATA_PATH.read_text(encoding="utf-8"))
    metadata["configuration"] = candidate_metadata["configuration"]
    metadata["model_version"] = f"promoted-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    metadata["promotion"] = {
        "status": "promoted",
        "new_feedbacks": feedback_count,
        "reference_set": str(REFERENCE_SET.relative_to(ROOT)),
        "metrics": candidate_metrics,
    }
    PROMOTED_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-feedback", type=int, default=200)
    args = parser.parse_args()
    if args.min_feedback < 1:
        parser.error("--min-feedback must be positive")

    feedbacks = load_unconsumed_feedbacks()
    feedback_count = len(feedbacks)
    if not should_retrain(feedback_count, args.min_feedback):
        print(f"Skip retrain: {feedback_count} new feedbacks < {args.min_feedback}")
        return 0

    X_train, y_train = build_training_data(feedbacks)
    candidate = build_candidate()
    candidate.fit(X_train, y_train)

    probabilities = candidate.predict_proba(X_train)
    predictions = candidate.predict(X_train)
    if probabilities.shape[1] != 3 or not np.isfinite(probabilities).all():
        raise ValueError("Candidate must expose finite probabilities for 3 classes")

    metrics = {
        "accuracy": float(accuracy_score(y_train, predictions)),
        "f1_macro": float(f1_score(y_train, predictions, average="macro", zero_division=0)),
        "recall_classe_2": float(
            recall_score(y_train, predictions, labels=[2], average=None, zero_division=0)[0]
        ),
    }
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(candidate, CANDIDATE_PATH, compress=3)
    write_candidate_metadata(candidate, len(X_train), feedback_count, metrics)

    production = joblib.load(PRODUCTION_PATH)
    candidate_reference_metrics = evaluate_on_reference(candidate)
    production_reference_metrics = evaluate_on_reference(production)
    decision = decide_promotion(candidate_reference_metrics, production_reference_metrics)
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_decision(candidate_reference_metrics, production_reference_metrics, decision)

    if decision.promote:
        shutil.copy2(CANDIDATE_PATH, PROMOTED_PATH)
        write_promoted_metadata(candidate_reference_metrics, feedback_count)

    mark_feedbacks_consumed()
    print(
        json.dumps(
            {
                "status": "promoted" if decision.promote else "rejected",
                "candidate_path": str(CANDIDATE_PATH),
                "promoted_path": str(PROMOTED_PATH) if decision.promote else None,
                "decision": decision.reason,
                "metrics_train": metrics,
                "metrics_reference": candidate_reference_metrics,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
