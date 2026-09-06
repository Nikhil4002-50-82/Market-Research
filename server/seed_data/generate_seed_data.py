import os
import argparse
import numpy as np
import pandas as pd

INDIAN_STATES = ["Karnataka", "Maharashtra", "Uttar Pradesh", "Tamil Nadu", "West Bengal", "Bihar"]
URBAN_RURAL_CATEGORIES = ["urban", "rural"]
INCOME_BRACKETS = ["<10k", "10k-25k", "25k-50k", "50k-100k", "100k+"]
GENDER_CATEGORIES = ["male", "female"]
EDUCATION_LEVELS = ["none", "primary", "secondary", "graduate", "postgraduate"]
OCCUPATION_TYPES = [
    "agriculture",
    "informal_trade",
    "salaried_private",
    "salaried_govt",
    "self_employed",
    "student",
    "unemployed",
]


def generate_households(record_count: int, seed: int) -> pd.DataFrame:
    random_generator = np.random.default_rng(seed)
    return pd.DataFrame({
        "id": np.arange(1, record_count + 1),
        "state": random_generator.choice(INDIAN_STATES, record_count),
        "district": [f"district_{i % 50}" for i in range(record_count)],
        "urban_rural": random_generator.choice(URBAN_RURAL_CATEGORIES, record_count, p=[0.35, 0.65]),
        "income_band": random_generator.choice(INCOME_BRACKETS, record_count, p=[0.25, 0.30, 0.25, 0.15, 0.05]),
        "household_size": random_generator.integers(1, 8, record_count),
        "source_dataset": "seed_synthetic",
        "source_year": 2026,
    })


def generate_individuals(households_dataframe: pd.DataFrame, seed: int) -> pd.DataFrame:
    random_generator = np.random.default_rng(seed + 1)
    record_count = len(households_dataframe)

    income_to_education_bias = {
        "<10k": [0.35, 0.35, 0.20, 0.08, 0.02],
        "10k-25k": [0.20, 0.30, 0.30, 0.15, 0.05],
        "25k-50k": [0.10, 0.20, 0.35, 0.25, 0.10],
        "50k-100k": [0.05, 0.10, 0.25, 0.40, 0.20],
        "100k+": [0.02, 0.05, 0.13, 0.40, 0.40],
    }
    income_to_digital_mean = {
        "<10k": 0.15,
        "10k-25k": 0.30,
        "25k-50k": 0.50,
        "50k-100k": 0.70,
        "100k+": 0.85,
    }

    individual_rows = []
    for _, household in households_dataframe.iterrows():
        income_tier = household["income_band"]
        education_probabilities = income_to_education_bias[income_tier]
        digital_mean = income_to_digital_mean[income_tier]

        individual_rows.append({
            "household_id": household["id"],
            "age": int(random_generator.integers(18, 75)),
            "gender": random_generator.choice(GENDER_CATEGORIES),
            "education": random_generator.choice(EDUCATION_LEVELS, p=education_probabilities),
            "occupation": random_generator.choice(OCCUPATION_TYPES),
            "digital_access_score": float(np.clip(random_generator.normal(digital_mean, 0.15), 0.0, 1.0)),
        })

    individuals_dataframe = pd.DataFrame(individual_rows)
    individuals_dataframe.insert(0, "id", np.arange(1, record_count + 1))
    return individuals_dataframe


def generate_and_save_seed_data(record_count: int = 5000, output_directory: str = "./seed_output", seed: int = 42):
    os.makedirs(output_directory, exist_ok=True)
    households = generate_households(record_count, seed)
    individuals = generate_individuals(households, seed)

    households.to_csv(os.path.join(output_directory, "seed_households.csv"), index=False)
    individuals.to_csv(os.path.join(output_directory, "seed_individuals.csv"), index=False)
    return households, individuals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--out", type=str, default="./seed_output")
    parser.add_argument("--seed", type=int, default=42)
    arguments = parser.parse_args()

    generate_and_save_seed_data(arguments.n, arguments.out, arguments.seed)


if __name__ == "__main__":
    main()
