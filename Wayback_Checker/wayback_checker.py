#!/usr/bin/env python3
"""
wayback_checker.py — Wayback Machine Checker
OSINT Portfolio | Skript 6a

Porovná aktuální verzi webu s nejnovější archivní verzí na Wayback Machine.
Výstup: terminál + CSV s rozdíly.

Použití:
  Jedna URL:    python wayback_checker.py -u https://example.com
  Seznam URL:   python wayback_checker.py -f urls.txt
"""

import argparse
import csv
import os
import sys
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup


# ─── Konfigurace ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "output"
REQUEST_DELAY = 2          # Pauza mezi požadavky (sekundy) — etiketa vůči API
REQUEST_TIMEOUT = 15       # Timeout pro HTTP požadavky (sekundy)

HEADERS = {
    "User-Agent": "OSINT-WaybackChecker/1.0 (research tool)"
}


# ─── Pomocné funkce ───────────────────────────────────────────────────────────

def ensure_output_dir():
    """Vytvoří složku output/ pokud neexistuje."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_output_filename():
    """Vygeneruje název výstupního souboru s timestampem."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUTPUT_DIR, f"wayback_checker_{ts}.csv")


def extract_text(html_content):
    """
    Vytáhne čistý text z HTML.
    BeautifulSoup odstraní tagy, skripty a styly — zůstane jen čitelný text.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Odstraň skripty a styly — ty nejsou součástí viditelného obsahu
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Získej text, normalizuj mezery
    text = soup.get_text(separator=" ")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = " ".join(line for line in lines if line)
    return cleaned


def fetch_url(url):
    """
    Stáhne obsah URL a vrátí text nebo None při chybě.
    Vrací tuple (html_text, status_code, error_message).
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        return response.text, response.status_code, None
    except requests.exceptions.Timeout:
        return None, None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "Chyba připojení"
    except requests.exceptions.RequestException as e:
        return None, None, str(e)


def get_wayback_url(original_url):
    """
    Dotáže se Wayback Machine CDX API na nejnovější archivní snímek dané URL.
    CDX API je zdarma, nevyžaduje klíč.

    Vrací tuple (wayback_url, archive_date, error_message).
    """
    # CDX API endpoint — vrací metadata o archivních snímcích
    cdx_api = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": original_url,
        "output": "json",
        "limit": 1,            # Chceme jen jeden (nejnovější) záznam
        "fl": "timestamp,original,statuscode",  # Pole, která chceme
        "filter": "statuscode:200",  # Jen úspěšné snímky
        "from": "",
        "to": "",
    }

    try:
        response = requests.get(
            cdx_api, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
        data = response.json()

        # CDX API vrací seznam — první řádek jsou hlavičky, druhý+ jsou data
        if len(data) < 2:
            return None, None, "Žádný archivní snímek nenalezen"

        # data[0] = ['timestamp', 'original', 'statuscode']
        # data[1] = ['20230101120000', 'http://...', '200']
        _, record = data[0], data[1]
        timestamp = record[0]   # Formát: YYYYMMDDHHMMSS

        # Sestaví URL archivní verze ve formátu, který Wayback Machine akceptuje
        wayback_url = f"https://web.archive.org/web/{timestamp}/{original_url}"

        # Zformátuj datum pro výstup: YYYYMMDDHHMMSS → YYYY-MM-DD HH:MM:SS
        archive_date = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:14]}"

        return wayback_url, archive_date, None

    except Exception as e:
        return None, None, f"CDX API chyba: {str(e)}"


def compare_texts(text_archive, text_current):
    """
    Porovná dva texty na úrovni slov a najde přidaný/odebraný obsah.

    Vrací dict s klíči:
      - added_words: slova přidaná v aktuální verzi (nebyla v archivu)
      - removed_words: slova odebraná z aktuální verze (byla v archivu)
      - similarity_pct: procentuální podobnost (0–100)
      - summary: krátký lidsky čitelný popis rozdílu
    """
    # Rozlož text na množiny slov (set = každé slovo jen jednou)
    words_archive = set(text_archive.lower().split())
    words_current = set(text_current.lower().split())

    added = words_current - words_archive      # V aktuální, ale ne v archivu
    removed = words_archive - words_current    # V archivu, ale ne v aktuální

    # Jaccardova podobnost: průnik / sjednocení (0 = úplně jiné, 1 = identické)
    union = words_archive | words_current
    if union:
        similarity = (len(words_archive & words_current) / len(union)) * 100
    else:
        similarity = 100.0

    # Stručný popis pro terminálový výpis
    if similarity >= 95:
        summary = "Bez výrazných změn"
    elif similarity >= 75:
        summary = "Mírné změny"
    elif similarity >= 50:
        summary = "Výrazné změny"
    else:
        summary = "Zásadně odlišný obsah"

    # Pro CSV: prvních 20 přidaných/odebraných slov jako náhled
    added_preview = ", ".join(sorted(added)[:20]) if added else "—"
    removed_preview = ", ".join(sorted(removed)[:20]) if removed else "—"

    return {
        "added_words": added_preview,
        "removed_words": removed_preview,
        "similarity_pct": round(similarity, 1),
        "summary": summary,
    }


