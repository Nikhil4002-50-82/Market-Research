import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer

CATEGORICAL_FEATURES = ["state", "urban_rural", "income_band", "gender", "education", "occupation"]
NUMERICAL_FEATURES = ["age", "digital_access_score"]


def build_archetypes(
    population_dataframe: pd.DataFrame,
    number_of_clusters: int = 150,
    random_seed: int = 42
):
    if len(population_dataframe) < number_of_clusters:
        raise ValueError(
            f"number_of_clusters ({number_of_clusters}) cannot exceed population size ({len(population_dataframe)})"
        )

    feature_preprocessor = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("numerical", StandardScaler(), NUMERICAL_FEATURES),
    ])

    transformed_features = feature_preprocessor.fit_transform(population_dataframe)
    kmeans_model = KMeans(n_clusters=number_of_clusters, random_state=random_seed, n_init=10)
    cluster_labels = kmeans_model.fit_predict(transformed_features)

    clustered_dataframe = population_dataframe.copy()
    clustered_dataframe["archetype_id"] = cluster_labels

    cluster_weights = clustered_dataframe["archetype_id"].value_counts(normalize=True).to_dict()
    representative_archetypes = clustered_dataframe.groupby("archetype_id").first().reset_index()
    representative_archetypes["population_weight"] = representative_archetypes["archetype_id"].map(cluster_weights)

    return clustered_dataframe, representative_archetypes
