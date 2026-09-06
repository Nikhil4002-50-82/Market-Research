import json
import numpy as np
import pandas as pd
from app.data.models import SyntheticProfile


def build_conditional_distributions(database_session) -> pd.DataFrame:
    query = """
        SELECT h.state, h.urban_rural, h.income_band, i.age, i.gender,
               i.education, i.occupation, i.digital_access_score
        FROM households h JOIN individuals i ON i.household_id = h.id
    """
    return pd.read_sql(query, database_session.bind)


def join_seed_data(households_dataframe: pd.DataFrame, individuals_dataframe: pd.DataFrame) -> pd.DataFrame:
    merged_dataframe = individuals_dataframe.merge(
        households_dataframe,
        left_on="household_id",
        right_on="id",
        suffixes=("_ind", "_hh")
    )
    return merged_dataframe[[
        "state", "urban_rural", "income_band", "age", "gender",
        "education", "occupation", "digital_access_score"
    ]]


def sample_synthetic_population(
    base_dataframe: pd.DataFrame,
    sample_size: int,
    random_seed: int = 42
) -> pd.DataFrame:
    if len(base_dataframe) == 0:
        raise ValueError("base_dataframe is empty — no data available to sample from")

    random_generator = np.random.default_rng(random_seed)
    sampled_indices = random_generator.choice(len(base_dataframe), size=sample_size, replace=True)
    sampled_dataframe = base_dataframe.iloc[sampled_indices].reset_index(drop=True)

    sampled_dataframe["digital_access_score"] = np.clip(
        sampled_dataframe["digital_access_score"] + random_generator.normal(0, 0.02, sample_size),
        0.0,
        1.0
    )
    sampled_dataframe["age"] = np.clip(
        sampled_dataframe["age"] + random_generator.integers(-1, 2, sample_size),
        18,
        100
    )
    return sampled_dataframe


def persist_population(database_session, run_id: str, population_dataframe: pd.DataFrame):
    records = [
        SyntheticProfile(run_id=run_id, attributes=json.loads(row.to_json()))
        for _, row in population_dataframe.iterrows()
    ]
    database_session.bulk_save_objects(records)
    database_session.commit()
