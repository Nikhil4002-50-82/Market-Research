import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_database_session
from app.data.models import PricingOptimizationRun, Archetype
from app.schemas.pricing import (
    PricingRunRequest,
    PricingRunResponse,
    PricePointSummary,
    PricingCurvePoint,
    PriceThresholdResponse,
)
from app.simulation.pricing_psm import (
    elicit_archetype_pricing,
    compute_van_westendorp_psm,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/van-westendorp/run", response_model=PricingRunResponse)
def run_pricing_simulation(
    request: PricingRunRequest,
    database_session: Session = Depends(get_database_session),
):
    archetypes = database_session.query(Archetype).filter_by(run_id=request.population_run_id).all()
    if not archetypes:
        raise HTTPException(
            status_code=400,
            detail=f"No archetypes found for population_run_id '{request.population_run_id}'. Please generate a population first.",
        )

    target_count = request.n_archetypes_override or 4
    selected = archetypes[:target_count]
    total_w = sum(a.population_weight for a in selected)
    normalized_archetypes = [
        {
            "id": a.id,
            "centroid_attributes": a.centroid_attributes,
            "population_weight": (a.population_weight / total_w) if total_w > 0 else (1.0 / len(selected)),
        }
        for a in selected
    ]

    archetype_responses = []
    for arch in normalized_archetypes:
        pricing_data = elicit_archetype_pricing(
            archetype=arch,
            product_concept=request.product_concept,
            category=request.category,
            currency=request.currency,
        )
        attrs = arch["centroid_attributes"]
        summary_str = f"{attrs.get('age', 30)}y {attrs.get('gender', 'person')}, {attrs.get('occupation', 'worker')} in {attrs.get('urban_rural', 'Urban')}, Income: {attrs.get('income_band', 'Middle')}"
        archetype_responses.append({
            "archetype_id": arch["id"],
            "demographic_summary": summary_str,
            "population_weight": arch["population_weight"],
            "too_cheap": pricing_data["too_cheap"],
            "cheap": pricing_data["cheap"],
            "expensive": pricing_data["expensive"],
            "too_expensive": pricing_data["too_expensive"],
            "rationale": pricing_data["rationale"],
        })

    psm_analysis = compute_van_westendorp_psm(archetype_responses)

    run_id = str(uuid.uuid4())
    run_record = PricingOptimizationRun(
        id=run_id,
        product_concept=request.product_concept,
        category=request.category,
        population_run_id=request.population_run_id,
        currency=request.currency,
        status="completed",
        results={
            "summary": psm_analysis["summary"],
            "curves": psm_analysis["curves"],
            "archetype_responses": archetype_responses,
            "strategic_recommendations": psm_analysis["strategic_recommendations"],
        },
    )
    database_session.add(run_record)
    database_session.commit()

    return PricingRunResponse(
        run_id=run_id,
        status="completed",
        product_concept=request.product_concept,
        category=request.category,
        currency=request.currency,
        summary=PricePointSummary(**psm_analysis["summary"]),
        curves=[PricingCurvePoint(**pt) for pt in psm_analysis["curves"]],
        archetype_responses=[PriceThresholdResponse(**ar) for ar in archetype_responses],
        strategic_recommendations=psm_analysis["strategic_recommendations"],
    )


@router.get("/simulations/{run_id}", response_model=PricingRunResponse)
def get_pricing_simulation(
    run_id: str,
    database_session: Session = Depends(get_database_session),
):
    run_record = database_session.query(PricingOptimizationRun).filter_by(id=run_id).first()
    if not run_record:
        raise HTTPException(status_code=404, detail="Pricing simulation run not found.")

    res = run_record.results or {}
    summary_obj = PricePointSummary(**res["summary"]) if "summary" in res else None
    curves_obj = [PricingCurvePoint(**pt) for pt in res.get("curves", [])] if "curves" in res else None
    archetypes_obj = [PriceThresholdResponse(**ar) for ar in res.get("archetype_responses", [])] if "archetype_responses" in res else None

    return PricingRunResponse(
        run_id=run_record.id,
        status=run_record.status,
        product_concept=run_record.product_concept,
        category=run_record.category,
        currency=run_record.currency,
        summary=summary_obj,
        curves=curves_obj,
        archetype_responses=archetypes_obj,
        strategic_recommendations=res.get("strategic_recommendations"),
    )
