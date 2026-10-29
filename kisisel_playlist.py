"""
Kişisel Playlist Üreticisi
──────────────────────────
Sana sorular sorar:
  - İsmin
  - Yaşın
  - Nasıl hissediyorsun / Ne tarif ediyorsun

Groq AI sana özel:
  - Playlist ismi üretir (isminle birlikte)
  - Yaş ve ruh haline göre şarkı arama sorguları çıkarır
  - Görsel kapak prompt'u yazar

Spotify'da playlist açar, Pollinations AI kapak çizer.
"""

import os
import json
import time
import base64
from dotenv import load_dotenv
from groq import Groq
from kapak import ai_kapak_base64
from curator import persona_filter, diversity_filter, smart_rank, mood_aware_rank, PERSONAS, EmbeddingEngine
from burc import burc_bul, yas_hesapla, tarih_parse, burc_emoji
from mood_yorumlayici import mood_yorumla, profil_ozet

load_dotenv()

# ─── Spotify ──────────────────────────────────────────────────────────────
from spotify_auth import get_sp
sp       = get_sp()
me       = sp.current_user()
HESAP_ID = me["id"]

# ─── Groq ─────────────────────────────────────────────────────────────────
from ai_config import groq_yanit
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─── Spotify yardımcı (yeni API: 'item' field) ─────────────────────────────
def _track_cek(item):
    return item.get("track") or item.get("item")

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 1: KULLANICIDAN BİLGİ AL
# ─────────────────────────────────────────────────────────────────────────────

def kullanici_bilgi_al():
    print("\n" + "─" * 50)
    print("  KİŞİSEL PLAYLIST ÜRETİCİSİ")
    print("─" * 50 + "\n")

    isim = input("İsmin ne? → ").strip()
    while not isim:
        isim = input("İsim boş olamaz, tekrar dene → ").strip()

    while True:
        yas_str = input("Kaç yaşındasın? → ").strip()
        try:
            yas = int(yas_str)
            if 10 <= yas <= 100:
                break
            print("  10-100 arası bir yaş gir.")
        except ValueError:
            print("  Sayı olmalı.")

    print("\nNasıl hissediyorsun? Ya da nasıl bir şey dinlemek istiyorsun?")
    print("(Örn: 'çok yorgunum, beni rahatlatacak bir şeyler', 'gece sürüşü vibe', 'eski sevgilime özlem'...)")
    his = input("→ ").strip()
    while not his:
        his = input("Bir şeyler yazmalısın → ").strip()

    return isim, yas, his

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 2: GROQ İLE KİŞİSEL TASARIM
# ─────────────────────────────────────────────────────────────────────────────

SISTEM_PROMPT = """
Sen kullanıcılar için kişisel Spotify playlist'leri tasarlayan bir AI'sın.
Kullanıcının ismi, yaşı, burcu ve ruh haline göre:

1. İsmin etimolojik/sembolik anlamını araştır
2. Burç + mood'a göre 1 cümle yorum yaz
3. Yaratıcı, kişisel playlist ismi üret
4. ÖNEMLİ: Şarkı bulmak için 3 farklı SİNYAL üret:

   a) ANCHOR_ARTISTS (4-6 sanatçı): Mood'u TAM yakalayan, gerçek sanatçı isimleri.
      Generic değil — "sad music" değil "Phoebe Bridgers", "Lana Del Rey", "Boygenius".
      Underground/mainstream karışık olabilir.

   b) ANCHOR_TRACKS (3-5 şarkı): Mood'u temsil eden SPECİFİC şarkılar.
      Format: "Şarkı Adı - Sanatçı"
      Örn: "Motion Sickness - Phoebe Bridgers"

   c) SUB_GENRES (3-5 sub-tür): Niş alt türler.
      Generic: "indie", "pop" → KÖTÜ
      Specific: "bedroom pop", "slowcore", "ambient drone", "dream pop", "indie sleaze" → İYİ

5. MOOD_DESCRIPTION: 1-2 cümle, ÇOK SOMUT mood açıklaması İngilizce.
   Embedding için kullanılacak — duygu kelimeleri, atmosfer, zaman/mekan.
   Örnek: "late night driving alone in summer rain, melancholy but content,
   reflective indie with hushed vocals"

6. AI görsel kapak için İngilizce visual prompt
   - İsim sembolik öğeleri (cennet→garden, deniz→ocean)
   - Burç elementi görsel etkisi (Ateş/Toprak/Hava/Su)

Yaş notu:
- 13-18: TikTok/hyperpop kuşağı
- 19-25: indie/alternative/modern
- 26-35: millennial/throwback
- 35+: classic/timeless

Yanıt SADECE geçerli JSON olsun, başka metin ekleme.
"""

