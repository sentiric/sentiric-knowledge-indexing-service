# ✍️ Sentiric Knowledge Indexing Service - Mantık ve Akış Mimarisi

**Stratejik Rol:** RAG mimarisinin "Yazma" (Indexing) bacağını temsil eder. Harici veri kaynaklarından (PostgreSQL, Web Siteleri, Dosyalar) gelen yapılandırılmış veya yapılandırılmamış veriyi işler, parçalar (chunking), vektörleştirir ve Vector Database'e (Qdrant) yazar.

---

## 1. CQRS Mimarisi ve Yazma Akışı

Bu servis, olay tabanlı veya periyodik olarak çalışır.

```mermaid
sequenceDiagram
    participant Source as Veri Kaynağı (Postgres, Web)
    participant Worker as Indexing Worker
    participant Embedding as Embedding Model
    participant Qdrant as Vector DB
    
    Note over Worker: 1. Tetikleme (Periyodik veya Event)
    Worker->>Source: FetchData(tenant_id, source_uri)
    Source-->>Worker: Ham Veri (Text/HTML)
    
    Note over Worker: 2. Chunking & Temizleme
    Worker->>Embedding: Embed(chunk_of_text)
    Embedding-->>Worker: Vector
    
    Note over Worker: 3. Vector DB Yazma
    Worker->>Qdrant: UpsertPoints(collection=tenant_id, vector, payload)
    Qdrant-->>Worker: OK
    
    Worker->>Worker: Mark source as indexed
```

## 2. Ana İşleyiciler (Ingesters)
*Indexing Service, farklı veri kaynaklarını işlemek için modüler ingester'lar kullanır:
* postgres_ingester.py: PostgreSQL tablolarını okur.
* web_ingester.py: URL'leri (örneğin kurumsal FAQ sayfaları) okur ve ayrıştırır.