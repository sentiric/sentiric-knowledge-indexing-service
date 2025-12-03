# 🛠️ Sentiric Knowledge CLI Kullanım Kılavuzu

Bu proje, veri kaynaklarını yönetmek ve indekslemeyi tetiklemek için yerleşik bir komut satırı aracı (`manage.py`) içerir.

## 🚀 Nasıl Kullanılır?

Bu aracı çalıştırmanın en kolay ve önerilen yolu, halihazırda çalışan Docker konteyneri üzerinden komut göndermektir. Böylece yerel bilgisayarınıza Python kütüphanesi kurmanıza gerek kalmaz.

### 1. Veri Kaynaklarını Listeleme

Mevcut tüm kayıtlı kaynakları ve durumlarını (başarılı, hatalı vb.) gösterir.

```bash
# Konteyner ismini bulmak için: docker ps
docker exec -it sentiric-knowledge-indexing-service python manage.py list
```

### 2. Yeni Veri Kaynağı Ekleme

Sisteme indekslenmesi için yeni bir web sitesi veya dosya ekler.

```bash
# Sentiric web sitesini ekle
docker exec -it sentiric-knowledge-indexing-service python manage.py add "https://sentiric.ai" --type web --tenant sentiric_demo
```

### 3. İndekslemeyi Manuel Tetikleme

Zamanlayıcıyı beklemeden, o anki tüm aktif kaynakları tarar ve günceller.

```bash
docker exec -it sentiric-knowledge-indexing-service python manage.py run
```

---

## 🐍 Yerel Çalıştırma (Opsiyonel)

Eğer Docker kullanmadan, doğrudan kendi terminalinizden çalıştırmak isterseniz:

1.  Sanal ortam oluşturun ve aktif edin:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
2.  Bağımlılıkları kurun:
    ```bash
    pip install -r requirements.txt
    ```
3.  `.env` dosyasındaki veritabanı ayarlarının `localhost`'u gösterdiğinden emin olun ve çalıştırın:
    ```bash
    python3 manage.py list
    ```
