import json
import re
import requests
import urllib3
from bs4 import BeautifulSoup

# Отключаем предупреждения о необрабатываемых SSL-сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://gnumner.minfin.am"
TARGET_URL = f"{BASE_URL}/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def clean_text(text: str) -> str:
    """Очищает текст от лишних пробелов и переносов строк."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def parse_tenders():
    print(f"📡 Загрузка страницы: {TARGET_URL}")
    
    response = requests.get(TARGET_URL, headers=HEADERS, timeout=15, verify=False)
    response.raise_for_status()
    response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.text, 'html.parser')
    tenders = []
    
    # Ищем все блоки карточек тендеров <div class="tender">
    tender_blocks = soup.find_all('div', class_='tender')
    
    for block in tender_blocks:
        # Извлекаем ссылку и заголовок
        link_elem = block.find('a', href=True)
        if not link_elem:
            continue
            
        full_url = link_elem['href'].strip()
        title = clean_text(link_elem.get_text())
        
        if not title:
            continue
            
        # Извлекаем блок с датой <p class="tender_time">
        time_elem = block.find('p', class_='tender_time')
        date_text = clean_text(time_elem.get_text()) if time_elem else ""
        
        # Извлекаем категорию/код, если они есть в скобках [ ... ]
        category = ""
        cat_match = re.search(r'\[(.*?)\]', title)
        if cat_match:
            category = cat_match.group(1).strip()
            title = title.replace(f"[{category}]", "").strip()

        tender_data = {
            "title": title,
            "category": category,
            "date": date_text,
            "url": full_url
        }
        
        if tender_data not in tenders:
            tenders.append(tender_data)
                
    print(f"✅ Найдено тендеров: {len(tenders)}")
    return tenders

def main():
    try:
        tenders = parse_tenders()
        
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)
            
        print("💾 Данные успешно сохранены в data.json")
    except Exception as e:
        print(f"❌ Ошибка при выполнении парсера: {e}")
        exit(1)

if __name__ == "__main__":
    main()
