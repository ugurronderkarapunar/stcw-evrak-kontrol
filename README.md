# 📋 Personel Belge Takip Sistemi

Kurumsal ortamlarda kullanılmak üzere tasarlanmış, Excel/CSV tabanlı personel
belge geçerlilik takibi ve risk analizi paneli. **Streamlit** ile geliştirilmiş,
**Streamlit Community Cloud** üzerinde barındırılmaya hazırdır.

## ✨ Özellikler

- **Otomatik kolon tespiti** — Excel dosyanızdaki kolon isimleri farklı olsa bile
  (Personel Adı / Ad Soyad / Employee / Crew gibi) sistem alanları otomatik eşler.
- **Çoklu tarih formatı desteği** — `GG.AA.YYYY`, `DD/MM/YYYY`, `YYYY-MM-DD`,
  Excel seri tarih numaraları vb. otomatik ayrıştırılır.
- **Otomatik durum sınıflandırma**
  - 🔴 Süresi Geçmiş (0 günden az kalan)
  - 🟠 Kritik (0–30 gün)
  - 🟡 Yaklaşıyor (31–90 gün)
  - 🟢 Geçerli (90+ gün)
  - ⚪ Tarih Yok (eksik/hatalı veri)
- **Personel bazlı birleştirme** — aynı kişinin farklı satırlarda bulunan tüm
  belgeleri tek bir kartta özetlenir.
- **Ünvan bazlı analiz** — filtreleme, riskli ünvan tablosu ve grafikler.
- **Zengin dashboard** — KPI kartları, 8 farklı grafik, 5 detay tablosu.
- **Canlı arama** ve **çok kriterli filtreleme** (ünvan, belge türü, durum, ay, yıl).
- **Excel / CSV / PDF** olarak tek tıkla dışa aktarma.
- **Dark / Light mod** desteği (Streamlit temasıyla uyumlu).
- **100.000+ satırlık dosyalarda** çalışacak şekilde vectorized pandas işlemleri.
- Bozuk dosya, eksik kolon, hatalı tarih gibi durumlar için kullanıcı dostu
  hata yönetimi.

## 🗂️ Proje Yapısı

```
project/
├── app.py                      # Ana giriş noktası (orkestrasyon)
├── pages/                      # (İleride çoklu sayfa genişlemesi için)
├── components/                 # Görsel bileşenler
│   ├── kpi_cards.py
│   ├── charts.py
│   ├── tables.py
│   └── filters.py
├── services/                   # İş mantığı / servis katmanı
│   ├── file_loader.py          # Dosya okuma + hata yönetimi
│   ├── data_processor.py       # Analiz motoru
│   └── report_generator.py     # Excel/CSV/PDF dışa aktarma
├── utils/                      # Yardımcı fonksiyonlar
│   ├── date_utils.py           # Tarih ayrıştırma
│   └── column_mapper.py        # Esnek kolon eşleştirme
├── models/
│   └── document_status.py      # Durum sınıflandırma sabitleri/mantığı
├── assets/
│   └── style.css                # Kurumsal tema
├── data/                        # (Kullanıcı verisi buraya commit edilmez)
├── requirements.txt
├── .gitignore
└── README.md
```

## 🚀 Kurulum (Yerel)

```bash
git clone https://github.com/<kullanici-adiniz>/<repo-adiniz>.git
cd <repo-adiniz>

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

streamlit run app.py
```

Uygulama varsayılan olarak `http://localhost:8501` adresinde açılır.

## ☁️ Streamlit Cloud Üzerinde Yayınlama

1. Bu depoyu kendi GitHub hesabınıza fork'layın veya push'layın.
2. [share.streamlit.io](https://share.streamlit.io) adresinden GitHub hesabınızla giriş yapın.
3. "New app" → deponuzu seçin → Main file path olarak `app.py` girin.
4. Deploy edin. Birkaç dakika içinde uygulamanız internet üzerinden erişilebilir olur.

> Not: `requirements.txt` dosyası Streamlit Cloud tarafından otomatik olarak
> okunur, ek bir yapılandırmaya gerek yoktur.

## 📥 Beklenen Excel/CSV Şablonu

Kolon adları esnektir (sistem otomatik tespit eder), ancak en az şu bilgileri
içermelidir:

| Personel Adı | Ünvan   | Belge Adı | Bitiş Tarihi |
|--------------|---------|-----------|--------------|
| Ali Yılmaz   | Kaptan  | STCW      | 15.03.2026   |
| Ali Yılmaz   | Kaptan  | SRC       | 01.01.2025   |
| Ayşe Demir   | Gemici  | Sağlık    | 20.09.2026   |

Sistem otomatik tespit edemezse, uygulama içinden manuel kolon eşleştirmesi
yapabilirsiniz.

## ⚙️ Durum Eşiklerini Özelleştirme

Sol panelden "Durum Eşikleri" bölümünü açarak "Kritik" ve "Yaklaşıyor"
gün eşiklerini kurumunuzun politikasına göre değiştirebilirsiniz
(varsayılan: 30 / 90 gün).

## 🧩 Mimari Prensipler

- **Katmanlı mimari**: `app.py` yalnızca orkestrasyon yapar; iş mantığı
  `services/`, görsel bileşenler `components/` içindedir.
- **Vectorized işlemler**: `pandas`/`numpy` döngüsüz vectorized operasyonlarla
  büyük veri setlerinde performanslı çalışır.
- **Genişletilebilirlik**: Yeni bir grafik/tablo eklemek için yalnızca
  `components/` altına yeni bir fonksiyon eklemek yeterlidir; mevcut yapı
  bozulmaz.

## 🛠️ Katkıda Bulunma

1. Depoyu fork'layın.
2. Yeni bir özellik dalı oluşturun: `git checkout -b ozellik/yeni-grafik`.
3. Değişikliklerinizi commit'leyin ve push'layın.
4. Pull Request açın.

## 📄 Lisans

Bu proje kurum içi kullanım amacıyla geliştirilmiştir. Kullanım koşullarını
kendi kurumunuzun politikalarına göre belirleyebilirsiniz.
