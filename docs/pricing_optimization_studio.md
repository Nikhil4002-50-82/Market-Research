# Pricing Optimization Engine (Van Westendorp PSM): Backend Architecture & Workflow Specification

## 1. Executive Summary & Purpose

Pricing products or services for the Indian consumer market is uniquely challenging:
* Indian consumers exhibit intense price sensitivity and value consciousness (*"paisa vasool"*).
* Pricing too low causes **quality skepticism**: consumers associate excessively cheap offerings with counterfeit goods, inferior materials, or digital scams.
* Pricing too high triggers **immediate drop-off and churn**, pushing consumers to unbranded alternatives or local informal substitutes.
* A single blanket price across India ignores the massive income disparity between Tier-1 metro professionals and Tier-2/Tier-3 semi-urban households.

The **Pricing Optimization Engine** implements an API-first econometric backend based on the **Van Westendorp Price Sensitivity Meter (PSM)** augmented by demographic LLM elicitation. The backend elicits psychological price thresholds from representative demographic archetypes, computes continuous cumulative frequency curves, identifies critical economic intersections (PMC, PME, IPP, OPP), optimizes revenue-maximizing price points, and synthesizes strategic pricing directives.

---

## 2. System Architecture & End-to-End Backend Workflow

```mermaid
flowchart TD
    subgraph Client ["Client Layer"]
        App["API Client / Pricing Dashboard / Financial Microservice"]
    end

    subgraph API ["FastAPI Router (api/routers/pricing.py)"]
        RunRouter["POST /pricing/van-westendorp/run"]
        GetRouter["GET /pricing/simulations/{run_id}"]
    end

    subgraph CoreEngine ["PSM Econometric Engine (simulation/pricing_psm.py)"]
        Elicitor["elicit_archetype_pricing()<br/>Gemini 4-Point PSM Prompt Chain"]
        Sorter["Monotonicity Validator & Sorter<br/>too_cheap <= cheap <= expensive <= too_expensive"]
        Fallback["Econometric Heuristic Fallback<br/>(Category Baseline & Income Multipliers)"]
        Grid["Continuous Price Grid Evaluator<br/>(Weighted Cumulative Frequencies)"]
        Intersections["find_curve_intersection()<br/>Calculates PMC, PME, IPP, OPP"]
        RevMaximizer["Revenue Index Maximizer<br/>P * Acceptable%"]
        Advisory["Rule-Based Strategic Recommendation Generator"]
    end

    subgraph DB ["Operational DB (data/models.py)"]
        T_Arch["archetypes table"]
        T_Pricing["pricing_optimization_runs table"]
    end

    App -->|POST PricingRequest| RunRouter
    RunRouter -->|Fetch demographic archetypes| T_Arch
    RunRouter --> Elicitor
    Elicitor --> Sorter
    Sorter -->|Validation Failure?| Fallback
    Sorter & Fallback --> Grid
    Grid --> Intersections
    Grid --> RevMaximizer
    Intersections & RevMaximizer --> Advisory
    Advisory -->|Persist complete results JSON| T_Pricing
    RunRouter -->|Return PricingRunResponse| App

    App -->|GET /pricing/simulations/{run_id}| GetRouter
    GetRouter -->|Read stored run| T_Pricing
```

---

## 3. Detailed Backend Operational Workflows

### Workflow 1: Pricing Run Request Ingestion

