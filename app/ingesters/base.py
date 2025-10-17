# sentiric-knowledge-indexing-service/app/ingesters/base.py
from abc import ABC, abstractmethod
from typing import List
from app.core.models import Document, DataSource

class BaseIngester(ABC):
    """Tüm veri yükleyiciler için soyut temel sınıf."""

    @abstractmethod
    async def load(self, source: DataSource) -> List[Document]:
        """
        Verilen veri kaynağından dokümanları yükler.
        """
        pass