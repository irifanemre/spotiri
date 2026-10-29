"""
curator.py — Akıllı Şarkı Küratörü

Sağlar:
  - Persona sistemi (Mainstream / Underground / Throwback / Fresh)
  - Diversity filter (sanatçı domination önler)
  - Embedding-based similarity (semantic, sentence-transformers)
  - Coherence scorer (playlist tutarlılığı)
  - SQLite embedding cache (yeniden hesaplama yok)

Tüm playlist üretici scriptlerin import edip kullanabileceği merkezi modül.
"""

import os
import sqlite3
import pickle
from typing import Iterable, Optional
from datetime import datetime

import numpy as np

ROOT      = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(ROOT, "embeddings.db")
MODEL_DIR = os.path.join(ROOT, ".models")

# ─────────────────────────────────────────────
# PERSONA TANIMLARI
# Her persona şarkı seçimini farklı yönlendirir.
# ─────────────────────────────────────────────

PERSONAS = {
    "default": {
        "etiket":         "Default",
        "aciklama":       "Dengeli karışım, hit + nişin ortası",
        "min_popularity": 30,
        "max_popularity": 100,
        "min_yil":        2000,
        "prompt_hint":    "Balanced mix of popular and quality picks.",
    },
    "mainstream": {
        "etiket":         "Mainstream Curator",
        "aciklama":       "TikTok hit'leri, chart-topper'lar, anında akılda kalan",
        "min_popularity": 60,
        "max_popularity": 100,
        "min_yil":        2020,
        "prompt_hint":    "Focus on mainstream chart-toppers and viral hits only. Avoid obscure tracks.",
    },
    "underground": {
        "etiket":         "Underground Curator",
        "aciklama":       "Gizli cevherler, niş sahneler, düşük popülerlik",
        "min_popularity": 0,
        "max_popularity": 45,
        "min_yil":        2018,
        "prompt_hint":    "Find hidden gems and underground tracks below mainstream radar. Avoid top charts.",
    },
    "throwback": {
        "etiket":         "Throwback Curator",
        "aciklama":       "Eski klasikler, nostaljik vibler",
        "min_popularity": 20,
        "max_popularity": 100,
        "min_yil":        1980,
        "max_yil":        2015,
        "prompt_hint":    "Focus on older tracks that aged well, classics from 1980-2015. No new releases.",
    },
    "fresh": {
        "etiket":         "Fresh Curator",
        "aciklama":       "Bu haftanın drop'ları, taze çıkanlar",
        "min_popularity": 20,
        "max_popularity": 100,
        "min_yil":        datetime.now().year - 1,
        "prompt_hint":    f"Only freshest releases from {datetime.now().year - 1}-{datetime.now().year}. No throwbacks.",
    },
}

def persona_listesi() -> list[tuple[str, str, str]]:
    """(kod, etiket, açıklama) tuple listesi döndürür — UI için."""
    return [(k, v["etiket"], v["aciklama"]) for k, v in PERSONAS.items()]

def persona_filter(tracks: list, persona: str = "default") -> list:
    """Persona kriterlerine göre tracks listesini filtreler."""
    p = PERSONAS.get(persona, PERSONAS["default"])
    sonuc = []
    for t in tracks:
        pop = t.get("popularity") or 0
        if not (p["min_popularity"] <= pop <= p["max_popularity"]):
            continue
        tarih = (t.get("album") or {}).get("release_date", "2000-01-01")
        try:
            yil = int(tarih[:4])
        except Exception:
            yil = 2000
        if yil < p["min_yil"]:
            continue
        if "max_yil" in p and yil > p["max_yil"]:
            continue
        sonuc.append(t)
    return sonuc

# ─────────────────────────────────────────────
# DIVERSITY FILTER
# ─────────────────────────────────────────────

def diversity_filter(tracks: list, max_per_artist: int = 2) -> list:
    """Bir sanatçı playlist'in tamamını ele geçirmesin."""
    sayac = {}
    sonuc = []
    for t in tracks:
        artists = t.get("artists") or []
        if not artists:
            continue
        ana_aid = artists[0].get("id")
        if not ana_aid:
            continue
        if sayac.get(ana_aid, 0) >= max_per_artist:
            continue
        sayac[ana_aid] = sayac.get(ana_aid, 0) + 1
        sonuc.append(t)
    return sonuc

# ─────────────────────────────────────────────
# EMBEDDING ENGINE (Lazy load — model 80MB)
# ─────────────────────────────────────────────

