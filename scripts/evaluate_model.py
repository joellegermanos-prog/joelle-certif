"""Évaluation continue + tracking MLflow (SQUELETTE M5-B2 À COMPLÉTER).

À chaque release : recalcule les métriques cibles sur un jeu de référence
figé, **trace le run dans MLflow**, compare aux seuils, et **sort un code
retour non-zéro** si dégradation (→ bloque la release en CI).

Renommez ce fichier en `scripts/evaluate_model.py` une fois complété.
Mini-cours : `07_MLflow_tracking_essentiel.md` + `08_Evaluation_continue_seuils`.

Usage cible::

    python scripts/evaluate_model.py --freeze-baseline             # une fois, au gel du jeu
    python scripts/evaluate_model.py --release-tag v2.0.0
    python scripts/evaluate_model.py --release-tag bad --degrade   # test du rouge
    mlflow ui    # comparer les runs

⚠️ **Le piège central du brief.** La tentation est de comparer vos métriques à
la baseline holdout annoncée en M1 (`metrics_holdout` dans le `.json`). Ne le
faites pas : le holdout et votre jeu de référence n'ont ni la même taille ni la
même composition. Vous mesureriez l'écart entre **deux populations**, pas la
dégradation du **modèle** — et votre garde-fou se déclencherait tout seul.
La baseline du garde-fou, c'est le **golden run** : les métriques mesurées sur
**votre** jeu de référence, au moment où vous le gelez.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.metrics import f1_score, recall_score, roc_auc_score

ROOT = Path(__file__).parent.parent
MODELS_DIR = ROOT / "services" / "model" / "models"
REFERENCE_SET = ROOT / "data" / "reference_set.csv"
REFERENCE_BASELINE = ROOT / "data" / "reference_baseline.json"

# Seuils conservateurs pour bloquer une release uniquement sur une vraie
# dégradation du modèle sur le jeu de référence gelé.
# - plancher absolu : on ne lâche pas sous un minimum acceptable
# - tolérance relative : on tolère une baisse limitée par rapport au golden run
# Ces valeurs sont choisies pour rester plus larges que le bruit de mesure du
# jeu de référence (ici ~0.02). On garde donc des marges sûres sans se
# déclencher sur du bruit de sampling.
THRESHOLDS: dict[str, dict[str, float]] = {
    "f1_macro": {"absolute_min": 0.56, "max_drop_vs_baseline": 0.04},
    "f1_default": {"absolute_min": 0.36, "max_drop_vs_baseline": 0.05},
    "roc_auc": {"absolute_min": 0.70, "max_drop_vs_baseline": 0.04},
    "recall_default": {"absolute_min": 0.60, "max_drop_vs_baseline": 0.05},
}


def compute_metrics(model, df: pd.DataFrame, meta: dict) -> dict[str, float]:
    """Calcule les métriques cibles sur le jeu de référence."""
    target_col = meta["target_column"]
    target_map = meta["target_mapping"]

    feature_cols = meta["feature_columns_numeric"] + meta["feature_columns_categorical"]
    X = df[feature_cols]
    y_true = df[target_col].map(target_map).astype(int)

    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]

    return {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "f1_default": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "recall_default": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
    }


def check_thresholds(metrics: dict[str, float], baseline: dict) -> list[str]:
    """Retourne la liste des violations de seuil (vide = release OK)."""
    baseline_metrics = baseline["metrics"]
    violations: list[str] = []

    for metric_name, cfg in THRESHOLDS.items():
        current = float(metrics.get(metric_name, -1.0))
        baseline_value = float(baseline_metrics.get(metric_name, 0.0))
        abs_min = float(cfg["absolute_min"])
        max_drop = float(cfg["max_drop_vs_baseline"])

        if current < abs_min:
            violations.append(
                f"{metric_name}={current:.4f} < absolute_min={abs_min:.4f}"
            )

        drop = baseline_value - current
        if drop > max_drop:
            violations.append(
                f"{metric_name} drop={drop:.4f} > max_drop_vs_baseline={max_drop:.4f} "
                f"(baseline={baseline_value:.4f}, current={current:.4f})"
            )

    return violations


def load_baseline() -> dict:
    """Charge le golden run (baseline mesurée sur le jeu de référence)."""
    if not REFERENCE_BASELINE.exists():
        raise SystemExit(
            f"{REFERENCE_BASELINE} est absent. Lancez d'abord : "
            "python scripts/evaluate_model.py --freeze-baseline"
        )

    baseline = json.loads(REFERENCE_BASELINE.read_text(encoding="utf-8"))
    if "metrics" not in baseline:
        raise SystemExit(f"{REFERENCE_BASELINE} ne contient pas de bloc 'metrics'.")
    return baseline


def freeze_baseline(model, df: pd.DataFrame, meta: dict) -> dict:
    """Mesure et gèle le golden run sur le jeu de référence.

    Le fichier JSON produit est la baseline de référence (golden run) que les
    futures releases devront comparer à leur sortie.
    """
    target_col = meta["target_column"]
    target_map = meta["target_mapping"]

    y_true = df[target_col].map(target_map).astype(int)
    feature_cols = meta["feature_columns_numeric"] + meta["feature_columns_categorical"]
    X = df[feature_cols]

    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]

    metrics = {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "f1_default": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "recall_default": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
    }

    payload = {
        "model_version": meta["model_version"],
        "reference_set": "data/reference_set.csv",
        "n_reference": int(len(df)),
        "metrics": metrics,
        "target_column": target_col,
        "target_mapping": target_map,
    }

    REFERENCE_BASELINE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Golden run saved to {REFERENCE_BASELINE}")
    print(json.dumps(payload, indent=2))
    return payload


def load_reference_set() -> pd.DataFrame:
    """Charge le jeu de référence, avec un garde-fou sur sa validité.

    Le jeu de référence est VOTRE instrument de mesure : vous le construisez
    à partir du holdout M1 (cf. `data/README.md`). Le fichier
    `reference_set_TEMPLATE.csv` livré dans le repo est un **exemple de
    format** de 20 lignes, pas un jeu de référence utilisable.
    """
    if not REFERENCE_SET.exists():
        raise SystemExit(
            f"{REFERENCE_SET} est absent.\n"
            "Ce fichier n'est pas fourni : c'est à vous de le construire à "
            "partir du holdout M1 (`data/lending_club_holdout.csv`).\n"
            "Mode d'emploi : data/README.md — étape 0."
        )
    df = pd.read_csv(REFERENCE_SET)
    if len(df) < 100 or df.iloc[:, -1].nunique() < 2:
        raise SystemExit(
            f"{REFERENCE_SET} contient {len(df)} ligne(s) et "
            f"{df.iloc[:, -1].nunique()} classe(s) de cible.\n"
            "Un instrument de mesure a besoin des DEUX classes et d'assez "
            "d'observations de la classe rare (~500 lignes attendues).\n"
            "Avez-vous copié reference_set_TEMPLATE.csv ? C'est un exemple de "
            "format, pas un jeu de référence — cf. data/README.md."
        )
    return df


def build_mlflow_params(meta: dict, release_tag: str, n_reference: int) -> dict:
    """Construit les params MLflow à partir du JSON du modèle, pas à la main."""
    params: dict[str, object] = {
        "model_version": meta.get("model_version", "unknown"),
        "release_tag": release_tag,
        "reference_set": str(REFERENCE_SET.name),
        "n_reference": int(n_reference),
        "target_column": meta.get("target_column", "unknown"),
        "dataset_sha256": meta.get("dataset_sha256", "unknown"),
    }

    hyperparams = meta.get("hyperparameters", {})
    for key, value in hyperparams.items():
        params[f"hyperparameters.{key}"] = value

    return params


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-tag", default="dev")
    parser.add_argument("--degrade", action="store_true")
    parser.add_argument("--freeze-baseline", action="store_true")
    args = parser.parse_args()

    model = joblib.load(MODELS_DIR / "pyrenex_risk_v2.joblib")
    meta = json.loads((MODELS_DIR / "pyrenex_risk_v2.json").read_text(encoding="utf-8"))
    df = load_reference_set()

    if args.freeze_baseline:
        print(json.dumps(freeze_baseline(model, df, meta), indent=2))
        return 0

    if args.degrade:
        # Simule un bug de preprocessing réaliste : les labels sont permutés
        # sans changer les features, ce qui casse l'alignement X / y.
        df = df.copy()
        df["loan_status"] = df["loan_status"].sample(
            frac=1.0,
            random_state=42,
        ).reset_index(drop=True)

    metrics = compute_metrics(model, df, meta)
    baseline = load_baseline()  # ← le golden run, PAS metrics_holdout
    violations = check_thresholds(metrics, baseline)

    # --- Bloc MLflow — params lus depuis le JSON du modèle ------------------
    mlflow.set_experiment("pyrenex-eval-continue")
    with mlflow.start_run(run_name=args.release_tag):
        mlflow.log_params(build_mlflow_params(meta, args.release_tag, len(df)))
        mlflow.log_metrics(metrics)
        mlflow.set_tag("status", "failed" if violations else "passed")
        mlflow.set_tag("release_blocked", str(bool(violations)))
    # ------------------------------------------------------------------------

    print(json.dumps({"metrics": metrics, "violations": violations}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