KULLANICI_SABLONU = """
İsim: {isim} · Yaş: {yas} · Burç: {burc_tr} ({burc_en}) · Element: {eleman}
Yazdığı: "{his}"

PROFESYONEL MOOD ANALİZİ (önceden yapıldı, kullan):
  Ana duygu:    {ana_duygu}
  İkincil:      {ikincil}
  Aktivite:     {aktivite}
  Enerji:       {enerji} · Tempo: {tempo} · Vokal: {vokal}
  Ses paleti:   {palet}
  Tarz aile:    {tarz_aile}
  Kaçınılacak:  {kacinilacak}
  Anlatım:      {anlatim}

Bu profili harfiyen takip et. Anchor seçimlerinde "kaçınılacak" listesine asla
girme. Tempo ve vokal tercihini şiddetle dikkate al.

Format:
{{
  "isim_anlami":   "ismin etimolojik/sembolik anlamı, 1 cümle Türkçe",
  "burc_yorum":    "Bu burç + bu mood için 1 cümle Türkçe yorum",
  "playlist_ismi": "kişisel ve yaratıcı bir isim",
  "aciklama":      "kısa açıklama, 1-2 cümle",
  "mood_description": "{anlatim}",
  "anchor_artists":  ["mood profilini TAM yakalayan 5-6 sanatçı"],
  "anchor_tracks":   ["Şarkı - Sanatçı formatında 3-5 örnek"],
  "sub_genres":      ["3-5 spesifik niş sub-genre (yukarıdaki tarz_aile içinden)"],
  "gorsel_prompt":   "English visual prompt. Include: name symbolism + {eleman} element + {palet} palette. No text."
}}
"""

def groq_kisisel_uret(isim, yas, his, burc_info, profil):
    prompt = KULLANICI_SABLONU.format(
        isim=isim, yas=yas, his=his,
        burc_tr=burc_info["tr"], burc_en=burc_info["en"],
        eleman=burc_info["eleman"],
        ana_duygu=profil.get("ana_duygu", "—"),
        ikincil=", ".join(profil.get("ikincil_duygular", [])),
        aktivite=profil.get("olasi_aktivite", "—"),
        enerji=profil.get("enerji", "—"),
        tempo=profil.get("tempo_hedefi", "—"),
        vokal=profil.get("vokal_tarzi", "—"),
        palet=profil.get("ses_paleti", "—"),
        tarz_aile=", ".join(profil.get("tarz_aile", [])),
        kacinilacak=", ".join(profil.get("kacinilacak", [])),
        anlatim=profil.get("anlatim", his),
    )
    print("\n  Groq düşünüyor...")
    ham = groq_yanit(groq, [
        {"role": "system", "content": SISTEM_PROMPT},
        {"role": "user",   "content": prompt}
    ], max_tokens=600)
    if not ham.startswith("{"):
        ham = ham[ham.find("{"):ham.rfind("}") + 1]
    return json.loads(ham)

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 3: SPOTIFY'DAN ŞARKI ÇEK
# ─────────────────────────────────────────────────────────────────────────────

def sarkilari_topla(tasarim, hedef=20, persona="default"):
    """
    3 sinyal kaynağından şarkı toplar:
    1. ANCHOR ARTISTS    → her sanatçının top şarkıları (mood'u garanti yakalar)
    2. ANCHOR TRACKS     → spesifik şarkıları arar
    3. SUB GENRES        → niş türleri tarar

    Toplanan havuz mood_description ile semantic olarak yeniden sıralanır.
    """
    sarkilar = []
    gorulen  = set()

    def _ekle(sonuc):
        if not sonuc or "tracks" not in sonuc:
            return
        for t in sonuc["tracks"]["items"]:
            tid = t.get("id")
            if not tid or tid in gorulen:
                continue
            gorulen.add(tid)
            sarkilar.append(t)

    def _ara(query):
        try:
            time.sleep(0.4)  # rate limit nezaketi
            return sp.search(q=query, type="track", limit=5)
        except Exception as e:
            print(f"  [UYARI] '{query}': {e}")
            return None

    # 1) ANCHOR ARTISTS — her sanatçının ismini search'le, top şarkıları gelir
    for sanatci in (tasarim.get("anchor_artists") or [])[:6]:
        _ekle(_ara(sanatci))

    # 2) ANCHOR TRACKS
    for track_str in (tasarim.get("anchor_tracks") or [])[:5]:
        _ekle(_ara(track_str))

    # 3) SUB GENRES
    for genre in (tasarim.get("sub_genres") or [])[:5]:
        _ekle(_ara(genre))

    ham_sayi = len(sarkilar)

    # Mood-aware semantic ranking
    mood_desc = tasarim.get("mood_description") or tasarim.get("aciklama", "")
    engine    = EmbeddingEngine()
    secilen   = mood_aware_rank(
        sarkilar,
        mood_text=mood_desc,
        persona=persona,
        diversity_cap=2,
        target=hedef,
        engine=engine,
    )

    print(f"  → {ham_sayi} ham → {len(secilen)} mood-eşleşmeli ({PERSONAS[persona]['etiket']})")
    return secilen

# ─────────────────────────────────────────────────────────────────────────────
# FAZ 4: PLAYLİST OLUŞTUR + KAPAK YÜKLE
# ─────────────────────────────────────────────────────────────────────────────

