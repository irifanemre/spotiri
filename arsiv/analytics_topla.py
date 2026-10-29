"""
Günlük analytics snapshot toplayıcı.
Her playlist için: takipçi sayısı, şarkı sayısı, kapak URL.
SQLite'a tarih bazlı kaydeder. Cron tarafından her gece çalıştırılır.
"""

import os
import sqlite3
import datetime
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="playlist-read-private user-read-private"
))
me = sp.current_user()
HESAP_ID = me["id"]

DB_YOL = "/Users/iri/Desktop/projectiRi/analytics.db"

# ─── DB hazırla ────────────────────────────────────────────────────────────
con = sqlite3.connect(DB_YOL)
cur = con.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    playlist_id   TEXT NOT NULL,
    playlist_name TEXT NOT NULL,
    followers     INTEGER,
    tracks_count  INTEGER,
    cover_url     TEXT,
    spotify_url   TEXT,
    UNIQUE(snapshot_date, playlist_id)
)
""")
con.commit()

bugun = datetime.date.today().isoformat()
print(f"[{bugun}] Snapshot toplanıyor...")

# ─── Playlist'leri tara ───────────────────────────────────────────────────
sonuc = sp.current_user_playlists(limit=50)
mine  = [p for p in sonuc["items"] if p and p["owner"]["id"] == HESAP_ID]
print(f"{len(mine)} playlist bulundu.")

eklenen = 0
guncellenen = 0

def sarki_say(playlist_id):
    """Geçerli şarkı sayısını manuel sayar — tracks.total artık güvenilmez."""
    toplam = 0
    offset = 0
    while True:
        sayfa = sp.playlist_tracks(playlist_id, limit=50, offset=offset)
        items = sayfa.get("items", [])
        if not items:
            break
        for it in items:
            tr = it.get("track") or it.get("item")
            if tr and tr.get("id"):
                toplam += 1
        if len(items) < 50:
            break
        offset += 50
    return toplam

for p in mine:
    try:
        # Detay çek (takipçi sayısı için)
        detay = sp.playlist(p["id"], fields="followers,images,name,external_urls")
        followers   = detay.get("followers", {}).get("total", 0)
        tracks_cnt  = sarki_say(p["id"])
        cover       = (detay.get("images") or [{}])[0].get("url", "")
        spotify_url = detay.get("external_urls", {}).get("spotify", "")

        cur.execute("""
        INSERT INTO snapshots
        (snapshot_date, playlist_id, playlist_name, followers, tracks_count, cover_url, spotify_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date, playlist_id) DO UPDATE SET
            playlist_name = excluded.playlist_name,
            followers     = excluded.followers,
            tracks_count  = excluded.tracks_count,
            cover_url     = excluded.cover_url,
            spotify_url   = excluded.spotify_url
        """, (bugun, p["id"], p["name"], followers, tracks_cnt, cover, spotify_url))
        eklenen += 1
        print(f"  ✓ {p['name'][:45]:<45} | takipçi: {followers:>3} | şarkı: {tracks_cnt:>2}")
    except Exception as e:
        print(f"  ✗ {p['name']}: {e}")

con.commit()
con.close()
print(f"\n=== TAMAMLANDI: {eklenen} playlist için snapshot kaydedildi ===")
