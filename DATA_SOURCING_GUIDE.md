# Data Sourcing Guide — What to Download and How

This is the concrete, step-by-step companion to the backend implementation plan. It covers exactly which datasets to pull, where from, what registration is needed, and what format to expect — so you can go from "nothing downloaded" to "raw files ready for the normalizer" without guessing.

**Recommended order**: start with PLFS (richest, free, moderate registration). Add one Census table for demographic cross-checks. Add NFHS last, once the core pipeline is working, for asset/health depth.

---

## 1. PLFS / NSSO (Periodic Labour Force Survey) — start here

**What it gives you**: employment status, income proxies (via Current Weekly Status), education, occupation, industry, age, sex, state/district, urban/rural — the backbone of your `Individual` table.

**Format you'll actually get**: fixed-width text files (no headers, no delimiters) plus a separate layout/data-dictionary file explaining byte positions and codes. This is exactly the format `app/data/etl/normalize_raw_dataset.py` and `plfs_person_mapping.json` are built for.

### Steps
1. Go to **microdata.gov.in** (MoSPI's official microdata portal).
2. Click **Register** (top right) — free account, just email + basic details.
3. Verify your email and log in.
4. Go to **Catalog** → search **"PLFS"**.
5. Pick the most recent annual round available (rounds are typically named like "PLFS 2023-24"). Click into it.
6. You'll see a list of files — look for:
   - The **person-level file** (often named something like `CPERV1` or similar — this is what our `plfs_person_mapping.json` is built against)
   - The **household-level file** (household composition, often `CHHV1`)
   - The **layout/data dictionary file** (critical — this tells you the exact byte positions and code meanings for that specific round; don't skip downloading this)
7. Some files download immediately; others require clicking "Get Microdata" and a short access request form (stating research/analysis purpose) — approval is typically fast since it's not gated behind an academic-only policy.
8. Unzip everything into one folder — you'll have `.txt` (fixed-width data) files and layout files (often `.xlsx` or `.doc`/`.pdf`).

### Before running the ETL
Open the layout file and check it against `app/data/etl/mappings/plfs_person_mapping.json`:
- Confirm the **colspecs** (byte positions) match — they can shift slightly between rounds.
- Confirm the **education** and **occupation** code tables in the mapping — the ones shipped are placeholders and need to match your round's actual codebook.
- Confirm **state/district codes** if you're working with states beyond Karnataka (only Karnataka is pre-filled in the mapping as a verified example, sourced from MoSPI's own Appendix-II document).

---

## 2. Census of India — for demographic cross-checks

**What it gives you**: district-level age/sex/literacy/occupation distributions, household size, urban/rural splits — good for validating that your PLFS-derived population isn't skewed relative to the actual census counts.

**Important caveat**: the last *completed* census is **2011**. The next census was delayed and is currently underway (house-listing phase started in 2026, enumeration expected in 2027) — so 2011 is still the most recent full dataset available, and you should treat it as a structural/proportional reference rather than assuming absolute numbers are current.

**Format you'll get**: mostly Excel or PDF tables (District Census Handbooks, Primary Census Abstract) — not clean CSVs. Expect junk header rows before the real data starts (title, table number, generation date), which is exactly what `census_mapping.json`'s `skiprows` setting handles.

### Steps
1. Go to **censusindia.gov.in**.
2. Navigate to **Census 2011 Data** → **District Census Handbooks** (or **Primary Census Abstract** for state/district summary tables).
3. Pick your state(s) of interest, download the relevant table (e.g., "Primary Census Abstract" for age/sex/literacy, or "Village and Town Directory" for more granular detail).
4. No registration required — these are direct public downloads.
5. Open the file once downloaded and note: how many header rows precede the actual data, and what the column names actually say (they vary by table type) — you'll adjust `census_mapping.json`'s `column_rename` and `read_kwargs.skiprows` to match.

---

## 3. NFHS (National Family Health Survey) — add once the core pipeline works

**What it gives you**: household asset ownership, health indicators, more detailed household composition — good for adding a richer "digital access proxy" or asset-based wealth indicator beyond PLFS's income bands.

**Format you'll get**: SPSS (`.sav`), Stata (`.dta`), or flat ASCII files, plus a codebook — will need `pandas.read_spss()` or `pyreadstat` (for `.sav`) or `pandas.read_stata()` (for `.dta`) rather than the CSV/Excel/fixed-width paths already built; you'd add a fourth `file_format` branch to `normalize_raw_dataset.py` if you go this route.

### Steps
1. Go to **dhsprogram.com/data** (the DHS Program administers NFHS internationally).
2. Register for a free account.
3. Once logged in, go to **Data → Request a Dataset**, search for **India** and select **NFHS-5 (2019-21)** (most recent full round).
4. Fill in the short project request form — a title and 1-2 sentence description of your use case (e.g., "market research population modeling for a startup") is sufficient; this is not a strict academic-only gate.
5. Approval typically arrives within about 24 hours (business days) via email with download instructions.
6. Download the **Household Recode** and **Individual Recode** files for India — these are the two you'll want for household asset ownership and individual-level demographic detail.

---

## 4. Supplementary sources (optional, add as needed)

| Source | What it adds | Access |
|---|---|---|
| **TRAI** (trai.gov.in) | Telecom subscriber counts, data usage by circle/state | Free, public reports — useful for building a real `digital_access_score` instead of the current placeholder constant |
| **IAMAI-Kantar ICUBE** | Internet penetration, device usage by urban/rural | Usually a free summary PDF report published annually — search "IAMAI ICUBE report [year]" |
| **RBI** (rbi.org.in) | Household financial behavior, digital payments | Free, public reports |
| **NPCI/UPI dashboards** | Real transaction volume by state/category | Public dashboards on npci.org.in |

None of these need registration — they're published reports/dashboards, useful for filling the `digital_access_score` gap flagged in the NSSO ingestion script, by merging in a state-level penetration rate as a proxy.

---

## 5. What to do once files are downloaded

1. Save raw files into a local `app/data/raw/` folder (keep this out of version control — these files can be large and some sources have redistribution restrictions).
2. Open each layout/codebook file and update the corresponding mapping config (`plfs_person_mapping.json`, `census_mapping.json`, or a new one you create for NFHS) to match the actual column positions/names/codes in front of you.
3. Run the normalizer against a **small sample first** (e.g., the first few hundred lines of a fixed-width file) to catch mapping mismatches quickly, before running it against the full file — the normalizer is designed to fail loudly on the first unmapped code or missing column, which is exactly what you want during this calibration step.
4. Once a small sample passes cleanly, run the full file through `ingest_census.py` / `ingest_nsso.py`.

## 6. A note on realism vs. effort

You don't need all of these before your first working pipeline run. **PLFS alone** gives you income, education, occupation, age, sex, urban/rural, and (for Karnataka specifically) district — enough to generate a meaningfully realistic synthetic population and run the full simulation loop end-to-end. Treat Census and NFHS as enrichment passes once the core loop is proven, not prerequisites to starting.
