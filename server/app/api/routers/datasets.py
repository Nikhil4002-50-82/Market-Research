import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_database_session
from app.data.etl.ingest_census import ingest_census_file
from app.data.etl.ingest_nsso import ingest_nsso_file
from app.schemas.datasets import IngestResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])

RAW_DATA_DIRECTORY = "app/data/raw"
os.makedirs(RAW_DATA_DIRECTORY, exist_ok=True)

SUPPORTED_SOURCES = {
    "census": ingest_census_file,
    "nsso": ingest_nsso_file,
}


@router.post("/ingest", response_model=IngestResponse)
def ingest_dataset(
    source: str,
    file: UploadFile = File(...),
    database_session: Session = Depends(get_database_session),
):
    source_key = source.lower().strip()
    if source_key not in SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source '{source}'. Supported: {list(SUPPORTED_SOURCES.keys())}"
        )

    saved_filename = f"{uuid.uuid4()}_{file.filename}"
    saved_file_path = os.path.join(RAW_DATA_DIRECTORY, saved_filename)
    with open(saved_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ingest_function = SUPPORTED_SOURCES[source_key]
    rows_count = ingest_function(saved_file_path)

    return IngestResponse(
        source=source_key,
        rows_ingested_from=file.filename or saved_filename,
        status="completed",
        rows_count=rows_count,
    )


@router.get("/sources")
def list_supported_sources():
    return {"supported_sources": list(SUPPORTED_SOURCES.keys())}
