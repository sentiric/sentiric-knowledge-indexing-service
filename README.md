### 📄 File: `README.md` | 🏷️ Markdown

```markdown
# ✍️ Sentiric Knowledge Indexing Service

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python-blue.svg)]()
[![Engine](https://img.shields.io/badge/engine-RAGIndexing-red.svg)]()

**Sentiric Knowledge Indexing Service**, platformun RAG bilgi tabanını güncel ve tutarlı tutar. Veri kaynaklarından (PostgreSQL, RabbitMQ, Web) gelen bilgiyi işleyerek, dil modelinin kullanabileceği vektör formatına dönüştürür ve Qdrant'ta depolar.

Bu, LLM'in doğru bilgiye erişimini garanti eden kritik bir arka plan servisidir.

## 🎯 Temel Sorumluluklar

*   **Veri Çekme:** Çeşitli API ve veritabanı bağlantıları üzerinden ham veriyi alır.
*   **Vektörleştirme:** `Sentence-Transformers` kullanarak metinleri vektörlere dönüştürür.
*   **Chunking ve Metadata:** Uzun metinleri LLM için uygun parçalara ayırır ve gerekli meta verileri (source URL, tenant ID) ekler.
*   **Qdrant Yönetimi:** Koleksiyonları oluşturur, günceller ve siler.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11 (Yüksek bilimsel kütüphane desteği nedeniyle)
*   **Core Logic:** Asenkron Worker (asyncio)
*   **Vector DB:** Qdrant Client
*   **Bağımlılıklar:** `asyncpg`, `qdrant-client`, `sentence-transformers`

## 🔌 API Etkileşimleri

*   **Gelen (Sunucu/Worker):**
    *   `sentiric-task-service` (gRPC): `TriggerReindex` RPC'si (İndekslemeyi manuel tetiklemek için).
    *   RabbitMQ (AMQP): Harici veri değişikliği olaylarını dinler.
*   **Giden (İstemci):**
    *   PostgreSQL (Veri çekme).
    *   Qdrant (Vektör yazma).

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın](https://github.com/sentiric/sentiric-governance) **Horizontal Capability Layer**'ında yer alan uzman bir bileşendir.