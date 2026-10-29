import os
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

# --- SENİN VIP ANAHTARLARIN ---
CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:8888/callback'

# LİSTE ID'N (URL'ndeki o karışık kod)
PLAYLIST_ID = '3DO2sz2kdYIzIZJoO9hojG'

scope = "playlist-modify-public playlist-modify-private"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI, scope=scope))

print("--- OTOMATİK KÜRATÖR DEVREDE ---")

# 1. Phonk dünyasını tara
results = sp.search(q='phonk', type='track', limit=5)
sepet = []

print("\n🔍 Uygun şarkılar ayıklanıyor...")

for track in results['tracks']['items']:
    t_id = track['id']
    t_name = track['name']
    is_explicit = track['explicit']
    
    # KRİTERİMİZ: Eğer şarkı sert/sansürsüzse (Explicit) sepete at!
    if is_explicit:
        sepet.append(t_id)
        print(f"✅ Eklenecek: {t_name}")

# 2. SEPETTEKİLERİ LİSTEYE BOŞALT
if sepet:
    sp.playlist_add_items(PLAYLIST_ID, sepet)
    print(f"\n🚀 İŞLEM TAMAM! {len(sepet)} yeni mermi listeye sürüldü.")
else:
    print("\n❌ Kriterlere uygun yeni şarkı bulunamadı.")
