import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_database_session, SessionLocal
from app.data.models import SimulationRun, Archetype
from app.schemas.simulation import SimulationRequest, SimulationStatus, SimulationResult
from app.llm.persona_chain import run_persona_simulation
from app.llm.persona_graph import (
    node_initial_reaction,
    node_social_influence,
    summarize_peer_reactions,
    PersonaState,
)
from app.simulation.reweighting import aggregate_results

router = APIRouter(prefix="/simulations", tags=["simulations"])


def execute_simulation_task(
    run_id: str,
    stimulus_description: str,
    population_run_id: str,
    use_social_influence: bool,
    archetypes_override_count: int | None,
):
    database_session = SessionLocal()
    try:
        run_record = database_session.query(SimulationRun).filter_by(id=run_id).first()
        if not run_record:
            return

        run_record.status = "running"
        database_session.commit()

        archetypes = database_session.query(Archetype).filter_by(run_id=population_run_id).all()
        if not archetypes:
            run_record.status = "failed: No archetypes found for this population run"
            database_session.commit()
            return

        if archetypes_override_count and archetypes_override_count < len(archetypes):
            archetypes = archetypes[:archetypes_override_count]
            normalized_total = sum(item.population_weight for item in archetypes)
            archetype_list = [
                {
                    "attributes": item.centroid_attributes,
                    "population_weight": item.population_weight / normalized_total,
                }
                for item in archetypes
            ]
        else:
            archetype_list = [
                {
                    "attributes": item.centroid_attributes,
                    "population_weight": item.population_weight,
                }
                for item in archetypes
            ]

        results_list = []

        if use_social_influence:
            stage_one_states = []
            for item in archetype_list:
                state: PersonaState = {
                    "archetype": {**item["attributes"], "population_weight": item["population_weight"]},
                    "stimulus": stimulus_description,
                    "peer_summary": None,
                    "initial_reaction": None,
                    "final_decision": None,
                    "intent_shift": None,
                }
                evaluated_state = node_initial_reaction(state)
                stage_one_states.append(evaluated_state)

            reactions_for_summary = [
                {
                    "population_weight": item["archetype"]["population_weight"],
                    "initial_reaction": item["initial_reaction"],
                }
                for item in stage_one_states
            ]
            peer_summary_text = summarize_peer_reactions(reactions_for_summary)

            for state in stage_one_states:
                state["peer_summary"] = peer_summary_text
                final_state = node_social_influence(state)
                results_list.append({
                    "population_weight": final_state["archetype"]["population_weight"],
                    "purchase_intent": final_state["final_decision"]["purchase_intent"],
                    "sentiment": final_state["final_decision"]["sentiment"],
                    "objection": final_state["final_decision"]["objection"],
                    "quote": final_state["final_decision"]["quote"],
                    "intent_shift": final_state["intent_shift"],
                })

        else:
            for item in archetype_list:
                archetype_payload = {
                    **item["attributes"],
                    "population_weight": item["population_weight"],
                }
                response = run_persona_simulation(archetype_payload, stimulus_description)
                results_list.append({
                    "population_weight": item["population_weight"],
                    "purchase_intent": response.purchase_intent,
                    "sentiment": response.sentiment,
                    "objection": response.objection,
                    "quote": response.quote,
                })

        aggregated = aggregate_results(results_list)
        run_record.results = {
            **aggregated,
            "archetype_details": results_list,
        }
        run_record.status = "completed"
        database_session.commit()

    except Exception as error:
        database_session.rollback()
        run_record = database_session.query(SimulationRun).filter_by(id=run_id).first()
        if run_record:
            run_record.status = f"failed: {str(error)}"
            database_session.commit()
    finally:
        database_session.close()


@router.post("/run", response_model=SimulationStatus)
def start_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks,
    database_session: Session = Depends(get_database_session),
):
    existing_archetypes_count = database_session.query(Archetype).filter_by(run_id=request.population_run_id).count()
    if existing_archetypes_count == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No archetypes found for population_run_id '{request.population_run_id}'. Please generate a population via POST /population/generate first and use that run_id."
        )

    run_id = str(uuid.uuid4())
    simulation_record = SimulationRun(
        id=run_id,
        stimulus={
            "description": request.stimulus_description,
            "population_run_id": request.population_run_id,
        },
        status="pending",
    )
    database_session.add(simulation_record)
    database_session.commit()

    background_tasks.add_task(
        execute_simulation_task,
        run_id=run_id,
        stimulus_description=request.stimulus_description,
        population_run_id=request.population_run_id,
        use_social_influence=request.use_social_influence,
        archetypes_override_count=request.n_archetypes_override,
    )

    return SimulationStatus(run_id=run_id, status="pending")


@router.get("/{run_id}/status", response_model=SimulationStatus)
def get_simulation_status(
    run_id: str,
    database_session: Session = Depends(get_database_session),
):
    record = database_session.query(SimulationRun).filter_by(id=run_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return SimulationStatus(run_id=run_id, status=record.status)


@router.get("/{run_id}/results", response_model=SimulationResult)
def get_simulation_results(
    run_id: str,
    database_session: Session = Depends(get_database_session),
):
    record = database_session.query(SimulationRun).filter_by(id=run_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return SimulationResult(run_id=run_id, status=record.status, results=record.results)