class EmbeddingEngine:
    """Şarkıları semantik vektörlere çevirir, SQLite'a cache'ler."""

    _model = None  # singleton

    def __init__(self):
        self._db_init()

    @classmethod
    def _model_yukle(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            os.makedirs(MODEL_DIR, exist_ok=True)
            print("  [Embedding] Model yükleniyor (ilk seferde ~80MB indirir)...")
            cls._model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2",
                cache_folder=MODEL_DIR,
            )
        return cls._model

    def _db_init(self):
        with sqlite3.connect(DB_PATH) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    track_id TEXT PRIMARY KEY,
                    text     TEXT,
                    vector   BLOB,
                    created  TEXT
                )
            """)

    def _track_to_text(self, track: dict) -> str:
        """Şarkıyı arama için zengin metne çevir."""
        isim    = track.get("name", "")
        sanatci = (track.get("artists") or [{}])[0].get("name", "")
        album   = (track.get("album") or {}).get("name", "")
        return f"{isim} by {sanatci} from {album}"

    def _get_cached(self, track_id: str) -> Optional[np.ndarray]:
        with sqlite3.connect(DB_PATH) as con:
            row = con.execute(
                "SELECT vector FROM embeddings WHERE track_id = ?",
                (track_id,)
            ).fetchone()
            if row:
                return pickle.loads(row[0])
        return None

    def _cache(self, track_id: str, text: str, vec: np.ndarray):
        with sqlite3.connect(DB_PATH) as con:
            con.execute(
                "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?)",
                (track_id, text, pickle.dumps(vec), datetime.now().isoformat())
            )

    def embed_track(self, track: dict) -> np.ndarray:
        tid = track.get("id")
        if not tid:
            return None
        cached = self._get_cached(tid)
        if cached is not None:
            return cached
        text  = self._track_to_text(track)
        model = self._model_yukle()
        vec   = model.encode(text, show_progress_bar=False)
        self._cache(tid, text, vec)
        return vec

    def embed_text(self, text: str) -> np.ndarray:
        """Genel metin embedding (mood description için)."""
        model = self._model_yukle()
        return model.encode(text, show_progress_bar=False)

    def embed_batch(self, tracks: list) -> dict[str, np.ndarray]:
        """Birden fazla şarkıyı verimli batch'le."""
        sonuc       = {}
        yeniler     = []
        yeni_idler  = []
        for t in tracks:
            tid = t.get("id")
            if not tid:
                continue
            cached = self._get_cached(tid)
            if cached is not None:
                sonuc[tid] = cached
            else:
                yeniler.append(self._track_to_text(t))
                yeni_idler.append((tid, t))

        if yeniler:
            model = self._model_yukle()
            vecs  = model.encode(yeniler, show_progress_bar=False, batch_size=32)
            for (tid, track), vec in zip(yeni_idler, vecs):
                self._cache(tid, self._track_to_text(track), vec)
                sonuc[tid] = vec
        return sonuc

    def similarity(self, t1: dict, t2: dict) -> float:
        from sklearn.metrics.pairwise import cosine_similarity
        v1 = self.embed_track(t1)
        v2 = self.embed_track(t2)
        if v1 is None or v2 is None:
            return 0.0
        return float(cosine_similarity([v1], [v2])[0][0])

    def find_similar(self, target: dict, candidates: list, k: int = 10) -> list:
        """Hedef şarkıya en benzer K adayı döndür."""
        from sklearn.metrics.pairwise import cosine_similarity
        target_v = self.embed_track(target)
        if target_v is None:
            return []
        aday_vecs = self.embed_batch(candidates)
        skorlar = []
        for c in candidates:
            cid = c.get("id")
            if cid not in aday_vecs:
                continue
            sim = float(cosine_similarity([target_v], [aday_vecs[cid]])[0][0])
            skorlar.append((sim, c))
        skorlar.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in skorlar[:k]]

# ─────────────────────────────────────────────
# COHERENCE SCORER
# ─────────────────────────────────────────────

def coherence_score(tracks: list, engine: Optional[EmbeddingEngine] = None) -> float:
    """
    Playlist içinde şarkılar ne kadar tutarlı? 0-1 arası.
    1 = aynı türde sıkı paket, 0 = chaotic karışım
    """
    from sklearn.metrics.pairwise import cosine_similarity
    if len(tracks) < 2:
        return 1.0
    if engine is None:
        engine = EmbeddingEngine()
    vecs_map = engine.embed_batch(tracks)
    vecs = [vecs_map[t["id"]] for t in tracks if t.get("id") in vecs_map]
    if len(vecs) < 2:
        return 1.0
    arr  = np.array(vecs)
    sims = cosine_similarity(arr)
    mask = ~np.eye(len(vecs), dtype=bool)
    return float(sims[mask].mean())

