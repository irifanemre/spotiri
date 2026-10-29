from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

scope = "playlist-modify-public playlist-modify-private user-read-private user-library-read user-top-read"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

print("=== API ERİŞİM TESTİ ===\n")

# Test 1: Kullanıcı bilgisi
try:
    u = sp.current_user()
    print(f"[OK] current_user: {u['display_name']}")
except Exception as e:
    print(f"[FAIL] current_user: {e}")

# Test 2: Arama (küçük limit)
try:
    r = sp.search(q="phonk", type="track", limit=5)
    print(f"[OK] search: {len(r['tracks']['items'])} sonuç")
except Exception as e:
    print(f"[FAIL] search: {e}")

# Test 3: Kendi playlist'ini oku (dj_bot.py'deki ID)
try:
    r = sp.playlist_tracks("3DO2sz2kdYIzIZJoO9hojG", limit=5)
    print(f"[OK] playlist_tracks (kendi): {len(r['items'])} şarkı")
except Exception as e:
    print(f"[FAIL] playlist_tracks (kendi): {e}")

# Test 4: Belirli bir şarkıyı ID ile çek
try:
    t = sp.track("3n3Ppam7vgaVa1iaRUIOKE")  # Mr. Brightside
    print(f"[OK] track by ID: {t['name']} (popülerlik: {t['popularity']})")
except Exception as e:
    print(f"[FAIL] track by ID: {e}")

# Test 5: Artist top tracks
try:
    r = sp.artist_top_tracks("06HL4z0CvFAxyc27GXpf02")  # Taylor Swift
    print(f"[OK] artist_top_tracks: {len(r['tracks'])} şarkı")
except Exception as e:
    print(f"[FAIL] artist_top_tracks: {e}")

# Test 6: Kullanıcının kendi top tracks'leri
try:
    r = sp.current_user_top_tracks(limit=5, time_range="medium_term")
    print(f"[OK] current_user_top_tracks: {len(r['items'])} şarkı")
except Exception as e:
    print(f"[FAIL] current_user_top_tracks: {e}")

# Test 7: Kullanıcının kayıtlı şarkıları (liked songs)
try:
    r = sp.current_user_saved_tracks(limit=5)
    print(f"[OK] current_user_saved_tracks: {len(r['items'])} şarkı")
except Exception as e:
    print(f"[FAIL] current_user_saved_tracks: {e}")

print("\n=== TEST TAMAMLANDI ===")
