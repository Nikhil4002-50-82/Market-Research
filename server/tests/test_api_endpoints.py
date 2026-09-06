import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import initialize_database


@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    initialize_database()


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_datasets_sources_endpoint(client):
    response = client.get("/datasets/sources")
    assert response.status_code == 200
    json_data = response.json()
    assert "supported_sources" in json_data
    assert "census" in json_data["supported_sources"]
    assert "nsso" in json_data["supported_sources"]


def test_population_generate_and_get_archetypes(client):
    request_payload = {
        "n": 500,
        "n_archetypes": 10,
        "seed": 42
    }
    response = client.post("/population/generate", json=request_payload)
    assert response.status_code == 200
    response_data = response.json()
    assert "run_id" in response_data
    assert response_data["n_generated"] == 500
    assert response_data["n_archetypes"] == 10

    generated_run_id = response_data["run_id"]
    archetypes_response = client.get(f"/population/{generated_run_id}/archetypes")
    assert archetypes_response.status_code == 200
    archetypes_list = archetypes_response.json()
    assert len(archetypes_list) == 10
    assert "attributes" in archetypes_list[0]
    assert "population_weight" in archetypes_list[0]


def test_simulation_status_not_found(client):
    response = client.get("/simulations/non-existent-id/status")
    assert response.status_code == 404
