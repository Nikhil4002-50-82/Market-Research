import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.simulation.reweighting import aggregate_multimodal_results

client = TestClient(app)


def test_aggregate_multimodal_results_calculates_weighted_scores():
    sample_results = [
        {
            "population_weight": 0.6,
            "purchase_intent": 8,
            "visual_comprehension_score": 9.0,
            "visual_trust_score": 8.0,
            "first_visual_hook": "24K Gold Badge",
            "ui_friction_points": ["Text too small on mobile"],
            "sentiment": "positive",
        },
        {
            "population_weight": 0.4,
            "purchase_intent": 3,
            "visual_comprehension_score": 4.0,
            "visual_trust_score": 3.0,
            "first_visual_hook": "₹10 Banner",
            "ui_friction_points": ["Text too small on mobile", "Unclear refund terms"],
            "sentiment": "negative",
        },
    ]

    aggregated = aggregate_multimodal_results(sample_results)

    assert aggregated["population_purchase_intent"] == pytest.approx(6.0, 0.01)
    assert aggregated["visual_comprehension_score"] == pytest.approx(7.0, 0.01)
    assert aggregated["visual_trust_score"] == pytest.approx(6.0, 0.01)
    assert "Text too small on mobile" in aggregated["ui_friction_points"]
    assert "Unclear refund terms" in aggregated["ui_friction_points"]
    assert len(aggregated["first_visual_hooks"]) == 2


def test_multimodal_simulation_rejects_unsupported_file_type():
    invalid_file = io.BytesIO(b"fake text content")
    response = client.post(
        "/simulations/multimodal/run",
        data={
            "stimulus_description": "Digital gold savings app banner",
            "category": "Fintech",
            "population_run_id": "non-existent-id",
        },
        files={
            "creative_image": ("sample.txt", invalid_file, "text/plain"),
        },
    )
    assert response.status_code == 400
    assert "Unsupported image type" in response.json()["detail"]


def test_multimodal_simulation_rejects_empty_file():
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/simulations/multimodal/run",
        data={
            "stimulus_description": "Digital gold savings app banner",
            "category": "Fintech",
            "population_run_id": "non-existent-id",
        },
        files={
            "creative_image": ("sample.png", empty_file, "image/png"),
        },
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_multimodal_simulation_rejects_missing_population_run():
    valid_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    image_file = io.BytesIO(valid_png_bytes)
    response = client.post(
        "/simulations/multimodal/run",
        data={
            "stimulus_description": "Digital gold savings app banner",
            "category": "Fintech",
            "population_run_id": "00000000-0000-0000-0000-000000000000",
        },
        files={
            "creative_image": ("banner.png", image_file, "image/png"),
        },
    )
    assert response.status_code == 400
    assert "No archetypes found" in response.json()["detail"]


from unittest.mock import patch
from app.schemas.simulation import MultimodalPersonaResponse


def test_multimodal_simulation_schedules_successfully():
    pop_res = client.post(
        "/population/generate",
        json={"n": 100, "n_archetypes": 2, "seed": 42},
    )
    assert pop_res.status_code == 200
    run_id = pop_res.json()["run_id"]

    valid_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    image_file = io.BytesIO(valid_png_bytes)

    mock_response = MultimodalPersonaResponse(
        purchase_intent=7,
        visual_comprehension_score=8,
        visual_trust_score=8,
        first_visual_hook="Gold Coin Logo",
        ui_friction_points=["Small fine print"],
        quote="Looks trustworthy and attractive.",
        objection="None",
        sentiment="positive",
    )

    with patch("app.api.routers.simulations.run_multimodal_persona_simulation", return_value=mock_response):
        sim_res = client.post(
            "/simulations/multimodal/run",
            data={
                "stimulus_description": "Digital gold savings app visual banner",
                "category": "Fintech",
                "population_run_id": run_id,
                "use_social_influence": False,
                "n_archetypes_override": 2,
            },
            files={
                "creative_image": ("banner.png", image_file, "image/png"),
            },
        )
        assert sim_res.status_code == 200
        sim_id = sim_res.json()["run_id"]
        assert sim_id is not None

        status_res = client.get(f"/simulations/{sim_id}/status")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "completed"

        results_res = client.get(f"/simulations/{sim_id}/results")
        assert results_res.status_code == 200
        results_data = results_res.json()["results"]
        assert results_data["population_purchase_intent"] == pytest.approx(7.0, 0.1)
        assert results_data["visual_comprehension_score"] == pytest.approx(8.0, 0.1)
        assert results_data["visual_trust_score"] == pytest.approx(8.0, 0.1)
