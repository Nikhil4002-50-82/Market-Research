def aggregate_results(archetype_results: list[dict]) -> dict:
    if not archetype_results:
        raise ValueError("archetype_results is empty — nothing to aggregate")

    total_weight = sum(item["population_weight"] for item in archetype_results)
    if total_weight == 0:
        raise ValueError("total population_weight is zero — check archetype weighting")

    weighted_intent = sum(
        item["population_weight"] * item["purchase_intent"] for item in archetype_results
    ) / total_weight

    raw_sentiment_distribution = {}
    for item in archetype_results:
        sentiment_label = item["sentiment"]
        raw_sentiment_distribution[sentiment_label] = (
            raw_sentiment_distribution.get(sentiment_label, 0.0) + item["population_weight"]
        )

    normalized_sentiment_distribution = {
        label: weight / total_weight for label, weight in raw_sentiment_distribution.items()
    }

    return {
        "population_purchase_intent": weighted_intent,
        "sentiment_distribution": normalized_sentiment_distribution,
        "n_archetypes": len(archetype_results),
    }


def aggregate_multimodal_results(archetype_results: list[dict]) -> dict:
    base_aggregation = aggregate_results(archetype_results)
    total_weight = sum(item["population_weight"] for item in archetype_results)

    weighted_comprehension = sum(
        item["population_weight"] * item.get("visual_comprehension_score", 5.0)
        for item in archetype_results
    ) / total_weight

    weighted_trust = sum(
        item["population_weight"] * item.get("visual_trust_score", 5.0)
        for item in archetype_results
    ) / total_weight

    aggregated_friction_points = []
    first_visual_hooks = []
    for item in archetype_results:
        for friction in item.get("ui_friction_points", []):
            if friction and friction not in aggregated_friction_points:
                aggregated_friction_points.append(friction)
        hook = item.get("first_visual_hook")
        if hook and hook not in first_visual_hooks:
            first_visual_hooks.append(hook)

    return {
        **base_aggregation,
        "visual_comprehension_score": round(weighted_comprehension, 2),
        "visual_trust_score": round(weighted_trust, 2),
        "ui_friction_points": aggregated_friction_points,
        "first_visual_hooks": first_visual_hooks,
    }