def check_url(url):
    """
    Zpracuje jednu URL:
      1. Najde nejnovější archivní snímek na Wayback Machine
      2. Stáhne archivní verzi
      3. Stáhne aktuální verzi
      4. Porovná texty
      5. Vrátí dict s výsledky pro terminál i CSV
    """
    result = {
        "url": url,
        "archive_url": "",
        "archive_date": "",
        "similarity_pct": "",
        "summary": "",
        "added_words_preview": "",
        "removed_words_preview": "",
        "error": "",
    }

    print(f"\n  Hledám archivní snímek...", end=" ", flush=True)
    wayback_url, archive_date, err = get_wayback_url(url)

    if err:
        result["error"] = err
        print(f"CHYBA: {err}")
        return result

    result["archive_url"] = wayback_url
    result["archive_date"] = archive_date
    print(f"nalezen ({archive_date})")

    # Stáhni archivní verzi
    print(f"  Stahuji archivní verzi...", end=" ", flush=True)
    time.sleep(REQUEST_DELAY)
    html_archive, status_archive, err = fetch_url(wayback_url)

    if err or not html_archive:
        result["error"] = f"Archiv nedostupný: {err}"
        print(f"CHYBA")
        return result
    print(f"OK ({status_archive})")

    # Stáhni aktuální verzi
    print(f"  Stahuji aktuální verzi...", end=" ", flush=True)
    time.sleep(REQUEST_DELAY)
    html_current, status_current, err = fetch_url(url)

    if err or not html_current:
        result["error"] = f"Aktuální web nedostupný: {err}"
        print(f"CHYBA")
        return result
    print(f"OK ({status_current})")

    # Extrahuj text a porovnej
    print(f"  Porovnávám obsah...", end=" ", flush=True)
    text_archive = extract_text(html_archive)
    text_current = extract_text(html_current)
    diff = compare_texts(text_archive, text_current)

    result["similarity_pct"] = diff["similarity_pct"]
    result["summary"] = diff["summary"]
    result["added_words_preview"] = diff["added_words"]
    result["removed_words_preview"] = diff["removed_words"]

    print(f"hotovo ({diff['similarity_pct']}% shoda — {diff['summary']})")

    return result


def print_result(result):
    """
    Vytiskne výsledek jedné URL do terminálu v přehledném formátu.
    """
    print(f"\n{'─'*60}")
    print(f"  URL:          {result['url']}")

    if result["error"]:
        print(f"  CHYBA:        {result['error']}")
        return

    print(f"  Archiv z:     {result['archive_date']}")
    print(f"  Archivní URL: {result['archive_url']}")
    print(f"  Podobnost:    {result['similarity_pct']}%  →  {result['summary']}")

    if result["added_words_preview"] != "—":
        print(f"  Přidáno:      {result['added_words_preview']}")
    if result["removed_words_preview"] != "—":
        print(f"  Odebráno:     {result['removed_words_preview']}")


def save_to_csv(results, filepath):
    """
    Uloží všechny výsledky do CSV souboru.
    """
    fieldnames = [
        "url",
        "archive_date",
        "archive_url",
        "similarity_pct",
        "summary",
        "added_words_preview",
        "removed_words_preview",
        "error",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✓ CSV uloženo: {filepath}")


# ─── Hlavní funkce ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Wayback Machine Checker — porovná archivní a aktuální verzi webu.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  python wayback_checker.py -u https://ria.ru/
  python wayback_checker.py -f urls.txt
        """,
    )

    # Přepínač: buď jedna URL (-u) nebo soubor se seznamem (-f)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-u", "--url",
        help="Jedna URL ke kontrole (např. https://example.com)"
    )
    group.add_argument(
        "-f", "--file",
        help="Textový soubor s URL (jedna URL na řádek)"
    )

    args = parser.parse_args()

    # Sestavení seznamu URL
    urls = []
    if args.url:
        urls = [args.url.strip()]
    elif args.file:
        if not os.path.exists(args.file):
            print(f"CHYBA: Soubor '{args.file}' nenalezen.")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            # Přečti řádky, odstraň prázdné a komentáře (začínající #)
            urls = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
        if not urls:
            print(f"CHYBA: Soubor '{args.file}' neobsahuje žádné URL.")
            sys.exit(1)

    # Hlavičky výstupu
    print("=" * 60)
    print("  WAYBACK MACHINE CHECKER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Počet URL: {len(urls)}")
    print("=" * 60)

    ensure_output_dir()
    output_file = generate_output_filename()
    results = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] {url}")
        result = check_url(url)
        print_result(result)
        results.append(result)

        # Pauza mezi URL (vyjma poslední) — nezdržuj zbytečně
        if i < len(urls):
            time.sleep(REQUEST_DELAY)

    # Souhrn
    print(f"\n{'='*60}")
    successful = [r for r in results if not r["error"]]
    errors = [r for r in results if r["error"]]
    print(f"  Hotovo: {len(successful)} OK, {len(errors)} chyb")

    if successful:
        # Průměrná podobnost jen pro úspěšné výsledky
        avg_sim = sum(r["similarity_pct"] for r in successful) / len(successful)
        print(f"  Průměrná podobnost: {avg_sim:.1f}%")

        # Upozornění na podezřelé URL (podobnost pod 50 %)
        suspicious = [r for r in successful if r["similarity_pct"] < 50]
        if suspicious:
            print(f"\n  ⚠ Podezřelé URL (< 50% shoda):")
            for r in suspicious:
                print(f"    {r['url']}  →  {r['similarity_pct']}%")

    # Ulož CSV
    save_to_csv(results, output_file)


if __name__ == "__main__":
    main()
