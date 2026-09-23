from scripts.promotion import decide_promotion


def test_promotion_accepts_candidate_with_class_two_gain():
    decision = decide_promotion(
        {
            "f1_macro": 0.74,
            "f1_classe_2": 0.66,
            "recall_classe_2": 0.70,
            "roc_auc_ovr_macro": 0.88,
        },
        {
            "f1_macro": 0.72,
            "f1_classe_2": 0.63,
            "recall_classe_2": 0.65,
            "roc_auc_ovr_macro": 0.87,
        },
    )

    assert decision.promote is True


def test_promotion_rejects_class_two_regression():
    decision = decide_promotion(
        {
            "f1_macro": 0.74,
            "f1_classe_2": 0.60,
            "recall_classe_2": 0.60,
            "roc_auc_ovr_macro": 0.88,
        },
        {
            "f1_macro": 0.72,
            "f1_classe_2": 0.63,
            "recall_classe_2": 0.65,
            "roc_auc_ovr_macro": 0.87,
        },
    )

    assert decision.promote is False
    assert "regression" in decision.reason
