import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Şifreleri yükle
load_dotenv()

# İzinleri belirle (Okuma yetkisini de ekledik)
scope = "playlist-modify-public playlist-modify-private user-library-read playlist-read-private"

# Spotify'a bağlan
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))

# Bağlantıyı test et
user_info = sp.current_user()

print("--- BAĞLANTI BAŞARILI ---")
print(f"Hoş geldin: {user_info['display_name']}")
# --- FAZ 1: İSTİHBARAT TOPLAMA ---
print("\n--- MEVCUT ÇALMA LİSTELERİN ---")

# Spotify'dan kullanıcının ilk 10 çalma listesini çekiyoruz
listeler = sp.current_user_playlists(limit=10)

# Gelen verinin içindeki 'items' (ögeler) kutusunu açıp tek tek dönüyoruz
for i, liste in enumerate(listeler['items']):
    liste_adi = liste['name']
    liste_id = liste['id']
    print(f"{i+1}. {liste_adi} | Kimlik (ID): {liste_id}")
    
  # --- FAZ 2: ŞANTİYE (VERİ YAZMA) ---
print("\n--- YENİ LİSTE OLUŞTURULUYOR ---")

benim_id = user_info['id']

yeni_liste = sp.user_playlist_create(
    user=benim_id,
    name="C4 Gece Sürüşü",
    public=False
)

print(f"Tebrikler! '{yeni_liste['name']}' adlı liste başarıyla oluşturuldu.")
