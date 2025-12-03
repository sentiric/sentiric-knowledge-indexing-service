.PHONY: help up down logs build clean setup cli-add cli-list cli-run

help:
	@echo "🎨 Sentiric Knowledge Indexing Service - Yönetim Aracı"
	@echo "-------------------------------------------------------"
	@echo "make up      : Servisleri başlatır"
	@echo "make down    : Servisleri durdurur"
	@echo "make logs    : Logları izler"
	@echo "make cli-list: Mevcut veri kaynaklarını listeler"
	@echo "make cli-add URI=<url> TENANT=<id> : Yeni kaynak ekler"
	@echo "make cli-run : İndekslemeyi tetikler"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "⚠️ .env oluşturuldu, lütfen düzenleyin!"; fi
	@if [ ! -d "../sentiric-certificates" ]; then echo "❌ '../sentiric-certificates' bulunamadı! Sertifika mount'u çalışmayacak."; exit 1; fi

# Geliştirme Modu: Override dosyasını kullanır (Local Build)
up: setup
	docker compose -f docker-compose.infra.yml -f docker-compose.yml -f docker-compose.override.yml up --build -d

# Üretim Simülasyonu: Override dosyasını YOK SAYAR (Hazır İmaj)
prod: setup
	docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml -f docker-compose.override.yml down --remove-orphans

logs:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml logs -f

# --- CLI KOMUTLARI ---
# Bu komutlar docker-compose.yml ve infra.yml dosyalarını otomatik dahil eder

cli-list:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml exec knowledge-indexing-service python manage.py list

cli-add:
	@if [ -z "$(URI)" ]; then echo "❌ Hata: URI parametresi gerekli. Örn: make cli-add URI='https://example.com'"; exit 1; fi
	docker compose -f docker-compose.infra.yml -f docker-compose.yml exec knowledge-indexing-service python manage.py add "$(URI)" --type web --tenant $(or $(TENANT),sentiric_demo)

cli-run:
	docker compose -f docker-compose.infra.yml -f docker-compose.yml exec knowledge-indexing-service python manage.py run