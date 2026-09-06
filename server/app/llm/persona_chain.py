from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.llm.prompts import PERSONA_SYSTEM_TEMPLATE, STIMULUS_TEMPLATE
from app.llm.gemini_client import get_gemini_llm


class PersonaResponse(BaseModel):
    purchase_intent: int = Field(ge=0, le=10)
    sentiment: str
    objection: str
    quote: str


def build_persona_chain():
    language_model = get_gemini_llm()
    output_parser = PydanticOutputParser(pydantic_object=PersonaResponse)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", PERSONA_SYSTEM_TEMPLATE),
        ("human", STIMULUS_TEMPLATE + "\n\n{format_instructions}"),
    ])
    executable_chain = prompt_template | language_model | output_parser
    return executable_chain, output_parser


def run_persona_simulation(archetype_attributes: dict, stimulus_description: str) -> PersonaResponse:
    executable_chain, output_parser = build_persona_chain()
    population_percentage = round(archetype_attributes.get("population_weight", 0.0) * 100, 2)

    prompt_inputs = {
        **archetype_attributes,
        "population_weight_pct": population_percentage,
        "stimulus_description": stimulus_description,
        "format_instructions": output_parser.get_format_instructions(),
    }
    return executable_chain.invoke(prompt_inputs)
