import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_database_session
from app.data.models import SimulationRun, ValidationResult
from app.validation.calibration import calibration_score, weight_expand_scores
from app.schemas.validation import ValidationResponse

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/compare", response_model=ValidationResponse)
def compare_simulation_to_real_survey(
    simulation_run_id: str,
    real_survey_score_column: str = "purchase_intent",
    file: UploadFile = File(...),
    database_session: Session = Depends(get_database_session),
):
    simulation_record = database_session.query(SimulationRun).filter_by(id=simulation_run_id).first()
    if not simulation_record or simulation_record.status != "completed":
        raise HTTPException(status_code=400, detail="Simulation run not found or not completed")

    real_survey_dataframe = pd.read_csv(file.file)
    if real_survey_score_column not in real_survey_dataframe.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Column '{real_survey_score_column}' not found in uploaded file. Available: {list(real_survey_dataframe.columns)}"
        )

    archetype_details = simulation_record.results.get("archetype_details", [])
    if not archetype_details:
        raise HTTPException(status_code=400, detail="No archetype details found in simulation results")

    simulated_scores = weight_expand_scores(
        archetype_results=archetype_details,
        score_key="purchase_intent",
        resolution=1000,
    )
    real_scores = real_survey_dataframe[real_survey_score_column].dropna().astype(float).tolist()

    score_result = calibration_score(simulated_scores, real_scores)

    validation_record = ValidationResult(
        run_id=simulation_run_id,
        calibration_score=score_result["wasserstein_distance"],
        details=score_result,
    )
    database_session.add(validation_record)
    database_session.commit()

    return ValidationResponse(**score_result)


@router.get("/{run_id}/history")
def get_validation_history(
    run_id: str,
    database_session: Session = Depends(get_database_session),
):
    records = database_session.query(ValidationResult).filter_by(run_id=run_id).all()
    return [
        {"calibration_score": item.calibration_score, "details": item.details}
        for item in records
    ]
