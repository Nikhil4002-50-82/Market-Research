from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from app.llm.gemini_client import get_gemini_llm
from app.llm.prompts import VAN_WESTENDORP_PRICING_TEMPLATE


class PersonaPricingThreshold(BaseModel):
    too_cheap: float = Field(ge=0)
    cheap: float = Field(ge=0)
    expensive: float = Field(ge=0)
    too_expensive: float = Field(ge=0)
    rationale: str


def generate_fallback_price_thresholds(
    archetype: Dict[str, Any],
    product_concept: str,
    category: str,
) -> Dict[str, Any]:
    attrs = archetype.get("attributes") or archetype.get("centroid_attributes") or archetype
    income_band = str(attrs.get("income_band", "Middle")).lower()
    urban_rural = str(attrs.get("urban_rural", "Urban")).lower()
    cat_lower = category.lower()

    if "saas" in cat_lower or "software" in cat_lower or "b2b" in cat_lower:
        base_cheap = 499.0
    elif "fmcg" in cat_lower or "grocery" in cat_lower or "food" in cat_lower:
        base_cheap = 149.0
    elif "fintech" in cat_lower or "gold" in cat_lower:
        base_cheap = 299.0
    elif "edtech" in cat_lower or "course" in cat_lower:
        base_cheap = 599.0
    else:
        base_cheap = 249.0

    multiplier = 1.0
    if "low" in income_band or "tier 3" in income_band or "tier-3" in income_band:
        multiplier = 0.6
    elif "high" in income_band or "upper" in income_band:
        multiplier = 2.2
    elif "rural" in urban_rural:
        multiplier *= 0.85

    cheap = round(base_cheap * multiplier, 2)
    too_cheap = round(cheap * 0.45, 2)
    expensive = round(cheap * 2.2, 2)
    too_expensive = round(expensive * 1.8, 2)

    occupation = attrs.get("occupation", "Consumer")
    location = attrs.get("state", "India")
    rationale = f"Given {income_band} income and living costs in {location} as a {occupation}, anything below ₹{too_cheap} suggests poor quality, while above ₹{too_expensive} is completely out of budget."

    return {
        "too_cheap": too_cheap,
        "cheap": cheap,
        "expensive": expensive,
        "too_expensive": too_expensive,
        "rationale": rationale,
    }


def elicit_archetype_pricing(
    archetype: Dict[str, Any],
    product_concept: str,
    category: str,
    currency: str = "INR",
) -> Dict[str, Any]:
    attrs = archetype.get("attributes") or archetype.get("centroid_attributes") or archetype
    demographic_summary = f"{attrs.get('age', 30)}y {attrs.get('gender', 'person')}, {attrs.get('occupation', 'worker')} in {attrs.get('urban_rural', 'Urban')} sector."
    location = f"{attrs.get('district', 'District')}, {attrs.get('state', 'State')}"
    income_band = str(attrs.get("income_band", "Middle Income"))
    digital_score = float(attrs.get("digital_access_score", 0.6))

    try:
        language_model = get_gemini_llm(temperature=0.3)
        output_parser = PydanticOutputParser(pydantic_object=PersonaPricingThreshold)
        prompt = ChatPromptTemplate.from_messages([
            ("human", VAN_WESTENDORP_PRICING_TEMPLATE + "\n\n{format_instructions}"),
        ])
        chain = prompt | language_model | output_parser

        result = chain.invoke({
            "demographic_summary": demographic_summary,
            "location": location,
            "income_band": income_band,
            "digital_access_score": digital_score,
            "product_concept": product_concept,
            "category": category,
            "currency": currency,
            "format_instructions": output_parser.get_format_instructions(),
        })

        vals = sorted([result.too_cheap, result.cheap, result.expensive, result.too_expensive])
        return {
            "too_cheap": vals[0],
            "cheap": vals[1],
            "expensive": vals[2],
            "too_expensive": vals[3],
            "rationale": result.rationale,
        }
    except Exception:
        return generate_fallback_price_thresholds(archetype, product_concept, category)


def find_curve_intersection(
    prices: List[float],
    series_a: List[float],
    series_b: List[float],
) -> float:
    if not prices:
        return 0.0

    min_diff = float("inf")
    best_price = prices[0]

    for index in range(len(prices)):
        diff = abs(series_a[index] - series_b[index])
        if diff < min_diff:
            min_diff = diff
            best_price = prices[index]

    return round(best_price, 2)


