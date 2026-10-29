# spotiri

Spotify playlist otomasyonu. Tek bir web arayüzünden çalışan modüller; playlist'leri
AI ile isimlendirip dolduruyor, kapaklarını üretiyor, büyümelerini takip ediyor.

![Python](https://img.shields.io/badge/python-3.13-blue) ![NiceGUI](https://img.shields.io/badge/ui-NiceGUI-1db954)

## Kurulum

```bash
pip install nicegui spotipy python-dotenv groq google-genai pillow moviepy \
            google-api-python-client sentence-transformers pandas numpy requests
```

Proje kökünde bir `.env` dosyası oluştur:

```
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
GROQ_API_KEY=...
GOOGLE_API_KEY=...          # Gemini — AI kapak üretimi
YOUTUBE_API_KEY=...         # YouTube playlist modülü
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

İlk çalıştırmada Spotify yetkilendirme ekranı açılır; token `.cache` dosyasına yazılır
ve bütün modüller aynı token'ı paylaşır (`spotify_auth.py`).

## Çalıştırma

```bash
python web.py
```

Arayüz: http://localhost:8080 — her modül arka planda subprocess olarak çalışır,
çıktısı canlı log paneline akar.

## Modüller

| Dosya | Ne yapar |
|---|---|
| `web.py` | NiceGUI arayüzü: dashboard, analytics, playlist tarayıcı, ayarlar |
| `kisisel_playlist.py` | Ruh hali + isim anlamı + burç → kişiye özel playlist |
| `oto_playlist.py` | 9 tür için günlük otomatik playlist güncellemesi |
| `trend_playlist.py` | Reddit trendleri → AI'ın yazdığı viral playlist isimleri |
| `tiktok_uretici.py` | Playlist'ten 9:16 MP4 + otomatik caption |
| `sanatci_eksik.py` | Spotify ✕ YouTube ✕ MusicBrainz: eksik şarkı avı |
| `yt_playlist_olustur.py` | Eksik şarkılardan YouTube playlist'i |
| `kapak_doldur.py` | Kapağı olmayan playlist'lere kapak üretir |
| `kapali_yap.py` | Tüm playlist'leri non-collaborative yapar |
| `analitik.py` | SQLite snapshot: takipçi/şarkı sayısı zaman serisi |
| `curator.py` | Persona filtreleri, çeşitlilik, embedding tabanlı sıralama |
| `kapak.py` | Pillow gradient + Gemini ile kapak görseli |
| `ai_config.py` | Model adları tek yerde (`GROQ_MODEL`, `GEMINI_IMAGE_MODEL`) |
| `spotify_auth.py` | Ortak OAuth + `kendi_playlistlerim()` sayfalama yardımcısı |

## Zamanlama (macOS)

Cron macOS'ta güvenilir çalışmıyor; işler launchd ajanlarıyla kurulu:

| Ajan | Ne zaman | Ne çalışır |
|---|---|---|
| `com.iri.projectiri.gunluk` | her gün 09:00 | `oto_playlist.py` |
| `com.iri.projectiri.trend` | Pazartesi 09:30 | `trend_playlist.py` |
| `com.iri.projectiri.analytics` | her gün 03:00 | `analitik.py snapshot` |

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.iri.projectiri.gunluk.plist
launchctl kickstart gui/$(id -u)/com.iri.projectiri.gunluk   # elle tetikle
```

Loglar `~/Library/Logs/projectiri/` altında. **Not:** launchd, Masaüstü'nde önceden var olan
bir log dosyasını açamıyor (TCC) — log yolu bu yüzden `~/Library/Logs` içinde.

## Notlar

- `oto_playlist.py`, `trend_playlist.py`, `kapak_doldur.py` ve `kapali_yap.py` script olarak
  çalışacak şekilde yazıldı; import edilirlerse kendilerini kapatırlar (yanlışlıkla
  canlı playlist değiştirmesinler diye).
- Spotify `audio_features` / `recommendations` uçları yeni uygulamalara kapalı; şarkı skoru
  `popularity` üzerinden hesaplanıyor.
- `.env`, `.cache`, `client_secret.json` ve tarayıcı profilleri depoya dahil değildir.
