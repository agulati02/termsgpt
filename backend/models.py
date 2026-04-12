from pydantic import BaseModel, Field
from typing import List


class Section(BaseModel):
    heading: str
    char_offset: int = Field(alias="charOffset")

    model_config = {"populate_by_name": True}


class IngestRequest(BaseModel):
    text: str
    sections: List[Section]


class RiskCitation(BaseModel):
    heading: str
    snippet: str


class RiskEntry(BaseModel):
    category: str
    severity: str  # "🔴" | "🟡" | "🟢"
    finding: str
    citation: RiskCitation


class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int
    risk_report: List[RiskEntry] = []


class QueryRequest(BaseModel):
    doc_id: str
    query: str


class Citation(BaseModel):
    heading: str
    snippet: str
    relevance_score: float = 0.0


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]


class ErrorResponse(BaseModel):
    detail: str
