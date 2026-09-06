import pytest
from app.simulation.reweighting import aggregate_results


def test_aggregate_results_weighted_intent_is_between_min_and_max():
    results = [
        {"population_weight": 0.7, "purchase_intent": 2, "sentiment": "negative"},
        {"population_weight": 0.3, "purchase_intent": 9, "sentiment": "positive"},
    ]
    aggregated = aggregate_results(results)
    assert 2 <= aggregated["population_purchase_intent"] <= 9
    assert aggregated["population_purchase_intent"] < 5


def test_aggregate_results_sentiment_distribution_sums_to_one():
    results = [
        {"population_weight": 0.5, "purchase_intent": 5, "sentiment": "positive"},
        {"population_weight": 0.3, "purchase_intent": 3, "sentiment": "neutral"},
        {"population_weight": 0.2, "purchase_intent": 1, "sentiment": "negative"},
    ]
    aggregated = aggregate_results(results)
    assert abs(sum(aggregated["sentiment_distribution"].values()) - 1.0) < 1e-9


def test_aggregate_results_raises_on_empty_input():
    with pytest.raises(ValueError):
        aggregate_results([])


def test_aggregate_results_raises_on_zero_total_weight():
    results = [{"population_weight": 0, "purchase_intent": 5, "sentiment": "positive"}]
    with pytest.raises(ValueError):
        aggregate_results(results)
