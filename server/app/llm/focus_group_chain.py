import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.llm.gemini_client import get_gemini_llm
from app.llm.prompts import FOCUS_GROUP_PERSONA_TEMPLATE, FOCUS_GROUP_SYNTHESIS_TEMPLATE


class FocusPersonaReply(BaseModel):
    reply: str
    sentiment: str = Field(description="positive, neutral, negative, or mixed")


class FocusSynthesisOutput(BaseModel):
    key_takeaways: List[str]
    consensus_points: List[str]
    divergence_points: List[str]
    strategic_recommendations: List[str]


AVATAR_COLORS = [
    "#6366F1",
    "#10B981",
    "#F59E0B",
    "#EC4899",
    "#8B5CF6",
    "#06B6D4",
]

INDIAN_NAMES_MALE = [
    "Rajesh Sharma",
    "Vikram Patel",
    "Amitabh Verma",
    "Suresh Nair",
    "Manoj Yadav",
    "Deepak Mukherjee",
]

INDIAN_NAMES_FEMALE = [
    "Sunita Sharma",
    "Priyanka Verma",
    "Ananya Sen",
    "Lakshmi Narayanan",
    "Pooja Deshmukh",
    "Meena Kumari",
]


def generate_focus_group_personas(archetypes: List[Dict[str, Any]], target_count: int = 4) -> List[Dict[str, Any]]:
    personas = []
    selected_archetypes = archetypes[:target_count]
    if not selected_archetypes:
        return personas

    total_weight = sum(item.get("population_weight", 1.0) for item in selected_archetypes)

    for index, item in enumerate(selected_archetypes):
        attrs = item.get("attributes") or item.get("centroid_attributes") or item
        gender = str(attrs.get("gender", "male")).strip().lower()
        state = str(attrs.get("state", "India"))
        district = str(attrs.get("district", "Urban Area"))
        age = int(attrs.get("age", 32))
        occupation = str(attrs.get("occupation", "Professional"))
        income_band = str(attrs.get("income_band", "Middle Income"))
        urban_rural = str(attrs.get("urban_rural", "Urban"))
        digital_score = float(attrs.get("digital_access_score", 0.6))
        raw_weight = float(item.get("population_weight", 1.0 / len(selected_archetypes)))
        normalized_weight = round(raw_weight / total_weight, 4) if total_weight > 0 else 0.25

        if "fem" in gender or gender == "f" or gender == "female":
            name_pool = INDIAN_NAMES_FEMALE
            assigned_gender = "Female"
        else:
            name_pool = INDIAN_NAMES_MALE
            assigned_gender = "Male"

        assigned_name = name_pool[index % len(name_pool)]
        persona_id = f"persona_{index + 1}_{uuid.uuid4().hex[:6]}"
        avatar_color = AVATAR_COLORS[index % len(AVATAR_COLORS)]

        bio = f"{assigned_name}, {age}, {assigned_gender} residing in {district} ({state}). Works as {occupation} in an {urban_rural} setting with {income_band} income. Digital access index: {digital_score:.1f}."

        personas.append({
            "id": persona_id,
            "name": assigned_name,
            "archetype_id": index + 1,
            "age": age,
            "gender": assigned_gender,
            "occupation": occupation,
            "location": f"{district}, {state}",
            "income_band": income_band,
            "digital_access_score": digital_score,
            "bio": bio,
            "avatar_color": avatar_color,
            "population_weight": normalized_weight,
        })

    return personas


def build_fallback_persona_reply(persona: Dict[str, Any], topic: str, user_prompt: str) -> Dict[str, str]:
    name = persona.get("name", "Participant")
    occupation = persona.get("occupation", "resident")
    income = persona.get("income_band", "fixed income")
    location = persona.get("location", "our city")
    digital_score = float(persona.get("digital_access_score", 0.5))

    question_lower = user_prompt.lower()

    if any(word in question_lower for word in ["price", "cost", "fee", "expensive", "rupee", "rs", "₹", "spend", "charge"]):
        if "low" in income.lower() or "tier" in income.lower():
            reply = f"Honestly, as someone earning a {income} in {location}, every single rupee counts for my family. Even a small recurring fee feels heavy unless there is an undeniable daily cash saving or guarantee."
            sentiment = "negative"
        else:
            reply = f"For our household in {location}, the pricing seems acceptable provided the service is reliable and saves us time. But if quality drops after initial discounts, we will stop paying immediately."
            sentiment = "neutral"
    elif any(word in question_lower for word in ["trust", "safe", "scam", "fraud", "security", "reliable"]):
        if digital_score < 0.5:
            reply = f"We prefer dealing with known local people in {location}. If there is a dispute or problem, whom do I meet face-to-face? Digital apps must have clear customer support in our local language."
            sentiment = "neutral"
        else:
            reply = f"Trust comes down to clear refund policies and transparent terms. As an {occupation}, I check online reviews and UPI safety before trying anything new."
            sentiment = "positive"
    elif any(word in question_lower for word in ["switch", "competitor", "alternative", "kirana", "local", "market"]):
        reply = f"In {location}, our local routine is very established. To switch, this product needs to be distinctly faster or offer benefits that my existing offline setup simply cannot match."
        sentiment = "neutral"
    else:
        reply = f"Speaking from my daily routine as a {occupation} in {location}, regarding '{topic}', my main priority is reliability and value for money. If it simplifies our everyday routine without hidden surprises, I would be interested."
        sentiment = "positive"

    return {"reply": reply, "sentiment": sentiment}


