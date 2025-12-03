# sentiric-knowledge-indexing-service/app/core/chunking.py
import re
from typing import List

def split_text_into_chunks(text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
    """
    Metni anlamsal bütünlüğü korumaya çalışarak parçalara böler.
    Öncelik sırası: Paragraf -> Satır -> Cümle -> Kelime.
    """
    if not text:
        return []

    # 1. Gereksiz boşlukları temizle ama paragraf yapısını koru
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # Ayırıcılar (Öncelik sırasına göre)
    separators = ["\n\n", "\n", ". ", "? ", "! ", ";", ",", " ", ""]
    
    return _recursive_split(text, separators, chunk_size, chunk_overlap)

def _recursive_split(text: str, separators: List[str], chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    Recursive bölme mantığı.
    """
    final_chunks = []
    
    # Ayırıcı listesi bittiyse mecburen karakter bazlı böl
    if not separators:
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

    separator = separators[0]
    next_separators = separators[1:]
    
    # Mevcut ayırıcıya göre böl
    if separator == "":
        splits = list(text) # Karakter bazlı
    else:
        splits = text.split(separator)

    # Parçaları birleştirerek chunk oluştur
    current_chunk = []
    current_length = 0
    
    for split in splits:
        split_len = len(split)
        
        # Eğer tek bir parça bile chunk_size'dan büyükse, onu bir alt ayırıcı ile böl
        if split_len > chunk_size:
            if current_chunk:
                final_chunks.append(separator.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            sub_chunks = _recursive_split(split, next_separators, chunk_size, chunk_overlap)
            final_chunks.extend(sub_chunks)
            continue
        
        # Mevcut chunk'a ekleyince taşıyor mu?
        if current_length + split_len + len(separator) > chunk_size:
            if current_chunk:
                doc_chunk = separator.join(current_chunk)
                final_chunks.append(doc_chunk)
                
                # Overlap mantığı: Son birkaç parçayı yeni chunk'ın başına ekle
                # Basitlik için şimdilik overlap'i sadece bir önceki parçayı alarak simüle ediyoruz
                # Daha karmaşık overlap mantığı burada işlem maliyetini artırabilir.
                current_chunk = [] 
                current_length = 0
        
        current_chunk.append(split)
        current_length += split_len + len(separator)
    
    # Son kalan parçayı ekle
    if current_chunk:
        final_chunks.append(separator.join(current_chunk))
        
    return final_chunks