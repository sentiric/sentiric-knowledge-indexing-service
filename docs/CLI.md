# 🛠️ Sentiric Knowledge CLI Kullanım Kılavuzu

Bu proje, veri kaynaklarını yönetmek için `Makefile` üzerinden kolay erişilebilir komutlar sunar.

## 🚀 Hızlı Komutlar

Tüm komutlar, çalışan Docker konteyneri üzerinden çalıştırılır. Servisler ayakta olmalıdır (`make up`).

### 1. Veri Kaynaklarını Listeleme

Mevcut kaynakları ve durumlarını görmek için:

```bash
make cli-list
```

### 2. Yeni Veri Kaynağı Ekleme

Yeni bir web sayfası eklemek için:

```bash
# Varsayılan tenant: sentiric_demo
make cli-add URI="https://sentiric.github.io/sentiric-assets/"

# Özel tenant ile:
make cli-add URI="https://example.com" TENANT="my_company"
```

### 3. İndekslemeyi Tetikleme

Zamanlayıcıyı beklemeden hemen indeksleme başlatmak için:

```bash
make cli-run
```
