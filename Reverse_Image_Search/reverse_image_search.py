#!/usr/bin/env python3
"""
reverse_image_search.py — Reverse Image Search Automator

Zadáš fotografii (soubor nebo URL), skript otevře záložky v prohlížeči
pro Yandex Images, TinEye a Google Images. Ty zadáš nálezy ručně,
skript uloží výsledky do CSV.

Použití:
  Lokální soubor:  python3 reverse_image_search.py -f input/foto.jpg
  URL obrázku:     python3 reverse_image_search.py -u https://example.com/foto.jpg
"""

import argparse
import csv
import os
import sys
import time
import webbrowser
import requests
from datetime import datetime
from urllib.parse import quote


# ─── Konfigurace ─────────────────────────────────────────────────────────────

OUTPUT_DIR = "output"
REQUEST_TIMEOUT = 15

HEADERS = {
    "User-Agent": "OSINT-ReverseImageSearch/1.0 (research tool)"
}

# Dočasné úložiště pro nahrání lokálního souboru — imgbb.com (zdarma, bez registrace)
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"

# Prodleva mezi otevřením záložek (sekundy) — aby se prohlížeč stihl načíst
TAB_DELAY = 1.5


# ─── Pomocné funkce ───────────────────────────────────────────────────────────

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_output_filename():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUTPUT_DIR, f"reverse_image_search_{ts}.csv")


def validate_image_file(filepath):
    """Zkontroluje, že soubor existuje a má podporovaný formát."""
    if not os.path.exists(filepath):
        print(f"CHYBA: Soubor '{filepath}' nenalezen.")
        sys.exit(1)

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        print(f"CHYBA: Nepodporovaný formát '{ext}'. Podporované: jpg, jpeg, png, webp, gif")
        sys.exit(1)


