import os
import sys
import time
import pandas as pd
import numpy as np
from sqlalchemy import text
from app.core.database import engine, SessionLocal, initialize_database
from app.data.models import Household, Individual

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")

BASE_PLFS_DIR = os.path.join(DATA_DIR, "PLFS  NSSO (Periodic Labour Force Survey)")
if not os.path.exists(BASE_PLFS_DIR):
    BASE_PLFS_DIR = os.path.join(ROOT_DIR, "PLFS  NSSO (Periodic Labour Force Survey)")

BASE_CENSUS_DIR = os.path.join(DATA_DIR, "Census_2011")
if not os.path.exists(BASE_CENSUS_DIR):
    BASE_CENSUS_DIR = os.path.join(ROOT_DIR, "Census_2011")

CSV_DIR = os.path.join(BASE_PLFS_DIR, "extracted", "Data_in_CSV")


def ensure_csvs_extracted():
    chhv_path = os.path.join(CSV_DIR, "chhv12025.csv")
    cper_path = os.path.join(CSV_DIR, "cperv12025.csv")
    if not (os.path.exists(chhv_path) and os.path.exists(cper_path)):
        zip_path = os.path.join(BASE_PLFS_DIR, "Data_in_CSV.zip")
        if os.path.exists(zip_path):
            import zipfile
            print(f"Extracting raw survey CSVs from {zip_path}...")
            extract_target = os.path.join(BASE_PLFS_DIR, "extracted")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_target)
            print("Auto-extraction complete.")
        else:
            raise FileNotFoundError(f"Neither extracted CSVs nor {zip_path} found.")

STATE_EXCEL = os.path.join(BASE_PLFS_DIR, "Indian_States_and_UTs_CodeName.xlsx")
DIST_EXCEL = os.path.join(BASE_PLFS_DIR, "Indian_Districts_CodeName.xlsx")
CENSUS_EXCEL = os.path.join(BASE_CENSUS_DIR, "A-1_NO_OF_VILLAGES_TOWNS_HOUSEHOLDS_POPULATION_AND_AREA.xlsx")

KEY_COLS = ["qtr", "st", "dc", "nss_reg", "strm", "sstrm", "mfsu", "sss", "ssu"]


def load_geographic_lookups():
    print("Loading official geographic lookups...")
    df_st = pd.read_excel(STATE_EXCEL)
    state_map = dict(zip(df_st["State Code"].astype(str).str.zfill(2), df_st["State/UT Name"].astype(str).str.strip()))

    df_dt = pd.read_excel(DIST_EXCEL)
    dist_map = {}
    for _, r in df_dt.iterrows():
        s = str(r["State Code"]).strip().zfill(2)
        d = str(r["District Code"]).strip().zfill(2)
        dist_map[(s, d)] = str(r["District Name"]).strip()

    print(f"Loaded {len(state_map)} States/UTs and {len(dist_map)} District mappings.")
    return state_map, dist_map


def map_income_band(hce: float) -> str:
    if pd.isna(hce) or hce <= 0:
        return "10k-25k"
    if hce < 10000:
        return "<10k"
    elif hce < 25000:
        return "10k-25k"
    elif hce < 50000:
        return "25k-50k"
    elif hce < 100000:
        return "50k-100k"
    else:
        return "100k+"


def map_education(code) -> str:
    try:
        c = int(code)
    except (ValueError, TypeError):
        return "secondary"
    if c <= 1:
        return "none"
    elif c in [2, 3, 4]:
        return "primary"
    elif c == 5:
        return "middle"
    elif c in [6, 7]:
        return "secondary"
    elif c == 8:
        return "diploma"
    elif c in [10, 12]:
        return "graduate"
    elif c in [11, 13]:
        return "postgraduate"
    return "secondary"


