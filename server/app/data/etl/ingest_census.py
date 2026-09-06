from app.core.database import SessionLocal
from app.data.models import Household
from app.data.etl.normalize_raw_dataset import normalize_dataset, validate_against_schema

DEFAULT_MAPPING_PATH = "app/data/etl/mappings/census_mapping.json"
REQUIRED_COLUMNS = ["state", "district", "urban_rural", "household_size"]


def ingest_census_file(file_path: str, mapping_path: str = DEFAULT_MAPPING_PATH) -> int:
    normalized_dataframe = normalize_dataset(file_path, mapping_path)

    validation_problems = validate_against_schema(normalized_dataframe, REQUIRED_COLUMNS)
    if validation_problems:
        raise ValueError(f"Census file failed validation after normalization: {validation_problems}")

    database_session = SessionLocal()
    try:
        for _, row in normalized_dataframe.iterrows():
            household_record = Household(
                state=row["state"],
                district=row["district"],
                urban_rural=row["urban_rural"],
                income_band=row.get("income_band", "unknown"),
                household_size=row["household_size"],
                source_dataset=row["source_dataset"],
                source_year=row["source_year"],
            )
            database_session.add(household_record)
        database_session.commit()
        return len(normalized_dataframe)
    finally:
        database_session.close()
