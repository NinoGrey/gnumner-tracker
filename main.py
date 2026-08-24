import json
import re
import time
import urllib3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://gnumner.minfin.am"

# Список всех нужных разделов сайта
SECTIONS = [
    {
        "name": "Электронный аукцион (Էլեկտրոնային աճուրդ)",
        "url": f"{BASE_URL}/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver"
    },
    {
        "name": "Открытый конкурс (Բաց մրցույթ)",
        "url": f"{BASE_URL}/hy/page/bac_mrcuyti_haytararutyun_ev_hraver"
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.9,en;q=0.8,ru;q=0.7",
}

# Отсечка: сканировать только тендеры начиная с 1 августа 2026 года
CUTOFF_DATE = datetime.strptime("2026-08-01", "%Y-%m-%d")
MAX_PAGES_PER_SECTION = 50
DELAY_BETWEEN_PAGES = 2.0

execution_logs = []


def log_msg(msg: str):
    print(msg)
    execution_logs.append(msg)


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def extract_dates(block) -> tuple[datetime | None, str, str]:
    """Извлекает даты из параграфа <p class="tender_time"> (формат YYYY-MM-DD HH:MM:SS)."""
    time_elem = block.find('p', class_='tender_time')
    text = time_elem.get_text() if time_elem else block.get_text()

    # Поиск дат формата YYYY-MM-DD
    raw_dates = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', text)

    pub_dt = None
    pub_str = "—"
    end_str = "—"

    if len(raw_dates) >= 1:
        try:
            pub_dt = datetime.strptime(raw_dates[0], "%Y-%m-%d")
            pub_str = pub_dt.strftime("%d.%m.%Y")
        except ValueError:
            pub_dt = None

    if len(raw_dates) >= 2:
        try:
            end_dt = datetime.strptime(raw_dates[1], "%Y-%m-%d")
            end_str = end_dt.strftime("%d.%m.%Y")
        except ValueError:
            end_str = raw_dates[1]

    return pub_dt, pub_str, end_str


def fetch_with_retries(session: requests.Session, url: str, retries: int = 3) -> requests.Response | None:
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=20, verify=False)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response
        except Exception as e:
            log_msg(f"⚠️ [Попытка {attempt}/{retries}] Сбой запроса: {e}")
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def parse_section(session: requests.Session, section: dict, existing_urls: set, tenders_list: list):
    section_name = section["name"]
    start_url = section["url"]

    log_msg(f"\n📂 === Парсинг раздела: {section_name} ===")

    page = 1
    stop_parsing = False
    added_in_section = 0

    while not stop_parsing and page <= MAX_PAGES_PER_SECTION:
        url = start_url if page == 1 else f"{start_url.rstrip('/')}/{page}"
        log_msg(f"📡 [Стр. {page}] Загрузка: {url}")

        response = fetch_with_retries(session, url)
        if not response:
            log_msg(f"🏁 Не удалось получить страницу {page} (404 или ошибка сети). Переход дальше.")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        # Точный поиск контейнеров <div class="tender">
        tender_blocks = soup.find_all('div', class_='tender')
        if not tender_blocks:
            tender_blocks = soup.find_all('tr', class_=re.compile(r'(even|odd)'))

        if not tender_blocks:
            log_msg("🏁 Блоки тендеров не найдены. Конец текущего раздела.")
            break

        added_on_page = 0

        for block in tender_blocks:
            link_elem = block.find('a', href=True)
            if not link_elem:
                continue

            href = link_elem['href'].strip()
            full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
            title = clean_text(link_elem.get_text())

            if not title or len(title) < 3:
                continue

            pub_date_dt, pub_date_str, end_date_str = extract_dates(block)

            # Проверка отсечки по дате
            if pub_date_dt and pub_date_dt < CUTOFF_DATE:
                log_msg(f"⏹ ОСТАНОВКА РАЗДЕЛА: Найдена дата {pub_date_str} (раньше {CUTOFF_DATE.strftime('%d.%m.%Y')}).")
                log_msg(f"   └ Тендер: \"{title[:60]}...\"")
                stop_parsing = True
                break

            category = ""
            cat_match = re.search(r'\[(.*?)\]', title)
            if cat_match:
                category = cat_match.group(1).strip()
                title = title.replace(f"[{category}]", "").strip()

            if full_url not in existing_urls:
                existing_urls.add(full_url)
                tenders_list.append({
                    "title": title,
                    "category": category,
                    "date": pub_date_str,
                    "end_date": end_date_str,
                    "url": full_url
                })
                added_on_page += 1
                added_in_section += 1

        log_msg(f"   ├ Добавлено со страницы: {added_on_page}")
        log_msg(f"   └ Накоплено всего в базе: {len(tenders_list)}")

        if stop_parsing or added_on_page == 0:
            break

        page += 1
        time.sleep(DELAY_BETWEEN_PAGES)

    log_msg(f"✅ Раздел «{section_name}» обработан. Добавлено: {added_in_section} тендеров.")


def main():
    try:
        session = requests.Session()
        tenders = []
        existing_urls = set()

        log_msg(f"🚀 Старт парсинга. Отсечка по дате публикации: {CUTOFF_DATE.strftime('%d.%m.%Y')}")

        for section in SECTIONS:
            parse_section(session, section, existing_urls, tenders)

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)

        log_payload = {
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "total_tenders": len(tenders),
            "logs": execution_logs
        }
        with open('log.json', 'w', encoding='utf-8') as f:
            json.dump(log_payload, f, ensure_ascii=False, indent=2)

        print("💾 Файлы data.json и log.json успешно обновлены.")
    except Exception as e:
        log_msg(f"❌ Критическая ошибка в main: {e}")
        exit(1)


if __name__ == "__main__":
    main()
