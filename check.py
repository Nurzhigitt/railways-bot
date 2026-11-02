"""
Разовая проверка новых IT-вакансий на job.railways.kz (Астана).
Запускается GitHub Actions по расписанию.

Нужны секреты репозитория:
  BOT_TOKEN — токен бота от @BotFather
  CHAT_ID   — ваш chat_id (можно несколько через запятую, или id канала/группы)
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_IDS = [c.strip() for c in os.environ.get("CHAT_ID", "").split(",") if c.strip()]
PAGES_TO_CHECK = 2
CITY_CODE = "710000000"          # г. Астана; "" = все города
IT_CATEGORIES = range(1, 38)     # рубрика «Информационные технологии» на сайте

BASE = "https://job.railways.kz"
SEEN_FILE = Path(__file__).parent / "seen.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch_page(page):
    params = [("sort", "-updated_at"), ("page", page)]
    if CITY_CODE:
        params.append(("c[]", CITY_CODE))
    params += [("p[]", p) for p in IT_CATEGORIES]
    r = requests.get(f"{BASE}/vacancy", params=params, headers=HEADERS, timeout=40)
    r.raise_for_status()
    return r.text


def parse_list(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.select("a.vacancy-item[href]"):
        vid = a["href"].rstrip("/").split("/")[-1]
        if not vid.isdigit():
            continue
        get = lambda sel: (a.select_one(sel).get_text(" ", strip=True) if a.select_one(sel) else "")
        org = a.select_one(".org")
        org_name, extras = "", []
        if org:
            extras = [s.get_text(" ", strip=True) for s in org.select(".type-work")]
            org_name = next((t.strip() for t in org.find_all(string=True, recursive=False) if t.strip()), "")
        items.append({
            "id": vid,
            "url": f"{BASE}/vacancy/{vid}",
            "title": get(".title") or "Без названия",
            "org": org_name,
            "extras": extras,
            "salary": get(".salary"),
            "date": get(".date"),
        })
    return items


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(v):
    lines = [f"💻 <b>{esc(v['title'])}</b>"]
    if v["org"]:
        lines.append(f"🏢 {esc(v['org'])}")
    if v["extras"]:
        lines.append("📍 " + esc(" · ".join(v["extras"])))
    if v["salary"]:
        lines.append(f"💰 {esc(v['salary'])}")
    if v["date"]:
        lines.append(f"📅 {esc(v['date'])}")
    lines.append(f'🔗 <a href="{v["url"]}">Открыть вакансию</a>')
    return "\n".join(lines)


def send(text):
    for chat in CHAT_IDS:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={
            "chat_id": chat, "text": text, "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=30)
        if not r.ok:
            print(f"Ошибка отправки в {chat}: {r.status_code} {r.text}")
        time.sleep(0.1)


def main():
    if not BOT_TOKEN or not CHAT_IDS:
        sys.exit("Не заданы секреты BOT_TOKEN и/или CHAT_ID в настройках репозитория.")

    vacancies, ids = [], set()
    for page in range(1, PAGES_TO_CHECK + 1):
        for v in parse_list(fetch_page(page)):
            if v["id"] not in ids:
                ids.add(v["id"])
                vacancies.append(v)
        time.sleep(1)
    print(f"На сайте найдено вакансий: {len(vacancies)}")

    try:
        seen = set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError):
        seen = set()

    new = [v for v in vacancies if v["id"] not in seen]
    print(f"Новых: {len(new)}")

    if not seen:
        send(f"✅ Бот подключён! Запомнил {len(vacancies)} текущих IT-вакансий.\n"
             "Теперь буду присылать только новые.")
    else:
        for v in reversed(new):  # от старых к новым
            send(fmt(v))

    if new:
        SEEN_FILE.write_text(json.dumps(sorted(seen | {v["id"] for v in new}), indent=0),
                             encoding="utf-8")


if __name__ == "__main__":
    main()
