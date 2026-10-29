"""
mood_yorumlayici.py — Ruh Hali Yorumlayıcı

Kullanıcının yazdığı serbest mood metnini profesyonel bir müzik küratörü
bakışıyla analiz eder. Çıktısı yapısal bir "müzik profili":
  - ana ve ikincil duygu
  - olası aktivite (ders, spor, gece sürüşü vs.)
  - enerji seviyesi + BPM hedefi
  - vokal tarzı + ses paleti
  - tarz ailesi + kaçınılacaklar
  - 1-2 cümlelik İngilizce mood anlatımı

Bu profil playlist üreticisine girer, çok daha isabetli şarkılar gelir.
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

from ai_config import groq_yanit
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────
# AKTİVİTE × MÜZİK PATERNİ
# Yorumlayıcının prompt'una eklenecek baz bilgi.
# ─────────────────────────────────────────────

AKTIVITE_PATERNI = """
KÜRATÖRLÜK BİLGİSİ — Aktivite × Müzik Karakteri:

| Aktivite/Durum           | Enerji  | BPM      | Vokal              | Tarz Aile |
|--------------------------|---------|----------|--------------------|-----------|
| Ders/odaklanma           | düşük   | 60-90    | yok/enstrumental   | lofi, ambient, classical, post-rock |
| Spor/gym                 | yüksek  | 130-160  | güçlü, motivasyon  | hip-hop, edm, hard rock, phonk |
| Gece araba sürüşü        | orta    | 100-130  | atmospheric, soft  | synthwave, indie cinematic, dream pop |
| Uyumadan önce            | çok düş | <80      | yok/fısıltı        | ambient, soft acoustic, classical |
| Temizlik/günlük iş       | yüksek  | 110-140  | upbeat, catchy     | pop, dance, latin |
| Yaratıcı iş              | düşük-or| değişken | minimal/enstrumental| jazz, post-rock, ambient, lofi |
| Geç saat çalışma         | düşük   | 70-100   | hafif/jazzy        | lofi, neo-soul, jazz-hop |
| Ağlamak/duygusal boşalım | düşük   | <90      | ağır/duygusal      | indie folk, sad pop, ballads |
| Parti                    | çok yüks| 120-140  | catchy, anthemic   | pop, edm, hip-hop hits |
| Reflektif/günlük yazma   | düşük   | <100     | poetic/soft        | indie folk, singer-songwriter, acoustic |
| Yağmurlu sabah kahve     | düş-or  | 80-110   | warm/jazzy         | jazz, soft folk, acoustic indie |
| Yeni başlangıç hissi     | or-yük  | 110-140  | uplifting, bright  | indie pop, optimistic anthems |
| Eski sevgili özlemi      | düşük   | <100     | emotional, soft    | sad indie, ballads, dream pop |
| Babam/aile gurur duysun  | or-yük  | 100-130  | uplifting, heartfelt| anthemic pop, indie warm, classical-emotive |
| Ofiste sıkıldım          | orta    | 100-130  | upbeat, distract   | indie pop, alt rock, funk |
| Öfke/sinir               | yüksek  | değişken | aggressive         | metal, punk, rage rap |
| Romantik/yakınlık        | düş-or  | <110     | smooth, sensual    | r&b, jazz, slow indie |
| Yalnızlık hissi          | düşük   | <100     | introspective      | sad indie, alt-folk, slowcore |
"""

# ─────────────────────────────────────────────
# YORUMLAYICI PROMPT
# ─────────────────────────────────────────────

SISTEM_PROMPT = f"""
Sen 20 yıllık deneyimli bir müzik küratörüsün. Spotify editöryal ekibinde
çalışıyorsun. Görevin: kullanıcının yazdığı serbest ruh hali metnini
profesyonel bir müzik profiline çevirmek.

{AKTIVITE_PATERNI}

KURALLAR:
1. Kullanıcının metnini DİKKATLE oku, kelimelerin altındaki gerçek duyguyu çıkar.
2. Direkt aktivite belirtmişse (ders, spor, sürüş) o paterni kullan.
3. Soyut bir ruh hali yazmışsa (örn. "babamı mutlu etmek istiyorum")
   altındaki duyguyu yorumla: bu motivasyon, gurur, aile sıcaklığı demek.
4. Asla generic kalma. "sad music" yerine "introspective slowcore with sparse
   acoustic guitar, hushed vocals" gibi spesifik ol.
5. Yaş ve burç bilgisini de dikkate al ama ezme.

Yanıt SADECE geçerli JSON olsun.
"""

KULLANICI_SABLONU = """
İsim: {isim}
Yaş: {yas}
Burç: {burc_tr} · Element: {eleman} · Karakter: {burc_vibe}
Yazdığı: "{his}"

Format:
{{
  "anlam":           "Türkçe — 'Seni şöyle anladım' tarzında 1 cümle (sıcak, kişisel)",
  "ana_duygu":       "İngilizce primary emotion (tek kelime, örn. 'melancholy', 'hopeful', 'restless')",
  "ikincil_duygular":["İngilizce 2-3 ek duygu/atmosfer kelimesi"],
  "olasi_aktivite":  "İngilizce — kullanıcı muhtemelen ne yapıyor? (örn. 'late night reflection', 'celebrating achievement', 'studying')",
  "enerji":          "very_low / low / medium / high / very_high",
  "tempo_hedefi":    "BPM aralığı string olarak, örn. '70-95 BPM'",
  "vokal_tarzi":     "İngilizce — vokal tercihi, örn. 'hushed and emotive', 'powerful and anthemic', 'instrumental preferred'",
  "ses_paleti":      "İngilizce — warm/cold/bright/dark/lush/sparse",
  "tarz_aile":       ["3-5 spesifik tür/sub-genre İngilizce"],
  "kacinilacak":     ["İngilizce 2-3 kaçınılması gereken eleman, örn. 'aggressive drops', 'autotune-heavy pop'"],
  "anlatim":         "1-2 İngilizce cümle, embedding için zengin mood anlatımı"
}}
"""

def mood_yorumla(his: str, isim: str = "", yas: int = 25, burc_info: dict = None) -> dict:
    """
    Serbest ruh hali metnini yapısal müzik profiline çevirir.
    Groq Llama 3.3 ile profesyonel küratör perspektifi.
    """
    if burc_info is None:
        burc_info = {"tr": "—", "eleman": "—", "vibe": "balanced"}

    prompt = KULLANICI_SABLONU.format(
        isim=isim, yas=yas, his=his,
        burc_tr=burc_info["tr"],
        eleman=burc_info["eleman"],
        burc_vibe=burc_info["vibe"],
    )
    ham = groq_yanit(groq, [
        {"role": "system", "content": SISTEM_PROMPT},
        {"role": "user",   "content": prompt}
    ], max_tokens=600)
    if not ham.startswith("{"):
        ham = ham[ham.find("{"):ham.rfind("}") + 1]
    return json.loads(ham)

def profil_ozet(profil: dict) -> str:
    """Profili tek satırda terminal-friendly özet."""
    return (
        f"{profil.get('ana_duygu', '?').upper()} · "
        f"{profil.get('enerji', '?')} energy · "
        f"{profil.get('tempo_hedefi', '?')} · "
        f"{profil.get('ses_paleti', '?')}"
    )
