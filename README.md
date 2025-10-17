# ✍️ Sentiric Knowledge Indexing Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python-blue.svg)]()
[![Engine](https://img.shields.io/badge/engine-RAGIndexing-red.svg)]()

**Sentiric Knowledge Indexing Service**, platformun RAG bilgi tabanını güncel ve tutarlı tutar. Veri kaynaklarından (PostgreSQL, Web Siteleri) gelen bilgiyi işleyerek, dil modelinin kullanabileceği vektör formatına dönüştürür ve Qdrant'ta depolar.

Bu, LLM'in doğru bilgiye erişimini garanti eden kritik bir arka plan servisidir.

## 🎯 Temel Sorumluluklar

*   **Veri Çekme:** PostgreSQL'de tanımlı veri kaynaklarını (veritabanı tabloları, web URL'leri) okur.
*   **Vektörleştirme:** `Sentence-Transformers` kullanarak metinleri vektörlere dönüştürür.
*   **Chunking ve Metadata:** Uzun metinleri LLM için uygun parçalara ayırır ve gerekli meta verileri (source URI, tenant ID) ekler.
*   **Qdrant Yönetimi:** Her kiracı (tenant) için ayrı koleksiyonlar oluşturur, verileri bu koleksiyonlara yazar (`upsert`).
*   **Periyodik ve Manuel Tetikleme:** Belirli aralıklarla otomatik çalışır ve `POST /reindex` API'si ile manuel olarak tetiklenebilir.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **Web Çerçevesi:** FastAPI (Sadece yönetim API'leri için)
*   **Core Logic:** Asenkron Worker (`asyncio`)
*   **Vector DB:** Qdrant Client
*   **Bağımlılıklar:** `asyncpg`, `qdrant-client`, `sentence-transformers`, `httpx`, `beautifulsoup4`

## 🚀 Başlarken

### 1. Bağımlılıkları Kurun
Bu proje `poetry` kullanmaktadır.

```bash
poetry install
```

### 2. Ortam Değişkenlerini Ayarlayın
Proje kök dizininde `.env` adında bir dosya oluşturun ve aşağıdaki şablonu doldurun:

```dotenv
# .env.example

# Servis Ayarları
ENV="development"
LOG_LEVEL="INFO"

# Bağlanılacak PostgreSQL veritabanı. `datasources` tablosunu içermelidir.
POSTGRES_URL="postgresql://user:password@localhost:5432/sentiric_db"

# Bağlanılacak Qdrant adresi
QDRANT_HTTP_URL="http://localhost:6333"
# QDRANT_API_KEY="your-qdrant-api-key" # Gerekliyse

# Qdrant'ta oluşturulacak koleksiyonların ön eki. Sonuna tenant_id eklenecek.
QDRANT_DB_COLLECTION_PREFIX="sentiric_kb_"

# Metinleri vektöre çevirmek için kullanılacak model.
QDRANT_DB_EMBEDDING_MODEL_NAME="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Worker'ın ne sıklıkla yeniden indeksleme yapacağı (saniye cinsinden)
KNOWLEDGE_INDEXING_INTERVAL_SECONDS=3600
```

### 3. Servisi Çalıştırın

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 17030
```

Servis başlatıldığında, `KNOWLEDGE_INDEXING_INTERVAL_SECONDS` ile belirlenen aralıklarla otomatik olarak indeksleme yapmaya başlayacaktır.

## 🔌 API Etkileşimleri

*   **`GET /health`**: Servisin ve bağımlılıklarının (Qdrant, Model) sağlıklı olup olmadığını kontrol eder.
*   **`POST /reindex`**: İndeksleme döngüsünü manuel olarak tetikler.
    ```json
    // Body (Opsiyonel)
    {
      "tenant_id": "sentiric_demo"
    }
    ```

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın](https://github.com/sentiric/sentiric-governance) **Horizontal Capability Layer**'ında yer alan uzman bir bileşendir.

