# Dosya: TASKS.md

## Mimari Uyumluluk Denetimi ve Düzeltmeler (Auto-Generated)

- [x] **mTLS Zorunluluğu:** `app/main.py` dosyasındaki gRPC sertifika (mTLS) kontrolünde sertifika bulunamadığında devreye giren "güvensiz porta (insecure_port) düşme" (fallback) mantığı tamamen kaldırılmıştır. Servis mimari anayasa gereği sertifikasız başlatılmayacak ve güvenliği tehlikeye atmayacaktır.
- [x] **Trace-ID Context Yayılımı:** `app/main.py` içerisindeki FastAPI servisine HTTP middleware eklenerek dış dünyadan gelen `x-trace-id` log context'e bağlanmıştır.
- [x] **gRPC Context Yayılımı:** `KnowledgeIndexingServicer` içerisinde gRPC metadata'sından okunan `trace_id` `structlog` context değişkenlerine aktarılmıştır.
- [x] **Worker İzlenebilirliği:** `app/workers/indexing_worker.py` içindeki arka plan döngüsüne (scheduler trigger veya manual event) kendi `trace_id` kimliğini yaratıp loglara aktarma özelliği eklenmiştir.