"""
burc.py — Doğum tarihinden burç hesaplama + müzikal kişilik haritası
"""

from datetime import datetime, date

# (başlangıç_ay, başlangıç_gün), (bitiş_ay, bitiş_gün), TR, EN, eleman, vibe (İngilizce)
BURCLAR = [
    ((3, 21),  (4, 19),  "Koç",      "Aries",       "Ateş", "bold, fiery, energetic, pioneering, fast-paced"),
    ((4, 20),  (5, 20),  "Boğa",     "Taurus",      "Toprak", "sensual, grounded, indulgent, luxurious, slow-burn"),
    ((5, 21),  (6, 20),  "İkizler",  "Gemini",      "Hava", "curious, dual, witty, eclectic, fast-talking"),
    ((6, 21),  (7, 22),  "Yengeç",   "Cancer",      "Su", "emotional, nurturing, nostalgic, moody, intuitive"),
    ((7, 23),  (8, 22),  "Aslan",    "Leo",         "Ateş", "dramatic, confident, theatrical, bold, regal"),
    ((8, 23),  (9, 22),  "Başak",    "Virgo",       "Toprak", "analytical, refined, precise, calm, perfectionist"),
    ((9, 23),  (10, 22), "Terazi",   "Libra",       "Hava", "harmonious, aesthetic, balanced, romantic, smooth"),
    ((10, 23), (11, 21), "Akrep",    "Scorpio",     "Su", "intense, mysterious, transformative, sensual, dark"),
    ((11, 22), (12, 21), "Yay",      "Sagittarius", "Ateş", "adventurous, philosophical, free-spirited, worldly"),
    ((12, 22), (1, 19),  "Oğlak",    "Capricorn",   "Toprak", "disciplined, ambitious, classic, structured, timeless"),
    ((1, 20),  (2, 18),  "Kova",     "Aquarius",    "Hava", "innovative, eccentric, futuristic, humanitarian, electronic"),
    ((2, 19),  (3, 20),  "Balık",    "Pisces",      "Su", "dreamy, ethereal, artistic, escapist, ambient"),
]

def burc_bul(dogum: date) -> dict:
    """Doğum tarihinden burç ve özelliklerini döndürür."""
    ay, gun = dogum.month, dogum.day
    for (sa, sg), (ea, eg), tr, en, eleman, vibe in BURCLAR:
        if sa > ea:  # yıl sınırını aşan (Oğlak)
            if (ay == sa and gun >= sg) or (ay == ea and gun <= eg):
                return {"tr": tr, "en": en, "eleman": eleman, "vibe": vibe}
        else:
            if (ay == sa and gun >= sg) or (ay == ea and gun <= eg):
                return {"tr": tr, "en": en, "eleman": eleman, "vibe": vibe}
    return {"tr": "Bilinmiyor", "en": "Unknown", "eleman": "—", "vibe": "balanced"}

def yas_hesapla(dogum: date) -> int:
    bugun = date.today()
    return bugun.year - dogum.year - (
        (bugun.month, bugun.day) < (dogum.month, dogum.day)
    )

def tarih_parse(metin: str) -> date | None:
    """Birden fazla format destekler: GG.AA.YYYY, GG/AA/YYYY, YYYY-MM-DD"""
    metin = metin.strip()
    formatlar = ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]
    for fmt in formatlar:
        try:
            return datetime.strptime(metin, fmt).date()
        except ValueError:
            continue
    return None

def burc_emoji(burc_en: str) -> str:
    """Konsol uyumlu sembol (renkli emoji yok, Unicode)"""
    map = {
        "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
        "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
        "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
    }
    return map.get(burc_en, "✦")
