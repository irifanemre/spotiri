import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

current_dir = os.getcwd()
profile_path = os.path.join(current_dir, "bot_hafiza_1")

options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)
options.add_argument(f"user-data-dir={profile_path}")

# --- SUSTURUCU AYARLARI ---
prefs = {
    "profile.default_content_setting_values.notifications": 2, # Bildirimleri engelle (İzin ver/Engelle pop-upları)
    "profile.default_content_setting_values.popups": 2,        # Klasik pop-upları engelle
    "protocol_handler.excluded_schemes": {"spotify": True}     # "Mac'teki Spotify Uygulamasında Aç" uyarısını engelle
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 45)

print("--- AJAN BOT UYANDIRILIYOR ---")
# Senin Listenin Tam Linki
PLAYLIST_LINK = "https://open.spotify.com/playlist/3DO2sz2kdYIzIZJoO9hojG?si=-CDJxsSxSvS-bRz6SECqhA"

try:
    driver.get(PLAYLIST_LINK)
    print("Hedef listeye inildi. Çevrenin güvenliği sağlanıyor (8 saniye bekleme)...")
    time.sleep(8) # Reklamların ve pop-up'ların yüklenip geçmesini bekliyoruz
    
    print("Doğrudan Play (Oynat) butonunun yanındaki (+) işaretine kilitleniliyor...")
    
    # JavaScript Keskin Nişancı Kodu: Sadece ve sadece ana paneldeki takip butonunu vurur
    js_hedefleme = """
    // 1. Play butonunun olduğu asıl aksiyon çubuğunu bul
    var actionBar = document.querySelector('div[data-testid="action-bar-row"]');
    if (actionBar) {
        // 2. Çubuğun içindeki 'Ekle' veya 'Takip Et' butonunu bul
        var addButton = actionBar.querySelector('button[data-testid="add-button"], button[data-testid="add-to-library-button"]');
        if (addButton) {
            addButton.click();
            return "VURULDU";
        }
    }
    // 3. Eğer üstteki bulamazsa, sadece aria-label'ı kesin uyan butona tıkla
    var backupButtons = document.querySelectorAll('button[aria-label="Kitaplığa ekle"], button[aria-label="Save to Your Library"]');
    for(var i=0; i<backupButtons.length; i++) {
        backupButtons[i].click();
        return "VURULDU";
    }
    return "KARAVANA";
    """
    
    sonuc = driver.execute_script(js_hedefleme)
    
    if sonuc == "VURULDU":
        print("\n--- BİNGO! OPERASYON BAŞARILI! ---")
        print("Ajan o yuvarlak (+) butonuna bastı (Tıklandığında yeşil tik olmalı).")
    else:
        print("\n[Hata] Buton bulunamadı, Spotify yine arayüz değiştirmiş olabilir.")

except Exception as e:
    print(f"\nHata: {e}")
