import json
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://gnumner.minfin.am"
TARGET_URL = f"{BASE_URL}/hy/page/haytararutyunner_tsanowtsowmner/"

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
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_category(title: str) -> tuple[str, str]:
    """
    Извлекает префикс/категорию из заголовка (например, [Аукцион], [Գնանշում] и т.д.)
    Возвращает кортеж: (Категория, Очищенный заголовок).
    """
    match = re.match(r'^\s*\[(.*?)\]\s*(.*)$', title)
    if match:
        category = match.group(1).strip()
        clean_title = match.group(2).strip()
        return category, clean_title
    return "", title

def parse_tenders():
    print(f"📡 Загрузка страницы: {TARGET_URL}")
    response = requests.get(TARGET_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    
    # Указываем правильную кодировку для корректного отображения армянских символов
    response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.text, 'html.parser')
    tenders = []
    
    # Ищем все ссылки на объявления в таблицах или списках
    links = soup.find_all('a', href=True)
    
    for a in links:
        href = a['href']
        text = clean_text(a.get_text())
        
        # Фильтруем ссылки, относящиеся к объявлениям (содержат /hy/news/ или /hy/page/)
        if '/hy/news/item/' in href or '/hy/page/' in href:
            if not text or len(text) < 5:
                continue
            
            # Формируем полную ссылку
            full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
            
            # Попытка найти дату рядом с элементом
            parent_row = a.find_parent(['tr', 'li', 'div'])
            date_text = ""
            if parent_row:
                # Ищем шаблон даты ДД.ММ.ГГГГ
                date_match = re.search(r'\b\d{2}\.\d{2}\.\d{4}\b', parent_row.get_text())
                if date_match:
                    date_text = date_match.group(0)
            
            # Выделяем категорию из заголовка
            category, clean_title = extract_category(text)
            
            # Исключаем дубликаты
            tender_data = {
                "title": clean_title,
                "category": category,
                "date": date_text,
                "url": full_url
            }
            
            if tender_data not in tenders:
                tenders.append(tender_data)
                
    print(f"✅ Найдено объявлений: {len(tenders)}")
    return tenders

def main():
    try:
        tenders = parse_tenders()
        
        # Сохраняем в data.json с красивым форматированием
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)
            
        print("💾 Данные успешно сохранены в data.json")
    except Exception as e:
        print(f"❌ Ошибка при выполнении парсера: {e}")
        exit(1)

if __name__ == "__main__":
    main()
