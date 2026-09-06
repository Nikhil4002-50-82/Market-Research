import uuid
import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_database_session
from app.data.models import FocusGroupSession, Archetype
from app.schemas.focus_group import (
    FocusGroupCreateRequest,
    FocusGroupMessageRequest,
    FocusGroupSessionResponse,
    FocusGroupMessageItem,
    FocusGroupSynthesisResponse,
)
from app.llm.focus_group_chain import (
    generate_focus_group_personas,
    generate_persona_focus_reply,
    synthesize_focus_group_session,
)

router = APIRouter(prefix="/focus-group", tags=["focus-group"])


@router.post("/sessions", response_model=FocusGroupSessionResponse)
def create_focus_group_session(
    request: FocusGroupCreateRequest,
    database_session: Session = Depends(get_database_session),
):
    archetypes = database_session.query(Archetype).filter_by(run_id=request.population_run_id).all()
    if not archetypes:
        raise HTTPException(
            status_code=400,
            detail=f"No archetypes found for population_run_id '{request.population_run_id}'. Please generate a population first.",
        )

    archetype_data = [
        {
            "centroid_attributes": item.centroid_attributes,
            "population_weight": item.population_weight,
        }
        for item in archetypes
    ]
    personas = generate_focus_group_personas(archetype_data, target_count=request.n_personas or 4)

    session_id = str(uuid.uuid4())
    initial_message = {
        "id": str(uuid.uuid4()),
        "sender_type": "system",
        "sender_id": "system",
        "sender_name": "Focus Room Host",
        "message": f"Welcome everyone to today's focus group. We are exploring the topic: '{request.topic}'. Feel free to share your candid opinions and experiences.",
        "sentiment": "neutral",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    session_record = FocusGroupSession(
        id=session_id,
        topic=request.topic,
        population_run_id=request.population_run_id,
        status="active",
        personas=personas,
        messages=[initial_message],
        synthesis=None,
    )
    database_session.add(session_record)
    database_session.commit()
    database_session.refresh(session_record)

    return FocusGroupSessionResponse(
        id=session_record.id,
        topic=session_record.topic,
        population_run_id=session_record.population_run_id,
        status=session_record.status,
        personas=session_record.personas,
        messages=session_record.messages,
        synthesis=session_record.synthesis,
    )


@router.get("/sessions/{session_id}", response_model=FocusGroupSessionResponse)
def get_focus_group_session(
    session_id: str,
    database_session: Session = Depends(get_database_session),
):
    session_record = database_session.query(FocusGroupSession).filter_by(id=session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Focus group session not found.")

    return FocusGroupSessionResponse(
        id=session_record.id,
        topic=session_record.topic,
        population_run_id=session_record.population_run_id,
        status=session_record.status,
        personas=session_record.personas,
        messages=session_record.messages,
        synthesis=session_record.synthesis,
    )


@router.post("/sessions/{session_id}/message", response_model=List[FocusGroupMessageItem])
def post_focus_group_message(
    session_id: str,
    request: FocusGroupMessageRequest,
    database_session: Session = Depends(get_database_session),
):
    session_record = database_session.query(FocusGroupSession).filter_by(id=session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Focus group session not found.")

    current_messages = list(session_record.messages or [])

    moderator_msg = {
        "id": str(uuid.uuid4()),
        "sender_type": "moderator",
        "sender_id": "moderator",
        "sender_name": "Moderator",
        "message": request.message,
        "sentiment": None,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    current_messages.append(moderator_msg)
    new_messages = [moderator_msg]

    target_personas = []
    if request.target_persona_id:
        target_personas = [p for p in session_record.personas if p["id"] == request.target_persona_id]
        if not target_personas:
            target_personas = session_record.personas
    else:
        target_personas = session_record.personas

    for persona in target_personas:
        reply_dict = generate_persona_focus_reply(
            persona=persona,
            topic=session_record.topic,
            conversation_history=current_messages,
            user_prompt=request.message,
        )
        persona_msg = {
            "id": str(uuid.uuid4()),
            "sender_type": "persona",
            "sender_id": persona["id"],
            "sender_name": persona["name"],
            "message": reply_dict["reply"],
            "sentiment": reply_dict.get("sentiment", "neutral"),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        current_messages.append(persona_msg)
        new_messages.append(persona_msg)

    session_record.messages = current_messages
    database_session.commit()

    return [FocusGroupMessageItem(**item) for item in new_messages]


@router.post("/sessions/{session_id}/synthesize", response_model=FocusGroupSynthesisResponse)
def synthesize_session_insights(
    session_id: str,
    database_session: Session = Depends(get_database_session),
):
    session_record = database_session.query(FocusGroupSession).filter_by(id=session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Focus group session not found.")

    synthesis_result = synthesize_focus_group_session(
        topic=session_record.topic,
        personas=session_record.personas,
        messages=session_record.messages,
    )

    session_record.synthesis = synthesis_result
    database_session.commit()

    return FocusGroupSynthesisResponse(**synthesis_result)
