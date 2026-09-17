"""Pydantic schemas for the Pyrenex Risk API — fourni.

Aligned with feature_columns from pyrenex_risk_v2.json (M1-B1 correctif).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmploymentApplication(BaseModel):
    """Input schema for the CISIA employment-return model."""

    age: float = Field(..., ge=16, le=100)
    niveau_diplome: Literal["Sans diplôme", "Bac", "Bac+2", "Bac+5"]
    anciennete_poste_ans: float = Field(..., ge=0)
    code_rome_vise: str
    code_insee_commune: str
    synthese_entretien: str


class Prediction(BaseModel):
    """Multiclass response for the CISIA employment-return model."""

    prediction: int = Field(..., ge=0, le=2)
    prediction_label: str
    probabilities: dict[str, float]
    model_version: str
    request_id: str


class HealthResponse(BaseModel):
    """Output schema for /health."""

    status: str


class InfoResponse(BaseModel):
    """Output schema for /info."""

    api_version: str
    model_name: str
    model_version: str
    model_created_at: str
    metrics_holdout: dict | None = None
    sklearn_version: str | None = None
    dataset_sha256: str | None = None
