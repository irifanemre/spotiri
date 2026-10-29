"""
TikTok için Spotify playlist tanıtım videosu üretici.
- Bir playlist seç → cover + 1 track preview alır
- 1080x1920 (9:16) MP4 video üretir
- Groq ile viral caption + hashtag yazar
- Çıktı: tiktok_videos/ klasörü
Sen sadece yüklersin.
"""

import os
import sys
import io
import time
import random
import argparse
import requests
from dotenv import load_dotenv
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from groq import Groq
from moviepy import ImageClip, AudioFileClip, CompositeVideoClip

load_dotenv()

# ─── Spotify ───────────────────────────────────────────────────────────────
from spotify_auth import get_sp, kendi_playlistlerim
sp = get_sp()
me       = sp.current_user()
HESAP_ID = me["id"]

# ─── Groq ──────────────────────────────────────────────────────────────────
from ai_config import groq_yanit
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─── Ayarlar ───────────────────────────────────────────────────────────────
GENISLIK     = 1080
YUKSEKLIK    = 1920
VIDEO_SURESI = 15            # saniye
CIKTI_KLASOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok_videos")
os.makedirs(CIKTI_KLASOR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 1: PLAYLİST + TRACK SEÇ
# ─────────────────────────────────────────────────────────────────────────────

def _track_cek(item):
    """Spotify hem 'track' hem 'item' field'ı kullanıyor, ikisini de dene."""
    return item.get("track") or item.get("item")

def playlist_sec(isim_parca=None):
    mine = kendi_playlistlerim(sp, HESAP_ID)
    if isim_parca:
        mine = [p for p in mine if isim_parca.lower() in p["name"].lower()]
    if not mine:
        sys.exit("Eşleşen playlist yok.")
    random.shuffle(mine)
    for p in mine:
        items = sp.playlist_tracks(p["id"], limit=1)
        if items.get("items") and _track_cek(items["items"][0]):
            return p
    sys.exit("Tüm playlist'ler boş — önce daily script çalışmalı.")

def previewli_track_bul(playlist_id):
    # Bazen Spotify boş döndürüyor, 3 defaya kadar dene
    for deneme in range(3):
        items  = sp.playlist_tracks(playlist_id, limit=30)
        tracks = [_track_cek(it) for it in items.get("items", [])]
        tracks = [t for t in tracks if t and t.get("id")]
        if tracks:
            previewli = [t for t in tracks if t.get("preview_url")]
            return random.choice(previewli or tracks)
        time.sleep(1)
    return None

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 2: GROQ İLE CAPTION ÜRET
# ─────────────────────────────────────────────────────────────────────────────

def caption_uret(playlist_adi, track_adi, sanatci):
    prompt = f"""Spotify playlist'i için TikTok caption yaz.
Playlist ismi: "{playlist_adi}"
Şu an çalan: {track_adi} - {sanatci}

Format:
1. İlk satır: 1 cümlelik viral "POV:" tarzı hook (Türkçe veya İngilizce, playlist diliyle uyumlu)
2. Sonraki satır boş
3. Son satır: 6-8 TikTok hashtag (#spotifyplaylist #fyp dahil)

SADECE caption'ı döndür, başka açıklama yok.
"""
    return groq_yanit(groq, [{"role": "user", "content": prompt}], max_tokens=200)

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 3: GÖRSEL OLUŞTUR (1080x1920)
# ─────────────────────────────────────────────────────────────────────────────

def font_yukle(boyut, kalin=True):
    for yol in ["/System/Library/Fonts/HelveticaNeue.ttc",
                "/System/Library/Fonts/Helvetica.ttc"]:
        for idx in ([1, 0] if kalin else [0]):
            try:
                return ImageFont.truetype(yol, boyut, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()

def text_wrap(metin, font, max_gen, draw):
    kelimeler = metin.split()
    satirlar  = []
    aktif     = ""
    for k in kelimeler:
        deneme = (aktif + " " + k).strip()
        if draw.textlength(deneme, font=font) <= max_gen:
            aktif = deneme
        else:
            if aktif: satirlar.append(aktif)
            aktif = k
    if aktif: satirlar.append(aktif)
    return satirlar

def gorsel_olustur(cover_url, playlist_adi, track_adi, sanatci):
    # Cover indir
    cover = Image.open(io.BytesIO(requests.get(cover_url, timeout=15).content)).convert("RGB")

    # ── Bulanık arka plan ──
    arkaplan = cover.resize((GENISLIK, GENISLIK), Image.LANCZOS)
    # 9:16 için en/boy oranı: cover'ı orantılı büyüt sonra kırp
    arkaplan = cover.resize((GENISLIK, int(GENISLIK * cover.size[1] / cover.size[0])), Image.LANCZOS)
    if arkaplan.size[1] < YUKSEKLIK:
        arkaplan = arkaplan.resize((int(YUKSEKLIK * arkaplan.size[0] / arkaplan.size[1]), YUKSEKLIK), Image.LANCZOS)
    # Merkezden kırp
    sol = (arkaplan.size[0] - GENISLIK) // 2
    ust = (arkaplan.size[1] - YUKSEKLIK) // 2
    arkaplan = arkaplan.crop((sol, ust, sol + GENISLIK, ust + YUKSEKLIK))
    arkaplan = arkaplan.filter(ImageFilter.GaussianBlur(40))

    # ── Karartma katmanı ──
    karart = Image.new("RGBA", (GENISLIK, YUKSEKLIK), (0, 0, 0, 140))
    arkaplan = Image.alpha_composite(arkaplan.convert("RGBA"), karart)

    draw = ImageDraw.Draw(arkaplan)

    # ── Playlist adı (üstte) ──
    baslik_font = font_yukle(80, kalin=True)
    satirlar    = text_wrap(playlist_adi.upper(), baslik_font, GENISLIK - 120, draw)
    y = 280
    for satir in satirlar:
        draw.text((GENISLIK // 2, y), satir, font=baslik_font, fill=(255, 255, 255), anchor="mm")
        y += 95

    # ── Cover (ortada) ──
    cover_kare = cover.resize((720, 720), Image.LANCZOS)
    cover_kare_rgba = cover_kare.convert("RGBA")
    # Köşeleri yuvarla
    mask = Image.new("L", (720, 720), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 720, 720], radius=40, fill=255)
    cover_kare_rgba.putalpha(mask)
    arkaplan.paste(cover_kare_rgba, ((GENISLIK - 720) // 2, 750), cover_kare_rgba)

    # ── Track ismi (alt) ──
    track_font = font_yukle(48, kalin=True)
    sanatci_font = font_yukle(38, kalin=False)

    draw = ImageDraw.Draw(arkaplan)
    draw.text((GENISLIK // 2, 1580), f"♪ {track_adi[:35]}",
              font=track_font, fill=(255, 255, 255), anchor="mm")
    draw.text((GENISLIK // 2, 1640), sanatci[:40],
              font=sanatci_font, fill=(200, 200, 200), anchor="mm")

    # ── CTA (en alt) ──
    cta_font = font_yukle(42, kalin=True)
    draw.text((GENISLIK // 2, 1820), "▶ Spotify'da dinle",
              font=cta_font, fill=(30, 215, 96), anchor="mm")

    return arkaplan.convert("RGB")

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 4: VİDEO BİRLEŞTİR
# ─────────────────────────────────────────────────────────────────────────────

def video_olustur(gorsel_yol, preview_url, cikti_yol):
    if preview_url:
        ses_data = requests.get(preview_url, timeout=20).content
        ses_yol  = cikti_yol.replace(".mp4", "_audio.mp3")
        with open(ses_yol, "wb") as f:
            f.write(ses_data)
        ses = AudioFileClip(ses_yol).subclipped(0, min(VIDEO_SURESI, 29))
    else:
        ses = None
        ses_yol = None

    klip = ImageClip(gorsel_yol).with_duration(VIDEO_SURESI)
    if ses:
        klip = klip.with_audio(ses)

    klip.write_videofile(cikti_yol, fps=30, codec="libx264",
                         audio_codec="aac", logger=None)

    if ses_yol and os.path.exists(ses_yol):
        os.remove(ses_yol)

# ─────────────────────────────────────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────────────────────────────────────

if __name__ != "__main__":
    sys.exit(0)

parser = argparse.ArgumentParser()
parser.add_argument("--playlist", help="Playlist ismi içinde geçen kelime (boşsa rastgele)")
parser.add_argument("--sayi", type=int, default=1, help="Üretilecek video sayısı")
args = parser.parse_args()

for i in range(args.sayi):
    print(f"\n=== VİDEO {i+1}/{args.sayi} ===")

    playlist = playlist_sec(args.playlist)
    print(f"Playlist: {playlist['name']}")

    track = previewli_track_bul(playlist["id"])
    if not track:
        print("Hiç track yok, atlanıyor.")
        continue
    sanatci = track["artists"][0]["name"]
    print(f"Track: {track['name']} — {sanatci}")
    print(f"Preview: {'VAR' if track.get('preview_url') else 'YOK (sessiz video)'}")

    cover_url = playlist["images"][0]["url"] if playlist.get("images") else track["album"]["images"][0]["url"]

    print("Görsel oluşturuluyor...")
    img = gorsel_olustur(cover_url, playlist["name"], track["name"], sanatci)

    zaman_dmg = time.strftime("%Y%m%d_%H%M%S")
    guvenli_isim = "".join(c if c.isalnum() else "_" for c in playlist["name"])[:40]
    temel = f"{CIKTI_KLASOR}/{zaman_dmg}_{guvenli_isim}"

    img_yol = f"{temel}.jpg"
    img.save(img_yol, quality=92)

    print("Video birleştiriliyor...")
    video_yol = f"{temel}.mp4"
    video_olustur(img_yol, track.get("preview_url"), video_yol)

    print("Caption üretiliyor...")
    try:
        caption = caption_uret(playlist["name"], track["name"], sanatci)
    except Exception as e:
        caption = f"#spotifyplaylist #fyp #playlist (caption hata: {e})"

    caption_yol = f"{temel}_caption.txt"
    with open(caption_yol, "w") as f:
        f.write(caption + f"\n\n🔗 Spotify: {playlist['external_urls']['spotify']}\n")

    print(f"\n✅ HAZIR:")
    print(f"   Video:   {video_yol}")
    print(f"   Caption: {caption_yol}")

print(f"\n=== TÜM VIDEOLAR {CIKTI_KLASOR} İÇİNDE ===")
