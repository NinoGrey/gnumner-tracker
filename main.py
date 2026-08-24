import json
import re
import time
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
    ),
    "Accept-Language": "hy,en-US;q=0.9,en;q=0.8,ru;q=0.7",
}

CUTOFF_DATE = datetime.strptime("2026-08-01", "%Y-%m-%d")
MAX_PAGES = 50
DELAY_BETWEEN_PAGES = 2.0

# Глобальный список для накопления лога
execution_logs = []


def log_msg(msg: str):
    """Печатает лог в консоль и сохраняет его для сайта."""
    print(msg)
    execution_logs.append(msg)


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def extract_dates(block) -> tuple[datetime | None, str, str]:
    text = block.get_text()
    dates = re.findall(r'\b(\d{2}[\./]\d{2}[\./]\d{4})\b', text)
    dates = [d.replace('/', '.') for d in dates]

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
            log_msg(f"⚠️ [Попытка {attempt}/{retries}] Сбой сетевого запроса: {e}")
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def parse_tenders():
    tenders = []
    page = 1
    stop_parsing = False
    session = requests.Session()

    log_msg(f"🚀 Старт парсинга. Отсечка по дате: {CUTOFF_DATE.strftime('%d.%m.%Y')}")

    while not stop_parsing and page <= MAX_PAGES:
        url = START_URL if page == 1 else f"{START_URL}/{page}"
        log_msg(f"📡 [Страница {page}] Загрузка: {url}")

        response = fetch_with_retries(session, url)
        if not response:
            log_msg(f"🏁 Не удалось получить страницу {page} или конец списка (404).")
            break

        soup = BeautifulSoup(response.text, 'html.parser')

        tender_blocks = soup.find_all('div', class_='tender')
        if not tender_blocks:
            tender_blocks = soup.find_all('tr', class_=re.compile(r'(even|odd)'))
        if not tender_blocks:
            tender_blocks = soup.find_all('div', class_='views-row')

        if not tender_blocks:
            log_msg("🏁 Блоки тендеров не найдены. Завершение.")
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

            if pub_date_dt and pub_date_dt < CUTOFF_DATE:
                log_msg(f"⏹ ОСТАНОВКА: Найдена дата {pub_date_str} (раньше отсечки).")
                log_msg(f"   └ Тендер: \"{title[:60]}...\"")
                stop_parsing = True
                break

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

        log_msg(f"   ├ Добавлено со страницы: {added_on_page}")
        log_msg(f"   └ Накоплено всего: {len(tenders)}")

        if stop_parsing or added_on_page == 0:
            break

        page += 1
        time.sleep(DELAY_BETWEEN_PAGES)

    log_msg(f"✅ Финиш: собрано {len(tenders)} тендеров с {page} страниц.")
    return tenders, page


def main():
    try:
        tenders, total_pages = parse_tenders()

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(tenders, f, ensure_ascii=False, indent=2)

        # Сохранение лога в отдельный файл
        log_payload = {
            "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "total_tenders": len(tenders),
            "total_pages": total_pages,
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
