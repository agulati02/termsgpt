from pydantic import BaseModel, Field
from typing import List


class Section(BaseModel):
    heading: str
    char_offset: int = Field(alias="charOffset")

    model_config = {"populate_by_name": True}


class IngestRequest(BaseModel):
    text: str
    sections: List[Section]


class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int


class QueryRequest(BaseModel):
    doc_id: str
    query: str


class Citation(BaseModel):
    heading: str
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation]


class ErrorResponse(BaseModel):
    detail: str
