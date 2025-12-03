# sentiric-knowledge-indexing-service/app/ingesters/web_ingester.py
import httpx
import structlog
import re
from bs4 import BeautifulSoup, Comment
from typing import List
from .base import BaseIngester
from app.core.models import Document, DataSource

logger = structlog.get_logger(__name__)

class WebIngester(BaseIngester):
    """Web sitelerinden metin içeriği çeken optimize edilmiş yükleyici."""

    async def load(self, source: DataSource) -> List[Document]:
        logger.info("Web sayfasından veri çekiliyor...", url=source.source_uri)
        try:
            async with httpx.AsyncClient(verify=False) as client: # SSL hatalarını yoksay (internal siteler için)
                response = await client.get(
                    source.source_uri, 
                    follow_redirects=True, 
                    timeout=30.0,
                    headers={"User-Agent": "SentiricBot/1.0"}
                )
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            
            # 1. Gereksiz etiketleri temizle (Gürültü azaltma)
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg", "meta", "link"]):
                element.decompose()

            # 2. Yorum satırlarını temizle
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()

            # 3. Metni çıkar
            text = soup.get_text(separator="\n")
            
            # 4. Boşluk ve satır temizliği (Regex ile)
            # Çoklu yeni satırları tekil yeni satıra indir, satır başı/sonu boşluklarını sil
            cleaned_lines = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    cleaned_lines.append(stripped)
            
            clean_text = "\n".join(cleaned_lines)

            if not clean_text or len(clean_text) < 50: # Çok kısa içerikleri yoksay
                logger.warning("Web sayfası içeriği yetersiz veya boş.", url=source.source_uri)
                return []

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
            logger.error("Web sayfasına erişilemedi.", url=source.source_uri, status_code=e.response.status_code)
            return []
        except Exception as e:
            logger.error("Web yükleyicide beklenmedik bir hata oluştu.", url=source.source_uri, error=str(e))
            return []