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

# Граница отсечки по дате (включительно)
CUTOFF_DATE = datetime.strptime("2026-08-01", "%Y-%m-%d")
MAX_PAGES = 100


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def extract_dates(block) -> tuple[datetime | None, str, str]:
    """
    Извлекает все даты (DD.MM.YYYY) из текста блока тендера.
    Возвращает: (pub_date_datetime, pub_date_str, end_date_str)
    """
    text = block.get_text()
    dates = re.findall(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
    
    pub_dt = None
    pub_str = "—"
    end_str = "—"

    if len(dates) >= 1:
        pub_str = dates[0]
        try:
            pub_dt = datetime.strptime(pub_str, "%d.%m.%Y")
        except ValueError:
            pub_dt = None

    if len(dates) >= 2:
        end_str = dates[1]

    return pub_dt, pub_str, end_str


def parse_tenders():
    tenders = []
    page = 1
    stop_parsing = False

    while not stop_parsing and page <= MAX_PAGES:
        # Надежная пагинация через параметр ?page=N
        url = f"{START_URL}?page={page}" if page > 1 else START_URL
        print(f"\n📡 [Страница {page}] Загрузка: {url}")

        try:
            response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
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

            # Извлечение даты публикации и даты завершения
            pub_date_dt, pub_date_str, end_date_str = extract_dates(block)

            # Проверка отсечки по дате публикации
            if pub_date_dt and pub_date_dt < CUTOFF_DATE:
                print(f"⏹ ОСТАНОВКА: Найдена дата {pub_date_str} (раньше {CUTOFF_DATE.strftime('%d.%m.%Y')}).")
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
                "date": pub_date_str,
                "end_date": end_date_str,
                "url": full_url
            }

            if tender_data not in tenders:
                tenders.append(tender_data)
                added_on_page += 1

        print(f"   ├ Добавлено с этой страницы: {added_on_page}")
        print(f"   └ Накоплено всего: {len(tenders)}")

        if stop_parsing:
            break

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
