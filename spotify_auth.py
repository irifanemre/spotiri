"""
spotify_auth.py — Merkezi Spotify Auth

Tüm scriptlerin aynı genişletilmiş scope ile aynı .cache dosyasını kullanmasını sağlar.
Bir kez auth yapılır → tüm modüller (web + subprocess'ler) aynı token'ı paylaşır.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

ROOT       = Path(__file__).parent
CACHE_PATH = str(ROOT / ".cache")

# TÜM scope'lar — projedeki herhangi bir scriptin ihtiyacı olan her şey
SCOPES = (
    "playlist-read-private "
    "playlist-modify-public "
    "playlist-modify-private "
    "user-read-private "
    "user-library-read "
    "user-top-read "
    "ugc-image-upload"
)

def get_sp() -> spotipy.Spotify:
    """Tek bir Spotify client döndürür. Tüm scriptler bunu kullanmalı."""
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope=SCOPES,
        cache_path=CACHE_PATH,
    ))

# ─────────────────────────────────────────────
# ORTAK YARDIMCILAR
# Spotify 2024+ API'sinde "track" field'ı "item" oldu.
# Tüm scriptler bunu kullanmalı, ikisini de dene.
# ─────────────────────────────────────────────

def track_cek(item: dict) -> dict | None:
    """Playlist item içinden track objesini güvenle çıkar."""
    if not item:
        return None
    return item.get("track") or item.get("item")

def kendi_playlistlerim(sp, hesap_id: str | None = None) -> list[dict]:
    """Hesabın sahibi olduğu TÜM playlist'ler.

    current_user_playlists sayfa başına en fazla 50 kayıt döndürür;
    50'den fazla playlist olduğunda tek çağrı sessizce eksik liste verir
    (isimle playlist arayan scriptler o yüzden kopya playlist oluşturur).
    """
    if hesap_id is None:
        hesap_id = sp.current_user()["id"]

    hepsi, offset = [], 0
    while True:
        items = sp.current_user_playlists(limit=50, offset=offset).get("items") or []
        if not items:
            break
        hepsi += [p for p in items if p and p["owner"]["id"] == hesap_id]
        if len(items) < 50:
            break
        offset += 50
    return hepsi