**Primary Endpoint**: `POST /pricing/van-westendorp/run`  
**Backend Handler**: `run_pricing_simulation()` in [`server/app/api/routers/pricing.py`](file:///c:/Users/Dell/Desktop/Market-Research/server/app/api/routers/pricing.py)

#### Step 1: Request Schema Validation
The router receives a `PricingRunRequest`:
```python
class PricingRunRequest(BaseModel):
    product_concept: str
    category: str = "Consumer Goods"
    population_run_id: str
    currency: str = "INR"
    price_range_hint: Optional[Dict[str, float]] = None
    n_archetypes_override: Optional[int] = Field(default=4, ge=1, le=10)
```

#### Step 2: Population Archetype Retrieval & Weight Normalization
* Queries the `archetypes` table for records matching `population_run_id`.
* If `n_archetypes_override` is specified (default: 4), slices the top representative archetypes.
* Normalizes the demographic weights $w_k$ across the selected subset to ensure:
  $$\sum_{k=1}^K w_k = 1.0$$

---

### Workflow 2: Psychological Price Threshold Elicitation

**Execution Function**: `elicit_archetype_pricing()` in [`server/app/simulation/pricing_psm.py`](file:///c:/Users/Dell/Desktop/Market-Research/server/app/simulation/pricing_psm.py)

#### Step 1: The 4 Van Westendorp Questions Formulation
For each archetype, the engine queries the consumer across four psychological thresholds:
1. **Too Cheap ($P_{\text{too cheap}}$)**: Price is so low that the consumer questions quality and refuses to buy.
2. **Cheap / Bargain ($P_{\text{cheap}}$)**: Price feels like a great bargain and compelling value for money.
3. **Expensive ($P_{\text{expensive}}$)**: Price feels high, but the consumer would still consider purchasing after careful deliberation.
4. **Too Expensive ($P_{\text{too expensive}}$)**: Price is prohibitive; completely out of budget.

#### Step 2: Gemini LLM Elicitation
Conditioned via `VAN_WESTENDORP_PRICING_TEMPLATE` ([`server/app/llm/prompts.py`](file:///c:/Users/Dell/Desktop/Market-Research/server/app/llm/prompts.py)):
* Injects demographic summary, location, household monthly income band, and digital access index.
* Invokes Gemini (`temperature=0.3` for quantitative consistency).
* Parses the output via `PydanticOutputParser(PersonaPricingThreshold)`:
  ```python
  class PersonaPricingThreshold(BaseModel):
      too_cheap: float = Field(ge=0)
      cheap: float = Field(ge=0)
      expensive: float = Field(ge=0)
      too_expensive: float = Field(ge=0)
      rationale: str
  ```

#### Step 3: Monotonicity Validation & Sorting
Econometric validity requires that:
$$P_{\text{too cheap}} \le P_{\text{cheap}} \le P_{\text{expensive}} \le P_{\text{too expensive}}$$
The engine enforces this strictly by sorting elicited price points:
```python
vals = sorted([result.too_cheap, result.cheap, result.expensive, result.too_expensive])
return {
    "too_cheap": vals[0],
    "cheap": vals[1],
    "expensive": vals[2],
    "too_expensive": vals[3],
    "rationale": result.rationale,
}
```

#### Step 4: Econometric Heuristic Fallback Engine
If upstream API connectivity fails, `generate_fallback_price_thresholds()` computes deterministic thresholds based on category baselines and demographic multipliers:
* **Category Baseline**: SaaS (₹499), EdTech (₹599), Fintech (₹299), FMCG (₹149), General Consumer (₹249).
* **Income Tier Multipliers**: Low-income ($0.6\times$), Middle-income ($1.0\times$), Upper-income ($2.2\times$).
* **Rural Adjustment**: Multiplies by $0.85\times$ for rural settings.

---

### Workflow 3: Econometric PSM Curve Computation & Grid Evaluation

**Execution Function**: `compute_van_westendorp_psm()` in [`server/app/simulation/pricing_psm.py`](file:///c:/Users/Dell/Desktop/Market-Research/server/app/simulation/pricing_psm.py)

#### Step 1: Continuous Price Grid Construction
Computes bounding limits and establishes a dynamic price evaluation grid:
$$P_{\min} = \max\left(1.0, \min(P_{\text{too cheap}}) \times 0.7\right)$$
$$P_{\max} = \max(P_{\text{too expensive}}) \times 1.25$$
Constructs $N_{\text{grid}} = 40$ uniformly spaced evaluation price points across $[P_{\min}, P_{\max}]$.

#### Step 2: Population-Weighted Cumulative Frequency Evaluation
For each price point $p$ on the grid, computes cumulative demographic percentages weighted by $w_i$:

$$\text{Too Cheap Percentage: } S_{\text{too cheap}}(p) = \frac{\sum_{i: p \le P_{\text{too cheap}, i}} w_i}{\sum w_i} \times 100\%$$

$$\text{Cheap Percentage: } S_{\text{cheap}}(p) = \frac{\sum_{i: p \le P_{\text{cheap}, i}} w_i}{\sum w_i} \times 100\%$$

$$\text{Expensive Percentage: } S_{\text{expensive}}(p) = \frac{\sum_{i: p \ge P_{\text{expensive}, i}} w_i}{\sum w_i} \times 100\%$$

$$\text{Too Expensive Percentage: } S_{\text{too expensive}}(p) = \frac{\sum_{i: p \ge P_{\text{too expensive}, i}} w_i}{\sum w_i} \times 100\%$$

$$\text{Acceptable Percentage: } S_{\text{acceptable}}(p) = \frac{\sum_{i: P_{\text{too cheap}, i} < p < P_{\text{too expensive}, i}} w_i}{\sum w_i} \times 100\%$$

#### Step 3: Economic Intersection Search Algorithm (`find_curve_intersection`)
Identifies critical economic boundary intersections where two cumulative curves cross:
1. **Point of Marginal Cheapness (PMC)**:
   * Intersection of **Too Cheap** and **Expensive** curves.
   * *Economic Meaning*: The lower price floor. Pricing below PMC damages sales because quality suspicion exceeds price resistance.
2. **Point of Marginal Expensiveness (PME)**:
   * Intersection of **Cheap** and **Too Expensive** curves.
   * *Economic Meaning*: The upper price ceiling. Pricing above PME damages sales because consumers consider the price completely prohibitive.
3. **Indifference Price Point (IPP)**:
   * Intersection of **Cheap** and **Expensive** curves.
   * *Economic Meaning*: The median price point where equal proportions of consumers view the product as cheap vs. expensive.
4. **Optimal Price Point (OPP)**:
   * Intersection of **Too Cheap** and **Too Expensive** curves.
   * *Economic Meaning*: Point of minimal consumer resistance.
5. **Acceptable Price Range**:
   Bounded corridor between $[\text{PMC}, \text{PME}]$.

---

### Workflow 4: Expected Revenue Optimization & Strategic Recommendation Engine

#### Step 1: Revenue Index Maximization
For each price point on the grid, computes the expected monetization index:
$$\text{Revenue Index}(p) = p \times \frac{S_{\text{acceptable}}(p)}{100}$$
Identifies $P_{\text{revenue max}}$, the price that maximizes monetization efficiency among addressable paying segments.

#### Step 2: Rule-Based Strategic Recommendation Synthesis
Generates structured executive directives:
* **Launch Recommendation**: Advises launching at ₹{OPP} to maximize volume and balance quality with affordability.
* **Corridor Boundary Guidance**: Recommends keeping mass-market tiers within [₹{PMC}, ₹{PME}].
* **Monetization Target**: Recommends setting premium tiers at ₹{Revenue Max}.
* **Discount Floor Warning**: Explicitly warns against discounting below ₹{PMC} to prevent brand devaluation.

#### Step 3: Database Persistence & Response
* Stores the complete simulation analysis in the `pricing_optimization_runs` table.
* Returns `PricingRunResponse` containing summary metrics, 40 curve points, archetype responses, and strategic recommendations.

---

### Workflow 5: Historical Run Retrieval

**Endpoint**: `GET /pricing/simulations/{run_id}`  
**Response Schema**: `PricingRunResponse`

```json
{
  "run_id": "5f3a1234-9c88-4221-a1b2-123456789abc",
  "status": "completed",
  "product_concept": "Cloud accounting software for Indian MSMEs",
  "category": "B2B SaaS",
  "currency": "INR",
  "summary": {
    "optimal_price_point": 349.0,
    "indifference_price_point": 449.0,
    "point_of_marginal_cheapness": 199.0,
    "point_of_marginal_expensiveness": 699.0,
    "acceptable_price_range_min": 199.0,
    "acceptable_price_range_max": 699.0,
    "revenue_maximizing_price": 499.0
  },
  "curves": [
    {
      "price": 199.0,
      "too_cheap_pct": 28.5,
      "cheap_pct": 82.0,
      "expensive_pct": 14.0,
      "too_expensive_pct": 4.5,
      "acceptable_pct": 67.0,
      "expected_revenue_index": 133.33
    }
  ],
  "strategic_recommendations": [
    "Optimal Entry Price: Launch at ₹349 to minimize friction and balance perceived quality with mass affordability.",
    "Acceptable Pricing Corridor: Keep mass-market pricing bounded between ₹199 (floor) and ₹699 (ceiling).",
    "Maximum Monetization: For a revenue-maximizing business model targeting paying segments, set the standard tier at ₹499.",
    "Discount Warning: Never drop prices below ₹199, as 28% of consumers correlate prices below this threshold with inferior quality or fraud."
  ]
}
```

---

## 4. Database Schema Specifications

### `pricing_optimization_runs` Table
| Column Name | SQLAlchemy Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `String` | Primary Key, Index | Pricing run UUID |
| `product_concept` | `String` | Not Null | Concept description |
| `category` | `String` | Not Null | Industry sector |
| `population_run_id` | `String` | Index, Not Null | Associated demographic population run ID |
| `currency` | `String` | Default="INR" | Currency code |
| `status` | `String` | Default="pending" | Run status (`completed`, `failed`) |
| `results` | `JSON` | Nullable | Complete PSM analysis payload |

---

## 5. Defensive Engineering & Econometric Safeguards

1. **Inverted PMC/PME Normalization**: If small sample sizes create inverted boundary crossings ($PMC > PME$), the engine normalizes them:
   ```python
   if pmc > pme:
       pmc, pme = min(pmc, pme), max(pmc, pme)
   ```
2. **Deterministic Heuristic Fallback**: If Gemini fails or times out, `generate_fallback_price_thresholds()` ensures that PSM calculations complete deterministically.
3. **Monotonicity Sorting**: Elicited prices are strictly sorted to maintain econometric integrity before computing cumulative distributions.