def map_occupation(acws) -> str:
    try:
        c = int(acws)
    except (ValueError, TypeError):
        return "salaried_private"
    if c in [11, 12]:
        return "self_employed"
    elif c == 21:
        return "informal_trade"
    elif c == 31:
        return "salaried_private"
    elif c in [41, 42, 51]:
        return "casual_labour"
    elif c == 81:
        return "unemployed"
    elif c == 91:
        return "student"
    elif c in [92, 93]:
        return "homemaker"
    elif c >= 94:
        return "retired_other"
    return "salaried_private"


def compute_digital_access(urban_rural: str, education: str, income_band: str, age: int) -> float:
    score = 0.35
    if urban_rural == "urban":
        score += 0.15
    if education in ["graduate", "postgraduate"]:
        score += 0.25
    elif education in ["secondary", "diploma"]:
        score += 0.15
    elif education == "none":
        score -= 0.15

    if income_band in ["100k+", "50k-100k"]:
        score += 0.20
    elif income_band == "25k-50k":
        score += 0.10
    elif income_band == "<10k":
        score -= 0.10

    if age < 30:
        score += 0.10
    elif age > 55:
        score -= 0.10

    return round(float(np.clip(score, 0.05, 0.98)), 2)


def reset_database_tables():
    print("Clearing previous records in households and individuals...")
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM individuals;"))
        session.execute(text("DELETE FROM households;"))
        session.commit()
    finally:
        session.close()


def ingest_census_baseline(state_map: dict):
    print("\n--- Ingesting Census 2011 District Baselines ---")
    df = pd.read_excel(CENSUS_EXCEL, skiprows=4, header=None)
    df_dist = df[df[3] == "DISTRICT"].copy()

    records = []
    for _, r in df_dist.iterrows():
        st_code = str(int(r[0])).zfill(2) if pd.notna(r[0]) else "00"
        st_name = state_map.get(st_code, str(r[4]))
        dist_name = str(r[4]).strip()
        ru_val = str(r[5]).strip()
        if ru_val not in ["Rural", "Urban"]:
            continue

        hh_count = float(r[9]) if pd.notna(r[9]) and r[9] > 0 else 1.0
        pop_count = float(r[10]) if pd.notna(r[10]) and r[10] > 0 else 4.0
        avg_hh_size = max(1, min(12, int(round(pop_count / hh_count))))

        records.append({
            "state": st_name,
            "district": dist_name,
            "urban_rural": ru_val.lower(),
            "income_band": "unknown",
            "household_size": avg_hh_size,
            "source_dataset": "census",
            "source_year": 2011,
        })

    session = SessionLocal()
    try:
        session.bulk_insert_mappings(Household, records)
        session.commit()
        print(f"Successfully inserted {len(records)} Census 2011 baseline household records.")
    finally:
        session.close()


