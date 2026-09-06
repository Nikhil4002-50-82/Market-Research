from typing import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.llm.prompts import PERSONA_SYSTEM_TEMPLATE, STIMULUS_TEMPLATE, SOCIAL_INFLUENCE_TEMPLATE
from app.llm.gemini_client import get_gemini_llm


class PersonaResponse(BaseModel):
    purchase_intent: int = Field(ge=0, le=10)
    sentiment: str
    objection: str
    quote: str


class PersonaState(TypedDict):
    archetype: dict
    stimulus: str
    peer_summary: str | None
    initial_reaction: dict | None
    final_decision: dict | None
    intent_shift: float | None


def build_llm_and_parser():
    language_model = get_gemini_llm()
    output_parser = PydanticOutputParser(pydantic_object=PersonaResponse)
    return language_model, output_parser


def node_initial_reaction(state: PersonaState) -> PersonaState:
    language_model, output_parser = build_llm_and_parser()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", PERSONA_SYSTEM_TEMPLATE),
        ("human", STIMULUS_TEMPLATE + "\n\n{format_instructions}"),
    ])
    executable_chain = prompt_template | language_model | output_parser

    population_percentage = round(state["archetype"].get("population_weight", 0.0) * 100, 2)
    prompt_inputs = {
        **state["archetype"],
        "population_weight_pct": population_percentage,
        "stimulus_description": state["stimulus"],
        "format_instructions": output_parser.get_format_instructions(),
    }
    execution_result = executable_chain.invoke(prompt_inputs)
    state["initial_reaction"] = execution_result.model_dump()
    return state


def node_social_influence(state: PersonaState) -> PersonaState:
    if not state.get("peer_summary"):
        state["final_decision"] = state["initial_reaction"]
        state["intent_shift"] = 0.0
        return state

    language_model, output_parser = build_llm_and_parser()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", PERSONA_SYSTEM_TEMPLATE),
        ("human", SOCIAL_INFLUENCE_TEMPLATE + "\n\n{format_instructions}"),
    ])
    executable_chain = prompt_template | language_model | output_parser

    initial_reaction_data = state["initial_reaction"]
    population_percentage = round(state["archetype"].get("population_weight", 0.0) * 100, 2)

    prompt_inputs = {
        **state["archetype"],
        "population_weight_pct": population_percentage,
        "initial_intent": initial_reaction_data["purchase_intent"],
        "initial_sentiment": initial_reaction_data["sentiment"],
        "initial_objection": initial_reaction_data["objection"],
        "peer_summary": state["peer_summary"],
        "format_instructions": output_parser.get_format_instructions(),
    }
    execution_result = executable_chain.invoke(prompt_inputs)
    state["final_decision"] = execution_result.model_dump()
    state["intent_shift"] = execution_result.purchase_intent - initial_reaction_data["purchase_intent"]
    return state


def build_persona_graph():
    graph_workflow = StateGraph(PersonaState)
    graph_workflow.add_node("initial_reaction", node_initial_reaction)
    graph_workflow.add_node("social_influence", node_social_influence)
    graph_workflow.set_entry_point("initial_reaction")
    graph_workflow.add_edge("initial_reaction", "social_influence")
    graph_workflow.add_edge("social_influence", END)
    return graph_workflow.compile()


def summarize_peer_reactions(other_archetype_reactions: list[dict]) -> str:
    if not other_archetype_reactions:
        return ""

    total_weight = sum(item["population_weight"] for item in other_archetype_reactions)
    average_intent = sum(
        item["population_weight"] * item["initial_reaction"]["purchase_intent"]
        for item in other_archetype_reactions
    ) / total_weight

    sentiment_weighted_counts = {}
    for item in other_archetype_reactions:
        sentiment_label = item["initial_reaction"]["sentiment"]
        sentiment_weighted_counts[sentiment_label] = (
            sentiment_weighted_counts.get(sentiment_label, 0.0) + item["population_weight"]
        )

    dominant_sentiment = max(sentiment_weighted_counts, key=sentiment_weighted_counts.get)

    return (
        f"Across a representative sample of the population, the average purchase "
        f"intent was {average_intent:.1f}/10, and the dominant overall sentiment was "
        f"'{dominant_sentiment}'."
    )
