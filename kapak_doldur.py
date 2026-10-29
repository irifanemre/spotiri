"""
Kapağı olmayan playlist'leri tarar, sadece onlara kapak yükler.
- Daily playlist'ler (DARK DRIVE, GOLDEN HOUR vs.) → Pillow gradient
- Trend playlist'ler (Groq-üretimi)               → Pollinations.ai
Spotify arama API'sini hiç kullanmaz, kotaya etki yapmaz.
"""

import os
import sys
import time
import base64
from dotenv import load_dotenv
from kapak import KONFIGLAR, base64_kapak, pollinations_kapak

load_dotenv()

from spotify_auth import get_sp, kendi_playlistlerim
sp = get_sp()

kullanici = sp.current_user()
HESAP_ID  = kullanici["id"]
print(f"Hesap: {kullanici['display_name']}\n")

# ─── İsim eşleştirmesi: playlist adı → Pillow konfigürasyon anahtarı ───
PLAYLIST_TO_KONFIG = {
    "DARK DRIVE":          "Phonk",
    "HEAVY IS THE CROWN":  "Hip-Hop",
    "GOLDEN HOUR":         "Pop",
    "AFTER MIDNIGHT":      "Electronic",
    "SILK HOURS":          "R&B",
    "RAW VOLTAGE":         "Rock",
    "STILL WATER":         "Chill",
    "FUEGO":               "Latin",
    "İSTANBUL GECELERİ":   "Türkçe",
}

def gercek_kapak_var_mi(playlist):
    """
    True  = kullanıcı upload etmiş gerçek kapak var.
    False = boş veya Spotify'ın otomatik mosaic'i (yenisi yüklenebilir).
    """
    images = playlist.get("images") or []
    if not images:
        return False
    url = images[0].get("url", "")
    # mosaic.scdn.co = Spotify'ın otomatik derlemesi
    if "mosaic.scdn.co" in url:
        return False
    return True

def gorsel_prompt_uret(playlist_adi, aciklama=""):
    """Playlist isminden Pollinations için görsel prompt üretir."""
    # İsim Türkçeyse İngilizceye çevirmiyoruz, Pollinations Türkçe anlamayabilir
    # ama mood kelimeleri ekleyerek tema açıkça kalsın
    ipuclari = []
    isim_lower = playlist_adi.lower()
    if any(k in isim_lower for k in ["dark", "phonk", "night", "midnight", "gece"]):
        ipuclari.append("dark moody atmospheric night")
    if any(k in isim_lower for k in ["chill", "still", "soft", "calm"]):
        ipuclari.append("soft pastel calming dreamy")
    if any(k in isim_lower for k in ["fire", "fuego", "heat", "hot"]):
        ipuclari.append("vibrant warm orange red energetic")
    if any(k in isim_lower for k in ["golden", "gold", "hour"]):
        ipuclari.append("golden hour sunset cinematic")
    if not ipuclari:
        ipuclari.append("cinematic atmospheric mood")

    mood = ", ".join(ipuclari)
    return f"{playlist_adi}, {mood}, aesthetic album cover art, vibrant composition"

def kapak_uret(playlist_adi):
    """Playlist tipini tespit edip uygun kapağı üretir, base64 döndürür."""
    if playlist_adi in PLAYLIST_TO_KONFIG:
        tur = PLAYLIST_TO_KONFIG[playlist_adi]
        return base64_kapak(tur), "Pillow"
    else:
        prompt    = gorsel_prompt_uret(playlist_adi)
        ham_bytes = pollinations_kapak(prompt)
        return base64.b64encode(ham_bytes).decode("utf-8"), "Pollinations"

# ─────────────────────────────────────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────────────────────────────────────

if __name__ != "__main__":
    sys.exit(0)   # import edilince kapak yükleme kendiliğinden çalışmasın

print("Tüm playlist'ler taranıyor...")
playlistler = kendi_playlistlerim(sp, HESAP_ID)
print(f"{len(playlistler)} senin playlist'in bulundu.\n")

islenecek = [p for p in playlistler if not gercek_kapak_var_mi(p)]
zaten_var = len(playlistler) - len(islenecek)

print(f"  → {zaten_var} playlist'in zaten kapağı var, atlanıyor")
print(f"  → {len(islenecek)} playlist'e kapak yüklenecek\n")

for pl in islenecek:
    isim = pl["name"]
    print(f"[{isim}]")
    try:
        b64, kaynak = kapak_uret(isim)
        sp.playlist_upload_cover_image(pl["id"], b64)
        print(f"  ✓ Yüklendi ({kaynak})")
    except Exception as e:
        print(f"  ✗ Hata: {e}")
    time.sleep(1)  # Spotify'a nezaket

print("\n=== TAMAMLANDI ===")
