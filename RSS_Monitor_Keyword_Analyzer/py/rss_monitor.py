#!/usr/bin/env python3
# =============================================================================
# RSS Monitor + Keyword Alert
# OSINT Portfolio — Skript 2
# =============================================================================

import feedparser
import json
import os
import time
import requests
import re
from datetime import datetime

# =============================================================================
# KONFIGURACE — upravuj zde
# =============================================================================

RSS_SOURCES = {
    "TASS":    "https://tass.ru/rss/v2.xml",
    "RIA":     "https://ria.ru/export/rss2/archive/index.xml",
    "Meduza":  "https://meduza.io/rss/all",
    "RBC":     "https://rbc.ru/rss/news",
    "TheIns":   "https://theins.ru/feed",
    "Ukrinform": "https://www.ukrinform.net/rss/block-lastnews",
    "UkrPravda": "https://www.pravda.com.ua/rss/view_news/",
    "NovGazeta": "https://novayagazeta.eu/feed/rss",
    "RT":        "https://www.rt.com/rss/",
    "RFERL":     "https://www.rferl.org/api/",
}

KEYWORDS = [
    "СВО", "наступление", "отступление", "БПЛА", "потери", "мобилизация", "повестка",
    "вброс", "иноагент", "блокировка", "Роскомнадзор", "замедление",
    "санкции", "импортозамещение", "НАТО", "денацификация", "релоканты",
    "casualties", "blockade", "offensive", "mobilization", "sanctions", "ceasefire", "propaganda",
]

CHECK_INTERVAL = 1800

BASE_DIR  = "/Volumes/OSINT/OSINT/PY/RSS_Monitor_Keyword_Analyzer"
SEEN_FILE = f"{BASE_DIR}/json/seen_articles.json"
LOG_FILE  = f"{BASE_DIR}/log/rss_alerts.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# =============================================================================
# TELEGRAM BOT — deaktivován, připraven k aktivaci
# =============================================================================
# BOT_TOKEN = "VAS_TOKEN_ZDE"
# CHAT_ID   = "VAS_CHAT_ID_ZDE"
#
# def send_telegram_alert(message):
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#     payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
#     try:
#         requests.post(url, data=payload, timeout=10)
#     except Exception as e:
#         print(f"[TELEGRAM ERROR] {e}")

# =============================================================================
# POMOCNÉ FUNKCE
# =============================================================================

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False)


def find_keywords(text):
    text_lower = text.lower()
    found = []
    for kw in KEYWORDS:
        pattern = r'(?<![а-яёa-z])' + re.escape(kw.lower()) + r'(?![а-яёa-z])'
        if re.search(pattern, text_lower):
            found.append(kw)
    return found


def write_log(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def print_alert(source, title, link, keywords_found, published):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 70
    alert = (
        f"\n{separator}\n"
        f"[ALERT] {timestamp}\n"
        f"Zdroj:      {source}\n"
        f"Klíčová slova: {', '.join(keywords_found)}\n"
        f"Titulek:    {title}\n"
        f"Publikováno:{published}\n"
        f"URL:        {link}\n"
        f"{separator}"
    )
    print(alert)
    write_log(alert)
    # send_telegram_alert(alert)


# =============================================================================
# HLAVNÍ LOGIKA
# =============================================================================

def process_feed(source_name, url, seen):
    alert_count = 0
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        feed = feedparser.parse(response.content)

        if feed.bozo and not feed.entries:
            print(f"[WARN] {source_name}: problém s parsováním feedu")

        for entry in feed.entries:
            article_id = getattr(entry, "id", None) or getattr(entry, "link", None) or getattr(entry, "title", None)
            if article_id:
                article_id = article_id.split("?")[0].strip()
            if not article_id:
                continue
            if article_id in seen:
                continue
            seen.add(article_id)

            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            full_text = f"{title} {summary}"

            found = find_keywords(full_text)
            if found:
                link = getattr(entry, "link", "N/A")
                published = getattr(entry, "published", "N/A")
                print_alert(source_name, title, link, found, published)
                alert_count += 1

    except Exception as e:
        print(f"[ERROR] {source_name}: {e}")

    return alert_count, seen


def run_cycle(seen):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] Spouštím kontrolu {len(RSS_SOURCES)} zdrojů...")

    total_alerts = 0
    for source_name, url in RSS_SOURCES.items():
        count, seen = process_feed(source_name, url, seen)
        total_alerts += count
        print(f"  ✓ {source_name} — hotovo ({count} alertů)")

    print(f"[INFO] Cyklus dokončen. Celkem alertů: {total_alerts}")
    print(f"[INFO] Další kontrola za {CHECK_INTERVAL // 60} minut. Zastav: Ctrl+C\n")
    return seen


# =============================================================================
# SPUŠTĚNÍ
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  RSS Monitor + Keyword Alert — OSINT Portfolio Skript 2")
    print("=" * 70)
    print(f"Monitorované zdroje: {', '.join(RSS_SOURCES.keys())}")
    print(f"Klíčových slov: {len(KEYWORDS)}")
    print(f"Interval: {CHECK_INTERVAL // 60} minut")
    print(f"Log soubor: {LOG_FILE}")
    print("Zastav Ctrl+C")
    print("=" * 70)

    seen = load_seen()

    try:
        while True:
            seen = run_cycle(seen)
            save_seen(seen)
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        save_seen(seen)
        print("\n[INFO] Monitor zastaven. Stav uložen.")
