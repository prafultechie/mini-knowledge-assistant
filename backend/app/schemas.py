from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.config import settings


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=settings.max_document_chars)

    @classmethod
    def clean_fields(cls, values):
        return values


class DocumentResponse(BaseModel):
    document_id: int
    title: str
    created_at: datetime
    status: str = "indexed"


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: int
    title: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    page: int
    page_size: int
    total: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.max_question_chars)


class SourceItem(BaseModel):
    document_id: int
    title: str
    chunk_id: int
    excerpt: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
