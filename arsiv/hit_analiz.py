import os
from datetime import datetime
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

scope = "playlist-read-private user-library-read"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

# ─────────────────────────────────────────────
# HIT SKORU — audio-features olmadan
#
# Spotify, audio-features endpoint'ini 2024 sonu
# itibarıyla yeni uygulamalara kapattı (403).
# Puanlama track metadata ile yapılıyor:
#
#   popularity  → 60 puan  (en güçlü sinyal)
#   süre        → 20 puan  (2:30–3:30 = ideal hit uzunluğu)
#   tazelik     → 20 puan  (son 2 yıl içindeyse tam puan)
#
# Toplam: 100 puan
# ─────────────────────────────────────────────

def sure_puani(duration_ms):
    """2:30–3:30 dakika aralığı ideal hit uzunluğu → tam puan."""
    saniye = duration_ms / 1000
    if 150 <= saniye <= 210:
        return 1.0
    elif saniye < 150:
        return max(0, saniye / 150)
    else:
        return max(0, 1 - (saniye - 210) / 120)

def tazelik_puani(release_date):
    """Son 2 yılda çıkmışsa tam puan, her geçen yıl için düşer."""
    try:
        if len(release_date) == 4:
            cikis = datetime(int(release_date), 1, 1)
        elif len(release_date) == 7:
            y, m = release_date.split("-")
            cikis = datetime(int(y), int(m), 1)
        else:
            cikis = datetime.strptime(release_date, "%Y-%m-%d")
    except Exception:
        return 0.5

    gecen_gun = (datetime.now() - cikis).days
    gecen_yil = gecen_gun / 365
    return max(0, 1 - (gecen_yil / 2))

def hit_skoru_hesapla(track):
    """Track metadata'sından 0-100 hit skoru üretir."""
    pop_puan    = (track["popularity"] / 100) * 60
    sure_p      = sure_puani(track["duration_ms"]) * 20
    tazelik_p   = tazelik_puani(track["album"]["release_date"]) * 20
    return round(pop_puan + sure_p + tazelik_p, 1)

def playlist_analiz_et(playlist_id):
    print(f"\n--- PLAYLİST ANALİZ EDİLİYOR: {playlist_id} ---")

    results = sp.playlist_tracks(playlist_id, limit=100)
    tracks = [(item.get("track") or item.get("item")) for item in results["items"]]
    tracks = [t for t in tracks if t and t.get("id")]

    print(f"{len(tracks)} şarkı bulundu.")

    if not tracks:
        print("Listede analiz edilebilir şarkı yok.")
        return []

    skorlar = []
    for track in tracks:
        skor = hit_skoru_hesapla(track)
        sure_sn = track["duration_ms"] // 1000
        skorlar.append({
            "isim":       track["name"],
            "sanatci":    track["artists"][0]["name"],
            "popularity": track["popularity"],
            "sure":       f"{sure_sn // 60}:{sure_sn % 60:02d}",
            "cikis":      track["album"]["release_date"][:7],
            "hit_skoru":  skor,
        })

    skorlar.sort(key=lambda x: x["hit_skoru"], reverse=True)
    return skorlar

def sonuclari_yazdir(skorlar):
    if not skorlar:
        return
    print(f"\n{'SIRA':<5} {'SKOR':<7} {'SANATCI':<22} {'ŞARKI':<38} {'POP':>4} {'SÜRE':>6} {'ÇIKIŞ':>8}")
    print("-" * 100)
    for i, s in enumerate(skorlar, 1):
        print(
            f"{i:<5} {s['hit_skoru']:<7} {s['sanatci'][:21]:<22} {s['isim'][:37]:<38} "
            f"{s['popularity']:>4} {s['sure']:>6} {s['cikis']:>8}"
        )

    print(f"\nToplam: {len(skorlar)} şarkı analiz edildi.")
    ortalama = sum(s["hit_skoru"] for s in skorlar) / len(skorlar)
    print(f"Playlist Ortalama Hit Skoru: {ortalama:.1f} / 100")

# ─────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────

PLAYLIST_ID = "3DO2sz2kdYIzIZJoO9hojG"

skorlar = playlist_analiz_et(PLAYLIST_ID)
sonuclari_yazdir(skorlar)
