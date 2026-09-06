import pandas as pd
import pytest
from app.simulation.population_generator import join_seed_data, sample_synthetic_population


@pytest.fixture
def seed_dataframes():
    households = pd.read_csv("seed_output/seed_households.csv")
    individuals = pd.read_csv("seed_output/seed_individuals.csv")
    return households, individuals


def test_join_seed_data_has_expected_columns(seed_dataframes):
    households, individuals = seed_dataframes
    joined = join_seed_data(households, individuals)
    expected_columns = {
        "state", "urban_rural", "income_band", "age", "gender",
        "education", "occupation", "digital_access_score"
    }
    assert expected_columns.issubset(set(joined.columns))
    assert len(joined) == len(individuals)


def test_sample_synthetic_population_produces_requested_size(seed_dataframes):
    households, individuals = seed_dataframes
    base_dataframe = join_seed_data(households, individuals)
    result = sample_synthetic_population(base_dataframe, sample_size=10000, random_seed=42)
    assert len(result) == 10000


def test_sample_synthetic_population_preserves_value_ranges(seed_dataframes):
    households, individuals = seed_dataframes
    base_dataframe = join_seed_data(households, individuals)
    result = sample_synthetic_population(base_dataframe, sample_size=5000, random_seed=42)

    assert result["digital_access_score"].between(0.0, 1.0).all()
    assert result["age"].between(18, 100).all()
    assert set(result["state"].unique()).issubset(set(base_dataframe["state"].unique()))


def test_sample_synthetic_population_is_reproducible_with_same_seed(seed_dataframes):
    households, individuals = seed_dataframes
    base_dataframe = join_seed_data(households, individuals)
    first_sample = sample_synthetic_population(base_dataframe, sample_size=1000, random_seed=99)
    second_sample = sample_synthetic_population(base_dataframe, sample_size=1000, random_seed=99)
    pd.testing.assert_frame_equal(first_sample, second_sample)


def test_sample_synthetic_population_raises_on_empty_input():
    empty_dataframe = pd.DataFrame(columns=[
        "state", "urban_rural", "income_band", "age", "gender",
        "education", "occupation", "digital_access_score"
    ])
    with pytest.raises(ValueError):
        sample_synthetic_population(empty_dataframe, sample_size=100)
