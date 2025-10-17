# sentiric-knowledge-indexing-service/app/ingesters/web_ingester.py
import httpx
import structlog
from bs4 import BeautifulSoup
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class WebIngester(BaseIngester):
    """Web sitelerinden metin içeriği çeken yükleyici."""

    async def load(self, source: DataSource) -> List[Document]:
        logger.info("Web sayfasından veri çekiliyor...", url=source.source_uri)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(source.source_uri, follow_redirects=True, timeout=30.0)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            # Gereksiz etiketleri temizle
            for script_or_style in soup(["script", "style", "nav", "footer", "header"]):
                script_or_style.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)

            if not clean_text:
                logger.warning("Web sayfasından metin içeriği çıkarılamadı.", url=source.source_uri)
                return []

            return [
                Document(
                    page_content=clean_text,
                    metadata={
                        "source_uri": source.source_uri,
                        "source_type": source.source_type,
                        "tenant_id": source.tenant_id
                    }
                )
            ]
        except httpx.HTTPStatusError as e:
            logger.error("Web sayfasına erişilemedi.", url=source.source_uri, status_code=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Web yükleyicide beklenmedik bir hata oluştu.", url=source.source_uri, error=str(e))
            return []