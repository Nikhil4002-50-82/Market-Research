from pydantic import BaseModel, Field


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


class MultimodalPersonaResponse(BaseModel):
    purchase_intent: int = Field(ge=0, le=10)
    visual_comprehension_score: int = Field(ge=0, le=10)
    visual_trust_score: int = Field(ge=0, le=10)
    first_visual_hook: str
    ui_friction_points: list[str]
    sentiment: str
    objection: str
    quote: str
