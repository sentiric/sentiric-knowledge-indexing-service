# sentiric-knowledge-indexing-service/app/core/chunking.py
from typing import List

def split_text_into_chunks(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    """
    Basit bir metin parçalama (chunking) fonksiyonu.
    """
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    
    return chunks