def ingest_plfs_microdata(state_map: dict, dist_map: dict, target_hh_count: int = 50000):
    print(f"\n--- Ingesting PLFS 2025 Microdata (Target: {target_hh_count} Households) ---")
    start_time = time.time()

    ensure_csvs_extracted()

    # Step 1: Read and sample households from disk CSV
    chh_file = os.path.join(CSV_DIR, "chhv12025.csv")
    use_cols = KEY_COLS + ["sec", "hh_size", "hce_tot"]
    df_hh_all = pd.read_csv(chh_file, usecols=use_cols)

    print(f"Loaded {len(df_hh_all)} total PLFS household records from CSV.")
    if len(df_hh_all) > target_hh_count:
        df_hh = df_hh_all.sample(n=target_hh_count, random_state=42).copy()
    else:
        df_hh = df_hh_all.copy()

    df_hh["hh_key"] = df_hh[KEY_COLS].astype(str).agg("_".join, axis=1)
    selected_hh_keys = set(df_hh["hh_key"])

    # Prepare household rows
    hh_records = []
    hh_metadata_map = {}

    for _, r in df_hh.iterrows():
        k = r["hh_key"]
        s_code = str(r["st"]).strip().zfill(2)
        d_code = str(r["dc"]).strip().zfill(2)
        st_name = state_map.get(s_code, f"State {s_code}")
        dist_name = dist_map.get((s_code, d_code), f"District {d_code}")
        ur = "rural" if int(r["sec"]) == 1 else "urban"
        inc = map_income_band(float(r["hce_tot"]) if pd.notna(r["hce_tot"]) else 0)
        hh_sz = int(r["hh_size"]) if pd.notna(r["hh_size"]) and r["hh_size"] > 0 else 4

        hh_dict = {
            "state": st_name,
            "district": dist_name,
            "urban_rural": ur,
            "income_band": inc,
            "household_size": hh_sz,
            "source_dataset": "plfs",
            "source_year": 2025,
        }
        hh_records.append(hh_dict)
        hh_metadata_map[k] = (st_name, dist_name, ur, inc)

    # Bulk insert households
    print(f"Inserting {len(hh_records)} PLFS households into SQLite...")
    session = SessionLocal()
    try:
        session.bulk_insert_mappings(Household, hh_records)
        session.commit()
    finally:
        session.close()

    # Query back newly created household IDs
    session = SessionLocal()
    try:
        hh_id_query = session.execute(
            text("SELECT id FROM households WHERE source_dataset = 'plfs' ORDER BY id ASC")
        )
        created_hh_ids = [row[0] for row in hh_id_query.fetchall()]
    finally:
        session.close()

    hh_key_list = df_hh["hh_key"].tolist()
    key_to_db_id = dict(zip(hh_key_list, created_hh_ids))

    # Read CPER CSV directly from disk in fast chunks
    print("Reading and matching adult individuals (age >= 18) from CPER CSV...")
    cper_file = os.path.join(CSV_DIR, "cperv12025.csv")
    individual_records = []
    cper_cols = KEY_COLS + ["srl", "sex", "age", "gedu_lvl", "acws"]

    for chunk in pd.read_csv(cper_file, usecols=cper_cols, chunksize=150000):
        chunk["hh_key"] = chunk[KEY_COLS].astype(str).agg("_".join, axis=1)
        matched = chunk[chunk["hh_key"].isin(selected_hh_keys)]
        if len(matched) == 0:
            continue

        adults = matched[matched["age"] >= 18]
        for _, p in adults.iterrows():
            k = p["hh_key"]
            hh_id = key_to_db_id.get(k)
            if not hh_id:
                continue

            _, _, ur, inc = hh_metadata_map.get(k, ("India", "District", "urban", "10k-25k"))
            age = int(p["age"])
            gender = "male" if int(p["sex"]) == 1 else ("female" if int(p["sex"]) == 2 else "transgender")
            edu = map_education(p["gedu_lvl"])
            occ = map_occupation(p["acws"])
            dig = compute_digital_access(ur, edu, inc, age)

            individual_records.append({
                "household_id": hh_id,
                "age": age,
                "gender": gender,
                "education": edu,
                "occupation": occ,
                "digital_access_score": dig,
            })

    print(f"Inserting {len(individual_records)} adult individuals into SQLite...")
    session = SessionLocal()
    try:
        chunk_size = 25000
        for i in range(0, len(individual_records), chunk_size):
            session.bulk_insert_mappings(Individual, individual_records[i:i + chunk_size])
            session.commit()
            print(f"  Inserted {min(i + chunk_size, len(individual_records))}/{len(individual_records)} individuals...")
    finally:
        session.close()

    elapsed = time.time() - start_time
    print(f"\n==========================================")
    print(f"Ingestion Complete in {elapsed:.1f}s")
    print(f"PLFS Households Ingested: {len(hh_records)}")
    print(f"PLFS Adult Individuals Ingested: {len(individual_records)}")
    print(f"==========================================")


if __name__ == "__main__":
    initialize_database()
    st_map, dt_map = load_geographic_lookups()
    reset_database_tables()
    ingest_census_baseline(st_map)
    ingest_plfs_microdata(st_map, dt_map, target_hh_count=50000)
