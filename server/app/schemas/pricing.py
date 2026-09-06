from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class PricingRunRequest(BaseModel):
    product_concept: str
    category: str = "Consumer Goods"
    population_run_id: str
    currency: str = "INR"
    price_range_hint: Optional[Dict[str, float]] = None
    n_archetypes_override: Optional[int] = Field(default=4, ge=1, le=10)


class PriceThresholdResponse(BaseModel):
    archetype_id: int
    demographic_summary: str
    population_weight: float
    too_cheap: float
    cheap: float
    expensive: float
    too_expensive: float
    rationale: str


class PricingCurvePoint(BaseModel):
    price: float
    too_cheap_pct: float
    cheap_pct: float
    expensive_pct: float
    too_expensive_pct: float
    acceptable_pct: float
    expected_revenue_index: float


class PricePointSummary(BaseModel):
    optimal_price_point: float
    indifference_price_point: float
    point_of_marginal_cheapness: float
    point_of_marginal_expensiveness: float
    acceptable_price_range_min: float
    acceptable_price_range_max: float
    revenue_maximizing_price: float


class PricingRunResponse(BaseModel):
    run_id: str
    status: str
    product_concept: str
    category: str
    currency: str
    summary: Optional[PricePointSummary] = None
    curves: Optional[List[PricingCurvePoint]] = None
    archetype_responses: Optional[List[PriceThresholdResponse]] = None
    strategic_recommendations: Optional[List[str]] = None
