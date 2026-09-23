import json
import sqlite3
import sys

import pandas as pd

from scripts.retrain import (
    TARGET_COLUMN,
    build_training_data,
    should_retrain,
)


def test_retrain_trigger_stays_off_below_threshold():
    assert should_retrain(199, 200) is False


def test_retrain_trigger_starts_at_threshold():
    assert should_retrain(200, 200) is True


def test_feedback_training_data_keeps_cisia_three_class_labels(tmp_path, monkeypatch):
    db_path = tmp_path / "feedbacks.db"
    monkeypatch.setenv("FEEDBACK_DB", str(db_path))
    source = pd.read_csv("data/dataset_trajectoire_emploi.csv")
    row = source.iloc[0].to_dict()
    request_id = row.pop("usager_id")
    true_label = int(row.pop(TARGET_COLUMN))

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE predictions (
                request_id TEXT PRIMARY KEY,
                input_json TEXT NOT NULL,
                prediction INTEGER NOT NULL,
                probabilities_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE feedbacks (
                request_id TEXT PRIMARY KEY,
                prediction INTEGER NOT NULL,
                true_label INTEGER NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL,
                used_for_training INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        connection.execute(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, json.dumps(row), true_label, "{}", "test", "now"),
        )
        connection.execute(
            "INSERT INTO feedbacks VALUES (?, ?, ?, ?, ?, 0)",
            (request_id, true_label, true_label, None, "now"),
        )

    from scripts.retrain import load_unconsumed_feedbacks

    feedbacks = load_unconsumed_feedbacks()
    _, target = build_training_data(feedbacks)

    assert set(target.unique()) == {0, 1, 2}
    assert len(target) == len(source) + 1


def test_feedback_to_promotion_end_to_end(tmp_path, monkeypatch):
    import scripts.retrain as retrain

    db_path = tmp_path / "feedbacks.db"
    monkeypatch.setenv("FEEDBACK_DB", str(db_path))
    source = pd.read_csv("data/dataset_trajectoire_emploi.csv")
    row = source.iloc[0].to_dict()
    request_id = row.pop("usager_id")
    true_label = int(row.pop(TARGET_COLUMN))

    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE predictions (
                request_id TEXT PRIMARY KEY,
                input_json TEXT NOT NULL,
                prediction INTEGER NOT NULL,
                probabilities_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE feedbacks (
                request_id TEXT PRIMARY KEY,
                prediction INTEGER NOT NULL,
                true_label INTEGER NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL,
                used_for_training INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        connection.execute(
            "INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, json.dumps(row), true_label, "{}", "test", "now"),
        )
        connection.execute(
            "INSERT INTO feedbacks VALUES (?, ?, ?, ?, ?, 0)",
            (request_id, true_label, true_label, None, "now"),
        )

    monkeypatch.setattr(retrain, "CANDIDATE_PATH", tmp_path / "candidate.joblib")
    monkeypatch.setattr(retrain, "CANDIDATE_METADATA_PATH", tmp_path / "candidate.json")
    monkeypatch.setattr(retrain, "PROMOTED_PATH", tmp_path / "promoted.joblib")
    monkeypatch.setattr(retrain, "PROMOTED_METADATA_PATH", tmp_path / "promoted.json")
    monkeypatch.setattr(retrain, "DECISION_LOG", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(sys, "argv", ["retrain.py", "--min-feedback", "1"])

    assert retrain.main() == 0
    assert (tmp_path / "candidate.joblib").exists()
    assert (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").strip()

    with sqlite3.connect(db_path) as connection:
        consumed = connection.execute(
            "SELECT used_for_training FROM feedbacks WHERE request_id = ?",
            (request_id,),
        ).fetchone()[0]
    assert consumed == 1