def playlist_olustur(tasarim, sarkilar):
    yeni = sp._post("me/playlists", payload={
        "name":        tasarim["playlist_ismi"],
        "public":      True,
        "description": tasarim["aciklama"]
    })
    pl_id = yeni["id"]

    track_ids = [t["id"] for t in sarkilar]
    for i in range(0, len(track_ids), 100):
        sp.playlist_add_items(pl_id, track_ids[i:i+100])

    # Kapak — AI fallback zinciri (Nano Banana → Cloudflare → Pollinations)
    try:
        print("  AI kapak çiziliyor...")
        b64 = ai_kapak_base64(tasarim["gorsel_prompt"])
        sp.playlist_upload_cover_image(pl_id, b64)
        print("  Kapak yüklendi.")
    except Exception as e:
        print(f"  [UYARI] Kapak yüklenemedi: {e}")

    return yeni

# ─────────────────────────────────────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--isim",    help="Kullanıcı ismi")
    parser.add_argument("--dogum",   help="Doğum tarihi (GG.AA.YYYY)")
    parser.add_argument("--his",     help="Ruh hali / tarif")
    parser.add_argument("--persona", help="Küratör kişiliği",
                        default="default",
                        choices=list(PERSONAS.keys()))
    args = parser.parse_args()

    persona = args.persona

    if args.isim and args.dogum and args.his:
        isim, his = args.isim, args.his
        dogum_tarihi = tarih_parse(args.dogum)
        if not dogum_tarihi:
            print(f"  [HATA] Geçersiz tarih formatı: {args.dogum} (GG.AA.YYYY olmalı)")
            exit(1)
        yas = yas_hesapla(dogum_tarihi)
    else:
        isim, yas, his = kullanici_bilgi_al()
        dogum_tarihi = None
        while not dogum_tarihi:
            d_str = input("Doğum tarihin? (GG.AA.YYYY) → ").strip()
            dogum_tarihi = tarih_parse(d_str)
            if not dogum_tarihi:
                print("  Geçersiz format, örn: 15.06.2002")
        yas = yas_hesapla(dogum_tarihi)

    burc_info = burc_bul(dogum_tarihi)
    burc_sym  = burc_emoji(burc_info["en"])

    print(f"\n  İsim: {isim}")
    print(f"  Doğum: {dogum_tarihi.strftime('%d.%m.%Y')} | Yaş: {yas}")
    print(f"  Burç: {burc_sym} {burc_info['tr']} ({burc_info['en']}) · {burc_info['eleman']}")
    print(f"  Mood: {his}")
    print(f"  Persona: {PERSONAS[persona]['etiket']}")
    print(f"\nMerhaba {isim}! Önce ruh halini yorumluyorum...")

    # ── ADIM 1: Mood'u profesyonel küratör gibi yorumla ──
    profil = mood_yorumla(his, isim=isim, yas=yas, burc_info=burc_info)

    print(f"\n  ✓ Yorumlandı")
    if profil.get("anlam"):
        print(f"  »  {profil['anlam']}")
    print(f"  →  {profil_ozet(profil)}")
    if profil.get("olasi_aktivite"):
        print(f"  →  Olası aktivite: {profil['olasi_aktivite']}")
    if profil.get("tarz_aile"):
        print(f"  →  Tarz: {', '.join(profil['tarz_aile'])}")

    # ── ADIM 2: Profile dayalı playlist tasarımı ──
    print(f"\n  Playlist tasarımı yapılıyor...")
    tasarim = groq_kisisel_uret(isim, yas, his, burc_info, profil)

    if tasarim.get("isim_anlami"):
        print(f"\n  ✦ {isim}: {tasarim['isim_anlami']}")
    if tasarim.get("burc_yorum"):
        print(f"  {burc_sym} {burc_info['tr']}: {tasarim['burc_yorum']}")
    print(f"  → Playlist: {tasarim['playlist_ismi']}")
    print(f"  → Açıklama: {tasarim['aciklama']}")

    # Açıklamayı burç + profil + persona ile zenginleştir
    tasarim["aciklama"] = (
        f"{tasarim['aciklama']} · "
        f"{burc_sym} {burc_info['tr']} · "
        f"{profil.get('ana_duygu', '').lower()} · "
        f"{PERSONAS[persona]['etiket']}"
    )

    print("\n  Spotify'da şarkılar aranıyor (anchor artists + sub-genres)...")
    sarkilar = sarkilari_topla(tasarim, persona=persona)

    if not sarkilar:
        print("\n  Şarkı bulunamadı, tekrar deneyebilirsin.")
        exit(1)

    print("\n  Playlist oluşturuluyor...")
    yeni = playlist_olustur(tasarim, sarkilar)

    print("\n" + "─" * 50)
    print(f"  ✅ HAZIR — {tasarim['playlist_ismi']}")
    print(f"  {burc_sym} {burc_info['tr']}  ·  {PERSONAS[persona]['etiket']}  ·  {len(sarkilar)} şarkı")
    print(f"  İlk şarkı: {sarkilar[0]['name']}")
    print(f"  Spotify: {yeni['external_urls']['spotify']}")
    print("─" * 50 + "\n")
