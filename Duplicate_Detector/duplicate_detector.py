#!/usr/bin/env python3
"""
duplicate_detector.py — Duplicate Content Detector

Detekuje stejný nebo velmi podobný text na více různých doménách.
Indikátor koordinované IO kampaně (astroturfing).

Použití:
  Text ze souboru:  python duplicate_detector.py -t input/clanek.txt -d input/domeny.txt
  URL článku:       python duplicate_detector.py -u https://example.com/article -d input/domeny.txt
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
REQUEST_DELAY = 2          # Pauza mezi požadavky (sekundy)
REQUEST_TIMEOUT = 15       # Timeout pro HTTP požadavky
SIMILARITY_THRESHOLD = 40  # Minimální % podobnosti pro zahrnutí do výsledků

HEADERS = {
    "User-Agent": "OSINT-DuplicateDetector/1.0 (research tool)"
}


# ─── Pomocné funkce ───────────────────────────────────────────────────────────

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_output_filename():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUTPUT_DIR, f"duplicate_detector_{ts}.csv")


def extract_text(html_content):
    """
    Vytáhne čistý text z HTML.
    Odstraní skripty, styly a navigační elementy.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Odstraň nepotřebné elementy
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    lines = [line.strip() for line in text.splitlines()]
    cleaned = " ".join(line for line in lines if line)
    return cleaned


def fetch_url(url):
    """
    Stáhne obsah URL.
    Vrací tuple (html_text, final_url, status_code, error_message).
    final_url zachytí případný redirect.
    """
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        return response.text, response.url, response.status_code, None
    except requests.exceptions.Timeout:
        return None, url, None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, url, None, "Chyba připojení"
    except requests.exceptions.RequestException as e:
        return None, url, None, str(e)


def normalize_domain_entry(entry):
    """
    Normalizuje jeden záznam ze souboru domén.

    Logika:
      - Začíná 'http://' nebo 'https://' → vrátí jako je (konkrétní URL)
      - Jinak → přidá 'https://' (holá doména nebo doména s cestou)

    Příklady:
      'ria.ru'                    → 'https://ria.ru'
      'tass.ru/world'             → 'https://tass.ru/world'
      'https://rt.com/news/'      → 'https://rt.com/news/'
    """
    entry = entry.strip()
    if entry.startswith("http://") or entry.startswith("https://"):
        return entry
    return "https://" + entry


