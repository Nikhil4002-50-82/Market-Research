from pydantic import BaseModel


class IngestResponse(BaseModel):
    source: str
    rows_ingested_from: str
    status: str
    rows_count: int
