from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evaluate import (
    evaluate_model,
    load_text_dataset,
    rebuild_holdout,
    validate_dataset,
)
from train import (
    build_robustness_table,
    compare_baseline_hyperparameters,
    compute_stratified_cv_summary,
    fine_tune_logistic_regression,
    fine_tune_lightgbm,
    fine_tune_random_forest,
    fine_tune_xgboost,
)


def test_validate_dataset_accepts_matching_hash(tmp_path: Path) -> None:
    data_path = tmp_path / "dataset.csv"
    data_path.write_text("a,b\n1,2\n", encoding="utf-8")
    expected_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()

    metadata = {"dataset": {"sha256": expected_hash}}

    validate_dataset(data_path, metadata)


def test_validate_dataset_rejects_modified_dataset(tmp_path: Path) -> None:
    data_path = tmp_path / "dataset.csv"
    data_path.write_text("a,b\n1,2\n", encoding="utf-8")

    metadata = {"dataset": {"sha256": "wrong_hash"}}

    with pytest.raises(ValueError, match="Le dataset a changé"):
        validate_dataset(data_path, metadata)


def test_load_text_dataset_returns_single_text_column(tmp_path: Path) -> None:
    data_path = tmp_path / "text.csv"
    pd.DataFrame({
        "synthese_entretien": ["Bonjour", "Merci"],
        "classe_retour_emploi": [0, 1],
    }).to_csv(data_path, index=False)

    X, y = load_text_dataset(data_path)

    assert list(X.columns) == ["synthese_entretien"]
    assert X.shape[1] == 1
    assert len(y) == len(X)
    assert set(y.unique()) <= {0, 1}


def test_rebuild_holdout_uses_test_indices(tmp_path: Path) -> None:
    data_path = tmp_path / "data.csv"
    df = pd.DataFrame({
        "synthese_entretien": ["a", "b", "c", "d"],
        "classe_retour_emploi": [0, 1, 2, 0],
    })
    df.to_csv(data_path, index=False)

    metadata = {
        "scenario": {"text_only": True, "include_sensitive": False, "include_text": True},
        "dataset": {"test_indices": [1, 3], "test_rows": 2},
    }

    X_holdout, y_holdout = rebuild_holdout(data_path, metadata)

    assert list(X_holdout.columns) == ["synthese_entretien"]
    assert len(X_holdout) == 2
    assert list(y_holdout.index) == [1, 3]


def test_evaluate_model_returns_metrics_and_predictions() -> None:
    class DummyModel:
        def predict(self, X):
            return np.array([0, 1, 2, 0])

        def predict_proba(self, X):
            return np.array([
                [0.8, 0.1, 0.1],
                [0.1, 0.8, 0.1],
                [0.1, 0.1, 0.8],
                [0.8, 0.1, 0.1],
            ])

    y_holdout = pd.Series([0, 1, 2, 0], name="classe_retour_emploi")
    X_holdout = pd.DataFrame({"synthese_entretien": ["a", "b", "c", "d"]})

    metrics, y_pred, y_proba, report_text = evaluate_model(DummyModel(), X_holdout, y_holdout)

    assert set(metrics.keys()) >= {
        "accuracy",
        "f1_macro",
        "f1_weighted",
        "f1_class_0",
        "f1_class_1",
        "f1_class_2",
        "confusion_matrix",
        "classification_report",
        "roc_auc_ovr_macro",
    }
    assert np.array_equal(y_pred, np.array([0, 1, 2, 0]))
    assert y_proba is not None
    assert "precision" in report_text


def test_compute_stratified_cv_summary_returns_metrics() -> None:
    documents = [
        "je cherche un emploi stable et durable",
        "je veux travailler dans une entreprise",
        "je souhaite un poste administratif",
        "je recherche un emploi en informatique",
        "je veux une opportunite de travail",
        "je cherche un emploi qualifie",
        "je veux developper mon experience professionnelle",
        "je recherche un poste technique",
        "je veux travailler dans le commerce",
        "je cherche un travail sur la finance",
        "je suis disponible pour un emploi",
        "je cherche un poste dans le marketing",
        "je veux une opportunite pour la logistique",
        "je recherche un travail en gestion",
        "je cherche emploi en service client",
        "je souhaite un contrat stable",
        "je veux travailler dans la restauration",
        "je cherche un poste dans la production",
        "je veux un emploi dans la vente",
        "je cherche un travail de bureau",
        "je souhaite un emploi en conception",
        "je cherche du travail pour un projet",
        "je veux un poste dans l'innovation",
        "je recherche un emploi de consultant",
        "je cherche une mission courte",
        "je veux travailler dans la communication",
        "je cherche un poste dans le digital",
        "je veux un emploi dans la data",
        "je recherche un travail de gestionnaire",
        "je cherche un poste en ressources humaines",
    ]

    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    result = compute_stratified_cv_summary(
        model_type="logistic_regression",
        scenario_name="texte_seul",
        config_name="balanced",
        X=X,
        y=y,
        n_splits=3,
    )

    assert result["enabled"] is True
    assert result["n_splits"] == 3
    assert set(result["metrics"].keys()) >= {"accuracy", "f1_macro", "f1_weighted"}
    assert 0.0 <= result["metrics"]["accuracy"]["mean"] <= 1.0


