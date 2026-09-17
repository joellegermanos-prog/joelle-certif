"""Service `model` — API de scoring Pyrenex (fourni — votre exemple de référence).

Reprise de l'API M1-B2 (routes `/health`, `/info`, `/predict`) + ajout de
l'endpoint `/metrics` Prometheus (latence/RPS/erreurs via instrumentator +
métriques métier custom). Service **interne** : il est appelé par le
`backend`, jamais directement par le navigateur — donc pas de CORS ici.
"""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, status
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator

from app.metrics import MODEL_INFO, observe_prediction
from app.middleware import LoggingMiddleware
from app.schemas import HealthResponse, InfoResponse, EmploymentApplication, Prediction
from preprocess import create_features

# --- Loguru -----------------------------------------------------------------

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True)
logger.add(
    LOGS_DIR / "api.log",
    rotation="10 MB",
    retention="7 days",
    serialize=True,
    enqueue=True,
    level="INFO",
)

# --- Lifespan ---------------------------------------------------------------

MODELS_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODELS_DIR / "cisia_emploi_xgboost_multimodal_complet_balanced.joblib"
META_PATH = MODELS_DIR / "cisia_emploi_xgboost_multimodal_complet_balanced.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle + métadonnées au démarrage, libère à l'arrêt."""
    if not MODEL_PATH.exists() or not META_PATH.exists():
        raise RuntimeError(f"Model artifacts missing in {MODELS_DIR}")
    app.state.model = joblib.load(MODEL_PATH)
    app.state.metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    MODEL_INFO.labels(
        model_name=app.state.metadata["model_name"],
        model_version=app.state.metadata["model_version"],
        scenario=app.state.metadata["scenario_name"],
    ).set(1)
    logger.info(
        "Model loaded: {name} {version}",
        name=app.state.metadata["model_name"],
        version=app.state.metadata["model_version"],
    )
    yield
    app.state.model = None
    logger.info("Model released")


app = FastAPI(
    title="Pyrenex Model Service",
    version="2.0.0",
    description="Service interne de scoring crédit Pyrenex (modèle pyrenex_risk_v2).",
    lifespan=lifespan,
)
app.add_middleware(LoggingMiddleware)

# Expose /metrics (latence, RPS, codes retour). should_group_status_codes=False
# pour distinguer 422 (validation) de 500 (erreur modèle) dans Grafana.
Instrumentator(should_group_status_codes=False).instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness : 503 si le modèle n'est pas chargé."""
    if not hasattr(app.state, "model") or app.state.model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model not loaded"
        )
    return HealthResponse(status="ok")


@app.get("/info", response_model=InfoResponse)
async def info() -> InfoResponse:
    """Métadonnées du modèle chargé."""
    meta = app.state.metadata
    return InfoResponse(
        api_version=app.version,
        model_name=meta["model_name"],
        model_version=meta["model_version"],
        model_created_at=meta.get("created_at_utc", ""),
        metrics_holdout=meta.get("evaluation", {}).get("metrics"),
        sklearn_version=meta.get("versions", {}).get("scikit_learn"),
        dataset_sha256=meta.get("dataset", {}).get("sha256"),
    )


@app.post("/predict", response_model=Prediction, status_code=status.HTTP_200_OK)
async def predict(application: EmploymentApplication, request: Request) -> Prediction:
    """Prédit le délai de retour à l'emploi avec le pipeline CISIA."""
    request_id = getattr(request.state, "request_id", "n/a")
    try:
        X = pd.DataFrame([application.model_dump()])
        X = create_features(X)
        pred = int(app.state.model.predict(X)[0])
        probabilities = app.state.model.predict_proba(X)[0]
    except Exception as exc:  # noqa: BLE001 — garde large en production
        logger.bind(request_id=request_id).exception("Prediction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {exc.__class__.__name__}",
        ) from exc

    class_labels = {
        0: "Retour rapide",
        1: "Retour moyen",
        2: "Risque de chômage longue durée",
    }
    observe_prediction(
        predicted_class=pred,
        proba_default=float(probabilities[pred]),
    )
    return Prediction(
        prediction=pred,
        prediction_label=class_labels[pred],
        probabilities={
            str(index): round(float(value), 4)
            for index, value in enumerate(probabilities)
        },
        model_version=app.state.metadata["model_version"],
        request_id=request_id,
    )
