import json
import re
import requests
import urllib3
from datetime import datetime
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

# --- НАСТРОЙКА ДИАПАЗОНА ДАТ (Формат: ГГГГ-ММ-ДД) ---
START_DATE = datetime.strptime("2026-08-01", "%Y-%m-%d")
END_DATE = datetime.strptime("2026-08-31", "%Y-%m-%d")


def clean_text(text: str) -> str:
    """Очищает текст от лишних пробелов и переносов строк."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def parse_date_from_text(text: str) -> datetime | None:
    """Извлекает первую дату публикации (DD.MM.YYYY) из текста и возвращает объект datetime."""
    match = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d.%m.%Y")
        except ValueError:
            return None
    return None


def parse_tenders():
    tenders = []
    page = 1
    stop_parsing = False

    while not stop_parsing:
        # Формируем URL с пагинацией: ?page=1, ?page=2 и т.д.
        url = f"{TARGET_URL}?page={page}" if page > 1 else TARGET_URL
        print(f"📡 Обработка страницы {page}: {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            response.raise_for_status()
            response.encoding = 'utf-8'
        except Exception as e:
            print(f"⚠️ Ошибка загрузки страницы {page}: {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        tender_blocks = soup.find_all('div', class_='tender')

        # Если на странице нет тендеров — дошли до конца пагинации
        if not tender_blocks:
            print("🏁 Достигнут конец страниц (нет больше тендеров).")
            break

        tenders_on_page = 0

        for block in tender_blocks:
            link_elem = block.find('a', href=True)
            if not link_elem:
                continue

            full_url = link_elem['href'].strip()
            title = clean_text(link_elem.get_text())

            if not title:
                continue

            # Извлекаем дату публикации из блока <p class="tender_time">
            time_elem = block.find('p', class_='tender_time')
            raw_time_text = clean_text(time_elem.get_text()) if time_elem else ""
            pub_date = parse_date_from_text(raw_time_text)

            # Проверка рамок дат
            if pub_date:
                # Если дата тендера старше START_DATE — прекращаем парсинг следующих страниц
                if pub_date < START_DATE:
                    print(f"⏹ Достигнута дата {pub_date.strftime('%d.%m.%Y')}, которая старше {START_DATE.strftime('%d.%m.%Y')}. Остановка.")
                    stop_parsing = True
                    break

                # Пропускаем тендеры, если они новее END_DATE
                if pub_date > END_DATE:
                    continue

            # Извлечение кода/категории из скобок
            category = ""
            cat_match = re.search(r'\[(.*?)\]', title)
            if cat_match:
                category = cat_match.group(1).strip()
                title = title.replace(f"[{category}]", "").strip()

            tender_data = {
                "title": title,
                "category": category,
                "date": pub_date.strftime("%d.%m.%Y") if pub_date else raw_time_text,
                "raw_date_info": raw_time_text,
                "url": full_url
            }

            if tender_data not in tenders:
                tenders.append(tender_data)
                tenders_on_page += 1

        print(f"   └ Добавлено тендеров со страницы: {tenders_on_page}")
        page += 1

    print(f"✅ Всего собрано тендеров: {len(tenders)}")
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
