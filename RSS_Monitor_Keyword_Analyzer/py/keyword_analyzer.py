#!/usr/bin/env python3
# =============================================================================
# Keyword Frequency Analyzer
# OSINT Portfolio — Skript 3
# =============================================================================

import feedparser
import requests
import json
import os
import csv
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from email.utils import parsedate_to_datetime

# =============================================================================
# KONFIGURACE — upravuj zde
# =============================================================================

# Klíčová slova pro analýzu frekvence
KEYWORDS = [
    "вброс",
    "потери",
    "мобилизация",
    "повестка",
    "наступление",
    "импортозамещение",
    "иноагент",
    "блокировка",
    "антивоенный",
    "релоканты",
    "casualties",
    "blockade",
    "offensive",
    "mobilization",
    "sanctions",
    "ceasefire",
    "propaganda",
]

# RSS zdroje (stejné jako Skript 2)
RSS_SOURCES = {
    "TASS":    "https://tass.ru/rss/v2.xml",
    "RIA":     "https://ria.ru/export/rss2/archive/index.xml",
    "Meduza":  "https://meduza.io/rss/all",
    "RBC":     "https://rbc.ru/rss/news",
    "TheIns":  "https://theins.ru/feed",
    "Ukrinform": "https://www.ukrinform.net/rss/block-lastnews",
    "UkrPravda": "https://www.pravda.com.ua/rss/view_news/",
    "NovGazeta": "https://novayagazeta.eu/feed/rss",
    "RT":        "https://www.rt.com/rss/",
    "RFERL":     "https://www.rferl.org/api/",
}

# Výchozí časové okno (dní)
DEFAULT_DAYS = 7

# Soubory
BASE_DIR   = "/Volumes/OSINT/OSINT/PY/RSS_Monitor_Keyword_Analyzer"
LOG_FILE   = f"{BASE_DIR}/log/rss_alerts.log"
CSV_OUTPUT = f"{BASE_DIR}/csv/keyword_frequency.csv"

# Hlavičky pro HTTP požadavky
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# =============================================================================
# PARSOVÁNÍ LOG SOUBORU
# =============================================================================

def parse_log_file(log_path, since):
    """
    Načte historická data z rss_alerts.log.
    Vrátí list záznamů: {"date": datetime, "source": str, "keywords": [str], "title": str}
    """
    records = []

    if not os.path.exists(log_path):
        print(f"[INFO] Log soubor '{log_path}' nenalezen — přeskakuji historická data.")
        return records

    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Každý alert je blok mezi separátory
    blocks = content.split("=" * 70)

    for block in blocks:
        block = block.strip()
        if not block or "[ALERT]" not in block:
            continue

        # Datum a čas
        date_match = re.search(r"\[ALERT\]\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", block)
        if not date_match:
            continue
        try:
            record_dt = datetime.strptime(date_match.group(1), "%Y-%m-%d %H:%M:%S")
            record_dt = record_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if record_dt < since:
            continue

        # Zdroj
        source_match = re.search(r"Zdroj:\s+(.+)", block)
        source = source_match.group(1).strip() if source_match else "Neznámý"

        # Klíčová slova
        kw_match = re.search(r"Klíčová slova:\s+(.+)", block)
        if kw_match:
            found_kws = [k.strip() for k in kw_match.group(1).split(",")]
            # Filtruj jen slova z aktuálního KEYWORDS seznamu
            found_kws = [k for k in found_kws if k in KEYWORDS]
        else:
            found_kws = []

        # Titulek
        title_match = re.search(r"Titulek:\s+(.+)", block)
        title = title_match.group(1).strip() if title_match else ""

        if found_kws:
            records.append({
                "date": record_dt,
                "source": source,
                "keywords": found_kws,
                "title": title,
                "origin": "log",
            })

    print(f"[INFO] Log: načteno {len(records)} záznamů z posledních {DEFAULT_DAYS} dní.")
    return records


# =============================================================================
# LIVE RSS FETCH
# =============================================================================

def fetch_live_feeds(since):
    """
    Stáhne aktuální RSS feedy a vrátí záznamy ve stejném formátu jako parse_log_file.
    """
    records = []

    for source_name, url in RSS_SOURCES.items():
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            feed = feedparser.parse(response.content)

            for entry in feed.entries:
                # Datum publikace
                pub = getattr(entry, "published", None)
                if pub:
                    try:
                        entry_dt = parsedate_to_datetime(pub)
                        if entry_dt.tzinfo is None:
                            entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        entry_dt = datetime.now(timezone.utc)
                else:
                    entry_dt = datetime.now(timezone.utc)

                if entry_dt < since:
                    continue

                # Text ke kontrole
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                full_text = f"{title} {summary}".lower()

                # Hledej klíčová slova
                found_kws = [
                    kw for kw in KEYWORDS
                    if re.search(r'(?<![а-яёa-z])' + re.escape(kw.lower()) + r'(?![а-яёa-z])', full_text)
                ]

                if found_kws:
                    records.append({
                        "date": entry_dt,
                        "source": source_name,
                        "keywords": found_kws,
                        "title": title,
                        "origin": "live",
                    })

            print(f"  ✓ {source_name} — načteno")

        except Exception as e:
            print(f"  [ERROR] {source_name}: {e}")

    print(f"[INFO] Live feedy: nalezeno {len(records)} článků s klíčovými slovy.")
    return records


# =============================================================================
# ANALÝZA FREKVENCE
# =============================================================================