def upload_image_to_imgbb(filepath):
    """
    Nahraje lokální obrázek na imgbb.com a vrátí veřejnou URL.

    imgbb nabízí anonymní nahrávání bez API klíče přes jejich web endpoint.
    Vrací tuple (public_url, error_message).

    POZNÁMKA: imgbb bez API klíče má omezení — pokud nahrávání selže,
    skript nabídne ruční alternativu.
    """
    import base64

    try:
        with open(filepath, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # imgbb vyžaduje API klíč pro přímé API volání
        # Místo toho použijeme alternativní přístup přes tmpfiles.org
        # který nevyžaduje klíč
        with open(filepath, "rb") as f:
            response = requests.post(
                "https://tmpfiles.org/api/v1/upload",
                files={"file": (os.path.basename(filepath), f)},
                timeout=REQUEST_TIMEOUT,
            )

        if response.status_code == 200:
            data = response.json()
            # tmpfiles.org vrací URL ve formátu https://tmpfiles.org/XXXXX/soubor.jpg
            # Pro přímý přístup k souboru potřebujeme /dl/ prefix
            url = data.get("data", {}).get("url", "")
            if url:
                # Převeď na přímý odkaz
                direct_url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                return direct_url, None

        return None, f"Nahrávání selhalo (status {response.status_code})"

    except Exception as e:
        return None, str(e)


def build_search_urls(image_url):
    """
    Sestaví URL pro vyhledávání obrázku na třech platformách.

    Každá platforma má jiný formát URL pro reverse image search:
    - Yandex: cbir/search?url=...
    - TinEye: tineye.com/search?url=...
    - Google: images.google.com?tbs=simg:...
    """
    encoded_url = quote(image_url, safe="")

    return {
        "Yandex Images": f"https://yandex.com/images/search?url={encoded_url}&rpt=imageview",
        "TinEye":        f"https://tineye.com/search?url={encoded_url}",
        "Google Images": f"https://images.google.com/searchbyimage?image_url={encoded_url}",
    }


def open_search_tabs(search_urls):
    """
    Otevře záložky v prohlížeči pro každou vyhledávací platformu.
    Mezi záložkami je krátká pauza, aby se prohlížeč stihl načíst.
    """
    print("\n  Otevírám záložky v prohlížeči...")
    for name, url in search_urls.items():
        print(f"    → {name}")
        webbrowser.open(url)
        time.sleep(TAB_DELAY)


def collect_results_interactively(image_label):
    """
    Interaktivní zadávání nálezů uživatelem.

    Skript čeká, uživatel prochází záložky v prohlížeči a zadává nálezy.
    Každý nález = jedna řádka v CSV.

    Vrací seznam dict s nálezy.
    """
    results = []

    print("\n" + "─" * 60)
    print("  Prohledej záložky v prohlížeči a zadej nálezy níže.")
    print("  Prázdný řádek = konec zadávání.")
    print("─" * 60)

    platforms = ["Yandex Images", "TinEye", "Google Images"]

    for platform in platforms:
        print(f"\n  [{platform}]")
        print("  Formát: URL výskytu (nebo Enter pro přeskočení)")
        print("  Více nálezů: zadej každý na nový řádek, prázdný řádek = další platforma\n")

        entry_count = 0
        while True:
            try:
                url_input = input("    URL: ").strip()
            except EOFError:
                break

            if not url_input:
                # Prázdný řádek = přechod na další platformu
                break

            # Volitelné doplňující informace
            try:
                date_input = input("    Datum výskytu (nebo Enter pro přeskočení): ").strip()
                note_input = input("    Poznámka (nebo Enter pro přeskočení): ").strip()
            except EOFError:
                date_input = ""
                note_input = ""

            results.append({
                "image_source": image_label,
                "platform": platform,
                "found_url": url_input,
                "found_date": date_input if date_input else "—",
                "note": note_input if note_input else "—",
                "search_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            entry_count += 1
            print(f"    ✓ Nález #{entry_count} uložen\n")

        if entry_count == 0:
            print(f"    (žádné nálezy pro {platform})")

    return results


def print_summary(results, image_label):
    """Vytiskne souhrn nálezů do terminálu."""
    print(f"\n{'='*60}")
    print(f"  SOUHRN")
    print(f"{'='*60}")
    print(f"  Prohledaný obrázek: {image_label}")
    print(f"  Celkem nálezů: {len(results)}")

    if results:
        print()
        # Seskup nálezy podle platformy
        by_platform = {}
        for r in results:
            platform = r["platform"]
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(r)

        for platform, entries in by_platform.items():
            print(f"  {platform}: {len(entries)} nález/ů")
            for e in entries:
                print(f"    • {e['found_url']}")
                if e["found_date"] != "—":
                    print(f"      Datum: {e['found_date']}")
                if e["note"] != "—":
                    print(f"      Poznámka: {e['note']}")


def save_to_csv(results, image_label, filepath):
    """Uloží nálezy do CSV."""
    fieldnames = [
        "image_source",
        "platform",
        "found_url",
        "found_date",
        "note",
        "search_timestamp",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(f"# reverse_image_search.py — výstup\n")
        f.write(f"# Prohledaný obrázek: {image_label}\n")
        f.write(f"# Datum: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        if results:
            writer.writerows(results)
        else:
            # Prázdný CSV s hlavičkou — pro konzistenci s ostatními skripty
            pass

    print(f"\n✓ CSV uloženo: {filepath}")


# ─── Hlavní funkce ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Reverse Image Search Automator — otevře záložky pro Yandex, TinEye, Google.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  python3 reverse_image_search.py -f input/foto.jpg
  python3 reverse_image_search.py -u https://example.com/foto.jpg
        """,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "-f", "--file",
        help="Lokální soubor obrázku (jpg, jpeg, png, webp, gif)"
    )
    source_group.add_argument(
        "-u", "--url",
        help="URL obrázku na webu"
    )

    args = parser.parse_args()

    # Hlavičky
    print("=" * 60)
    print("  REVERSE IMAGE SEARCH AUTOMATOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Získej URL obrázku pro vyhledávání
    if args.url:
        image_url = args.url
        image_label = args.url
        print(f"\n  Zdroj: URL")
        print(f"  {image_url}")

    else:
        # Lokální soubor — nutné nahrát na dočasné úložiště
        validate_image_file(args.file)
        image_label = args.file
        filename = os.path.basename(args.file)

        print(f"\n  Zdroj: lokální soubor")
        print(f"  {args.file}")
        print(f"\n  Nahrávám na dočasné úložiště...", end=" ", flush=True)

        image_url, err = upload_image_to_imgbb(args.file)

        if err or not image_url:
            print(f"CHYBA: {err}")
            print()
            print("  Nahrávání selhalo. Alternativa:")
            print("  1. Nahraj obrázek ručně na https://postimages.org")
            print("  2. Zkopíruj přímý odkaz na obrázek")
            print("  3. Spusť skript znovu s přepínačem -u a tou URL")
            sys.exit(1)

        print(f"OK")
        print(f"  Dočasná URL: {image_url}")
        print(f"  (Soubor bude dostupný cca 60 minut)")

    # Sestavení a otevření vyhledávacích URL
    search_urls = build_search_urls(image_url)

    print(f"\n  Vyhledávací platformy:")
    for name, url in search_urls.items():
        print(f"    {name}: {url[:80]}...")

    ensure_output_dir()
    output_file = generate_output_filename()

    # Otevři záložky
    open_search_tabs(search_urls)

    print("\n  Záložky otevřeny. Prohledej výsledky a vrať se sem.")

    # Interaktivní zadávání nálezů
    results = collect_results_interactively(image_label)

    # Souhrn a uložení
    print_summary(results, image_label)
    save_to_csv(results, image_label, output_file)


if __name__ == "__main__":
    main()
