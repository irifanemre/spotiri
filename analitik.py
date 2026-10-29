"""
analitik.py — Playlist Analytics & Snapshot Database

SQLite ile playlist'lerin zaman içindeki büyümesini takip eder.
Her snapshot: takipçi sayısı, şarkı sayısı, public/private durumu.

Kullanım:
  python analitik.py snapshot   → şimdi anki durumu kaydet
  python analitik.py list       → tüm snapshot'ları göster
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT    = Path(__file__).parent
DB_PATH = ROOT / "analytics.db"

# ─────────────────────────────────────────────
# DB İŞLEMLERİ
# ─────────────────────────────────────────────

TABLO_SEMASI = """
    CREATE TABLE IF NOT EXISTS snapshots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT NOT NULL,
        playlist_id   TEXT NOT NULL,
        playlist_name TEXT,
        followers     INTEGER,
        track_count   INTEGER,
        is_public     INTEGER,
        cover_url     TEXT
    )
"""

def _eski_semayi_tasi(con):
    """2026-05 öncesi şemadan (snapshot_date / tracks_count) yeni şemaya taşır.

    Eski tablo varken CREATE TABLE IF NOT EXISTS hiçbir şey yapmadığı için
    tüm sorgular "no such column: timestamp" ile patlıyordu.
    """
    kolonlar = {r[1] for r in con.execute("PRAGMA table_info(snapshots)")}
    if not kolonlar or "timestamp" in kolonlar:
        return

    print("  → eski analytics şeması yeni şemaya taşınıyor...")
    con.execute("ALTER TABLE snapshots RENAME TO snapshots_eski")
    con.execute(TABLO_SEMASI)
    con.execute("""
        INSERT INTO snapshots
            (timestamp, playlist_id, playlist_name, followers, track_count, is_public, cover_url)
        SELECT snapshot_date, playlist_id, playlist_name, followers, tracks_count, NULL, cover_url
        FROM snapshots_eski
    """)
    con.execute("DROP TABLE snapshots_eski")

def db_init():
    with sqlite3.connect(DB_PATH) as con:
        _eski_semayi_tasi(con)
        con.execute(TABLO_SEMASI)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_time
            ON snapshots(playlist_id, timestamp)
        """)

# ─────────────────────────────────────────────
# SNAPSHOT — şu anki durumu kaydet
# ─────────────────────────────────────────────

def snapshot_al():
    from spotify_auth import get_sp, kendi_playlistlerim
    sp = get_sp()
    me    = sp.current_user()
    hesap = me["id"]
    mine  = kendi_playlistlerim(sp, hesap)

    db_init()
    now = datetime.now().isoformat(timespec="seconds")
    eklenen = 0

    with sqlite3.connect(DB_PATH) as con:
        for p in mine:
            try:
                detay = sp.playlist(p["id"], fields="followers,images,name")
                fol   = (detay.get("followers") or {}).get("total", 0)
                imgs  = detay.get("images") or []
                cover = imgs[0]["url"] if imgs else None
            except Exception:
                fol   = 0
                cover = None

            # Tracks count
            tc = 0
            try:
                offset = 0
                while True:
                    s = sp.playlist_tracks(p["id"], limit=50, offset=offset)
                    items = s.get("items", [])
                    if not items: break
                    for it in items:
                        if (it.get("track") or it.get("item")):
                            tc += 1
                    if len(items) < 50: break
                    offset += 50
            except Exception:
                pass

            con.execute(
                "INSERT INTO snapshots (timestamp, playlist_id, playlist_name, "
                "followers, track_count, is_public, cover_url) VALUES (?,?,?,?,?,?,?)",
                (now, p["id"], p["name"], fol, tc, int(p.get("public", False)), cover)
            )
            eklenen += 1
            print(f"  {p['name'][:50]:<50}  {fol:>5} takipçi · {tc:>3} şarkı")

    print(f"\n  ✓ {eklenen} playlist snapshot'ı kaydedildi → {now}")
    return eklenen

# ─────────────────────────────────────────────
# SORGULAR
# ─────────────────────────────────────────────

def son_snapshot():
    """Her playlist için en son snapshot'ı döndürür."""
    db_init()
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT s.* FROM snapshots s
            INNER JOIN (
                SELECT playlist_id, MAX(timestamp) AS mts
                FROM snapshots GROUP BY playlist_id
            ) m ON s.playlist_id = m.playlist_id AND s.timestamp = m.mts
            ORDER BY s.followers DESC, s.playlist_name ASC
        """).fetchall()
    return [dict(r) for r in rows]

def gecmis(playlist_id, gun=30):
    """Bir playlist'in son N günlük geçmişini döndürür."""
    db_init()
    sinir = (datetime.now() - timedelta(days=gun)).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT timestamp, followers, track_count FROM snapshots "
            "WHERE playlist_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (playlist_id, sinir)
        ).fetchall()
    return [dict(r) for r in rows]

def buyume_skoru(playlist_id, gun=7):
    """Son N gündeki takipçi artışı."""
    g = gecmis(playlist_id, gun=gun)
    if len(g) < 2:
        return 0
    return g[-1]["followers"] - g[0]["followers"]

def toplam_istatistik():
    """Tüm playlist'ler için özet."""
    son = son_snapshot()
    return {
        "playlist_sayisi":  len(son),
        "toplam_takipci":   sum(r["followers"] or 0 for r in son),
        "toplam_sarki":     sum(r["track_count"] or 0 for r in son),
        "en_buyuk":         son[0] if son else None,
    }

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot":
        snapshot_al()
    elif cmd == "list":
        for r in son_snapshot():
            print(f"  {r['playlist_name'][:45]:<45}  {r['followers']:>5} fol · {r['track_count']:>3} tr")
    elif cmd == "stats":
        s = toplam_istatistik()
        print(f"  Playlist:  {s['playlist_sayisi']}")
        print(f"  Takipçi:   {s['toplam_takipci']}")
        print(f"  Şarkı:     {s['toplam_sarki']}")
        if s["en_buyuk"]:
            print(f"  En büyük:  {s['en_buyuk']['playlist_name']} ({s['en_buyuk']['followers']})")
