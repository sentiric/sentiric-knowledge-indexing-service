# ✍️ Sentiric Knowledge Indexing Service

[![Status](https://img.shields.io/badge/status-production--ready-success.svg)]()
[![Language](https://img.shields.io/badge/language-Python_3.11-blue.svg)]()
[![Framework](https://img.shields.io/badge/framework-FastAPI_&_gRPC-teal.svg)]()

**Sentiric Knowledge Indexing Service**, platformun RAG bilgi tabanını güncel ve tutarlı tutar. Veri kaynaklarından (PostgreSQL, Web Siteleri, Dosyalar) gelen bilgiyi işleyerek, dil modelinin kullanabileceği vektör formatına dönüştürür ve Qdrant'ta depolar.

## 🚀 Hızlı Başlangıç

### 1. Kurulum
```bash
# Ortam dosyasını hazırla
make setup

# Servisleri başlat
make up
```

### 2. Veri Kaynağı Yönetimi (CLI)
Bu servis, veri kaynaklarını yönetmek için yerleşik bir CLI aracı sunar. Docker konteyneri çalışırken şu komutları kullanabilirsiniz:

```bash
# 📋 Mevcut kaynakları listele
make cli-list

# ➕ Yeni bir web sitesi ekle
make cli-add URI="https://sentiric.github.io/sentiric-assets/"

# ▶️ İndekslemeyi manuel tetikle
make cli-run
```

Detaylı kullanım için [docs/CLI.md](docs/CLI.md) dosyasına bakın.

## 🎯 Temel Sorumluluklar

*   **Veri Çekme:** Web siteleri, veritabanı tabloları ve yerel dosyaları okur.
*   **Akıllı Chunking:** Metinleri anlamsal bütünlüğü bozmadan parçalara ayırır (Semantic Splitter).
*   **Vektörleştirme:** CPU dostu, asenkron ve batch (toplu) işleme ile yüksek performanslı embedding.
*   **Qdrant Yönetimi:** Koleksiyonları ve payload indekslerini otomatik oluşturur.

## 🛠️ Teknoloji Yığını

*   **Dil:** Python 3.11
*   **API:** FastAPI (HTTP), gRPC (Protobuf)
*   **Core Logic:** Asenkron Worker (`asyncio`), `SentenceTransformers`
*   **Vector DB:** Qdrant
*   **İzleme:** Prometheus Metrics (`/metrics`)

## 🔌 API Endpoint'leri

| Metot | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/health` | Sağlık durumu ve bağımlılık kontrolü. |
| `POST` | `/reindex` | İndekslemeyi manuel tetikler. |
| `GET` | `/metrics` | Prometheus metrikleri. |
| `GET` | `/docs` | Swagger UI (API Dokümantasyonu). |

---
## 🏛️ Anayasal Konum

Bu servis, [Sentiric Anayasası'nın](https://github.com/sentiric/sentiric-governance) **Horizontal Capability Layer**'ında yer alan uzman bir bileşendir.
