import pandas as pd
import pytest
from app.simulation.population_generator import join_seed_data, sample_synthetic_population
from app.simulation.clustering import build_archetypes


@pytest.fixture
def synthetic_population_sample():
    households = pd.read_csv("seed_output/seed_households.csv")
    individuals = pd.read_csv("seed_output/seed_individuals.csv")
    base_dataframe = join_seed_data(households, individuals)
    return sample_synthetic_population(base_dataframe, sample_size=5000, random_seed=42)


def test_build_archetypes_produces_requested_cluster_count(synthetic_population_sample):
    _, representatives = build_archetypes(synthetic_population_sample, number_of_clusters=50, random_seed=42)
    assert len(representatives) == 50


def test_archetype_weights_sum_to_one(synthetic_population_sample):
    _, representatives = build_archetypes(synthetic_population_sample, number_of_clusters=50, random_seed=42)
    assert abs(representatives["population_weight"].sum() - 1.0) < 1e-6


def test_archetype_weights_are_positive(synthetic_population_sample):
    _, representatives = build_archetypes(synthetic_population_sample, number_of_clusters=50, random_seed=42)
    assert (representatives["population_weight"] > 0).all()


def test_build_archetypes_raises_if_more_clusters_than_rows(synthetic_population_sample):
    with pytest.raises(ValueError):
        build_archetypes(
            synthetic_population_sample,
            number_of_clusters=len(synthetic_population_sample) + 1
        )
