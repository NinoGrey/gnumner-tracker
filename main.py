import json
import os
import datetime
import requests
from bs4 import BeautifulSoup

# Укажите здесь все 9 интересующих вас страниц
TARGET_URLS = [
    "https://https://gnumner.minfin.am/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver/",
   
    # Добавьте остальные 6 URL...
]

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run_tracker():
    tenders = load_data()
    # Множество существующих URL для быстрой проверки дубликатов
    seen_urls = {item["url"] for item in tenders}
    new_found = False

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    for page_url in TARGET_URLS:
        try:
            res = requests.get(page_url, headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"Ошибка загрузки {page_url}: статус {res.status_code}")
                continue
            
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", href=True)

            for a in links:
                href = a["href"]
                title = a.get_text(strip=True)

                # Фильтруем ссылки на целевые документы/тендеры
                if "/file/" in href or "haytararutyun" in href or ".zip" in href:
                    full_url = href if href.startswith("http") else f"https://gnumner.minfin.am{href}"
                    
                    if full_url not in seen_urls and title:
                        seen_urls.add(full_url)
                        new_found = True
                        
                        # Добавляем новый тендер в начало списка
                        tenders.insert(0, {
                            "title": title,
                            "url": full_url,
                            "date": now_str,
                            "source_page": page_url
                        })
        except Exception as e:
            print(f"Ошибка при обработке {page_url}: {e}")

    if new_found:
        save_data(tenders)
        print("База данных обновлена новым тендерами.")
    else:
        print("Новых тендеров не обнаружено.")

if __name__ == "__main__":
    run_tracker()
