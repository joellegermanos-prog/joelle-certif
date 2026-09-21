from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from reporting import create_benchmark, save_benchmark_chart, save_failures


def test_create_benchmark_sorts_and_writes_csv(tmp_path: Path) -> None:
    results = [
        {
            "model_type": "random_forest",
            "scenario_name": "multimodal_complet",
            "config_name": "balanced",
            "metrics": {
                "accuracy": 0.70,
                "f1_macro": 0.60,
                "f1_weighted": 0.68,
                "f1_class_0": 0.72,
                "f1_class_1": 0.59,
                "f1_class_2": 0.49,
                "roc_auc_ovr_macro": 0.82,
            },
        },
        {
            "model_type": "logistic_regression",
            "scenario_name": "texte_seul",
            "config_name": "balanced",
            "metrics": {
                "accuracy": 0.68,
                "f1_macro": 0.75,
                "f1_weighted": 0.70,
                "f1_class_0": 0.80,
                "f1_class_1": 0.70,
                "f1_class_2": 0.75,
                "roc_auc_ovr_macro": 0.88,
            },
        },
    ]

    output_path = tmp_path / "benchmark.csv"
    benchmark = create_benchmark(results, output_path)

    assert isinstance(benchmark, pd.DataFrame)
    assert list(benchmark.columns[:3]) == ["rang", "model_type", "scenario"]
    assert benchmark.iloc[0]["model_type"] == "logistic_regression"
    assert benchmark.iloc[0]["rang"] == 1
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_save_benchmark_chart_creates_png(tmp_path: Path) -> None:
    benchmark = pd.DataFrame(
        [
            {
                "rang": 1,
                "model_type": "random_forest",
                "scenario": "multimodal_complet",
                "config": "balanced",
                "accuracy": 0.70,
                "f1_macro": 0.65,
                "f1_weighted": 0.68,
                "f1_classe_0": 0.72,
                "f1_classe_1": 0.70,
                "f1_classe_2": 0.60,
                "roc_auc_ovr_macro": 0.85,
            }
        ]
    )

    output_path = tmp_path / "benchmark.png"
    save_benchmark_chart(benchmark, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_save_failures_writes_csv(tmp_path: Path) -> None:
    failures = [
        {
            "model_type": "xgboost",
            "scenario_name": "tabulaire_seul",
            "config_name": "balanced",
            "error": "File not found",
        }
    ]

    output_path = tmp_path / "missing.csv"
    save_failures(failures, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    df = pd.read_csv(output_path)
    assert list(df.columns) == ["model_type", "scenario_name", "config_name", "error"]
    assert df.iloc[0]["model_type"] == "xgboost"
