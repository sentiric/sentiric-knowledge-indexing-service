# app/core/models.py
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class DataSource(BaseModel):
    """
    Veritabanından çekilecek bir veri kaynağını temsil eder.
    """

    id: int
    tenant_id: str
    source_type: Literal["postgres", "web", "file"]
    source_uri: str
    last_indexed_at: Optional[datetime] = None


class Document:
    """
    Bir veri kaynağından yüklenen ve işlenmeye hazır bir dokümanı temsil eder.
    """

    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata

    def __repr__(self):
        return f"Document(metadata={self.metadata})"


class ReindexRequest(BaseModel):
    """
    /reindex endpoint'i için istek gövdesi modeli.
    """

    tenant_id: Optional[str] = None
