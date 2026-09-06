import pytest
from app.validation.calibration import weight_expand_scores, calibration_score


def test_weight_expand_scores_respects_relative_weights():
    archetype_results = [
        {"population_weight": 0.9, "purchase_intent": 8},
        {"population_weight": 0.1, "purchase_intent": 2},
    ]
    expanded_scores = weight_expand_scores(archetype_results, resolution=100)
    count_high_intent = expanded_scores.count(8)
    count_low_intent = expanded_scores.count(2)

    assert count_high_intent > count_low_intent
    assert count_high_intent / count_low_intent == pytest.approx(9, rel=0.2)


def test_weight_expand_scores_gives_small_archetypes_at_least_one_sample():
    archetype_results = [{"population_weight": 0.001, "purchase_intent": 5}]
    expanded_scores = weight_expand_scores(archetype_results, resolution=100)
    assert len(expanded_scores) >= 1


def test_calibration_score_zero_distance_for_identical_distributions():
    sample_scores = [5, 5, 5, 6, 6, 7]
    result = calibration_score(sample_scores, sample_scores)
    assert result["wasserstein_distance"] == pytest.approx(0, abs=1e-6)
    assert result["mean_gap"] == pytest.approx(0, abs=1e-6)


def test_calibration_score_detects_large_gap():
    simulated_scores = [9, 9, 9, 9]
    real_scores = [1, 1, 1, 1]
    result = calibration_score(simulated_scores, real_scores)
    assert result["mean_gap"] == pytest.approx(8, abs=1e-6)
    assert result["wasserstein_distance"] > 0


def test_calibration_score_raises_on_empty_input():
    with pytest.raises(ValueError):
        calibration_score([], [1, 2, 3])


def test_weighted_vs_unweighted_calibration_can_differ():
    archetype_results = [
        {"population_weight": 0.95, "purchase_intent": 2},
        {"population_weight": 0.05, "purchase_intent": 9},
    ]
    real_scores = [2, 2, 2, 2, 2]

    unweighted_scores = [item["purchase_intent"] for item in archetype_results]
    weighted_scores = weight_expand_scores(archetype_results, resolution=100)

    unweighted_result = calibration_score(unweighted_scores, real_scores)
    weighted_result = calibration_score(weighted_scores, real_scores)

    assert weighted_result["mean_gap"] < unweighted_result["mean_gap"]