def test_build_robustness_table_returns_std_by_scenario() -> None:
    results = [
        {
            "model_type": "random_forest",
            "scenario_name": "texte_seul",
            "config_name": "balanced",
            "cv_summary": {
                "metrics": {
                    "f1_macro": {"mean": 0.70, "std": 0.08},
                },
            },
        },
        {
            "model_type": "logistic_regression",
            "scenario_name": "texte_seul",
            "config_name": "balanced",
            "cv_summary": {
                "metrics": {
                    "f1_macro": {"mean": 0.75, "std": 0.03},
                },
            },
        },
    ]

    table = build_robustness_table(results)

    assert list(table.columns) == [
        "scenario_name",
        "model_type",
        "config_name",
        "metric",
        "mean",
        "std",
    ]
    assert list(table["model_type"]) == [
        "logistic_regression",
        "random_forest",
    ]
    assert list(table["std"]) == [0.03, 0.08]


def test_compare_baseline_hyperparameters_selects_one_configuration() -> None:
    documents = [
        "emploi stable administratif",
        "travail informatique entreprise",
        "poste commerce vente",
        "emploi gestion projet",
        "travail restauration service",
        "poste finance data",
    ] * 5
    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    table = compare_baseline_hyperparameters(
        model_type="random_forest",
        scenario_name="texte_seul",
        X_train=X,
        y_train=y,
        parameter_sets={
            "petit": {"n_estimators": 10, "max_depth": None},
            "profond": {"n_estimators": 10, "max_depth": 5},
        },
        cv_folds=3,
    )

    assert len(table) == 2
    assert table["selected"].sum() == 1
    assert set(table.columns) >= {
        "f1_macro_mean",
        "f1_macro_std",
        "recall_classe_2_mean",
        "analysis",
    }


def test_fine_tune_logistic_regression_returns_metric_table() -> None:
    documents = [
        "emploi stable administratif",
        "travail informatique entreprise",
        "poste commerce vente",
        "emploi gestion projet",
        "travail restauration service",
        "poste finance data",
    ] * 5
    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    table = fine_tune_logistic_regression(
        scenario_name="texte_seul",
        X_train=X,
        y_train=y,
        parameter_grid={
            "solver": ("lbfgs",),
            "C": (0.5, 1.0),
            "class_weight": ("balanced",),
            "max_iter": (200,),
        },
        cv_folds=3,
    )

    assert len(table) == 2
    assert table["selected"].sum() == 1
    assert (table["critical_2_to_0"] >= 0).all()
    assert set(table.columns) >= {
        "f1_macro",
        "recall_c2",
        "precision_c2",
        "f1_c2",
        "critical_2_to_0",
        "log_loss",
        "analysis",
    }


def test_fine_tune_random_forest_returns_metric_table() -> None:
    documents = [
        "emploi stable administratif",
        "travail informatique entreprise",
        "poste commerce vente",
        "emploi gestion projet",
        "travail restauration service",
        "poste finance data",
    ] * 5
    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    table = fine_tune_random_forest(
        scenario_name="texte_seul",
        X_train=X,
        y_train=y,
        parameter_grid={
            "class_weight": ("balanced",),
            "class_2_weight": (1.0, 2.0),
            "n_estimators": (10,),
            "max_depth": (5,),
            "min_samples_leaf": (2, 4),
            "max_features": ("sqrt",),
        },
        cv_folds=3,
    )

    assert len(table) == 4
    assert table["selected"].sum() == 1
    assert (table["critical_2_to_0"] >= 0).all()
    assert set(table.columns) >= {
        "class_2_weight",
        "n_estimators",
        "max_depth",
        "min_samples_leaf",
        "max_features",
        "class_weight",
        "f1_macro",
        "recall_c2",
        "analysis",
    }


def test_fine_tune_xgboost_returns_metric_table() -> None:
    documents = [
        "emploi stable administratif",
        "travail informatique entreprise",
        "poste commerce vente",
        "emploi gestion projet",
        "travail restauration service",
        "poste finance data",
    ] * 5
    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    table = fine_tune_xgboost(
        scenario_name="texte_seul",
        X_train=X,
        y_train=y,
        parameter_grid={
            "class_2_weight": (1.0, 2.5),
            "n_estimators": (10,),
            "learning_rate": (0.05, 0.1),
            "max_depth": (3,),
            "colsample_bytree": (0.7,),
        },
        cv_folds=3,
    )

    assert len(table) == 4
    assert table["selected"].sum() == 1
    assert (table["critical_2_to_0"] >= 0).all()
    assert set(table.columns) >= {
        "class_2_weight",
        "n_estimators",
        "learning_rate",
        "max_depth",
        "colsample_bytree",
        "f1_macro",
        "recall_c2",
        "analysis",
    }


def test_fine_tune_lightgbm_returns_metric_table() -> None:
    documents = [
        "emploi stable administratif",
        "travail informatique entreprise",
        "poste commerce vente",
        "emploi gestion projet",
        "travail restauration service",
        "poste finance data",
    ] * 5
    X = pd.DataFrame({"synthese_entretien": documents})
    y = pd.Series([0, 1, 2] * 10, name="classe_retour_emploi")

    table = fine_tune_lightgbm(
        scenario_name="texte_seul",
        X_train=X,
        y_train=y,
        parameter_grid={
            "class_weight": (None, "balanced"),
            "n_estimators": (10,),
            "learning_rate": (0.02, 0.05),
            "num_leaves": (15,),
            "min_child_samples": (10,),
            "colsample_bytree": (0.7,),
        },
        cv_folds=3,
    )

    assert len(table) == 4
    assert table["selected"].sum() == 1
    assert (table["critical_2_to_0"] >= 0).all()
    assert set(table.columns) >= {
        "n_estimators",
        "learning_rate",
        "num_leaves",
        "min_child_samples",
        "colsample_bytree",
        "f1_macro",
        "recall_c2",
        "analysis",
    }
