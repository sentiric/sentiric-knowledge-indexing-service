# 🧬 Indexing Management & CLI Logic

Bu belge, RAG (Retrieval-Augmented Generation) mimarisinin 'Yazma' (Indexing) motorunun nasıl yönetildiğini ve manuel tetiklemelerin nasıl çalıştığını açıklar.

## 1. Veri Kaynağı Yönetimi (Data Ingestion Logic)
Sistem otonom olarak veritabanını tarar ancak manuel müdahaleler (CLI) Docker konteyneri üzerinden yönetilir. 
CLI aracı, doğrudan `manage.py` betiği üzerinden asenkron veritabanı (PostgreSQL) işlemlerini tetikler.

## 2. CLI Komut Mantığı

### Kaynak Listeleme
Mevcut kaynakları ve durumlarını veritabanından asenkron olarak okur:
```bash
make cli-list
# Opsiyonel: make cli-list TENANT="sentiric_demo"
```

### Yeni Kaynak Ekleme (Upsert)
Yeni bir web sayfası veya dokümanı veri tabanına `is_active=TRUE` olarak ekler. `ON CONFLICT` durumu varsa kaydı günceller:
```bash
make cli-add URI="https://sentiric.github.io/sentiric-assets/"
```

### İndekslemeyi Tetikleme (Forced Re-index)
Zamanlayıcıyı (Interval) beklemeden, doğrudan HTTP üzerinden `/reindex` endpoint'ine `POST` atarak Worker'ı uyandırır:
```bash
make cli-run
```