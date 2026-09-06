from pydantic import BaseModel


class ValidationResponse(BaseModel):
    wasserstein_distance: float
    simulated_mean: float
    real_mean: float
    mean_gap: float
    simulated_std: float
    real_std: float
