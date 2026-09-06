import numpy as np
from scipy.stats import wasserstein_distance


def weight_expand_scores(
    archetype_results: list[dict],
    score_key: str = "purchase_intent",
    resolution: int = 1000
) -> list[float]:
    expanded_scores = []
    for item in archetype_results:
        repeat_count = max(1, round(item["population_weight"] * resolution))
        expanded_scores.extend([item[score_key]] * repeat_count)
    return expanded_scores


def calibration_score(simulated_scores: list[float], real_scores: list[float]) -> dict:
    if len(simulated_scores) == 0 or len(real_scores) == 0:
        raise ValueError("Both simulated_scores and real_scores must be non-empty")

    distance = wasserstein_distance(simulated_scores, real_scores)
    simulated_mean = np.mean(simulated_scores)
    real_mean = np.mean(real_scores)
    simulated_std = np.std(simulated_scores)
    real_std = np.std(real_scores)

    return {
        "wasserstein_distance": float(distance),
        "simulated_mean": float(simulated_mean),
        "real_mean": float(real_mean),
        "mean_gap": float(abs(simulated_mean - real_mean)),
        "simulated_std": float(simulated_std),
        "real_std": float(real_std),
    }
