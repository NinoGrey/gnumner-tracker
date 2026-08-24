import json
import os
import datetime
import requests
from bs4 import BeautifulSoup

# Словарь с понятными названиями для ваших 9 категорий
CATEGORIES = {
    "https://gnumner.minfin.am/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver/": "Электронный аукцион",
    "https://gnumner.minfin.am/hy/page/bac_mrcuyti_haytararutyun_ev_hraver/": "Открытый конкурс",
    "https://gnumner.minfin.am/hy/page/bac_mrcuyti_nakhaorakavorman_haytararutyun/": "Предквалификация",
    # Добавьте оставшиеся ссылки и их названия по аналогии:
    # "URL": "Название категории",
}

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

def extract_tenders_from_page(url, headers):
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
        
        soup = BeautifulSoup(res.text, "html.parser")
        tender_blocks = soup.find_all("div", class_="tender")
        page_tenders = []

        for block in tender_blocks:
            a_tag = block.find("a", href=True)
            if not a_tag:
                continue

            href = a_tag["href"]
            title = a_tag.get_text(strip=True)

            if href and title:
                full_url = href if href.startswith("http") else f"https://gnumner.minfin.am{href}"
                page_tenders.append({"title": title, "url": full_url})
                
        return page_tenders
    except Exception as e:
        print(f"Ошибка загрузки {url}: {e}")
        return []

def run_tracker():
    tenders = load_data()
    seen_urls = {item["url"] for item in tenders}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_tenders_batch = []

    for base_url, category_name in CATEGORIES.items():
        last_known_url = None
        for item in tenders:
            if item.get("source_page") == base_url:
                last_known_url = item["url"]
                break

        first_page_tenders = extract_tenders_from_page(base_url, headers)
        if not first_page_tenders:
            continue

        latest_site_url = first_page_tenders[0]["url"]
        if last_known_url and latest_site_url == last_known_url:
            print(f"Категория [{category_name}] актуальна.")
            continue

        print(f"Обнаружены обновления в [{category_name}]! Начинаем сбор...")

        category_new_tenders = []
        stop_parsing = False

        for page_num in range(1, 10):
            if stop_parsing:
                break
                
            page_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
            page_tenders = extract_tenders_from_page(page_url, headers) if page_num > 1 else first_page_tenders

            if not page_tenders:
                break

            for t in page_tenders:
                if t["url"] == last_known_url or t["url"] in seen_urls:
                    stop_parsing = True
                    break

                category_new_tenders.append({
                    "title": t["title"],
                    "url": t["url"],
                    "date": now_str,
                    "category": category_name, # Сохраняем имя категории
                    "source_page": base_url
                })
                seen_urls.add(t["url"])

        new_tenders_batch.extend(category_new_tenders)

    if new_tenders_batch:
        tenders = new_tenders_batch + tenders
        save_data(tenders)
        print(f"Успешно добавлено новых тендеров: {len(new_tenders_batch)}")
    else:
        print("Вся база находится в актуальном состоянии.")

if __name__ == "__main__":
    run_tracker()
