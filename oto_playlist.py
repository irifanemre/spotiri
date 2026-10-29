import os
import sys
import time
import datetime
from dotenv import load_dotenv
import spotipy
from kapak import base64_kapak, playlist_ismi

load_dotenv()

from spotify_auth import get_sp, kendi_playlistlerim
sp = get_sp()

kullanici = sp.current_user()
HESAP_ID  = kullanici["id"]
bugun     = datetime.date.today().isoformat()
print(f"[{bugun}] Hedef hesap: {kullanici['display_name']}")

# ─────────────────────────────────────────────
# AYARLAR
# ─────────────────────────────────────────────

MAX_SARKI = 30

# Her tür için birden fazla arama sorgusu → daha geniş + doğru tarama
TURLER = {
    "Phonk":       ["phonk",         "dark phonk",       "phonk drift"],
    "Hip-Hop":     ["hip hop rap",   "rap 2024",         "trap hip hop"],
    "Pop":         ["pop hits 2024", "pop music",        "popular songs"],
    "Electronic":  ["electronic",    "edm dance music",  "house music 2024"],
    "R&B":         ["r&b 2024",      "rnb soul music",   "contemporary r&b"],
    "Rock":        ["rock music",    "alternative rock", "indie rock 2024"],
    "Chill":       ["chill music",   "lofi hip hop",     "relaxing beats"],
    "Latin":       ["latin music",   "reggaeton 2024",   "latin pop"],
    "Türkçe":      ["türkçe pop",    "türkçe rap",       "türkçe müzik 2024"],
}

# Türe ait anahtar kelimeler — eşleştirme doğrulaması için
TUR_ANAHTAR = {
    "Phonk":      ["phonk", "drift", "dark"],
    "Hip-Hop":    ["hip hop", "rap", "trap", "drill", "hiphop"],
    "Pop":        ["pop"],
    "Electronic": ["electronic", "edm", "house", "techno", "dance"],
    "R&B":        ["r&b", "rnb", "soul", "rhythm"],
    "Rock":       ["rock", "metal", "indie", "alternative", "punk"],
    "Chill":      ["chill", "lo-fi", "lofi", "ambient", "sleep", "relax"],
    "Latin":      ["latin", "reggaeton", "salsa", "cumbia", "bachata"],
    "Türkçe":     ["turkish", "türk", "türkçe"],
}

TURK_KARAKTERLER = set("çğışöüÇĞİŞÖÜ")

# ─────────────────────────────────────────────
# METADATA OPTİMİZASYONU
# Spotify arama indexi: isim + açıklama + güncelleme sıklığı
# Anahtar kelimeler doğal cümle içinde geçmeli — spam değil
# ─────────────────────────────────────────────

METADATA = {
    "Phonk": {
        "aciklama": (
            "The hardest phonk and dark phonk tracks, updated daily. "
            "Perfect for night drives, gym sessions, and late-night focus. "
            "Dark phonk · drift phonk · phonk beats · aggressive phonk"
        ),
    },
    "Hip-Hop": {
        "aciklama": (
            "Top hip hop and rap hits refreshed every day. "
            "Trap, drill, boom bap — the best of street music in one place. "
            "hip hop playlist · rap music · trap beats · new rap songs"
        ),
    },
    "Pop": {
        "aciklama": (
            "Today's biggest pop songs, curated and updated daily. "
            "Chart-topping hits, feel-good energy, and mainstream bangers. "
            "pop music 2025 · popular songs · pop hits · top 40"
        ),
    },
    "Electronic": {
        "aciklama": (
            "Best electronic, house, and EDM tracks — refreshed every day. "
            "Late-night energy, festival vibes, and deep electronic cuts. "
            "edm playlist · house music · electronic beats · dance music 2025"
        ),
    },
    "R&B": {
        "aciklama": (
            "Smooth R&B and soul for every mood, updated daily. "
            "Contemporary R&B, neo-soul, and late-night slow jams. "
            "rnb playlist · r&b hits · soul music · slow jams · neo soul"
        ),
    },
    "Rock": {
        "aciklama": (
            "Rock and alternative anthems curated fresh every day. "
            "Indie rock, alt rock, and classic-inspired modern cuts. "
            "rock playlist · alternative rock · indie rock · rock music 2025"
        ),
    },
    "Chill": {
        "aciklama": (
            "Chill, lo-fi, and relaxing music for studying, working, or unwinding. "
            "Updated daily with the most soothing tracks on Spotify. "
            "lofi hip hop · chill beats · study music · relaxing playlist · lo-fi"
        ),
    },
    "Latin": {
        "aciklama": (
            "The hottest Latin and reggaeton tracks, updated every day. "
            "From global hits to underground gems — feel the heat. "
            "reggaeton playlist · latin music 2025 · latin pop · latin hits"
        ),
    },
    "Türkçe": {
        "aciklama": (
            "Güncel Türkçe müzik: pop, rap ve daha fazlası her gün güncelleniyor. "
            "Türkiye'nin en çok dinlenen şarkıları tek playlist'te. "
            "türkçe pop · türkçe rap · türk müziği · güncel Türkçe şarkılar 2025"
        ),
    },
}

