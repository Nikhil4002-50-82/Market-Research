from pydantic import BaseModel


class SimulationRequest(BaseModel):
    stimulus_description: str
    population_run_id: str
    use_social_influence: bool = False
    n_archetypes_override: int | None = None


class SimulationStatus(BaseModel):
    run_id: str
    status: str


class SimulationResult(BaseModel):
    run_id: str
    status: str
    results: dict | None
