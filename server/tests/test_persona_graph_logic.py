from app.llm.persona_graph import summarize_peer_reactions


def test_summarize_peer_reactions_empty_input_returns_empty_string():
    assert summarize_peer_reactions([]) == ""


def test_summarize_peer_reactions_reflects_dominant_sentiment():
    reactions = [
        {"population_weight": 0.8, "initial_reaction": {"purchase_intent": 8, "sentiment": "positive"}},
        {"population_weight": 0.2, "initial_reaction": {"purchase_intent": 2, "sentiment": "negative"}},
    ]
    summary_text = summarize_peer_reactions(reactions)
    assert "positive" in summary_text
    assert "6." in summary_text or "7." in summary_text


def test_summarize_peer_reactions_handles_uneven_weights_correctly():
    reactions = [
        {"population_weight": 0.5, "initial_reaction": {"purchase_intent": 4, "sentiment": "neutral"}},
        {"population_weight": 0.5, "initial_reaction": {"purchase_intent": 6, "sentiment": "positive"}},
    ]
    summary_text = summarize_peer_reactions(reactions)
    assert "5.0" in summary_text