def compute_van_westendorp_psm(
    archetype_responses: List[Dict[str, Any]],
    n_grid_points: int = 40,
) -> Dict[str, Any]:
    if not archetype_responses:
        raise ValueError("Archetype pricing responses cannot be empty.")

    all_too_cheap = [item["too_cheap"] for item in archetype_responses]
    all_too_exp = [item["too_expensive"] for item in archetype_responses]

    min_price = max(1.0, min(all_too_cheap) * 0.7)
    max_price = max(all_too_exp) * 1.25

    step = (max_price - min_price) / float(n_grid_points - 1)
    grid_prices = [round(min_price + i * step, 2) for i in range(n_grid_points)]

    total_weight = sum(item.get("population_weight", 1.0) for item in archetype_responses)
    if total_weight <= 0:
        total_weight = float(len(archetype_responses))

    curves = []
    too_cheap_series = []
    cheap_series = []
    expensive_series = []
    too_expensive_series = []

    best_revenue = -1.0
    revenue_max_price = grid_prices[0]

    for p in grid_prices:
        w_too_cheap = 0.0
        w_cheap = 0.0
        w_expensive = 0.0
        w_too_expensive = 0.0
        w_acceptable = 0.0

        for item in archetype_responses:
            weight = float(item.get("population_weight", 1.0))
            if p <= item["too_cheap"]:
                w_too_cheap += weight
            if p <= item["cheap"]:
                w_cheap += weight
            if p >= item["expensive"]:
                w_expensive += weight
            if p >= item["too_expensive"]:
                w_too_expensive += weight
            if p > item["too_cheap"] and p < item["too_expensive"]:
                w_acceptable += weight

        pct_too_cheap = round((w_too_cheap / total_weight) * 100.0, 2)
        pct_cheap = round((w_cheap / total_weight) * 100.0, 2)
        pct_expensive = round((w_expensive / total_weight) * 100.0, 2)
        pct_too_expensive = round((w_too_expensive / total_weight) * 100.0, 2)
        pct_acceptable = round((w_acceptable / total_weight) * 100.0, 2)

        rev_index = round(p * (pct_acceptable / 100.0), 2)
        if rev_index > best_revenue:
            best_revenue = rev_index
            revenue_max_price = p

        too_cheap_series.append(pct_too_cheap)
        cheap_series.append(pct_cheap)
        expensive_series.append(pct_expensive)
        too_expensive_series.append(pct_too_expensive)

        curves.append({
            "price": p,
            "too_cheap_pct": pct_too_cheap,
            "cheap_pct": pct_cheap,
            "expensive_pct": pct_expensive,
            "too_expensive_pct": pct_too_expensive,
            "acceptable_pct": pct_acceptable,
            "expected_revenue_index": rev_index,
        })

    opp = find_curve_intersection(grid_prices, too_cheap_series, too_expensive_series)
    ipp = find_curve_intersection(grid_prices, cheap_series, expensive_series)
    pmc = find_curve_intersection(grid_prices, too_cheap_series, expensive_series)
    pme = find_curve_intersection(grid_prices, too_expensive_series, cheap_series)

    if pmc > pme:
        pmc, pme = min(pmc, pme), max(pmc, pme)

    summary = {
        "optimal_price_point": opp,
        "indifference_price_point": ipp,
        "point_of_marginal_cheapness": pmc,
        "point_of_marginal_expensiveness": pme,
        "acceptable_price_range_min": pmc,
        "acceptable_price_range_max": pme,
        "revenue_maximizing_price": revenue_max_price,
    }

    recommendations = [
        f"Optimal Entry Price: Launch at ₹{opp:,.0f} to minimize friction and balance perceived quality with mass affordability.",
        f"Acceptable Pricing Corridor: Keep mass-market pricing bounded between ₹{pmc:,.0f} (floor) and ₹{pme:,.0f} (ceiling).",
        f"Maximum Monetization: For a revenue-maximizing business model targeting paying segments, set the standard tier at ₹{revenue_max_price:,.0f}.",
        f"Discount Warning: Never drop prices below ₹{pmc:,.0f}, as {too_cheap_series[0]:.0f}% of consumers correlate prices below this threshold with inferior quality or fraud.",
    ]

    return {
        "summary": summary,
        "curves": curves,
        "strategic_recommendations": recommendations,
    }
