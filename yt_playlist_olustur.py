"""
yt_playlist_olustur.py — Eksik şarkıları senin YouTube hesabında playlist'e çevirir

Akış:
  1. eksik_sarkilar/ klasöründeki JSON dosyalarını listele
  2. Kullanıcı bir tanesini seçer
  3. Google OAuth ile YouTube hesabına bağlan (ilk kullanımda izin ister)
  4. YouTube'da yeni playlist oluştur
  5. JSON'daki tüm videoları sırayla ekle
  6. Sonuç: playlist URL

Gereken (.env içinde):
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET

Bunları almak için:
  https://console.cloud.google.com/apis/credentials
  → Create Credentials → OAuth client ID → Desktop app
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery     import build
from googleapiclient.errors        import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials      import Credentials

load_dotenv()

ROOT        = os.path.dirname(os.path.abspath(__file__))
JSON_DIR    = os.path.join(ROOT, "eksik_sarkilar")
TOKEN_PATH  = os.path.join(ROOT, ".yt_token.json")
SECRET_PATH = os.path.join(ROOT, "client_secret.json")
SCOPES      = ["https://www.googleapis.com/auth/youtube"]

# ─────────────────────────────────────────────
# OAUTH — YouTube hesabına bağlan
# ─────────────────────────────────────────────

def youtube_baglan():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(SECRET_PATH):
                sys.exit(
                    f"\n  [HATA] {SECRET_PATH} bulunamadı.\n"
                    "  → Google Cloud Console'dan OAuth client'a tıkla\n"
                    "  → Download JSON ile dosyayı indir\n"
                    "  → projectiri/ klasörüne 'client_secret.json' adıyla kaydet\n"
                )
            flow  = InstalledAppFlow.from_client_secrets_file(SECRET_PATH, SCOPES)
            print("  Tarayıcı açılıyor, YouTube hesabınla izin ver...")
            # port=0 → OS boş port seçer
            creds = flow.run_local_server(port=0, open_browser=True)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

# ─────────────────────────────────────────────
# JSON SEÇİMİ
# ─────────────────────────────────────────────

def json_listesi():
    if not os.path.isdir(JSON_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(JSON_DIR) if f.endswith(".json")],
        key=lambda f: os.path.getmtime(os.path.join(JSON_DIR, f)),
        reverse=True,
    )
    return files

def json_oku(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ─────────────────────────────────────────────
# PLAYLIST OLUŞTUR + DOLDUR
# ─────────────────────────────────────────────

def playlist_olustur(yt, baslik, aciklama, public=False):
    body = {
        "snippet": {"title": baslik, "description": aciklama},
        "status":  {"privacyStatus": "public" if public else "private"},
    }
    sonuc = yt.playlists().insert(part="snippet,status", body=body).execute()
    return sonuc["id"]

def video_id_cikar(url):
    if "watch?v=" in url:
        return url.split("watch?v=")[-1].split("&")[0]
    return None

def videolari_ekle(yt, playlist_id, eksik_sarkilar):
    eklenen = 0
    hatali  = 0
    for i, sarki in enumerate(eksik_sarkilar, 1):
        vid_id = video_id_cikar(sarki.get("youtube_url", ""))
        if not vid_id:
            hatali += 1
            continue
        try:
            yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid_id},
                    }
                }
            ).execute()
            eklenen += 1
            print(f"  [{i:>3}/{len(eksik_sarkilar)}] ✓ {sarki['baslik'][:60]}")
        except HttpError as e:
            hatali += 1
            print(f"  [{i:>3}/{len(eksik_sarkilar)}] ✗ {sarki['baslik'][:50]}  ({e.resp.status})")
    return eklenen, hatali

# ─────────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json",   help="Doğrudan JSON dosya yolu")
    parser.add_argument("--public", action="store_true", help="Playlist public olsun")
    args = parser.parse_args()

    if args.json:
        json_path = args.json
    else:
        dosyalar = json_listesi()
        if not dosyalar:
            sys.exit("  eksik_sarkilar/ klasörü boş. Önce 'Missing Tracks Finder' çalıştır.")
        print("\n  ── EKSİK ŞARKI JSON'LARI ──")
        for i, f in enumerate(dosyalar, 1):
            print(f"  {i:>2}. {f}")
        try:
            secim = int(input("\n  Hangisini playlist'e çevirelim? → ").strip())
            json_path = os.path.join(JSON_DIR, dosyalar[secim - 1])
        except (ValueError, IndexError):
            sys.exit("  Geçersiz seçim.")

    veri = json_oku(json_path)
    sa   = veri.get("sanatci", "Unknown")
    eksik = veri.get("eksik_sarkilar", [])
    if not eksik:
        sys.exit("  Bu JSON'da eksik şarkı yok.")

    print(f"\n  Sanatçı: {sa}  ·  {len(eksik)} eksik şarkı")
    print("\n  YouTube'a bağlanılıyor...")
    yt = youtube_baglan()

    baslik   = f"{sa} — Hidden Tracks"
    aciklama = (
        f"Spotify'da bulunmayan ama YouTube'da popüler olan {sa} parçaları. "
        f"projectiri tarafından otomatik derlendi · {datetime.now().strftime('%Y-%m-%d')}"
    )

    print(f"\n  Playlist oluşturuluyor: '{baslik}'")
    pl_id = playlist_olustur(yt, baslik, aciklama, public=args.public)
    pl_url = f"https://www.youtube.com/playlist?list={pl_id}"
    print(f"  ✓ {pl_url}\n")

    print(f"  {len(eksik)} video ekleniyor...\n")
    eklenen, hatali = videolari_ekle(yt, pl_id, eksik)

    print(f"\n  ──────────────────────────────────────────────")
    print(f"  ✅ TAMAMLANDI")
    print(f"  Eklenen: {eklenen}  ·  Hatalı: {hatali}")
    print(f"  Playlist: {pl_url}")
    print(f"  ──────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
