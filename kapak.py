"""
Spotify playlist kapak görseli üretici.
- Günlük genre playlist'ler: Pillow ile gradient tasarım
- Haftalık trend playlist'ler: Nano Banana (Google Gemini) ile AI görsel
"""

import io
import os
import base64
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types as gtypes

BOYUT = 640

# ─────────────────────────────────────────────
# ARAŞTIRMAYA DAYALI PLAYLİST TANIMLARI
# Mood-based + activity = en yüksek etkileşim
# ─────────────────────────────────────────────

KONFIGLAR = {
    "Phonk": {
        "isim":     "DARK DRIVE",
        "alt":      "Night Frequencies",
        "renk1":    (15, 0, 35),
        "renk2":    (110, 0, 65),
        "yazi":     (240, 160, 255),
        "aksant":   (180, 0, 120),
    },
    "Hip-Hop": {
        "isim":     "HEAVY IS\nTHE CROWN",
        "alt":      "Street Dominance",
        "renk1":    (8, 8, 8),
        "renk2":    (55, 38, 0),
        "yazi":     (255, 200, 60),
        "aksant":   (200, 140, 0),
    },
    "Pop": {
        "isim":     "GOLDEN HOUR",
        "alt":      "Today's Hits",
        "renk1":    (180, 50, 70),
        "renk2":    (255, 150, 30),
        "yazi":     (255, 255, 255),
        "aksant":   (255, 220, 100),
    },
    "Electronic": {
        "isim":     "AFTER\nMIDNIGHT",
        "alt":      "Deep Frequencies",
        "renk1":    (0, 8, 45),
        "renk2":    (0, 140, 175),
        "yazi":     (80, 230, 255),
        "aksant":   (0, 200, 230),
    },
    "R&B": {
        "isim":     "SILK HOURS",
        "alt":      "Velvet Soul",
        "renk1":    (45, 0, 20),
        "renk2":    (150, 45, 85),
        "yazi":     (255, 190, 210),
        "aksant":   (210, 100, 140),
    },
    "Rock": {
        "isim":     "RAW VOLTAGE",
        "alt":      "Electric Edge",
        "renk1":    (12, 0, 0),
        "renk2":    (155, 18, 0),
        "yazi":     (255, 255, 255),
        "aksant":   (220, 50, 0),
    },
    "Chill": {
        "isim":     "STILL WATER",
        "alt":      "Weightless",
        "renk1":    (12, 35, 55),
        "renk2":    (60, 165, 148),
        "yazi":     (190, 255, 242),
        "aksant":   (80, 200, 180),
    },
    "Latin": {
        "isim":     "FUEGO",
        "alt":      "Solar Heat",
        "renk1":    (140, 25, 0),
        "renk2":    (255, 148, 0),
        "yazi":     (255, 255, 255),
        "aksant":   (255, 200, 50),
    },
    "Türkçe": {
        "isim":     "İSTANBUL\nGECELERİ",
        "alt":      "Şehir Işıkları",
        "renk1":    (100, 8, 12),
        "renk2":    (12, 18, 65),
        "yazi":     (255, 215, 170),
        "aksant":   (200, 100, 60),
    },
}

# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def font_yukle(boyut, kalin=False):
    adaylar = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    # HelveticaNeue.ttc: 0=Regular, 1=Bold, 2=BoldItalic, 3=Italic
    for yol in adaylar:
        for indeks in ([1, 0] if kalin else [0]):
            try:
                return ImageFont.truetype(yol, boyut, index=indeks)
            except Exception:
                continue
    return ImageFont.load_default()

def diagonal_gradient(boyut, renk1, renk2):
    """Sol-üst → sağ-alt köşegen geçişi."""
    img  = Image.new("RGB", (boyut, boyut))
    draw = ImageDraw.Draw(img)
    for y in range(boyut):
        t = y / boyut
        r = int(renk1[0] * (1 - t) + renk2[0] * t)
        g = int(renk1[1] * (1 - t) + renk2[1] * t)
        b = int(renk1[2] * (1 - t) + renk2[2] * t)
        draw.line([(0, y), (boyut, y)], fill=(r, g, b))
    return img

def geometrik_aksanlar(img, aksant_rengi, yazi_rengi):
    """Köşe çizgisi ve dekoratif daire."""
    draw = ImageDraw.Draw(img, "RGBA")
    a_r, a_g, a_b = aksant_rengi

    # Sol üst köşe L-çizgisi
    draw.line([(40, 40), (40, 110)],  fill=(*aksant_rengi, 180), width=2)
    draw.line([(40, 40), (110, 40)],  fill=(*aksant_rengi, 180), width=2)

    # Sağ alt köşe L-çizgisi
    draw.line([(600, 600), (600, 530)], fill=(*aksant_rengi, 180), width=2)
    draw.line([(600, 600), (530, 600)], fill=(*aksant_rengi, 180), width=2)

    # Büyük şeffaf daire (sağ-üst bölgede)
    draw.ellipse([380, -120, 780, 280], outline=(*aksant_rengi, 35), width=1)

    return img

