import json
import re
import urllib3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://gnumner.minfin.am"
START_URL = f"{BASE_URL}/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Ниже этой даты парсер не идет (включительно)
CUTOFF_DATE = datetime.strptime("2026-08-01", "%Y-%m-%d")
MAX_PAGES = 100  # Страховочный лимит страниц


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def parse_date_from_text(text: str) -> datetime | None:
    """Ищет первую дату DD.MM.YYYY в тексте блока времени."""
    match = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d.%m.%Y")
        except ValueError:
            return None
    return None


def get_next_page_url(soup: BeautifulSoup, current_page: int) -> str | None:
    """Находит реальную ссылку на следующую страницу в блоке пагинации сайта."""
    pagination = soup.find('div', class_='pagination')
    if not pagination:
        pagination = soup.find('ul', class_='pager')

    if pagination:
        # Ищем активную страницу или ссылку со следующим номером
        next_link = pagination.find('a', href=True, text=re.compile(str(current_page + 1)))
        if not next_link:
            # Запасной вариант: ищем стрелку '>', 'next' или 'հաջորդ'
            next_link = pagination.find('a', href=True, text=re.compile(r'(>|next|հաջորդ)', re.I))

        if next_link and next_link.get('href'):
            href = next_link['href'].strip()
            return href if href.startswith('http') else f"{BASE_URL}{href}"

    # Резервный формат GET-параметра, если кнопка не найдена в DOM
    return f"{START_URL}?page={current_page}"


def parse_tenders():
    tenders = []
    current_url = START_URL
    page = 1
    stop_parsing = False

    while current_url and not stop_parsing and page <= MAX_PAGES:
        print(f"\n📡 [Страница {page}] Загрузка: {current_url}")

        try:
            response = requests.get(current_url, headers=HEADERS, timeout=15, verify=False)
            response.raise_for_status()
            response.encoding = 'utf-8'
        except Exception as e:
            print(f"❌ Ошибка сетевого запроса: {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        tender_blocks = soup.find_all('div', class_='tender')

        if not tender_blocks:
            print("🏁 Блоки тендеров не найдены. Конец списка.")
            break

        added_on_page = 0

        for block in tender_blocks:
            link_elem = block.find('a', href=True)
            if not link_elem:
                continue

            href = link_elem['href'].strip()
            full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
            title = clean_text(link_elem.get_text())

            if not title:
                continue

            # Дата публикации
            time_elem = block.find('p', class_='tender_time')
            raw_time_text = clean_text(time_elem.get_text()) if time_elem else ""
            pub_date = parse_date_from_text(raw_time_text)

            date_str = pub_date.strftime("%d.%m.%Y") if pub_date else "Не указана"

            # Проверка отсечки по дате
            if pub_date and pub_date < CUTOFF_DATE:
                print(f"⏹ ОСТАНОВКА: Найдена дата {date_str} (раньше {CUTOFF_DATE.strftime('%d.%m.%Y')}).")
                print(f"   └ Тендер: \"{title[:60]}...\"")
                stop_parsing = True
                break

            # Извлечение категории/кода из скобок [ ... ]
            category = ""
            cat_match = re.search(r'\[(.*?)\]', title)
            if cat_match:
                category = cat_match.group(1).strip()
                title = title.replace(f"[{category}]", "").strip()

            tender_data = {
                "title": title,
                "category": category,
                "date": date_str,
                "raw_date_info": raw_time_text,
                "url": full_url
            }

            if tender_data not in tenders:
                tenders.append(tender_data)
                added_on_page += 1

        print(f"   ├ Добавлено с этой страницы: {added_on_page}")
        print(f"   └ Накоплено всего: {len(tenders)}")

        if stop_parsing:
            break

        # Переход к следующей странице
        next_url = get_next_page_url(soup, page)
        if next_url == current_url:
            print("🏁 Следующая страница совпадает с текущей. Завершение.")
            break

        current_url = next_url
        page += 1

    print(f"\n✅ Успешно собрано {len(tenders)} тендеров с {page} страниц.")
    return tenders


def main():
    try:
        tenders = parse_tenders()
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)
        print("💾 Файл data.json обновлен.")
    except Exception as e:
        print(f"❌ Ошибка в main: {e}")
        exit(1)


if __name__ == "__main__":
    main()
