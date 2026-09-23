"""Promotion policy for CISIA candidate models."""
from __future__ import annotations

from dataclasses import dataclass

QUALITY_FLOORS: dict[str, float] = {
    "f1_macro": 0.60,
    "f1_classe_2": 0.50,
    "recall_classe_2": 0.50,
    "roc_auc_ovr_macro": 0.70,
}

# The recall of class 2 is the critical business metric. A small measurement
# variation is tolerated, but a meaningful regression blocks promotion.
REGRESSION_TOLERANCES: dict[str, float] = {
    "f1_macro": 0.02,
    "f1_classe_2": 0.03,
    "recall_classe_2": 0.03,
    "roc_auc_ovr_macro": 0.02,
}


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    reason: str


def decide_promotion(
    candidate: dict[str, float],
    production: dict[str, float],
) -> PromotionDecision:
    """Allow promotion only if floors pass and no metric regresses too far."""
    for metric, floor in QUALITY_FLOORS.items():
        value = float(candidate.get(metric, 0.0))
        if value < floor:
            return PromotionDecision(
                False,
                f"quality floor not met: {metric}={value:.4f} < {floor:.4f}",
            )

    regressions = []
    for metric, tolerance in REGRESSION_TOLERANCES.items():
        drop = float(production.get(metric, 0.0)) - float(candidate.get(metric, 0.0))
        if drop > tolerance:
            regressions.append(f"{metric} drop={drop:.4f} > {tolerance:.4f}")
    if regressions:
        return PromotionDecision(False, "critical regression: " + "; ".join(regressions))

    gains = {
        metric: float(candidate.get(metric, 0.0)) - float(production.get(metric, 0.0))
        for metric in ("f1_macro", "recall_classe_2")
    }
    if max(gains.values()) <= 0:
        return PromotionDecision(
            False,
            "candidate does not improve f1_macro or recall_classe_2",
        )

    return PromotionDecision(
        True,
        f"candidate accepted: f1_macro={gains['f1_macro']:+.4f}, "
        f"recall_classe_2={gains['recall_classe_2']:+.4f}",
    )
