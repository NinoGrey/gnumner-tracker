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
    """Очищает текст от лишних пробелов, переносов строк и символов."""
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
    
    # Ищем строки таблицы (tr), где содержатся конкретные объявления
    rows = soup.find_all('tr')
    
    for row in rows:
        # Ищем ссылку внутри строки
        link_elem = row.find('a', href=True)
        if not link_elem:
            continue
            
        href = link_elem['href']
        title = clean_text(link_elem.get_text())
        
        # Пропускаем служебные ссылки и пустые элементы
        if not title or len(title) < 5 or 'javascript' in href:
            continue
            
        # Корректно формируем URL без потери слэша
        if href.startswith('http'):
            full_url = href
        else:
            full_url = f"{BASE_URL}/{href.lstrip('/')}"
            
        # Извлекаем дату из текста всей строки таблицы (формат ДД.ММ.ГГГГ)
        row_text = clean_text(row.get_text())
        date_match = re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', row_text)
        date_text = date_match.group(0) if date_match else ""
        
        # Выделяем код тендера/категорию из скобок (например, [ՀՀ ՖՆ-ԷԱՃԱՊՁԲ-24/1])
        category = ""
        cat_match = re.search(r'\[(.*?)\]', title)
        if cat_match:
            category = cat_match.group(1)
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
