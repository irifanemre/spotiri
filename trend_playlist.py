"""
Haftalık Trend Playlist Üreticisi
──────────────────────────────────
1. Reddit'ten güncel trendleri çeker (Turkey, GenZ, memes, worldnews)
2. Claude API'ye gönderip ironi/absürd playlist isimleri ürettirir
3. Her isim için Spotify'da şarkı arar ve public playlist açar
"""

import os
import sys
import json
import time
import datetime
import requests
from dotenv import load_dotenv
import spotipy
from groq import Groq
from kapak import ai_kapak_base64

load_dotenv()

# ─── Spotify ───────────────────────────────────────────────────────────────────
from spotify_auth import get_sp, kendi_playlistlerim
sp        = get_sp()
kullanici = sp.current_user()
HESAP_ID  = kullanici["id"]
bugun     = datetime.date.today().isoformat()
print(f"[{bugun}] Hesap: {kullanici['display_name']}")

# ─── Groq ─────────────────────────────────────────────────────────────────────
from ai_config import GROQ_MODEL, groq_yanit
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─── Ayarlar ──────────────────────────────────────────────────────────────────
MAX_SARKI         = 20
MIN_SARKI         = 5
HAFTALIK_PLAYLIST = 6   # Bu haftanın kaç yaratıcı playlist'i oluşturulsun

REDDIT_KAYNAKLAR = [
    ("Turkey",    15),   # (subreddit, kaç post)
    ("GenZ",      10),
    ("memes",     10),
    ("worldnews",  8),
    ("TikTokCringe", 5),
]

REDDIT_HEADERS = {"User-Agent": "Mozilla/5.0 SpotifyPlaylistBot/1.0"}

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 1: REDDIT'TEN TREND VERİSİ ÇEK
# ─────────────────────────────────────────────────────────────────────────────

