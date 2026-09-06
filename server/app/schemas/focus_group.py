from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PersonaIdentity(BaseModel):
    id: str
    name: str
    archetype_id: Optional[int] = None
    age: int
    gender: str
    occupation: str
    location: str
    income_band: str
    digital_access_score: float
    bio: str
    avatar_color: str
    population_weight: float = 0.25


class FocusGroupCreateRequest(BaseModel):
    topic: str
    population_run_id: str
    n_personas: Optional[int] = Field(default=4, ge=2, le=6)


class FocusGroupMessageRequest(BaseModel):
    message: str
    target_persona_id: Optional[str] = None


class FocusGroupMessageItem(BaseModel):
    id: str
    sender_type: str
    sender_id: str
    sender_name: str
    message: str
    sentiment: Optional[str] = None
    created_at: str


class FocusGroupSynthesisResponse(BaseModel):
    key_takeaways: List[str]
    consensus_points: List[str]
    divergence_points: List[str]
    strategic_recommendations: List[str]


class FocusGroupSessionResponse(BaseModel):
    id: str
    topic: str
    population_run_id: str
    status: str
    personas: List[PersonaIdentity]
    messages: List[FocusGroupMessageItem]
    synthesis: Optional[Dict[str, Any]] = None