def metin_boyutu_ayarla(draw, metin, max_gen, baslangic_boyutu, kalin=True):
    """Metin max_gen piksel içine sığana kadar font boyutunu küçültür."""
    boyut = baslangic_boyutu
    while boyut > 20:
        font = font_yukle(boyut, kalin)
        # Çok satırlı metin için en geniş satırı ölç
        max_satir_gen = max(
            draw.textlength(satir, font=font)
            for satir in metin.split("\n")
        )
        if max_satir_gen <= max_gen:
            return font, boyut
        boyut -= 4
    return font_yukle(20, kalin), 20

# ─────────────────────────────────────────────
# ANA FONKSİYON
# ─────────────────────────────────────────────

def kapak_olustur_bytes(tur_adi):
    """Tür adına göre kapak görseli üretir, JPEG bytes döndürür."""
    konfig = KONFIGLAR.get(tur_adi)
    if not konfig:
        raise ValueError(f"Bilinmeyen tür: {tur_adi}")

    img  = diagonal_gradient(BOYUT, konfig["renk1"], konfig["renk2"])
    img  = img.convert("RGBA")
    img  = geometrik_aksanlar(img, konfig["aksant"], konfig["yazi"])
    draw = ImageDraw.Draw(img)

    cx = BOYUT // 2   # merkez x
    cy = BOYUT // 2   # merkez y

    # ── Ana başlık ──
    max_gen   = BOYUT - 80   # kenar boşluğu
    ana_font, ana_boyut = metin_boyutu_ayarla(draw, konfig["isim"], max_gen, 100)
    satir_sayisi = konfig["isim"].count("\n") + 1
    satir_yuksek = ana_boyut * 1.15

    # Başlık dikey merkez
    toplam_yuksek = satir_sayisi * satir_yuksek
    baslik_y      = cy - toplam_yuksek / 2 - 20

    for i, satir in enumerate(konfig["isim"].split("\n")):
        y = baslik_y + i * satir_yuksek
        draw.text((cx, y), satir, font=ana_font,
                  fill=(*konfig["yazi"], 255), anchor="mm")

    # ── Yatay çizgi (başlık ile alt başlık arası) ──
    cizgi_y = baslik_y + toplam_yuksek + 18
    cizgi_rengi = (*konfig["aksant"], 180)
    draw.line([(cx - 80, cizgi_y), (cx + 80, cizgi_y)],
              fill=cizgi_rengi, width=1)

    # ── Alt başlık ──
    alt_font = font_yukle(26, kalin=False)
    alt_y    = cizgi_y + 28
    draw.text((cx, alt_y), konfig["alt"].upper(),
              font=alt_font, fill=(*konfig["yazi"], 160), anchor="mm")

    # ── Alt imza ──
    imza_font = font_yukle(18, kalin=False)
    draw.text((cx, BOYUT - 38), "AUTO CURATED",
              font=imza_font, fill=(*konfig["aksant"], 120), anchor="mm")

    # JPEG'e çevir ve boyut kontrolü yap
    img = img.convert("RGB")
    buffer = io.BytesIO()
    kalite = 90
    while kalite >= 60:
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, format="JPEG", quality=kalite)
        if buffer.tell() < 250_000:
            break
        kalite -= 10

    buffer.seek(0)
    return buffer.read()

def base64_kapak(tur_adi):
    """Tür için base64 kodlu JPEG string döndürür (Spotify API için)."""
    return base64.b64encode(kapak_olustur_bytes(tur_adi)).decode("utf-8")

def playlist_ismi(tur_adi):
    """Spotify'daki playlist adı olarak kullanılacak ismi döndürür."""
    konfig = KONFIGLAR.get(tur_adi, {})
    return konfig.get("isim", f"Auto | {tur_adi}").replace("\n", " ")

# ─────────────────────────────────────────────
# NANO BANANA — AI KAPAK ÜRETİCİ
# Google Gemini image generation (ücretsiz)
# Haftalık trend playlist'leri için kullanılır
# ─────────────────────────────────────────────

