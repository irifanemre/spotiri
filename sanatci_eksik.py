"""
sanatci_eksik.py — Sanatçı adıyla paylaşılan, Spotify'da olmayan en popüler YouTube parçaları

Akış:
  1. Spotify diskografisini çek (album + single + compilation)
  2. YouTube'da sanatçı adıyla geniş arama (Music kategorisi, view'a göre sıralı)
  3. Her video için istatistik (views + likes) çek
  4. Cover/tribute/karaoke gibi sahteleri ele
  5. Spotify'daki başlıklarla karşılaştır (normalize + substring)
  6. EKSİK olanları view sayısına göre sırala
  7. JSON + terminal tablo

Gereken: GOOGLE_API_KEY (.env) + YouTube Data API v3 etkin
"""

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

YT_KEY = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
YT_API = "https://www.googleapis.com/youtube/v3"

MB_API     = "https://musicbrainz.org/ws/2"
MB_HEADERS = {"User-Agent": "projectiri/1.0 (research-only)"}

from spotify_auth import get_sp
sp = get_sp()

ROOT      = os.path.dirname(os.path.abspath(__file__))
CIKTI_DIR = os.path.join(ROOT, "eksik_sarkilar")
os.makedirs(CIKTI_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# AYARLAR
# ─────────────────────────────────────────────

ARAMA_MAX        = 150  # YouTube'da max kaç sonuç tarayalım (3 sayfa × 50)
MIN_VIEWS        = 10_000   # gürültü filtresi
MIN_BENZERLIK    = 0.0      # placeholder, ileride embedding ekleyebiliriz

# Müzik olmayan / istemediğimiz başlık kelimeleri
HARIC = [
    "cover", "kover", "tribute", "tribüt", "karaoke", "instrumental olmayan",
    "remix by", "edit by", "fan made", "lyric video by",
    "tutorial", "how to play", "ders", "guitar lesson",
    "reaction", "react", "tepki", "yorum",
    "interview", "röportaj", "behind the scenes", "kamera arkası",
    "vlog", "podcast", "talks about", "anlatıyor",
    "trailer", "teaser", "tiktok", "shorts",
    "documentary", "belgesel", "making of",
]

# ─────────────────────────────────────────────
# BAŞLIK NORMALİZASYONU
# ─────────────────────────────────────────────

PARANTEZ = [
    r"\(official[^)]*\)", r"\[official[^\]]*\]",
    r"\(audio[^)]*\)",    r"\(lyric[^)]*\)",   r"\(visualizer[^)]*\)",
    r"\(music video[^)]*\)", r"\(hd[^)]*\)",   r"\(4k[^)]*\)",
    r"\(remaster[^)]*\)", r"\[remaster[^\]]*\]",
    r"\(live[^)]*\)",     r"\[live[^\]]*\]",
    r"feat\.?[^,()]*",    r"ft\.?[^,()]*",
    r"\([^)]*\)",         r"\[[^\]]*\]",
]

def normalize(text: str) -> str:
    text = text.lower()
    for p in PARANTEZ:
        text = re.sub(p, "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

def sarki_adi_cikar(yt_title: str, artist_name: str) -> str:
    """YouTube başlığından sanatçı adını çıkarıp şarkı adını döndür."""
    # Pattern: "Artist - Song", "Song - Artist", "Artist | Song" vs.
    parts = re.split(r"\s*[-–—|:]\s*", yt_title, maxsplit=2)
    if len(parts) >= 2:
        sanatci_pat = re.compile(re.escape(artist_name), re.IGNORECASE)
        non_artist  = [p for p in parts if not sanatci_pat.search(p)]
        if non_artist:
            return non_artist[0].strip()
    # Fallback: sanatçı adını çıkar
    cleaned = re.sub(re.escape(artist_name), "", yt_title, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\s\-–—|:]+|[\s\-–—|:]+$", "", cleaned).strip()
    return cleaned or yt_title.strip()

# ─────────────────────────────────────────────
# SPOTIFY DİSKOGRAFİSİ
# ─────────────────────────────────────────────

def spotify_diskografi(artist_name: str):
    """
    Dev mode'da artist_albums kısıtlı → sadece search kullan.
    Birden fazla query + tüm sayfa offsetlerinden şarkı toplar,
    her şarkıda sanatçı adı bizimkine eşleşmeli.
    """
    # ── Sanatçıyı bul: önce exact match, yoksa fuzzy ──
    aranan = artist_name.lower().strip()
    artist = None

    # 1) Exact phrase ile ara
    try:
        sonuc = sp.search(q=f'artist:"{artist_name}"', type="artist", limit=5)
        for a in sonuc["artists"]["items"]:
            if a["name"].lower().strip() == aranan:
                artist = a
                break
    except Exception:
        pass

    # 2) Bulunamazsa düz aramada exact name eşleşeni bul
    if not artist:
        try:
            sonuc = sp.search(q=artist_name, type="artist", limit=5)
            for a in sonuc["artists"]["items"]:
                if a["name"].lower().strip() == aranan:
                    artist = a
                    break
            # 3) Tam eşleşme yoksa en yakın benzeyeni al (case-insensitive substring)
            if not artist:
                for a in sonuc["artists"]["items"]:
                    if aranan in a["name"].lower() or a["name"].lower() in aranan:
                        artist = a
                        break
            # 4) Hâlâ yoksa en üstteki (uyarı ile)
            if not artist and sonuc["artists"]["items"]:
                artist = sonuc["artists"]["items"][0]
                print(f"    [UYARI] '{artist_name}' tam bulunamadı, en yakın eşleşme: '{artist['name']}'")
        except Exception:
            pass

    if not artist:
        return None, set()

    artist_low = artist["name"].lower()
    titles     = set()

    sorgular = [
        artist["name"],
        f'{artist["name"]} song',
        f'{artist["name"]} hit',
        f'{artist["name"]} album',
        f'{artist["name"]} single',
    ]

    print(f"    Spotify search ({len(sorgular)} sorgu × 50 sayfa)...")
    for q in sorgular:
        for offset in range(0, 50, 5):
            try:
                r = sp.search(q=q, type="track", limit=5, offset=offset)
            except Exception:
                break
            items = r.get("tracks", {}).get("items", [])
            if not items:
                break
            for t in items:
                art_names = [a.get("name", "").lower() for a in t.get("artists", [])]
                if artist_low in art_names and t.get("name"):
                    titles.add(normalize(t["name"]))
            time.sleep(0.25)

    return artist, titles

# ─────────────────────────────────────────────
# MUSICBRAINZ — tam diskografi (Spotify dev mode'un eksiğini kapatır)
# ─────────────────────────────────────────────

def musicbrainz_diskografi(artist_name: str, max_kayit: int = 500) -> set:
    """MusicBrainz'den sanatçının TÜM kayıtlarını çek (yıllarca biriktirilmiş açık veri)."""
    titles = set()

    # 1) Sanatçıyı bul
    try:
        q = requests.utils.quote(f'artist:"{artist_name}"')
        r = requests.get(
            f"{MB_API}/artist/?query={q}&limit=3&fmt=json",
            headers=MB_HEADERS, timeout=15
        )
        artists = r.json().get("artists", [])
        if not artists:
            return titles
        # En yüksek skorlu eşleşmeyi al
        artist_id = artists[0]["id"]
    except Exception as e:
        print(f"    [MB UYARI] sanatçı bulunamadı: {e}")
        return titles

    time.sleep(1.1)  # MB rate limit: 1 req/sec

    # 2) Tüm recording'leri al, sayfa sayfa (limit=100/sayfa)
    offset = 0
    while offset < max_kayit:
        try:
            r = requests.get(
                f"{MB_API}/recording/?artist={artist_id}&limit=100&offset={offset}&fmt=json",
                headers=MB_HEADERS, timeout=15
            )
            data = r.json()
        except Exception:
            break

        recs = data.get("recordings", [])
        if not recs:
            break
        for rec in recs:
            if rec.get("title"):
                titles.add(normalize(rec["title"]))

        offset += 100
        if len(recs) < 100:
            break
        time.sleep(1.1)

    return titles

# ─────────────────────────────────────────────
# YOUTUBE API
# ─────────────────────────────────────────────

def yt_api(endpoint, params):
    params["key"] = YT_KEY
    try:
        r    = requests.get(f"{YT_API}/{endpoint}", params=params, timeout=15)
        data = r.json()
        if "error" in data:
            mesaj = data["error"].get("message", "unknown")
            print(f"    [API HATA] {mesaj}")
            if "has not been used" in mesaj or "disabled" in mesaj:
                print("    → YouTube Data API v3 etkin değil:")
                print("    → https://console.cloud.google.com/apis/library/youtube.googleapis.com")
            return None
        return data
    except Exception as e:
        print(f"    [HATA] {e}")
        return None

def youtube_arama_view_sirali(artist_name: str, max_sonuc=ARAMA_MAX):
    """Sanatçı adıyla YouTube'da geniş arama, view sayısına göre sıralı."""
    sonuclar  = []
    next_page = None
    while len(sonuclar) < max_sonuc:
        params = {
            "q":               f'"{artist_name}"',  # tırnak: tam eşleşme
            "type":            "video",
            "videoCategoryId": "10",                # Music kategorisi
            "order":           "viewCount",         # en çok izlenen önce
            "maxResults":      50,
            "part":            "snippet",
        }
        if next_page:
            params["pageToken"] = next_page
        data = yt_api("search", params)
        if not data:
            break
        sonuclar.extend(data.get("items", []))
        next_page = data.get("nextPageToken")
        if not next_page:
            break
    return sonuclar[:max_sonuc]

def youtube_video_istatistik(video_ids):
    """Verilen video ID'leri için views + likes + snippet çek (batch 50)."""
    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        data  = yt_api("videos", {
            "id":   ",".join(batch),
            "part": "statistics,snippet,contentDetails",
        })
        if not data:
            continue
        for item in data.get("items", []):
            st = item.get("statistics", {})
            sn = item.get("snippet", {})
            stats[item["id"]] = {
                "title":     sn.get("title", ""),
                "channel":   sn.get("channelTitle", ""),
                "published": sn.get("publishedAt", "")[:10],
                "views":     int(st.get("viewCount", 0)),
                "likes":     int(st.get("likeCount", 0)) if "likeCount" in st else None,
                "duration":  item.get("contentDetails", {}).get("duration", ""),
            }
    return stats

# ─────────────────────────────────────────────
# FİLTRELER
# ─────────────────────────────────────────────

def sanatciya_ait_mi(title: str, channel: str, artist_name: str) -> bool:
    """
    SIKI eşleşme. False positive'leri eler:
      - "Teoman - Şarkı (feat. Şebnem Ferah)" → REDDEDİLİR
      - "Sezen Aksu Karaoke ft. Şebnem" → REDDEDİLİR

    Kabul kriterleri:
      1. Channel adı artist ile başlıyor (Şebnem Ferah, Şebnem Ferah VEVO, Şebnem Ferah - Topic)
      2. Title artist adıyla başlıyor ve hemen ardından separator var
         "Şebnem Ferah - Sil Baştan"   ✓
         "ŞEBNEM FERAH | Acoustic"     ✓
    """
    artist_pat = re.escape(artist_name)
    artist_low = artist_name.lower().strip()

    # 1) Channel eşleşmesi
    ch_low = channel.lower().strip()
    if ch_low == artist_low:
        return True
    # Şebnem Ferah VEVO / Şebnem Ferah - Topic / Şebnem Ferah Official
    if ch_low.startswith(artist_low) and any(
        s in ch_low for s in ["vevo", "official", "- topic", "music"]
    ):
        return True

    # 2) Title artist'le başlıyor + separator (Artist - Song)
    bas_pattern = r"^[\s\(\[\"']*" + artist_pat + r"\s*[-–—|:·•]"
    if re.match(bas_pattern, title, re.IGNORECASE):
        return True

    # 3) Title artist'le bitiyor (Song - Artist)
    bit_pattern = r"[-–—|:·•]\s*" + artist_pat + r"\s*[\)\]\"']*\s*$"
    if re.search(bit_pattern, title, re.IGNORECASE):
        return True

    return False

def duet_mu(title: str, artist_name: str) -> bool:
    """Title'da bizim sanatçımız feat/ft/with/ile olarak geçiyor mu?"""
    pat = (
        r"(feat\.?|ft\.?|with|ile|&|×|\bx\b)\s*[^,\(\)/-]*?"
        + re.escape(artist_name)
    )
    return bool(re.search(pat, title, re.IGNORECASE))

def baska_sanatci_basta_mi(title: str, kendi_sanatci: str) -> bool:
    """
    'X - Y' formatında X kendi sanatçımız değilse:
      - Düet mi? → izin ver
      - Değilse → reddet
    """
    parts = re.split(r"\s*[-–—|:·]\s*", title, maxsplit=1)
    if len(parts) < 2:
        return False
    first = re.sub(r"[\(\[].*", "", parts[0]).strip()
    if first.lower() == kendi_sanatci.lower():
        return False  # bizim sanatçı zaten başta
    if duet_mu(title, kendi_sanatci):
        return False  # düet, geçişe izin ver
    return True       # başka biri, reddet

def istenmeyen_mi(title: str) -> bool:
    """Cover/tribute/karaoke/reaction gibi başlıklar."""
    t = title.lower()
    return any(k in t for k in HARIC)

# ─────────────────────────────────────────────
# ANA AKIŞ
# ─────────────────────────────────────────────

def eksik_bul(artist_name: str):
    print(f"\n  [{artist_name}]")

    # 1a. Spotify diskografi
    print("  → Spotify diskografisi taranıyor...")
    artist, spotify_titles = spotify_diskografi(artist_name)
    if not artist:
        print(f"    ✗ Spotify'da '{artist_name}' bulunamadı")
        return None
    sa_resmi = artist["name"]
    print(f"    Spotify: {len(spotify_titles)} şarkı")

    # 1b. MusicBrainz tam diskografi (dev mode eksiğini kapatır)
    print("  → MusicBrainz'den tam diskografi alınıyor...")
    mb_titles = musicbrainz_diskografi(sa_resmi)
    print(f"    MusicBrainz: {len(mb_titles)} şarkı")

    # Birleştir — bu set "sanatçının bilinen tüm şarkıları"
    bilinen_titles = spotify_titles | mb_titles
    print(f"    Toplam bilinen: {len(bilinen_titles)} şarkı")

    # 2. YouTube geniş arama
    print(f"  → YouTube'da '{sa_resmi}' aranıyor (view sıralı)...")
    arama = youtube_arama_view_sirali(sa_resmi, max_sonuc=ARAMA_MAX)
    if not arama:
        print(f"    ✗ YouTube sonucu yok")
        return None
    print(f"    {len(arama)} aday video")

    # 3. Video ID'lerini topla, istatistik çek
    video_ids = [
        v["id"]["videoId"] for v in arama
        if v.get("id", {}).get("videoId")
    ]
    print(f"  → {len(video_ids)} video için istatistik çekiliyor...")
    stats = youtube_video_istatistik(video_ids)

    # 4. Filtreleme + cross-reference
    eksik = []
    for vid_id, info in stats.items():
        title   = info["title"]
        channel = info["channel"]
        views   = info["views"]

        # Filtre 1: sanatçıya ait mi? (sıkı)
        if not sanatciya_ait_mi(title, channel, sa_resmi):
            continue
        # Filtre 2: başka sanatçı başta mı? (Teoman - X feat. Şebnem gibi)
        if baska_sanatci_basta_mi(title, sa_resmi):
            continue
        # Filtre 3: cover/tribute/karaoke?
        if istenmeyen_mi(title):
            continue
        # Filtre 4: minimum view eşiği
        if views < MIN_VIEWS:
            continue
        # Filtre 5: bilinen diskografide var mı? (Spotify + MusicBrainz)
        song_title = sarki_adi_cikar(title, sa_resmi)
        norm       = normalize(song_title)
        if not norm or len(norm) < 3:
            continue
        if norm in bilinen_titles:
            continue
        # Substring toleransı: "aşk kırıntıları official video" → "aşk kırıntıları" var sayılır
        if any(st in norm or norm in st for st in bilinen_titles if len(st) > 4):
            continue

        eksik.append({
            "baslik":      song_title,
            "tam_baslik":  title,
            "kanal":       channel,
            "views":       views,
            "likes":       info["likes"],
            "tarih":       info["published"],
            "youtube_url": f"https://youtube.com/watch?v={vid_id}",
        })

    # View sayısına göre sırala (en popüler önce)
    eksik.sort(key=lambda x: x["views"], reverse=True)

    return {
        "sanatci":         sa_resmi,
        "spotify_id":      artist["id"],
        "spotify_sayi":    len(spotify_titles),
        "musicbrainz_sayi":len(mb_titles),
        "bilinen_toplam":  len(bilinen_titles),
        "youtube_tarand":  len(arama),
        "eksik_sayi":      len(eksik),
        "eksik_sarkilar":  eksik,
        "tarama_zamani":   datetime.now().isoformat(timespec="seconds"),
    }

# ─────────────────────────────────────────────
# ÇIKTI
# ─────────────────────────────────────────────

def kaydet(sonuc, artist_name):
    safe = re.sub(r"[^\w]+", "_", artist_name).strip("_")
    yol  = os.path.join(CIKTI_DIR, f"{safe}.json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=2)
    return yol

def view_format(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)

def tabloya_bas(sonuc, limit=40):
    print("\n  ──────────────────────────────────────────────")
    print(f"  {sonuc['sanatci']}")
    print(f"  Spotify: {sonuc['spotify_sayi']} şarkı  |  YouTube taranan: {sonuc['youtube_tarand']}")
    print(f"  EKSİK PARÇA SAYISI: {sonuc['eksik_sayi']}")
    print("  ──────────────────────────────────────────────\n")

    for i, e in enumerate(sonuc["eksik_sarkilar"][:limit], 1):
        likes = f" · {view_format(e['likes'])} beğeni" if e.get("likes") else ""
        print(f"  {i:>3}. {e['baslik']}")
        print(f"       {view_format(e['views'])} izlenme{likes}  ·  [{e['tarih']}]  ·  {e['kanal']}")
        print(f"       {e['youtube_url']}\n")

    if sonuc["eksik_sayi"] > limit:
        print(f"  ... ve {sonuc['eksik_sayi'] - limit} tane daha (JSON'da)")

# ─────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sanatci", help="Tek sanatçı adı")
    parser.add_argument("--dosya",   help="Sanatçı listesi dosyası")
    args = parser.parse_args()

    sanatcilar = []
    if args.sanatci:
        sanatcilar = [args.sanatci]
    elif args.dosya and os.path.exists(args.dosya):
        with open(args.dosya, encoding="utf-8") as f:
            sanatcilar = [s.strip() for s in f if s.strip() and not s.startswith("#")]
    else:
        s = input("Sanatçı adı → ").strip()
        if s:
            sanatcilar = [s]

    if not sanatcilar:
        print("Sanatçı belirtilmedi.")
        sys.exit(1)

    for sa in sanatcilar:
        sonuc = eksik_bul(sa)
        if sonuc:
            yol = kaydet(sonuc, sa)
            tabloya_bas(sonuc)
            print(f"\n  📁 Detaylar → {yol}\n")
