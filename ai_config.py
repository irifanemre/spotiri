"""
ai_config.py — Merkezi AI model tanımı

Groq modelleri emekliye ayırıyor: llama-3.3-70b-versatile artık hesapta yok,
bu yüzden Groq kullanan her modül "model_decommissioned" hatası veriyordu.
Model adı tek yerde dursun ki bir dahakinde her dosyayı tek tek aramak gerekmesin.

.env içine GROQ_MODEL=... yazarak değiştirilebilir.
Hesaptaki modelleri görmek için:  python ai_config.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Groq'ta şu an duran en büyük sohbet modeli (131k context)
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# gpt-oss bir "reasoning" modeli: düşünme tokenlarını da max_tokens
# bütçesinden harcıyor. Düşünmeyi kısık tutup bütçeye pay ekliyoruz,
# yoksa JSON yanıtlar yarıda kesiliyor (finish_reason="length").
GROQ_REASONING = os.getenv("GROQ_REASONING", "low")
DUSUNME_PAYI   = 2000

# Kapak üretimi — Google AI Studio
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

def groq_yanit(groq, messages: list[dict], max_tokens: int, **ek) -> str:
    """Groq'tan düz metin yanıt al — model/bütçe ayarları tek yerde.

    Groq kullanan tüm modüller bunu çağırmalı; böylece model değişince
    ya da reasoning davranışı değişince tek dosya güncellenir.
    """
    def cagir(**fazladan):
        yanit = groq.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=max_tokens + DUSUNME_PAYI,
            messages=messages,
            **fazladan,
            **ek,
        )
        return (yanit.choices[0].message.content or "").strip()

    try:
        return cagir(reasoning_effort=GROQ_REASONING)
    except Exception:
        # reasoning_effort desteklemeyen bir modele geçildiyse düz dene
        return cagir()

if __name__ == "__main__":
    from groq import Groq
    g = Groq(api_key=os.getenv("GROQ_API_KEY"))
    print(f"Kullanılan model: {GROQ_MODEL}\n")
    print("Hesaptaki Groq modelleri:")
    for m in sorted(g.models.list().data, key=lambda x: x.id):
        isaret = "→" if m.id == GROQ_MODEL else " "
        print(f"  {isaret} {m.id}")
