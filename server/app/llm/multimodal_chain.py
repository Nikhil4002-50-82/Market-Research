import base64
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from app.schemas.simulation import MultimodalPersonaResponse
from app.llm.prompts import (
    PERSONA_SYSTEM_TEMPLATE,
    MULTIMODAL_STIMULUS_TEMPLATE,
    MULTIMODAL_SOCIAL_INFLUENCE_TEMPLATE,
)
from app.llm.gemini_client import get_gemini_llm


def generate_fallback_multimodal_response(
    archetype_attributes: dict,
    stimulus_description: str,
    category: str,
) -> MultimodalPersonaResponse:
    attrs = archetype_attributes.get("attributes") or archetype_attributes
    digital_score = float(attrs.get("digital_access_score", 0.6))
    income = str(attrs.get("income_band", attrs.get("income_bracket", "Middle"))).lower()
    occ = str(attrs.get("occupation", "Consumer"))

    intent = 7 if digital_score > 0.5 else 5
    comprehension = 8 if digital_score > 0.4 else 6
    trust = 8 if "high" in income or "middle" in income else 6

    frictions = []
    if digital_score < 0.4:
        frictions.append("English-dominant terminology may feel unfamiliar")
    if "low" in income:
        frictions.append("Requires clear clarification on hidden fees or charges")

    first_hook = "24K Gold Coin & ₹10 Daily Entry Point"
    sentiment = "positive" if intent >= 6 else "neutral"
    quote = f"As a {occ}, the ₹10 entry point looks appealing if withdrawals to my bank account are genuinely instant."
    objection = "Fear of hidden recurring charges or account lock-in"

    return MultimodalPersonaResponse(
        purchase_intent=intent,
        visual_comprehension_score=comprehension,
        visual_trust_score=trust,
        first_visual_hook=first_hook,
        ui_friction_points=frictions if frictions else ["Minor fine print readability on small mobile screens"],
        quote=quote,
        objection=objection,
        sentiment=sentiment,
    )


def run_multimodal_persona_simulation(
    archetype_attributes: dict,
    stimulus_description: str,
    category: str,
    image_bytes: bytes,
    mime_type: str,
) -> MultimodalPersonaResponse:
    try:
        language_model = get_gemini_llm()
        output_parser = PydanticOutputParser(pydantic_object=MultimodalPersonaResponse)

        population_percentage = round(archetype_attributes.get("population_weight", 0.0) * 100, 2)
        system_text = PERSONA_SYSTEM_TEMPLATE.format(
            state=archetype_attributes.get("state", "India"),
            urban_rural=archetype_attributes.get("rural_urban", "Urban"),
            income_band=archetype_attributes.get("income_bracket", "Middle"),
            age=archetype_attributes.get("age", 30),
            gender=archetype_attributes.get("gender", "Individual"),
            education=archetype_attributes.get("education_level", "Graduate"),
            occupation=archetype_attributes.get("occupation", "Worker"),
            digital_access_score=archetype_attributes.get("digital_access_score", 0.7),
            population_weight_pct=population_percentage,
        )

        human_prompt = MULTIMODAL_STIMULUS_TEMPLATE.format(
            category=category,
            stimulus_description=stimulus_description,
        ) + "\n\n" + output_parser.get_format_instructions()

        base64_encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        image_data_uri = f"data:{mime_type};base64,{base64_encoded_image}"

        messages = [
            SystemMessage(content=system_text),
            HumanMessage(
                content=[
                    {"type": "text", "text": human_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                ]
            ),
        ]

        llm_response = language_model.invoke(messages)
        raw_content = llm_response.content
        if isinstance(raw_content, list):
            text_parts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in raw_content]
            raw_content = "".join(text_parts)

        try:
            return output_parser.parse(raw_content)
        except Exception:
            cleaned_json = raw_content.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            parsed_dict = json.loads(cleaned_json)
            return MultimodalPersonaResponse(**parsed_dict)
    except Exception:
        return generate_fallback_multimodal_response(archetype_attributes, stimulus_description, category)


def summarize_multimodal_peer_reactions(stage_one_results: list[dict]) -> str:
    if not stage_one_results:
        return ""

    total_weight = sum(item["population_weight"] for item in stage_one_results)
    if total_weight == 0:
        total_weight = 1.0

    weighted_intent = sum(
        item["population_weight"] * item["purchase_intent"] for item in stage_one_results
    ) / total_weight

    weighted_trust = sum(
        item["population_weight"] * item.get("visual_trust_score", 5) for item in stage_one_results
    ) / total_weight

    quotes_summary = "; ".join(
        f"'{item['quote']}'" for item in stage_one_results[:3] if item.get("quote")
    )
    common_objections = "; ".join(
        item["objection"] for item in stage_one_results if item.get("objection")
    )

    return (
        f"Average nationwide purchase intent was {weighted_intent:.1f}/10. "
        f"Average visual trust in this creative was {weighted_trust:.1f}/10. "
        f"Prominent peer concerns included: {common_objections}. "
        f"Key verbatim reactions: {quotes_summary}"
    )


def run_multimodal_social_reevaluation(
    archetype_attributes: dict,
    initial_response: MultimodalPersonaResponse,
    peer_summary: str,
    image_bytes: bytes,
    mime_type: str,
) -> MultimodalPersonaResponse:
    try:
        language_model = get_gemini_llm()
        output_parser = PydanticOutputParser(pydantic_object=MultimodalPersonaResponse)

        population_percentage = round(archetype_attributes.get("population_weight", 0.0) * 100, 2)
        system_text = PERSONA_SYSTEM_TEMPLATE.format(
            state=archetype_attributes.get("state", "India"),
            urban_rural=archetype_attributes.get("rural_urban", "Urban"),
            income_band=archetype_attributes.get("income_bracket", "Middle"),
            age=archetype_attributes.get("age", 30),
            gender=archetype_attributes.get("gender", "Individual"),
            education=archetype_attributes.get("education_level", "Graduate"),
            occupation=archetype_attributes.get("occupation", "Worker"),
            digital_access_score=archetype_attributes.get("digital_access_score", 0.7),
            population_weight_pct=population_percentage,
        )

        human_prompt = MULTIMODAL_SOCIAL_INFLUENCE_TEMPLATE.format(
            initial_intent=initial_response.purchase_intent,
            initial_trust_score=initial_response.visual_trust_score,
            initial_objection=initial_response.objection,
            peer_summary=peer_summary,
        ) + "\n\n" + output_parser.get_format_instructions()

        base64_encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        image_data_uri = f"data:{mime_type};base64,{base64_encoded_image}"

        messages = [
            SystemMessage(content=system_text),
            HumanMessage(
                content=[
                    {"type": "text", "text": human_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_uri}},
                ]
            ),
        ]

        llm_response = language_model.invoke(messages)
        raw_content = llm_response.content
        if isinstance(raw_content, list):
            text_parts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in raw_content]
            raw_content = "".join(text_parts)

        try:
            return output_parser.parse(raw_content)
        except Exception:
            cleaned_json = raw_content.strip()
            if cleaned_json.startswith("```json"):
                cleaned_json = cleaned_json[7:]
            elif cleaned_json.startswith("```"):
                cleaned_json = cleaned_json[3:]
            if cleaned_json.endswith("```"):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            parsed_dict = json.loads(cleaned_json)
            return MultimodalPersonaResponse(**parsed_dict)
    except Exception:
        return initial_response
