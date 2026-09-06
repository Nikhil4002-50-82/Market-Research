import os
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_database_session
from app.simulation.population_generator import (
    build_conditional_distributions,
    join_seed_data,
    sample_synthetic_population,
    persist_population,
)
from app.simulation.clustering import build_archetypes
from app.data.models import Archetype, SyntheticProfile
from app.schemas.population import PopulationRequest, PopulationResponse, ArchetypeItem

router = APIRouter(prefix="/population", tags=["population"])


@router.post("/generate", response_model=PopulationResponse)
def generate_population(
    request: PopulationRequest,
    database_session: Session = Depends(get_database_session),
):
    run_id = str(uuid.uuid4())

    base_dataframe = build_conditional_distributions(database_session)
    if len(base_dataframe) == 0:
        seed_households_path = "seed_output/seed_households.csv"
        seed_individuals_path = "seed_output/seed_individuals.csv"
        if os.path.exists(seed_households_path) and os.path.exists(seed_individuals_path):
            households_df = pd.read_csv(seed_households_path)
            individuals_df = pd.read_csv(seed_individuals_path)
            base_dataframe = join_seed_data(households_df, individuals_df)
        else:
            raise HTTPException(
                status_code=400,
                detail="No demographic data found in database and no seed CSV files exist. Please ingest data or run seed generator first."
            )

    synthetic_dataframe = sample_synthetic_population(
        base_dataframe=base_dataframe,
        sample_size=request.n,
        random_seed=request.seed,
    )
    persist_population(database_session, run_id, synthetic_dataframe)

    clustered_dataframe, representative_archetypes = build_archetypes(
        population_dataframe=synthetic_dataframe,
        number_of_clusters=request.n_archetypes,
        random_seed=request.seed,
    )

    for _, row in representative_archetypes.iterrows():
        attributes_dict = row.drop(["archetype_id", "population_weight"]).to_dict()
        archetype_record = Archetype(
            run_id=run_id,
            centroid_attributes=attributes_dict,
            population_weight=float(row["population_weight"]),
        )
        database_session.add(archetype_record)

    database_session.commit()

    return PopulationResponse(
        run_id=run_id,
        n_generated=len(synthetic_dataframe),
        n_archetypes=len(representative_archetypes),
    )


@router.get("/{run_id}/archetypes", response_model=list[ArchetypeItem])
def get_archetypes(
    run_id: str,
    database_session: Session = Depends(get_database_session),
):
    archetypes = database_session.query(Archetype).filter_by(run_id=run_id).all()
    if not archetypes:
        raise HTTPException(status_code=404, detail="Population run not found or has no archetypes")

    return [
        ArchetypeItem(
            id=item.id,
            attributes=item.centroid_attributes,
            population_weight=item.population_weight,
        )
        for item in archetypes
    ]
