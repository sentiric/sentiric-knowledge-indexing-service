# app/ingesters/web_ingester.py
import httpx
import structlog
from bs4 import BeautifulSoup, Comment
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger()

class WebIngester(BaseIngester):
    async def load(self, source: DataSource) -> List[Document]:
        logger.info(f"Scraping web page: {source.source_uri}", event_name="INGEST_WEB_FETCH")
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
                logger.warn("Web page content is empty or too short.", event_name="INGEST_WEB_EMPTY", url=source.source_uri)
                return []

            logger.info("Successfully scraped web page.", event_name="INGEST_WEB_SUCCESS", length=len(clean_text))
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
            logger.error(f"HTTP error fetching web page: {e.response.status_code}", event_name="INGEST_WEB_HTTP_ERROR", status_code=e.response.status_code)
            return []
        except Exception as e:
            logger.error(f"Unexpected error in web ingester: {e}", event_name="INGEST_WEB_ERROR", exc_info=True)
            return []