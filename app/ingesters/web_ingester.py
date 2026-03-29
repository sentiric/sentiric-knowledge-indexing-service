# app/ingesters/web_ingester.py
import httpx
import structlog
import re
from bs4 import BeautifulSoup, Comment
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class WebIngester(BaseIngester):

    async def load(self, source: DataSource) -> List[Document]:
        logger.info("Web sayfasından veri çekiliyor...", event="WEB_INGEST_START", url=source.source_uri)
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    source.source_uri, 
                    follow_redirects=True, 
                    timeout=30.0,
                    headers={"User-Agent": "SentiricBot/1.0"}
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg", "meta", "link"]):
                element.decompose()

            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            text = soup.get_text(separator="\n")
            
            cleaned_lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    cleaned_lines.append(stripped)
            
            clean_text = "\n".join(cleaned_lines)

            if not clean_text or len(clean_text) < 50:
                logger.warning("Web sayfası içeriği yetersiz veya boş.", event="WEB_INGEST_EMPTY", url=source.source_uri)
                return []

            logger.info("Web sayfası başarıyla çekildi.", event="WEB_INGEST_SUCCESS", url=source.source_uri)

            return [
                Document(
                    page_content=clean_text,
                    metadata={
                        "source_uri": source.source_uri,
                        "source_type": source.source_type,
                        "tenant_id": source.tenant_id,
                        "title": soup.title.string if soup.title else source.source_uri
                    }
                )
            ]
        except httpx.HTTPStatusError as e:
            logger.error("Web sayfasına erişilemedi.", event="WEB_INGEST_HTTP_ERROR", url=source.source_uri, status_code=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Web yükleyicide beklenmedik bir hata oluştu.", event="WEB_INGEST_FATAL_ERROR", url=source.source_uri, error=str(e))
            return []