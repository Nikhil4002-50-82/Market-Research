from pydantic import BaseModel


class PopulationRequest(BaseModel):
    n: int = 100000
    n_archetypes: int = 150
    seed: int = 42


class PopulationResponse(BaseModel):
    run_id: str
    n_generated: int
    n_archetypes: int


class ArchetypeItem(BaseModel):
    id: int
    attributes: dict
    population_weight: float
