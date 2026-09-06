import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.simulation.pricing_psm import compute_van_westendorp_psm

client = TestClient(app)


def test_pricing_simulation_requires_valid_population():
    res = client.post(
        "/pricing/van-westendorp/run",
        json={
            "product_concept": "Cloud Accounting ERP for Indian Kiranas",
            "category": "B2B SaaS",
            "population_run_id": "non-existent-run-id",
            "currency": "INR",
        },
    )
    assert res.status_code == 400
    assert "No archetypes found" in res.json()["detail"]


def test_compute_van_westendorp_psm_curves_and_intersections():
    sample_responses = [
        {
            "archetype_id": 1,
            "population_weight": 0.4,
            "too_cheap": 150.0,
            "cheap": 300.0,
            "expensive": 600.0,
            "too_expensive": 1000.0,
            "rationale": "Tier-2 middle income household perception.",
        },
        {
            "archetype_id": 2,
            "population_weight": 0.6,
            "too_cheap": 250.0,
            "cheap": 500.0,
            "expensive": 900.0,
            "too_expensive": 1500.0,
            "rationale": "Urban professional tech worker perception.",
        },
    ]

    analysis = compute_van_westendorp_psm(sample_responses, n_grid_points=30)
    summary = analysis["summary"]

    assert summary["optimal_price_point"] > 0
    assert summary["indifference_price_point"] > 0
    assert summary["point_of_marginal_cheapness"] <= summary["point_of_marginal_expensiveness"]
    assert summary["revenue_maximizing_price"] > 0

    curves = analysis["curves"]
    assert len(curves) == 30
    first_pt = curves[0]
    last_pt = curves[-1]

    assert first_pt["too_cheap_pct"] >= last_pt["too_cheap_pct"]
    assert first_pt["too_expensive_pct"] <= last_pt["too_expensive_pct"]
    assert len(analysis["strategic_recommendations"]) == 4


def test_pricing_simulation_endpoint_and_retrieval():
    pop_res = client.post(
        "/population/generate",
        json={"n": 100, "n_archetypes": 3, "seed": 77},
    )
    assert pop_res.status_code == 200
    run_id = pop_res.json()["run_id"]

    mock_pricing_return = {
        "too_cheap": 199.0,
        "cheap": 499.0,
        "expensive": 899.0,
        "too_expensive": 1499.0,
        "rationale": "Balanced pricing for Indian small retailers.",
    }

    with patch("app.api.routers.pricing.elicit_archetype_pricing", return_value=mock_pricing_return):
        run_res = client.post(
            "/pricing/van-westendorp/run",
            json={
                "product_concept": "Cloud Accounting & Invoicing for Kiranas",
                "category": "B2B SaaS",
                "population_run_id": run_id,
                "currency": "INR",
                "n_archetypes_override": 3,
            },
        )
        assert run_res.status_code == 200
        run_data = run_res.json()
        pricing_run_id = run_data["run_id"]
        assert pricing_run_id is not None
        assert run_data["status"] == "completed"
        assert run_data["summary"]["optimal_price_point"] > 0
        assert len(run_data["curves"]) > 0
        assert len(run_data["archetype_responses"]) == 3
        assert len(run_data["strategic_recommendations"]) >= 3

        get_res = client.get(f"/pricing/simulations/{pricing_run_id}")
        assert get_res.status_code == 200
        retrieved_data = get_res.json()
        assert retrieved_data["run_id"] == pricing_run_id
        assert retrieved_data["summary"]["optimal_price_point"] == run_data["summary"]["optimal_price_point"]