# ─────────────────────────────────────────────
# HIT SKORU (0–100)
# popularity : 60 puan  — Spotify'ın kendi skoru
# tazelik    : 25 puan  — son 2 yılda çıkmış = tam puan
# süre       : 15 puan  — 2:30–3:30 = ideal hit uzunluğu
# ─────────────────────────────────────────────

def hit_skoru(track):
    pop = track.get("popularity") or 0
    pop_puan = (pop / 100) * 60

    ms     = track.get("duration_ms") or 0
    saniye = ms / 1000
    if 150 <= saniye <= 210:
        sure_puan = 15
    elif saniye < 150:
        sure_puan = max(0, saniye / 150) * 15
    else:
        sure_puan = max(0, 1 - (saniye - 210) / 120) * 15

    release_date = (track.get("album") or {}).get("release_date", "2000-01-01")
    try:
        if len(release_date) == 4:
            cikis = datetime.datetime(int(release_date), 1, 1)
        elif len(release_date) == 7:
            y, m = release_date.split("-")
            cikis = datetime.datetime(int(y), int(m), 1)
        else:
            cikis = datetime.datetime.strptime(release_date, "%Y-%m-%d")
        gecen_yil    = (datetime.datetime.now() - cikis).days / 365
        tazelik_puan = max(0, 1 - gecen_yil / 2) * 25
    except Exception:
        tazelik_puan = 0

    return round(pop_puan + sure_puan + tazelik_puan, 1)

# ─────────────────────────────────────────────
# TÜR DOĞRULAMA
# Şarkı adı, sanatçı adı ve tür anahtarları karşılaştırılır.
# Eşleşme yoksa şarkı elenir.
# ─────────────────────────────────────────────

def tur_eslesme_skoru(track, tur_adi):
    """0 = hiç uymuyor, 1 = belirsiz, 2 = güçlü eşleşme."""
    anahtar = TUR_ANAHTAR.get(tur_adi, [])
    if not anahtar:
        return 1

    isim    = (track.get("name") or "").lower()
    sanatci = " ".join(a.get("name", "") for a in track.get("artists", [])).lower()
    metin   = isim + " " + sanatci

    # Türkçe tür için karakter tespiti
    if tur_adi == "Türkçe":
        if any(c in TURK_KARAKTERLER for c in metin):
            return 2

    eslesen = sum(1 for k in anahtar if k in metin)
    if eslesen >= 2:
        return 2
    if eslesen == 1:
        return 1
    return 0

# ─────────────────────────────────────────────
# FAZ 1: ARAMA & PUANLAMA
# ─────────────────────────────────────────────

