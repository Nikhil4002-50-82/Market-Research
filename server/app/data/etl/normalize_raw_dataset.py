import json
import pandas as pd


def load_mapping(mapping_path: str) -> dict:
    with open(mapping_path) as file:
        return json.load(file)


def read_raw_file(file_path: str, mapping: dict) -> pd.DataFrame:
    file_format = mapping["file_format"]

    if file_format == "csv":
        return pd.read_csv(file_path, **mapping.get("read_kwargs", {}))

    elif file_format == "excel":
        return pd.read_excel(file_path, **mapping.get("read_kwargs", {}))

    elif file_format == "fixed_width":
        column_specifications = [tuple(spec) for spec in mapping["colspecs"]]
        raw_column_names = mapping["raw_column_names"]
        read_kwargs = {"dtype": str, **mapping.get("read_kwargs", {})}
        return pd.read_fwf(
            file_path,
            colspecs=column_specifications,
            names=raw_column_names,
            **read_kwargs
        )

    else:
        raise ValueError(f"Unsupported file_format '{file_format}' in mapping config")


def apply_column_rename(dataframe: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    rename_map = mapping["column_rename"]
    missing_columns = [column for column in rename_map if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(
            f"Expected raw columns not found in file: {missing_columns}. "
            f"Available columns: {list(dataframe.columns)}."
        )
    renamed_df = dataframe.rename(columns=rename_map)
    passthrough_columns = [spec["output_column"] for spec in mapping.get("composite_lookups", [])]
    columns_to_keep = list(rename_map.values()) + [col for col in passthrough_columns if col in renamed_df.columns]
    return renamed_df[columns_to_keep]


def apply_value_recodes(dataframe: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    dataframe_copy = dataframe.copy()
    for column_name, recode_map in mapping.get("value_recodes", {}).items():
        if column_name not in dataframe_copy.columns:
            continue
        filtered_recode_map = {key: value for key, value in recode_map.items() if not key.startswith("_")}
        string_recode_map = {str(key): value for key, value in filtered_recode_map.items()}
        dataframe_copy[column_name] = dataframe_copy[column_name].astype(str).str.strip().map(string_recode_map)
        unmapped_count = dataframe_copy[column_name].isna().sum()
        if unmapped_count > 0:
            raise ValueError(
                f"{unmapped_count} values in column '{column_name}' did not match any key in the recode map."
            )
    return dataframe_copy


def apply_derived_fields(dataframe: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    dataframe_copy = dataframe.copy()
    for column_name, value in mapping.get("constant_fields", {}).items():
        dataframe_copy[column_name] = value
    return dataframe_copy


def apply_numeric_casts(dataframe: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    dataframe_copy = dataframe.copy()
    for column_name in mapping.get("numeric_fields", []):
        if column_name in dataframe_copy.columns:
            dataframe_copy[column_name] = pd.to_numeric(dataframe_copy[column_name], errors="raise")
    return dataframe_copy


def apply_composite_lookups(dataframe: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    dataframe_copy = dataframe.copy()
    for spec in mapping.get("composite_lookups", []):
        key_columns = spec["key_columns"]
        output_column = spec["output_column"]
        lookup = spec["lookup"]

        missing_columns = [col for col in key_columns if col not in dataframe_copy.columns]
        if missing_columns:
            raise ValueError(f"composite_lookups key_columns not found in dataframe: {missing_columns}")

        def resolve_composite_value(row):
            outer_key = str(row[key_columns[0]]).strip()
            inner_key = str(row[key_columns[1]]).strip()
            inner_map = lookup.get(outer_key)
            if inner_map is None:
                return None
            return inner_map.get(inner_key)

        dataframe_copy[output_column] = dataframe_copy.apply(resolve_composite_value, axis=1)
        unmapped_count = dataframe_copy[output_column].isna().sum()
        if unmapped_count > 0:
            unmapped_pairs = sorted(set(
                (row[key_columns[0]], row[key_columns[1]])
                for _, row in dataframe_copy[dataframe_copy[output_column].isna()].iterrows()
            ))
            raise ValueError(
                f"{unmapped_count} rows could not be resolved to a '{output_column}' via composite lookup. "
                f"Missing pairs: {unmapped_pairs[:10]}"
            )
    return dataframe_copy


def normalize_dataset(file_path: str, mapping_path: str) -> pd.DataFrame:
    mapping = load_mapping(mapping_path)
    raw_dataframe = read_raw_file(file_path, mapping)
    composite_dataframe = apply_composite_lookups(raw_dataframe, mapping)
    renamed_dataframe = apply_column_rename(composite_dataframe, mapping)
    recoded_dataframe = apply_value_recodes(renamed_dataframe, mapping)
    numeric_dataframe = apply_numeric_casts(recoded_dataframe, mapping)
    return apply_derived_fields(numeric_dataframe, mapping)


def validate_against_schema(dataframe: pd.DataFrame, required_columns: list[str]) -> list[str]:
    validation_problems = []
    missing_columns = set(required_columns) - set(dataframe.columns)
    if missing_columns:
        validation_problems.append(f"Missing required columns after normalization: {missing_columns}")
    for column_name in dataframe.columns:
        null_count = dataframe[column_name].isna().sum()
        if null_count > 0:
            validation_problems.append(f"Column '{column_name}' has {null_count} null values after normalization")
    return validation_problems