def reddit_trendleri_cek():
    trendler = []
    for subreddit, limit in REDDIT_KAYNAKLAR:
        try:
            url  = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            resp = requests.get(url, headers=REDDIT_HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            posts = resp.json()["data"]["children"]
            for post in posts:
                baslik = post["data"].get("title", "").strip()
                if baslik and len(baslik) > 10:
                    trendler.append(f"[{subreddit}] {baslik}")
        except Exception as e:
            print(f"  [UYARI] Reddit {subreddit}: {e}")
    print(f"  {len(trendler)} trend başlığı toplandı.")
    return trendler

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 2: CLAUDE API — YARATICI PLAYLİST İSİMLERİ ÜRET
# ─────────────────────────────────────────────────────────────────────────────

SISTEM_PROMPT = """
Sen Spotify için viral playlist isimleri üretiyorsun.
Hedef kitle: 18–30 yaş, ironi seven, internet kültürüne hakim, TikTok/Twitter'da vakit geçiren gençler.

Ürettiğin isimler şu formüllerden birini takip etmeli:
- Absürd tarihsel/dini referans: "Hz. İsa'nın çarmıha gerilirken dinlediği müzikler"
- Era formatı: "nerdy girl era", "situationship survivor era"
- Güncel olayla mizah: trendle ilgili ama beklenmedik bağlantı
- Varoluşsal komedi: "3 saattir uyumaya çalışırken beynin seni sabote ettiği anlar"
- Niş niyet: "patron yanına gelince hızlıca küçülttüğün ekran için müzikler"
- Türkçe absürd: "annem 'bi dakika' diyip 45 dakika gittiğinde dinlenecekler"

Yanıtın SADECE geçerli JSON olsun. Başka hiçbir metin ekleme.
"""

KULLANICI_PROMPT_SABLONU = """
Bu haftanın güncel trendleri:
{trendler}

Bu trendleri referans alarak {sayi} adet playlist üret.
3'ü Türkçe, 3'ü İngilizce olsun.
Trendleri kullanmak zorunda değilsin — genel ruh halinden ilham al.

Her playlist için şarkı aramak amacıyla 2-3 Spotify arama sorgusu da ekle.
Sorgular basit İngilizce kelimeler olsun (phonk, sad indie, dramatic classical vb.)

Format:
[
  {{
    "isim": "playlist ismi tam hali",
    "dil": "tr veya en",
    "tema_aciklama": "bu playlist hangi duyguya/ana hitap ediyor",
    "arama_sorgu": ["sorgu1", "sorgu2", "sorgu3"],
    "gorsel_prompt": "Vivid English visual description for AI image generation. Mood, colors, style, atmosphere. No text. Example: dark moody bedroom at 3am, blue neon light through window, cinematic, photorealistic"
  }}
]
"""

def claude_ile_isim_uret(trendler):
    trend_metni = "\n".join(trendler[:30])  # İlk 30 trend
    prompt = KULLANICI_PROMPT_SABLONU.format(
        trendler=trend_metni,
        sayi=HAFTALIK_PLAYLIST
    )
    print(f"  Groq API'ye gönderiliyor ({GROQ_MODEL})...")
    ham = groq_yanit(groq, [
        {"role": "system", "content": SISTEM_PROMPT},
        {"role": "user",   "content": prompt}
    ], max_tokens=1500)
    # JSON başlangıç/bitiş kontrolü
    if not ham.startswith("["):
        baslangic = ham.find("[")
        bitis     = ham.rfind("]") + 1
        ham = ham[baslangic:bitis]
    playlistler = json.loads(ham)
    print(f"  {len(playlistler)} yaratıcı playlist üretildi.")
    return playlistler

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 3: SPOTIFY'DAN ŞARKI ÇEK
# ─────────────────────────────────────────────────────────────────────────────

def spotify_ara(sorgu, offset=0, deneme=3):
    """Rate limit farkındalıklı Spotify arama. 429 gelirse bekler."""
    for i in range(deneme):
        try:
            return sp.search(q=sorgu, type="track", limit=5, offset=offset)
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                bekleme = int(e.headers.get("Retry-After", 30)) + 5
                print(f"  [RATE LIMIT] {bekleme}s bekleniyor...")
                time.sleep(bekleme)
            else:
                return None
        except Exception:
            return None
    return None

def sarkilari_cek(arama_sorgu_listesi):
    sarkilar = []
    gorulen  = set()
    # Sadece ilk sorgu, tek sayfa → minimum API isteği
    for sorgu in arama_sorgu_listesi[:2]:
        sonuc = spotify_ara(sorgu, offset=0)
        if not sonuc:
            continue
        for track in sonuc["tracks"]["items"]:
            tid = track.get("id")
            if not tid or tid in gorulen:
                continue
            gorulen.add(tid)
            sarkilar.append(track)
        time.sleep(1)  # istekler arası 1 saniye bekleme
    sarkilar.sort(key=lambda t: t.get("popularity") or 0, reverse=True)
    return sarkilar[:MAX_SARKI]

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 4: PLAYLİST OLUŞTUR
# ─────────────────────────────────────────────────────────────────────────────

def mevcut_bul(ad):
    for item in kendi_playlistlerim(sp, HESAP_ID):
        if item["name"] == ad:
            return item
    return None

def playlist_olustur(playlist_verisi, sarkilar):
    isim     = playlist_verisi["isim"]
    tema     = playlist_verisi.get("tema_aciklama", "")
    aciklama = f"{tema} · Haftalık otomatik güncelleme · {bugun}"

    mevcut = mevcut_bul(isim)

    if mevcut:
        sp.playlist_change_details(mevcut["id"], description=aciklama)
        sp.playlist_replace_items(mevcut["id"], [])
        playlist_id = mevcut["id"]
        durum = "GÜNCELLENDI"
    else:
        yeni = sp._post("me/playlists", payload={
            "name":        isim,
            "public":      True,
            "description": aciklama
        })
        playlist_id = yeni["id"]
        durum = "YENİ"

    if sarkilar:
        ids = [t["id"] for t in sarkilar]
        for i in range(0, len(ids), 100):
            sp.playlist_add_items(playlist_id, ids[i:i + 100])

    # Nano Banana ile AI kapak üret ve yükle
    gorsel_prompt = playlist_verisi.get("gorsel_prompt", "")
    if gorsel_prompt:
        try:
            print(f"    AI kapak üretiyor...")
            b64 = ai_kapak_base64(gorsel_prompt)
            sp.playlist_upload_cover_image(playlist_id, b64)
            print(f"    Kapak yüklendi.")
        except Exception as e:
            print(f"    [UYARI] Kapak üretilemedi: {e}")

    dil_etiketi = "🇹🇷" if playlist_verisi.get("dil") == "tr" else "🌍"
    print(f"  [{durum}] {dil_etiketi} \"{isim}\" — {len(sarkilar)} şarkı")

# ─────────────────────────────────────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────────────────────────────────────

if __name__ != "__main__":
    sys.exit(0)   # import edilince haftalık akış kendiliğinden çalışmasın

print("\n── FAZ 1: Trend verisi toplanıyor ──")
trendler = reddit_trendleri_cek()

print("\n── FAZ 2: Claude isim üretiyor ──")
playlistler = claude_ile_isim_uret(trendler)

print("\n── FAZ 3 & 4: Şarkılar çekiliyor ve playlist'ler oluşturuluyor ──")
for pl in playlistler:
    sarkilar = sarkilari_cek(pl["arama_sorgu"])
    if len(sarkilar) < MIN_SARKI:
        print(f"  [ATLANDI] \"{pl['isim']}\" — yeterli şarkı yok ({len(sarkilar)})")
        continue
    playlist_olustur(pl, sarkilar)

print(f"\n=== HAFTALIK GÜNCELLEME TAMAMLANDI [{bugun}] ===")