def sarkilari_cek(tur_adi, sorgular):
    havuz   = {}   # id → track
    skor_id = {}   # id → (hit_skoru, eslesme_skoru, sorgu_sirasi)

    for sorgu_sira, sorgu in enumerate(sorgular[:2]):  # max 2 sorgu/tür
        for offset in [0]:                              # sadece 1 sayfa
            try:
                results = sp.search(q=sorgu, type="track", limit=5, offset=offset)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 429:
                    bekleme = int(e.headers.get("Retry-After", 30)) + 5
                    print(f"  [RATE LIMIT] {bekleme}s bekleniyor...")
                    time.sleep(bekleme)
                    results = sp.search(q=sorgu, type="track", limit=5, offset=offset)
                else:
                    print(f"  [UYARI] '{sorgu}': {e}")
                    break
            except Exception as e:
                print(f"  [UYARI] '{sorgu}': {e}")
                break
            time.sleep(0.5)  # istekler arası küçük bekleme

            for track in results["tracks"]["items"]:
                tid = track.get("id")
                if not tid:
                    continue
                if tid in havuz:
                    continue

                eslesme = tur_eslesme_skoru(track, tur_adi)
                hs      = hit_skoru(track)

                havuz[tid]   = track
                skor_id[tid] = (hs, eslesme, sorgu_sira)

    # Önce güçlü eşleşmeler, sonra belirsizler — tamamen uyumsuzları at
    sonuclar = [
        (tid, skor_id[tid])
        for tid in havuz
        if skor_id[tid][1] > 0          # eslesme > 0 → belirsiz veya güçlü
    ]

    # Sıralama: eslesme (azalan) → hit_skoru (azalan)
    sonuclar.sort(key=lambda x: (x[1][1], x[1][0]), reverse=True)

    sirali = [havuz[tid] for tid, _ in sonuclar[:MAX_SARKI]]
    return sirali

# ─────────────────────────────────────────────
# FAZ 2: PLAYLİST OLUŞTUR / GÜNCELLE
# ─────────────────────────────────────────────

def mevcut_playlist_bul(ad):
    for item in kendi_playlistlerim(sp, HESAP_ID):
        if item["name"] == ad:
            return item
    return None

def kapak_yukle(playlist_id, tur_adi):
    try:
        b64 = base64_kapak(tur_adi)
        sp.playlist_upload_cover_image(playlist_id, b64)
        print(f"    Kapak yüklendi.")
    except Exception as e:
        print(f"    [UYARI] Kapak yüklenemedi: {e}")

def playlist_kaydet(tur_adi, sarkilar):
    if not sarkilar:
        print(f"  [ATLANDI] {tur_adi}: yeterli şarkı yok")
        return

    playlist_adi = playlist_ismi(tur_adi)
    meta         = METADATA.get(tur_adi, {})
    aciklama     = meta.get("aciklama", "") + f" · {bugun}"
    mevcut       = mevcut_playlist_bul(playlist_adi)

    if mevcut:
        sp.playlist_change_details(
            mevcut["id"],
            name=playlist_adi,
            description=aciklama,
            public=True
        )
        sp.playlist_replace_items(mevcut["id"], [])
        playlist_id = mevcut["id"]
        durum = "GÜNCELLENDI"
    else:
        yeni = sp._post("me/playlists", payload={
            "name":        playlist_adi,
            "public":      True,
            "description": aciklama
        })
        playlist_id = yeni["id"]
        durum = "YENİ"

    track_ids = [t["id"] for t in sarkilar]
    for i in range(0, len(track_ids), 100):
        sp.playlist_add_items(playlist_id, track_ids[i:i+100])

    kapak_yukle(playlist_id, tur_adi)

    en_iyi = sarkilar[0]
    hs     = hit_skoru(en_iyi)
    print(f"  [{durum}] {playlist_adi} — {len(sarkilar)} şarkı | #1: {en_iyi['name']} (skor: {hs})")

# ─────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────

if __name__ != "__main__":
    sys.exit(0)   # import edilince günlük akış kendiliğinden çalışmasın

print(f"Toplam {len(TURLER)} tür işlenecek | Max {MAX_SARKI} şarkı/playlist\n")

for tur_adi, sorgular in TURLER.items():
    print(f"Taranıyor: {tur_adi}...")
    sarkilar = sarkilari_cek(tur_adi, sorgular)
    playlist_kaydet(tur_adi, sarkilar)

print(f"\n=== TAMAMLANDI [{bugun}] ===")
