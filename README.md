# ✍️ Sentiric Knowledge Indexing Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python_3.11-blue.svg)]()
[![Framework](https://img.shields.io/badge/framework-FastAPI_&_gRPC-teal.svg)]()

**Sentiric Knowledge Indexing Service**, platformun RAG bilgi tabanını güncel ve tutarlı tutar. Veri kaynaklarından (PostgreSQL, Web Siteleri) gelen bilgiyi işleyerek, dil modelinin kullanabileceği vektör formatına dönüştürür ve Qdrant'ta depolar.

Bu, LLM'in doğru bilgiye erişimini garanti eden kritik bir arka plan servisidir. Servis, hem **HTTP/REST** (yönetim için) hem de **gRPC** (uzaktan tetikleme için) arayüzleri sunar.

## 🎯 Temel Sorumluluklar

*   **Veri Çekme:** PostgreSQL'de tanımlı veri kaynaklarını (veritabanı tabloları, web URL'leri) okur.
*   **Vektörleştirme:** `Sentence-Transformers` kullanarak metinleri vektörlere dönüştürür.
*   **Chunking ve Metadata:** Uzun metinleri LLM için uygun parçalara ayırır ve gerekli meta verileri (source URI, tenant ID) ekler.
*   **Qdrant Yönetimi:** Her kiracı (tenant) için ayrı koleksiyonlar oluşturur, verileri bu koleksiyonlara yazar (`upsert`).
*   **Periyodik ve Uzaktan Tetikleme:** Belirli aralıklarla otomatik çalışır ve API (HTTP/gRPC) aracılığıyla manuel olarak tetiklenebilir.
*   **İzlenebilirlik:** İndeksleme döngüsünün süresi, işlenen doküman sayısı ve hatalar gibi kritik performans metriklerini Prometheus formatında sunar.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **Web Çerçevesi:** FastAPI (Sadece yönetim API'leri için)
*   **RPC Çerçevesi:** gRPC (Uzaktan tetikleme için)
*   **Core Logic:** Asenkron Worker (`asyncio`)
*   **İzleme:** Prometheus Client
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
KNOWLEDGE_INDEXING_SERVICE_HTTP_PORT=17030
KNOWLEDGE_INDEXING_SERVICE_GRPC_PORT=17031
KNOWLEDGE_INDEXING_SERVICE_METRICS_PORT=17032

# Bağlanılacak PostgreSQL veritabanı.
POSTGRES_URL="postgresql://user:password@localhost:5432/sentiric_db"

# Bağlanılacak Qdrant adresi
QDRANT_HTTP_URL="http://localhost:6333"

# Paylaşılan RAG ayarları
QDRANT_DB_COLLECTION_PREFIX="sentiric_kb_"
QDRANT_DB_EMBEDDING_MODEL_NAME="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Worker'ın ne sıklıkla yeniden indeksleme yapacağı (saniye cinsinden)
KNOWLEDGE_INDEXING_INTERVAL_SECONDS=3600
```

### 3. Servisi Çalıştırın

```bash
poetry run python -m app.runner
```

Servis başlatıldığında, `KNOWLEDGE_INDEXING_INTERVAL_SECONDS` ile belirlenen aralıklarla otomatik olarak indeksleme yapmaya başlayacaktır.

## 🔌 API ve Protokoller

*   **HTTP (Port 17030)**
    *   `GET /health`: Servisin ve bağımlılıklarının sağlıklı olup olmadığını kontrol eder.
    *   `POST /reindex`: İndeksleme döngüsünü manuel olarak tetikler.

*   **gRPC (Port 17031)**
    *   **Servis:** `sentiric.knowledge.v1.KnowledgeIndexingService`
    *   **RPC:** `TriggerReindex`: Uzaktan indeksleme sürecini tetikler.

*   **Prometheus Metrics (Port 17032)**
    *   `GET /metrics`: Worker performansı, döngü süreleri ve işlenen veri miktarı gibi metrikleri sunar.

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın](https://github.com/sentiric/sentiric-governance) **Horizontal Capability Layer**'ında yer alan uzman bir bileşendir.