def generate_persona_focus_reply(
    persona: Dict[str, Any],
    topic: str,
    conversation_history: List[Dict[str, Any]],
    user_prompt: str,
) -> Dict[str, str]:
    formatted_history_list = []
    for msg in conversation_history[-6:]:
        sender = msg.get("sender_name", "Moderator")
        text = msg.get("message", "")
        formatted_history_list.append(f"{sender}: {text}")
    history_str = "\n".join(formatted_history_list) if formatted_history_list else "Discussion just started."

    try:
        language_model = get_gemini_llm(temperature=0.7)
        output_parser = PydanticOutputParser(pydantic_object=FocusPersonaReply)
        prompt = ChatPromptTemplate.from_messages([
            ("human", FOCUS_GROUP_PERSONA_TEMPLATE + "\n\n{format_instructions}"),
        ])
        chain = prompt | language_model | output_parser

        result = chain.invoke({
            "name": persona.get("name", "Participant"),
            "age": persona.get("age", 30),
            "gender": persona.get("gender", "Consumer"),
            "location": persona.get("location", "India"),
            "occupation": persona.get("occupation", "Working professional"),
            "income_band": persona.get("income_band", "Middle income"),
            "digital_access_score": persona.get("digital_access_score", 0.6),
            "bio": persona.get("bio", ""),
            "topic": topic,
            "conversation_history": history_str,
            "user_prompt": user_prompt,
            "format_instructions": output_parser.get_format_instructions(),
        })
        return {"reply": result.reply, "sentiment": result.sentiment}
    except Exception:
        return build_fallback_persona_reply(persona, topic, user_prompt)


def synthesize_focus_group_session(
    topic: str,
    personas: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    participants_summary_list = [
        f"- {p.get('name')}: {p.get('age')}y, {p.get('occupation')}, {p.get('location')}, Income: {p.get('income_band')}"
        for p in personas
    ]
    participants_str = "\n".join(participants_summary_list)

    transcript_list = [
        f"{m.get('sender_name', 'Speaker')}: {m.get('message', '')}"
        for m in messages
    ]
    transcript_str = "\n".join(transcript_list)

    try:
        language_model = get_gemini_llm(temperature=0.4)
        output_parser = PydanticOutputParser(pydantic_object=FocusSynthesisOutput)
        prompt = ChatPromptTemplate.from_messages([
            ("human", FOCUS_GROUP_SYNTHESIS_TEMPLATE + "\n\n{format_instructions}"),
        ])
        chain = prompt | language_model | output_parser

        result = chain.invoke({
            "topic": topic,
            "participants_summary": participants_str,
            "transcript": transcript_str,
            "format_instructions": output_parser.get_format_instructions(),
        })
        return {
            "key_takeaways": result.key_takeaways,
            "consensus_points": result.consensus_points,
            "divergence_points": result.divergence_points,
            "strategic_recommendations": result.strategic_recommendations,
        }
    except Exception:
        return {
            "key_takeaways": [
                f"Participants showed high contextual sensitivity to pricing and trust cues regarding '{topic}'.",
                "Tier-2 and Tier-3 demographic participants prioritized direct value and familiar payment or support channels.",
                "Higher income participants showed interest in time-saving features but expressed concerns about post-launch support quality.",
            ],
            "consensus_points": [
                "Universal demand for transparent, hidden-charge-free pricing structures.",
                "Need for reliable, responsive customer redressal in regional language contexts.",
            ],
            "divergence_points": [
                "Price tolerance varied sharply between salaried urban professionals and daily wage or local business owners.",
                "Digital-first onboarding was embraced by younger segments but caused hesitation among older, lower-digital-literacy personas.",
            ],
            "strategic_recommendations": [
                "Introduce transparent tiered pricing with a low barrier trial period to establish initial trust.",
                "Emphasize vernacular onboarding and immediate WhatsApp or phone support touchpoints.",
                "Tailor messaging around household savings for price-sensitive cohorts and convenience for high-income cohorts.",
            ],
        }
