from app.core.database import SessionLocal
from app.data.models import Household, Individual
from app.data.etl.normalize_raw_dataset import normalize_dataset, validate_against_schema

DEFAULT_MAPPING_PATH = "app/data/etl/mappings/plfs_person_mapping.json"
REQUIRED_COLUMNS = ["urban_rural", "state", "district", "gender", "age", "education", "occupation"]


def ingest_nsso_file(file_path: str, mapping_path: str = DEFAULT_MAPPING_PATH) -> int:
    normalized_dataframe = normalize_dataset(file_path, mapping_path)

    validation_problems = validate_against_schema(normalized_dataframe, REQUIRED_COLUMNS)
    if validation_problems:
        raise ValueError(f"NSSO/PLFS file failed validation after normalization: {validation_problems}")

    database_session = SessionLocal()
    try:
        for _, row in normalized_dataframe.iterrows():
            household_record = Household(
                state=row["state"],
                district=row["district"],
                urban_rural=row["urban_rural"],
                income_band="unknown",
                household_size=1,
                source_dataset=row["source_dataset"],
                source_year=row["source_year"],
            )
            database_session.add(household_record)
            database_session.flush()

            individual_record = Individual(
                household_id=household_record.id,
                age=int(row["age"]),
                gender=row["gender"],
                education=row["education"],
                occupation=row["occupation"],
                digital_access_score=0.5,
            )
            database_session.add(individual_record)

        database_session.commit()
        return len(normalized_dataframe)
    finally:
        database_session.close()