def nano_banana_kapak(gorsel_prompt: str) -> bytes:
    """
    Verilen prompt ile Nano Banana (Google Gemini) üzerinden
    AI kapak görseli üretir. JPEG bytes döndürür.
    Hata durumunda Pillow fallback devreye girer.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY .env dosyasında bulunamadı.")

    client = genai.Client(api_key=api_key)

    # Spotify için optimize prompt: kare format, yüksek kontrast, bold
    tam_prompt = (
        f"{gorsel_prompt}. "
        "Square format 1:1, album cover art style, bold composition, "
        "high contrast, no text, no watermark, professional music playlist cover."
    )

    from ai_config import GEMINI_IMAGE_MODEL
    yanit = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=tam_prompt,
    )

    for part in yanit.candidates[0].content.parts:
        if part.inline_data is not None and part.inline_data.data:
            ham_bytes = part.inline_data.data
            # PNG gelebilir → JPEG'e çevir, 250KB altına düşür
            img    = Image.open(io.BytesIO(ham_bytes)).convert("RGB")
            img    = img.resize((640, 640), Image.LANCZOS)
            buffer = io.BytesIO()
            kalite = 90
            while kalite >= 60:
                buffer.seek(0); buffer.truncate()
                img.save(buffer, format="JPEG", quality=kalite)
                if buffer.tell() < 250_000:
                    break
                kalite -= 10
            buffer.seek(0)
            return buffer.read()

    raise RuntimeError("Nano Banana görsel döndürmedi.")

def nano_banana_base64(gorsel_prompt: str) -> str:
    """Nano Banana ile üretilen görseli base64 string olarak döndürür."""
    return base64.b64encode(nano_banana_kapak(gorsel_prompt)).decode("utf-8")

# ─────────────────────────────────────────────
# POLLINATIONS.AI — ÜCRETSİZ AI GÖRSEL ÜRETİCİ
# API key gerektirmez, Stable Diffusion tabanlı
# Nano Banana'nın free tier alternatifi
# ─────────────────────────────────────────────

def pollinations_kapak(gorsel_prompt: str) -> bytes:
    """
    Pollinations.ai üzerinden ücretsiz AI görsel üretir.
    640x640 JPEG bytes döndürür.
    """
    tam_prompt = (
        f"{gorsel_prompt}, album cover art, square 1:1 composition, "
        "bold, high contrast, no text, no watermark, professional"
    )
    encoded = urllib.parse.quote(tam_prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        "?width=1024&height=1024&model=flux&nologo=true&enhance=true"
    )

    resp = requests.get(url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"Pollinations hata: {resp.status_code}")

    img    = Image.open(io.BytesIO(resp.content)).convert("RGB")
    img    = img.resize((640, 640), Image.LANCZOS)
    buffer = io.BytesIO()
    kalite = 90
    while kalite >= 60:
        buffer.seek(0); buffer.truncate()
        img.save(buffer, format="JPEG", quality=kalite)
        if buffer.tell() < 250_000:
            break
        kalite -= 10
    buffer.seek(0)
    return buffer.read()

# ─────────────────────────────────────────────
# CLOUDFLARE WORKERS AI — Ücretsiz 10K req/gün
# FLUX-1-schnell (4 step, hızlı + kaliteli)
# ─────────────────────────────────────────────

def cloudflare_kapak(gorsel_prompt: str) -> bytes:
    """
    Cloudflare Workers AI üzerinden FLUX-1-schnell ile görsel üretir.
    Ücretsiz: 10.000 istek/gün.
    """
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token  = os.getenv("CLOUDFLARE_API_TOKEN")
    if not (account_id and api_token):
        raise EnvironmentError(
            "CLOUDFLARE_ACCOUNT_ID veya CLOUDFLARE_API_TOKEN .env'de yok."
        )

    tam_prompt = (
        f"{gorsel_prompt}, album cover art, square 1:1 composition, "
        "bold high contrast, no text, no watermark, professional music cover"
    )

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type":  "application/json",
    }
    payload = {"prompt": tam_prompt, "steps": 4}

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Cloudflare AI hata: {resp.status_code} — {resp.text[:200]}")

    data = resp.json()
    if not data.get("success") or "result" not in data:
        raise RuntimeError(f"Cloudflare AI başarısız: {data}")

    # FLUX response: result.image = base64 PNG
    img_b64   = data["result"].get("image")
    if not img_b64:
        raise RuntimeError("Cloudflare AI görsel döndürmedi.")
    ham_bytes = base64.b64decode(img_b64)

    img    = Image.open(io.BytesIO(ham_bytes)).convert("RGB")
    img    = img.resize((640, 640), Image.LANCZOS)
    buffer = io.BytesIO()
    kalite = 90
    while kalite >= 60:
        buffer.seek(0); buffer.truncate()
        img.save(buffer, format="JPEG", quality=kalite)
        if buffer.tell() < 250_000:
            break
        kalite -= 10
    buffer.seek(0)
    return buffer.read()

def ai_kapak_base64(gorsel_prompt: str) -> str:
    """
    Akıllı kapak üretici — fallback zinciri:
      1. Nano Banana (Google Gemini)   — billing açıksa en kaliteli
      2. Cloudflare AI (FLUX-schnell)  — 10K/gün ücretsiz, hızlı
      3. Pollinations.ai               — eski yedek (artık ücretli)
    """
    for ad, fn in [
        ("Nano Banana", nano_banana_kapak),
        ("Cloudflare AI", cloudflare_kapak),
        ("Pollinations", pollinations_kapak),
    ]:
        try:
            data = fn(gorsel_prompt)
            print(f"    [{ad}] kapak üretildi ({len(data)/1024:.0f}KB)")
            return base64.b64encode(data).decode("utf-8")
        except Exception as e:
            print(f"    [{ad}] atlandı: {type(e).__name__}: {str(e)[:80]}")
            continue
    raise RuntimeError("Tüm AI kapak motorları başarısız oldu.")
