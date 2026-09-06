import pandas as pd
import pytest
from app.data.etl.normalize_raw_dataset import (
    normalize_dataset,
    validate_against_schema,
)

PLFS_MAPPING = "app/data/etl/mappings/plfs_person_mapping.json"
CENSUS_MAPPING = "app/data/etl/mappings/census_mapping.json"


def construct_plfs_record(sector, state, sex, age, edu, occ, district="18"):
    return (
        "01" + "12345" + "010" + "01" + "01" + str(sector) +
        state + district + "001" + "01" + "01" + "1" +
        "0001" + "00001" + "1" + "1" + "01" + "01" +
        str(sex) + f"{age:03d}" + edu + "11" + "01" + occ +
        "100" + "200" + "1234567890"
    )


@pytest.fixture
def plfs_fixed_width_file(tmp_path):
    rows = [
        construct_plfs_record(1, "29", 1, 34, "06", "003", district="01"),
        construct_plfs_record(2, "29", 2, 45, "10", "001", district="18"),
        construct_plfs_record(1, "29", 1, 60, "01", "006", district="09"),
    ]
    path = tmp_path / "sample_plfs_raw.txt"
    path.write_text("\n".join(rows) + "\n")
    return str(path)


@pytest.fixture
def census_excel_file(tmp_path):
    rows = [
        ["DISTRICT CENSUS HANDBOOK", None, None, None],
        ["Table PCA", None, None, None],
        ["Generated: 2011", None, None, None],
        ["", None, None, None],
        ["State/UT", "District", "Rural/Urban", "Total Population"],
        ["Karnataka", "Bangalore Urban", "Urban", 4],
        ["Bihar", "Patna", "Rural", 6],
    ]
    path = tmp_path / "sample_census_raw.xlsx"
    pd.DataFrame(rows).to_excel(str(path), index=False, header=False)
    return str(path)


def test_plfs_fixed_width_row_length_matches_colspec():
    row = construct_plfs_record(1, "10", 1, 34, "06", "003")
    assert len(row) == 71


def test_normalize_plfs_resolves_district_via_composite_lookup(plfs_fixed_width_file):
    dataframe = normalize_dataset(plfs_fixed_width_file, PLFS_MAPPING)
    assert dataframe.iloc[0]["district"] == "Belgaum"
    assert dataframe.iloc[1]["district"] == "Bangalore"
    assert dataframe.iloc[2]["district"] == "Uttara Kannada"


def test_normalize_plfs_raises_on_unmapped_state_district_pair(tmp_path):
    row = construct_plfs_record(1, "10", 1, 34, "06", "003", district="01")
    path = tmp_path / "bihar_plfs_raw.txt"
    path.write_text(row + "\n")
    with pytest.raises(ValueError, match="could not be resolved"):
        normalize_dataset(str(path), PLFS_MAPPING)


def test_normalize_plfs_raises_on_unmapped_district_within_known_state(tmp_path):
    row = construct_plfs_record(1, "29", 1, 34, "06", "003", district="99")
    path = tmp_path / "bad_district_plfs_raw.txt"
    path.write_text(row + "\n")
    with pytest.raises(ValueError, match="could not be resolved"):
        normalize_dataset(str(path), PLFS_MAPPING)


def test_normalize_plfs_produces_expected_columns(plfs_fixed_width_file):
    dataframe = normalize_dataset(plfs_fixed_width_file, PLFS_MAPPING)
    expected_columns = {"urban_rural", "state", "district", "gender", "age", "education", "occupation"}
    assert expected_columns.issubset(set(dataframe.columns))
    assert len(dataframe) == 3


def test_normalize_plfs_preserves_leading_zero_codes(plfs_fixed_width_file):
    dataframe = normalize_dataset(plfs_fixed_width_file, PLFS_MAPPING)
    assert dataframe.iloc[0]["education"] == "secondary"
    assert dataframe.iloc[1]["education"] == "graduate"
    assert dataframe.iloc[2]["education"] == "not_literate"


def test_normalize_plfs_recodes_sector_and_gender_correctly(plfs_fixed_width_file):
    dataframe = normalize_dataset(plfs_fixed_width_file, PLFS_MAPPING)
    assert dataframe.iloc[0]["urban_rural"] == "rural"
    assert dataframe.iloc[1]["urban_rural"] == "urban"
    assert dataframe.iloc[0]["gender"] == "male"
    assert dataframe.iloc[1]["gender"] == "female"


def test_normalize_plfs_age_is_cast_to_numeric(plfs_fixed_width_file):
    dataframe = normalize_dataset(plfs_fixed_width_file, PLFS_MAPPING)
    assert dataframe["age"].dtype.kind in ("i", "u")
    assert dataframe.iloc[0]["age"] == 34


def test_normalize_plfs_raises_on_unmapped_code(tmp_path):
    bad_row = construct_plfs_record(1, "29", 1, 34, "99", "003", district="18")
    path = tmp_path / "bad_plfs_raw.txt"
    path.write_text(bad_row + "\n")
    with pytest.raises(ValueError, match="did not match any key"):
        normalize_dataset(str(path), PLFS_MAPPING)


def test_normalize_census_excel_skips_junk_header_rows(census_excel_file):
    dataframe = normalize_dataset(census_excel_file, CENSUS_MAPPING)
    expected_columns = ["state", "district", "urban_rural", "household_size", "source_dataset", "source_year"]
    assert list(dataframe.columns) == expected_columns
    assert len(dataframe) == 2


def test_normalize_census_recodes_rural_urban(census_excel_file):
    dataframe = normalize_dataset(census_excel_file, CENSUS_MAPPING)
    assert set(dataframe["urban_rural"]) == {"rural", "urban"}


def test_validate_against_schema_flags_nulls():
    dataframe = pd.DataFrame({"state": ["Bihar", None], "age": [34, 45]})
    problems = validate_against_schema(dataframe, ["state", "age"])
    assert any("null" in p.lower() for p in problems)


def test_validate_against_schema_flags_missing_columns():
    dataframe = pd.DataFrame({"state": ["Bihar"]})
    problems = validate_against_schema(dataframe, ["state", "age"])
    assert any("missing" in p.lower() for p in problems)


def test_validate_against_schema_clean_data_has_no_problems():
    dataframe = pd.DataFrame({"state": ["Bihar", "Karnataka"], "age": [34, 45]})
    problems = validate_against_schema(dataframe, ["state", "age"])
    assert problems == []
