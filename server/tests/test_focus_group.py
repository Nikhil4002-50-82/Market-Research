import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_focus_group_create_session_requires_valid_population():
    res = client.post(
        "/focus-group/sessions",
        json={
            "topic": "Quick grocery delivery in Tier-2 India",
            "population_run_id": "non-existent-run-id",
            "n_personas": 4,
        },
    )
    assert res.status_code == 400
    assert "No archetypes found" in res.json()["detail"]


from unittest.mock import patch


def test_focus_group_lifecycle():
    pop_res = client.post(
        "/population/generate",
        json={"n": 100, "n_archetypes": 4, "seed": 99},
    )
    assert pop_res.status_code == 200
    run_id = pop_res.json()["run_id"]

    create_res = client.post(
        "/focus-group/sessions",
        json={
            "topic": "Electric Two-Wheeler Subscription for Gig Workers",
            "population_run_id": run_id,
            "n_personas": 4,
        },
    )
    assert create_res.status_code == 200
    session_data = create_res.json()
    session_id = session_data["id"]
    assert session_id is not None
    assert len(session_data["personas"]) == 4
    assert len(session_data["messages"]) >= 1
    assert session_data["messages"][0]["sender_type"] == "system"

    first_persona = session_data["personas"][0]
    assert "name" in first_persona
    assert "bio" in first_persona
    assert "avatar_color" in first_persona
    assert first_persona["avatar_color"].startswith("#")

    get_res = client.get(f"/focus-group/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id

    mock_reply = {"reply": "Battery swapping works well if stations are open 24/7.", "sentiment": "positive"}
    mock_synth = {
        "key_takeaways": ["Takeaway 1", "Takeaway 2"],
        "consensus_points": ["Consensus on 24/7 availability"],
        "divergence_points": ["Deposit sensitivity varies by tier"],
        "strategic_recommendations": ["Offer flexible daily rental plans"],
    }

    with patch("app.api.routers.focus_group.generate_persona_focus_reply", return_value=mock_reply):
        with patch("app.api.routers.focus_group.synthesize_focus_group_session", return_value=mock_synth):
            msg_res = client.post(
                f"/focus-group/sessions/{session_id}/message",
                json={
                    "message": "What is the biggest hesitation you have with battery swapping stations?",
                    "target_persona_id": None,
                },
            )
            assert msg_res.status_code == 200
            new_msgs = msg_res.json()
            assert len(new_msgs) == 5
            assert new_msgs[0]["sender_type"] == "moderator"
            assert new_msgs[1]["sender_type"] == "persona"

            single_target_id = first_persona["id"]
            target_res = client.post(
                f"/focus-group/sessions/{session_id}/message",
                json={
                    "message": "Would you pay a deposit of 2000 rupees?",
                    "target_persona_id": single_target_id,
                },
            )
            assert target_res.status_code == 200
            target_msgs = target_res.json()
            assert len(target_msgs) == 2
            assert target_msgs[0]["sender_type"] == "moderator"
            assert target_msgs[1]["sender_id"] == single_target_id

            synth_res = client.post(f"/focus-group/sessions/{session_id}/synthesize")
            assert synth_res.status_code == 200
            synth_data = synth_res.json()
            assert len(synth_data["key_takeaways"]) > 0
            assert len(synth_data["consensus_points"]) > 0
            assert len(synth_data["divergence_points"]) > 0
            assert len(synth_data["strategic_recommendations"]) > 0