def load_domains(filepath):
    """
    Načte seznam domén/URL ze souboru.
    Přeskočí prázdné řádky a komentáře (začínající #).
    Vrací seznam normalizovaných URL.
    """
    if not os.path.exists(filepath):
        print(f"CHYBA: Soubor '{filepath}' nenalezen.")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        entries = [
            normalize_domain_entry(line)
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    if not entries:
        print(f"CHYBA: Soubor '{filepath}' neobsahuje žádné záznamy.")
        sys.exit(1)

    return entries


def load_text_from_file(filepath):
    """Načte zdrojový text ze souboru."""
    if not os.path.exists(filepath):
        print(f"CHYBA: Soubor '{filepath}' nenalezen.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read().strip()


def compute_similarity(text_a, text_b):
    """
    Vypočítá Jaccardovu podobnost mezi dvěma texty na úrovni slov.

    Jaccardova podobnost = průnik / sjednocení
      - 100% = identické texty
      - 0%   = zcela odlišné texty

    Používáme množiny slov (set) — každé slovo se počítá jen jednou.
    Hledáme překryv témat/obsahu, ne přesné kopie.
    """
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())

    union = words_a | words_b
    if not union:
        return 0.0

    intersection = words_a & words_b
    return round((len(intersection) / len(union)) * 100, 1)


def classify_similarity(pct):
    """
    Přiřadí slovní hodnocení k procentuální podobnosti.
    Stupně jsou nastaveny pro detekci astroturfingu — nízký práh je záměrný.
    """
    if pct >= 80:
        return "Velmi vysoká — pravděpodobná kopie"
    elif pct >= 60:
        return "Vysoká — silná obsahová shoda"
    elif pct >= 40:
        return "Střední — sdílená témata/framing"
    else:
        return "Nízká"


def get_domain_from_url(url):
    """Vytáhne doménu z URL pro přehledný výstup."""
    try:
        # Odstraní protokol a cestu, ponechá jen doménu
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        return domain
    except Exception:
        return url


# ─── Hlavní logika ────────────────────────────────────────────────────────────

def check_domain(source_text, target_url, index, total):
    """
    Zkontroluje jednu doménu/URL vůči zdrojovému textu.
    Vrací dict s výsledky.
    """
    domain = get_domain_from_url(target_url)

    result = {
        "domain": domain,
        "url_checked": target_url,
        "final_url": "",
        "similarity_pct": "",
        "classification": "",
        "error": "",
    }

    print(f"  [{index}/{total}] {domain}", end=" ... ", flush=True)

    html, final_url, status, err = fetch_url(target_url)

    if err or not html:
        result["error"] = err or "Prázdná odpověď"
        print(f"CHYBA: {result['error']}")
        return result

    result["final_url"] = final_url

    target_text = extract_text(html)

    if not target_text:
        result["error"] = "Nepodařilo se extrahovat text"
        print("CHYBA: prázdný text")
        return result

    similarity = compute_similarity(source_text, target_text)
    result["similarity_pct"] = similarity
    result["classification"] = classify_similarity(similarity)

    # Vizuální indikátor v terminálu
    if similarity >= 80:
        indicator = "🔴"
    elif similarity >= 60:
        indicator = "🟠"
    elif similarity >= 40:
        indicator = "🟡"
    else:
        indicator = "⚪"

    print(f"{indicator} {similarity}%  —  {result['classification']}")
    return result


def print_summary(results, source_label):
    """Vytiskne přehledný souhrn do terminálu."""
    successful = [r for r in results if not r["error"] and r["similarity_pct"] != ""]
    errors = [r for r in results if r["error"]]

    print(f"\n{'='*60}")
    print(f"  SOUHRN")
    print(f"{'='*60}")
    print(f"  Zdrojový text: {source_label}")
    print(f"  Zkontrolováno: {len(successful)} domén, {len(errors)} chyb")

    if not successful:
        print("  Žádné výsledky ke zobrazení.")
        return

    # Seřaď sestupně podle podobnosti
    successful_sorted = sorted(successful, key=lambda r: r["similarity_pct"], reverse=True)

    # Zobraz jen výsledky nad prahem
    above_threshold = [r for r in successful_sorted if r["similarity_pct"] >= SIMILARITY_THRESHOLD]

    if above_threshold:
        print(f"\n  Shody nad {SIMILARITY_THRESHOLD}% (seřazeno sestupně):\n")
        for r in above_threshold:
            print(f"  {r['similarity_pct']:5.1f}%  {r['domain']}")
            print(f"         {r['classification']}")
    else:
        print(f"\n  Žádná doména nepřekročila práh {SIMILARITY_THRESHOLD}%.")

    if errors:
        print(f"\n  Nedostupné domény:")
        for r in errors:
            print(f"    {r['domain']}  —  {r['error']}")


def save_to_csv(results, source_label, filepath):
    """Uloží výsledky do CSV."""
    fieldnames = [
        "domain",
        "url_checked",
        "final_url",
        "similarity_pct",
        "classification",
        "error",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        # Metadata jako komentář na začátku CSV
        f.write(f"# duplicate_detector.py — výstup\n")
        f.write(f"# Zdrojový text: {source_label}\n")
        f.write(f"# Datum: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Práh podobnosti: {SIMILARITY_THRESHOLD}%\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✓ CSV uloženo: {filepath}")


# ─── Hlavní funkce ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Duplicate Content Detector — detekuje sdílený obsah napříč doménami.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  python duplicate_detector.py -t input/clanek.txt -d input/domeny.txt
  python duplicate_detector.py -u https://ria.ru/world/20240101/article.html -d input/domeny.txt

Formát souboru domén (input/domeny.txt):
  # Komentáře jsou ignorovány
  ria.ru
  tass.ru/world
  https://rt.com/news/
  sputniknews.com
        """,
    )

    # Přepínač zdroje: text ze souboru nebo URL
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "-t", "--text",
        help="Textový soubor se zdrojovým článkem (např. input/clanek.txt)"
    )
    source_group.add_argument(
        "-u", "--url",
        help="URL zdrojového článku (skript stáhne text sám)"
    )

    parser.add_argument(
        "-d", "--domains",
        required=True,
        help="Soubor se seznamem domén/URL ke kontrole (např. input/domeny.txt)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=SIMILARITY_THRESHOLD,
        help=f"Minimální %% podobnosti pro výsledky (výchozí: {SIMILARITY_THRESHOLD})"
    )

    args = parser.parse_args()

    # Načti nebo stáhni zdrojový text
    if args.text:
        print(f"Načítám zdrojový text ze souboru: {args.text}")
        source_text = load_text_from_file(args.text)
        source_label = args.text
    else:
        print(f"Stahuji zdrojový text z URL: {args.url}")
        html, final_url, status, err = fetch_url(args.url)
        if err or not html:
            print(f"CHYBA: Nepodařilo se stáhnout zdrojovou URL: {err}")
            sys.exit(1)
        source_text = extract_text(html)
        source_label = args.url
        print(f"  OK ({status}) — extrahováno {len(source_text.split())} slov")

    if not source_text:
        print("CHYBA: Zdrojový text je prázdný.")
        sys.exit(1)

    # Načti seznam domén
    domains = load_domains(args.domains)

    # Hlavičky
    print("\n" + "=" * 60)
    print("  DUPLICATE CONTENT DETECTOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Zdrojový text: {len(source_text.split())} slov")
    print(f"  Domén ke kontrole: {len(domains)}")
    print(f"  Práh podobnosti: {args.threshold}%")
    print("=" * 60)
    print()

    ensure_output_dir()
    output_file = generate_output_filename()
    results = []

    for i, url in enumerate(domains, 1):
        result = check_domain(source_text, url, i, len(domains))
        results.append(result)

        # Pauza mezi požadavky (vyjma poslední)
        if i < len(domains):
            time.sleep(REQUEST_DELAY)

    # Souhrn a uložení
    print_summary(results, source_label)
    save_to_csv(results, source_label, output_file)


if __name__ == "__main__":
    main()