# ─────────────────────────────────────────────
# MOOD-AWARE RANKING — semantic similarity
# Ruh hali metnini vektöre çevirip her şarkıyla cosine similarity hesaplar.
# Spotify keyword search'ün getirdiği şarkıları gerçek mood'a göre yeniden sıralar.
# ─────────────────────────────────────────────

def mood_aware_rank(
    tracks: list,
    mood_text: str,
    persona: str = "default",
    diversity_cap: int = 2,
    target: int = 25,
    engine: Optional[EmbeddingEngine] = None,
    mood_weight: float = 0.65,
    pop_weight:  float = 0.20,
    fresh_weight: float = 0.15,
) -> list:
    """
    Skorlama: mood_match * 0.65 + popularity * 0.20 + recency * 0.15

    mood_text:  serbest açıklama, örn. "tired but hopeful, late night reflective"
                Türkçe + İngilizce karışık olabilir, embedding cross-lingual.
    """
    from sklearn.metrics.pairwise import cosine_similarity
    if not tracks:
        return []
    if engine is None:
        engine = EmbeddingEngine()

    # 1) Persona filtresi
    aday = persona_filter(tracks, persona)
    if not aday:
        aday = tracks  # persona çok katıysa orijinal havuz

    # 2) Mood embedding
    mood_vec = engine.embed_text(mood_text).reshape(1, -1)

    # 3) Her track için embedding + skor
    embs = engine.embed_batch(aday)

    skorlar = []
    bugun_yil = datetime.now().year
    for t in aday:
        tid = t.get("id")
        if tid not in embs:
            continue
        # Mood benzerlik (0-1 arası)
        mood_sim = float(cosine_similarity(mood_vec, embs[tid].reshape(1, -1))[0][0])
        # Popularity normalize (0-1)
        pop = (t.get("popularity") or 0) / 100.0
        # Tazelik (son 5 yıl içindeyse yüksek)
        tarih = (t.get("album") or {}).get("release_date", "2000")
        try:
            yil = int(tarih[:4])
            tazelik = max(0.0, 1.0 - (bugun_yil - yil) / 5.0)
        except Exception:
            tazelik = 0.0
        # Kombine skor
        skor = (mood_sim * mood_weight +
                pop      * pop_weight +
                tazelik  * fresh_weight)
        skorlar.append((skor, mood_sim, t))

    # 4) Skora göre sırala
    skorlar.sort(key=lambda x: x[0], reverse=True)

    # 5) Mood-eşleşmesi çok düşük olanları ele (gürültü filtresi)
    eşik = 0.15  # cosine similarity için düşük ama anlamlı eşik
    iyi = [(s, m, t) for s, m, t in skorlar if m >= eşik]

    # 6) Diversity (sanatçı domination engelle)
    secilen = []
    sayac = {}
    for _, _, t in iyi:
        aid = (t.get("artists") or [{}])[0].get("id")
        if aid and sayac.get(aid, 0) >= diversity_cap:
            continue
        sayac[aid] = sayac.get(aid, 0) + 1
        secilen.append(t)
        if len(secilen) >= target:
            break

    return secilen

# ─────────────────────────────────────────────
# SMART RANKING — multi-signal kombinasyon
# ─────────────────────────────────────────────

def smart_rank(
    tracks: list,
    persona: str = "default",
    diversity_cap: int = 2,
    target: int = 25,
    coherence_ref: Optional[dict] = None,
    engine: Optional[EmbeddingEngine] = None,
) -> list:
    """
    1. Persona filtresi uygula
    2. Diversity uygula
    3. Coherence ref varsa o şarkıya yakın olanları öne çıkar
    4. Top N döndür
    """
    # 1. Persona
    filtered = persona_filter(tracks, persona)

    # 2. Coherence ranking (varsa)
    if coherence_ref and filtered:
        if engine is None:
            engine = EmbeddingEngine()
        filtered = engine.find_similar(coherence_ref, filtered, k=len(filtered))
    else:
        # Default: popülerliğe göre sırala
        filtered.sort(key=lambda t: t.get("popularity") or 0, reverse=True)

    # 3. Diversity
    filtered = diversity_filter(filtered, max_per_artist=diversity_cap)

    return filtered[:target]

# ─────────────────────────────────────────────
# CACHE İSTATİSTİĞİ
# ─────────────────────────────────────────────

def cache_stats() -> dict:
    with sqlite3.connect(DB_PATH) as con:
        toplam = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    return {
        "toplam_track":  toplam,
        "db_boyut_kb":   os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0,
    }
