"""
Tüm playlist'leri non-collaborative yapar.
Public kalırlar (herkes dinleyebilir) ama kimse şarkı ekleyip çıkaramaz.
"""

import sys
import time
from dotenv import load_dotenv

load_dotenv()
from spotify_auth import get_sp, kendi_playlistlerim
sp = get_sp()

me       = sp.current_user()
HESAP_ID = me["id"]

if __name__ != "__main__":
    sys.exit(0)   # import edilince tüm playlist'ler değiştirilmesin

print("Playlist'ler taranıyor...")
playlistler = kendi_playlistlerim(sp, HESAP_ID)
print(f"{len(playlistler)} playlist bulundu.\n")

for pl in playlistler:
    isim       = pl["name"]
    halen_acik = pl.get("collaborative", False)
    public     = pl.get("public", True)
    try:
        # Collaborative playlist private olmak zorunda
        # Önce public yap, sonra collaborative=False
        sp.playlist_change_details(
            pl["id"],
            public=True,
            collaborative=False
        )
        durum = "DEĞİŞTİRİLDİ" if halen_acik else "ZATEN KAPALI"
        print(f"  [{durum}] {isim}")
    except Exception as e:
        print(f"  [HATA] {isim}: {e}")
    time.sleep(0.3)

print("\n=== TAMAMLANDI ===")
print("Tüm playlist'lerin: public=True (herkes dinler), collaborative=False (kimse ekleyemez)")
