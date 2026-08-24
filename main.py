import json
import os
import re
import time
import urllib3
from datetime import datetime
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://gnumner.minfin.am"

SECTIONS = [
    {
        "name": "Электронный аукцион (Էլեկտրոնային աճուրդ)",
        "url": f"{BASE_URL}/hy/page/elektronayin_achurdi_haytararutyun_ev_hraver"
    },
    {
        "name": "Открытый конкурс (Բաց մրցույթ)",
        "url": f"{BASE_URL}/hy/page/bac_mrcuyti_haytararutyun_ev_hraver"
    },
    {
        "name": "Запрос котировок (Գնանշման հարցում)",
        "url": f"{BASE_URL}/hy/page/gnanshman_harcman_haytararutyun_ev_hraver"
    },
    {
        "name": "Двухэтапный конкурс — Предквалификация (Երկփուլ մրցույթի նախաորակավորում)",
        "url": f"{BASE_URL}/hy/page/erkpul_mrcuyti_nakhaorakavorman_haytararutyun"
    },
    {
        "name": "Открытый конкурс — Предквалификация (Բաց մրցույթի նախաորակավորում)",
        "url": f"{BASE_URL}/hy/page/bac_mrcuyti_nakhaorakavorman_haytararutyun"
    },
    {
        "name": "Запрос котировок — Предквалификация (Գնանշման հարցման նախաորակավորում)",
        "url": f"{BASE_URL}/hy/page/gnanshman_harcman_nakhaorakavorman_haytararutyun"
    },
    {
        "name": "Закрытый целевой конкурс — Предквалификация (Փակ նպատակային մրցույթի նախաորակավորում)",
        "url": f"{BASE_URL}/hy/page/_pak_npatakayin_mrcuyti_nakhaorakavorman_haytararutyun"
    },
    {
        "name": "Закрытый периодический конкурс — Предквалификация (Փակ պարբերական մրցույթի նախաորակավորում)",
        "url": f"{BASE_URL}/hy/page/pak_parberakan_mrcuyti_nakhaorakavorman_haytararutyun_ev_hraver"
    },
    {
        "name": "Закрытый периодический конкурс — Договоры (Փակ պարբերական մրցույթի սկզբնական պայմանագրեր)",
        "url": f"{BASE_URL}/hy/page/pak_parberakan_mrcuyti_ardyunqum_knqvats_skzbnakan_paymanagrer"
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "hy,en-US;q=0.9,en;q=0.8,ru;q=0.7",
}

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
    time_elem = block.find('p', class_='tender_time')
    text = time_elem.get_text() if time_elem else block.get_text()

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


def load_existing_data() -> tuple[list, set]:
    """Загружает уже имеющиеся тендеры из data.json и создает Set ссылок."""
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                urls = {item["url"] for item in data if isinstance(item, dict) and "url" in item}
                return data, urls
        except Exception as e:
            log_msg(f"⚠️ Ошибка загрузки локальной базы data.json: {e}")
    return [], set()


def parse_section(session: requests.Session, section: dict, existing_urls: set, new_tenders: list):
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

        tender_blocks = soup.find_all('div', class_='tender')
        if not tender_blocks:
            tender_blocks = soup.find_all('tr', class_=re.compile(r'(even|odd)'))

        if not tender_blocks:
            log_msg("🏁 Блоки тендеров не найдены. Конец раздела.")
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

            # РАННЯЯ ОСТАНОВКА: Встречен уже сохраненный в базе тендер
            if full_url in existing_urls:
                log_msg("⏹ ОСТАНОВКА РАЗДЕЛА: Достигнуты ранее спарсенные тендеры.")
                log_msg(f"    └ Известный URL: {full_url}")
                stop_parsing = True
                break

            pub_date_dt, pub_date_str, end_date_str = extract_dates(block)

            if pub_date_dt and pub_date_dt < CUTOFF_DATE:
                log_msg(f"⏹ ОСТАНОВКА РАЗДЕЛА: Найдена дата {pub_date_str} (раньше {CUTOFF_DATE.strftime('%d.%m.%Y')}).")
                log_msg(f"    └ Тендер: \"{title[:60]}...\"")
                stop_parsing = True
                break

            category = ""
            cat_match = re.search(r'\[(.*?)\]', title)
            if cat_match:
                category = cat_match.group(1).strip()
                title = title.replace(f"[{category}]", "").strip()

            existing_urls.add(full_url)
            new_tenders.append({
                "title": title,
                "category": category,
                "section": section_name,
                "date": pub_date_str,
                "end_date": end_date_str,
                "url": full_url
            })
            added_on_page += 1
            added_in_section += 1

        log_msg(f"    ├ Добавлено новых со страницы: {added_on_page}")
        log_msg(f"    └ Всего новых в этой сессии: {len(new_tenders)}")

        if stop_parsing or added_on_page == 0:
            break

        page += 1
        time.sleep(DELAY_BETWEEN_PAGES)

    log_msg(f"✅ Раздел «{section_name}» обработан. Добавлено новых: {added_in_section}.")


def parse_date_for_sort(item):
    """Преобразует строку даты DD.MM.YYYY в объект datetime для сортировки."""
    try:
        return datetime.strptime(item["date"], "%d.%m.%Y")
    except Exception:
        return datetime.min


def main():
    try:
        session = requests.Session()

        # 1. Загрузка ранее спасенных тендеров
        existing_tenders, existing_urls = load_existing_data()
        log_msg(f"📂 Загружена локальная база: {len(existing_tenders)} сохраненных тендеров.")

        new_tenders = []
        log_msg(f"🚀 Старт парсинга. Отсечка по дате публикации: {CUTOFF_DATE.strftime('%d.%m.%Y')}")

        # 2. Сбор только fresh-данных
        for section in SECTIONS:
            parse_section(session, section, existing_urls, new_tenders)

        # 3. Объединение свежих тендеров со старыми
        all_tenders = new_tenders + existing_tenders

        # 4. Сортировка всей базы по дате публикации (от новых к старым)
        all_tenders.sort(key=parse_date_for_sort, reverse=True)
        log_msg(f"📊 Добавлено новых: {len(new_tenders)}. Всего в базе: {len(all_tenders)}.")

        # 5. Перезапись файлов
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(all_tenders, f, ensure_ascii=False, indent=2)

        log_payload = {
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "total_tenders": len(all_tenders),
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
