import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 1. Hafıza Ayarları
current_dir = os.getcwd()
profile_path = os.path.join(current_dir, "spotify_session")

options = webdriver.ChromeOptions()
options.add_experimental_option("detach", True)
options.add_argument(f"user-data-dir={profile_path}")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 20)

print("--- CEPHANELİK YÜKLENİYOR ---")

# Senin listenin tam URL'si
PLAYLIST_LINK = "https://open.spotify.com/playlist/3DO2sz2kdYIzIZJoO9hojG?si=xlracnSVRsycotO2l0H3eQ"

sarkilar = [
    "Kavinsky Nightcall",
    "The Weeknd Blinding Lights",
    "Gesaffelstein Opr"
]

try:
    driver.get(PLAYLIST_LINK)
    print("Listeye inildi. Hedef kutu aranıyor...")
    time.sleep(6) # Spotify'ın arama motorunun kendine gelmesi için
    
    for sarki in sarkilar:
        print(f"Mermiye sürülen: {sarki}")
        
        # 1. Kutuyu kesin olarak bul ve tıklanabilir olmasını bekle
        search_xpath = "//input[contains(@placeholder, 'Şarkı veya bölüm ara')]"
        search_box = wait.until(EC.element_to_be_clickable((By.XPATH, search_xpath)))
        
        # 2. Önce kutuya tıkla ki Spotify uyansın
        search_box.click()
        time.sleep(1)
        
        # 3. İçini JavaScript ile tertemiz yap ve şarkıyı gönder
        driver.execute_script("arguments[0].value = '';", search_box)
        search_box.send_keys(sarki)
        
        # Şarkıyı algılaması için boşluk bırak (React'ı tetikler)
        search_box.send_keys(" ")
        time.sleep(4) # Arama sonuçlarının ekrana dökülmesini bekle
        
        # 4. En üstteki 'Ekle' butonunu (data-testid ile) bul
        add_btn_xpath = "(//button[@data-testid='add-to-playlist-button'])[1]"
        add_button = wait.until(EC.presence_of_element_located((By.XPATH, add_btn_xpath)))
        
        # 5. Görünmez engelleri aşarak tıkla
        driver.execute_script("arguments[0].click();", add_button)
        print(f"[BAŞARILI] {sarki} listeye eklendi!")
        
        time.sleep(2) # Diğer şarkıya geçmeden önce nefes al

    print("\n--- GÖREV TAMAM! LİSTEYE GÖZ AT ---")

except Exception as e:
    print(f"\nTerminalde hata: {e}")