def analyze(records):
    """
    Z listů záznamů vypočítá:
    - celkovou frekvenci každého klíčového slova
    - frekvenci podle zdroje
    - frekvenci podle dne
    """
    # Celková frekvence
    total = defaultdict(int)

    # Frekvence podle zdroje: {keyword: {source: count}}
    by_source = defaultdict(lambda: defaultdict(int))

    # Frekvence podle dne: {keyword: {date_str: count}}
    by_day = defaultdict(lambda: defaultdict(int))

    for record in records:
        day_str = record["date"].strftime("%Y-%m-%d")
        for kw in record["keywords"]:
            if kw in KEYWORDS:
                total[kw] += 1
                by_source[kw][record["source"]] += 1
                by_day[kw][day_str] += 1

    return total, by_source, by_day


# =============================================================================
# OUTPUT — TERMINÁL
# =============================================================================

def print_report(total, by_source, by_day, days):
    """Vypíše přehlednou tabulku do terminálu."""

    separator = "=" * 70
    print(f"\n{separator}")
    print(f"  KEYWORD FREQUENCY REPORT — posledních {days} dní")
    print(f"  Vygenerováno: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(separator)

    if not total:
        print("\n  Žádná data pro zobrazení.")
        return

    # Seřaď podle frekvence sestupně
    sorted_kws = sorted(total.items(), key=lambda x: x[1], reverse=True)

    print(f"\n{'KLÍČOVÉ SLOVO':<20} {'CELKEM':>7}  ZDROJE")
    print("-" * 70)

    for kw, count in sorted_kws:
        sources_str = ", ".join(
            f"{src}:{cnt}" for src, cnt in sorted(by_source[kw].items(), key=lambda x: x[1], reverse=True)
        )
        print(f"{kw:<20} {count:>7}  {sources_str}")

    print(separator)

    # Denní trend pro top 3 slova
    top3 = [kw for kw, _ in sorted_kws[:3]]
    if top3:
        print(f"\n  DENNÍ TREND — top 3 slova")
        print("-" * 70)

        # Získej všechny dny v datasetu
        all_days = sorted(set(
            day for kw in top3 for day in by_day[kw].keys()
        ))

        # Hlavička
        header = f"{'DATUM':<12}" + "".join(f"{kw:>18}" for kw in top3)
        print(header)
        print("-" * 70)

        for day in all_days:
            row = f"{day:<12}"
            for kw in top3:
                count = by_day[kw].get(day, 0)
                bar = "█" * min(count, 10)
                row += f"{count:>5} {bar:<13}"
            print(row)

    print(separator)


# =============================================================================
# OUTPUT — CSV
# =============================================================================

def save_csv(total, by_source, by_day, days, output_path):
    """Uloží výsledky do CSV souboru."""

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Sheet 1: Celková frekvence
        writer.writerow(["KEYWORD FREQUENCY REPORT"])
        writer.writerow([f"Období: posledních {days} dní"])
        writer.writerow([f"Vygenerováno: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])

        writer.writerow(["Klíčové slovo", "Celkem"] + list(RSS_SOURCES.keys()))
        for kw in sorted(total, key=lambda x: total[x], reverse=True):
            row = [kw, total[kw]]
            for src in RSS_SOURCES.keys():
                row.append(by_source[kw].get(src, 0))
            writer.writerow(row)

        writer.writerow([])

        # Sheet 2: Denní trend
        writer.writerow(["Denní trend"])
        all_days = sorted(set(day for kw in KEYWORDS for day in by_day[kw].keys()))
        writer.writerow(["Datum"] + KEYWORDS)
        for day in all_days:
            row = [day] + [by_day[kw].get(day, 0) for kw in KEYWORDS]
            writer.writerow(row)

    print(f"[INFO] CSV uloženo: {output_path}")


# =============================================================================
# SPUŠTĚNÍ
# =============================================================================

if __name__ == "__main__":
    import sys

    # Počet dní z argumentu nebo default
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print(f"[ERROR] Neplatný argument '{sys.argv[1]}' — použiji default {DEFAULT_DAYS} dní.")
            days = DEFAULT_DAYS
    else:
        days = DEFAULT_DAYS

    # Cesta k log souboru z druhého argumentu nebo default
    if len(sys.argv) > 2:
        log_file = sys.argv[2]
    else:
        log_file = LOG_FILE

    since_dt = datetime.now(timezone.utc) - timedelta(days=days)

    print("=" * 70)
    print("  Keyword Frequency Analyzer — OSINT Portfolio Skript 3")
    print("=" * 70)
    print(f"Časové okno: posledních {days} dní (od {since_dt.strftime('%Y-%m-%d')})")
    print(f"Klíčových slov: {len(KEYWORDS)}")
    print(f"Zdroje: log ({log_file}) + live RSS feedy")
    print("=" * 70)

    # 1. Historická data z logu
    log_records = parse_log_file(log_file, since_dt)

    # 2. Live data z RSS
    print(f"\n[INFO] Stahuji live RSS feedy...")
    live_records = fetch_live_feeds(since_dt)

    # 3. Sloučení a dedup podle titulku
    all_records = log_records + live_records
    seen_titles = set()
    unique_records = []
    for r in all_records:
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            unique_records.append(r)

    print(f"\n[INFO] Celkem unikátních záznamů: {len(unique_records)}")

    # 4. Analýza
    total, by_source, by_day = analyze(unique_records)

    # 5. Output
    print_report(total, by_source, by_day, days)
    save_csv(total, by_source, by_day, days, CSV_OUTPUT)
