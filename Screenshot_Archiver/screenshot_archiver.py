#!/usr/bin/env python3
"""
Zachytí full-page screenshot webu včetně URL a timestampu.
Výstup: PNG screenshot + JSON a CSV metadata soubory.

Použití:
  python screenshot_archiver.py -u https://example.com
  python screenshot_archiver.py -f urls.txt
  python screenshot_archiver.py -u https://example.com -o /cesta/k/výstupu
"""

import os
import sys
import csv
import json
import argparse
from datetime import datetime
from urllib.parse import urlparse

# Playwright se importuje takhle — sync_playwright je synchronní verze
# (jednodušší než async, vhodná pro skripty)
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ─────────────────────────────────────────────
# SEKCE 1: Pomocné funkce
# ─────────────────────────────────────────────

def sanitize_domain(url):
    """
    Z URL vytáhne doménu a upraví ji pro použití v názvu souboru.
    Příklad: https://vk.com/wall-123456 → vk_com
    """
    parsed = urlparse(url)
    domain = parsed.netloc  # např. "vk.com" nebo "www.t.me"
    domain = domain.replace("www.", "")  # odstraní www.
    domain = domain.replace(".", "_")    # tečky nahradí podtržítkem
    return domain


def make_filename(url, timestamp_str):
    """
    Sestaví název souboru z domény a timestampu.
    Příklad: vk_com_20250508_143022
    """
    domain = sanitize_domain(url)
    return f"{domain}_{timestamp_str}"


def load_urls_from_file(filepath):
    """
    Načte seznam URL z textového souboru.
    Každá URL musí být na samostatném řádku.
    Prázdné řádky a řádky začínající # jsou ignorovány.
    """
    if not os.path.isfile(filepath):
        print(f"[CHYBA] Soubor nenalezen: {filepath}")
        sys.exit(1)

    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    if not urls:
        print(f"[CHYBA] Soubor neobsahuje žádné URL: {filepath}")
        sys.exit(1)

    return urls


# ─────────────────────────────────────────────
# SEKCE 2: Screenshot funkce
# ─────────────────────────────────────────────

def take_screenshot(page, url, output_dir, timestamp_str):
    """
    Otevře URL v prohlížeči a zachytí full-page screenshot.
    Vrátí slovník s výsledkem (úspěch nebo chyba).
    """
    filename_base = make_filename(url, timestamp_str)
    screenshot_filename = f"{filename_base}.png"
    screenshot_path = os.path.join(output_dir, screenshot_filename)

    result = {
        "url": url,
        "timestamp": timestamp_str,
        "screenshot_soubor": "",
        "titulek_stranky": "",
        "http_status": "",
        "poznamka": ""
    }

    try:
        print(f"  [→] Načítám: {url}")

        # Otevře stránku, čeká max 30 sekund na načtení
        # "networkidle" znamená: počkej dokud síťový provoz neutichne
        response = page.goto(url, timeout=30000, wait_until="networkidle")

        # Uloží HTTP status kód (200 = OK, 404 = nenalezeno atd.)
        if response:
            result["http_status"] = response.status

        # Uloží titulek stránky
        result["titulek_stranky"] = page.title()

        # Zachytí full-page screenshot
        # full_page=True scrolluje stránku a zachytí vše, nejen viditelnou část
        page.screenshot(path=screenshot_path, full_page=True)

        result["screenshot_soubor"] = screenshot_filename
        result["poznamka"] = "ok"

        print(f"  [✓] Screenshot uložen: {screenshot_filename}")
        print(f"      Titulek: {result['titulek_stranky']}")
        print(f"      HTTP status: {result['http_status']}")

    except PlaywrightTimeoutError:
        result["poznamka"] = "chyba: timeout (stránka se nenačetla do 30s)"
        print(f"  [✗] Timeout: {url}")

    except Exception as e:
        result["poznamka"] = f"chyba: {str(e)}"
        print(f"  [✗] Chyba: {url} — {str(e)}")

    return result


# ─────────────────────────────────────────────
# SEKCE 3: Zpracování seznamu URL
# ─────────────────────────────────────────────

def process_urls(urls, output_dir):
    """
    Projde seznam URL, pro každou zachytí screenshot.
    Vrátí seznam výsledků.
    """
    results = []

    # sync_playwright() spustí headless Chromium prohlížeč
    with sync_playwright() as p:
        # Spustí prohlížeč — headless=True znamená bez okna (na pozadí)
        browser = p.chromium.launch(headless=True)

        # Nová stránka v prohlížeči s rozlišením 1280x900
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Nastaví User-Agent aby skript vypadal jako běžný prohlížeč
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] {url}")

            # Každá URL dostane svůj vlastní timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            result = take_screenshot(page, url, output_dir, timestamp_str)
            results.append(result)

        browser.close()

    return results


# ─────────────────────────────────────────────
# SEKCE 4: Uložení metadat (JSON + CSV)
# ─────────────────────────────────────────────

def save_metadata(results, output_dir):
    """
    Uloží metadata o všech screenshotech do JSON a CSV.
    Oba soubory mají timestamp v názvu.
    """
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── JSON ──
    json_filename = f"screenshots_{timestamp_str}.json"
    json_path = os.path.join(output_dir, json_filename)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ── CSV ──
    csv_filename = f"screenshots_{timestamp_str}.csv"
    csv_path = os.path.join(output_dir, csv_filename)

    fieldnames = ["url", "timestamp", "screenshot_soubor",
                  "titulek_stranky", "http_status", "poznamka"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    return json_path, csv_path


# ─────────────────────────────────────────────
# SEKCE 5: Hlavní funkce
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OSINT Skript 4b — Screenshot Archiver"
    )

    # Skupina: buď -u (jedna URL) nebo -f (soubor se seznamem), ne obojí
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-u", "--url",
        help="Jedna URL (např. -u https://vk.com/wall-123)"
    )
    group.add_argument(
        "-f", "--file",
        help="Textový soubor se seznamem URL (jedna na řádek)"
    )

    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Složka pro uložení screenshotů a metadat (výchozí: aktuální složka)"
    )

    args = parser.parse_args()

    # Sestavení seznamu URL
    if args.url:
        urls = [args.url]
    else:
        urls = load_urls_from_file(args.file)

    # Vytvoření výstupní složky pokud neexistuje
    os.makedirs(args.output, exist_ok=True)

    print(f"\n[INFO] Počet URL ke zpracování: {len(urls)}")
    print(f"[INFO] Výstupní složka: {args.output}")
    print(f"[INFO] Spouštím prohlížeč...\n")

    # Zpracování
    results = process_urls(urls, args.output)

    # Uložení metadat
    json_path, csv_path = save_metadata(results, args.output)

    # Shrnutí
    uspesne = sum(1 for r in results if r["poznamka"] == "ok")
    chyby = len(results) - uspesne

    print(f"\n{'═' * 50}")
    print(f"[HOTOVO] Zpracováno: {len(results)} URL")
    print(f"         Úspěšně:    {uspesne}")
    print(f"         Chyby:      {chyby}")
    print(f"[JSON]   Uloženo: {json_path}")
    print(f"[CSV]    Uloženo: {csv_path}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
