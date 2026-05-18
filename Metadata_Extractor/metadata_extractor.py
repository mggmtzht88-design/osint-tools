#!/usr/bin/env python3
"""
Metadata Extractor
Extrahuje EXIF metadata z fotografií (GPS, čas, zařízení).
Výstup: terminál + CSV s timestampem v názvu souboru.

Použití:
  python script_4a_metadata_extractor.py -f foto.jpg          # jedna fotografie
  python script_4a_metadata_extractor.py -d /cesta/ke/složce  # celá složka
"""

import os
import sys
import csv
import argparse
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


# ─────────────────────────────────────────────
# SEKCE 1: Převod GPS souřadnic z EXIF formátu
# ─────────────────────────────────────────────

def convert_gps_coordinate(value):
    """
    EXIF ukládá GPS jako trojici (stupně, minuty, sekundy).
    Tato funkce je převede na desetinné číslo.
    Příklad: (50, 12, 30.5) → 50.208472
    """
    degrees = float(value[0])
    minutes = float(value[1])
    seconds = float(value[2])
    return degrees + (minutes / 60.0) + (seconds / 3600.0)


def extract_gps(gps_data):
    """
    Zpracuje GPS blok z EXIF dat.
    Vrátí slovník s lat, lon, Google Maps odkazem — nebo None.
    """
    if not gps_data:
        return None

    # Přeloží číselné klíče na čitelné názvy (GPSLatitude, GPSLongitude atd.)
    decoded = {}
    for key, value in gps_data.items():
        tag_name = GPSTAGS.get(key, key)
        decoded[tag_name] = value

    # Zkontroluje, jestli máme všechna potřebná pole
    required = ["GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"]
    if not all(k in decoded for k in required):
        return None

    lat = convert_gps_coordinate(decoded["GPSLatitude"])
    lon = convert_gps_coordinate(decoded["GPSLongitude"])

    # Světové strany: S/N = kladné, J/S = záporné; E/V = kladné, Z/W = záporné
    if decoded["GPSLatitudeRef"] in ("S", "s"):
        lat = -lat
    if decoded["GPSLongitudeRef"] in ("W", "w"):
        lon = -lon

    maps_url = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"

    return {
        "gps_lat": round(lat, 6),
        "gps_lon": round(lon, 6),
        "gps_maps_url": maps_url
    }


# ─────────────────────────────────────────────
# SEKCE 2: Extrakce všech EXIF dat z fotografie
# ─────────────────────────────────────────────

def extract_metadata(image_path):
    """
    Otevře fotografii a vytáhne z ní EXIF metadata.
    Vrátí slovník s výsledky nebo chybovou zprávu.
    """
    result = {
        "soubor": os.path.basename(image_path),
        "cesta": image_path,
        "datum_cas": "",
        "vyrobce": "",
        "model_zarizeni": "",
        "software": "",
        "gps_lat": "",
        "gps_lon": "",
        "gps_maps_url": "",
        "poznamka": ""
    }

    try:
        img = Image.open(image_path)

        # Pillow vrátí None pokud obrázek nemá EXIF (např. PNG bez metadat)
        exif_data = img._getexif()

        if exif_data is None:
            result["poznamka"] = "no EXIF"
            return result

        # Projde všechna EXIF pole a uloží ta, která potřebujeme
        gps_raw = None

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)

            if tag_name == "DateTime":
                result["datum_cas"] = str(value)
            elif tag_name == "Make":
                result["vyrobce"] = str(value).strip()
            elif tag_name == "Model":
                result["model_zarizeni"] = str(value).strip()
            elif tag_name == "Software":
                result["software"] = str(value).strip()
            elif tag_name == "GPSInfo":
                gps_raw = value  # GPS je vnořený slovník, zpracujeme ho zvlášť

        # Zpracování GPS bloku
        if gps_raw:
            gps = extract_gps(gps_raw)
            if gps:
                result["gps_lat"] = gps["gps_lat"]
                result["gps_lon"] = gps["gps_lon"]
                result["gps_maps_url"] = gps["gps_maps_url"]
            else:
                result["poznamka"] = "GPS nalezeno, ale neúplné"
        else:
            result["poznamka"] = "no GPS"

    except Exception as e:
        # Pokud se soubor nepodaří otevřít nebo EXIF selže
        result["poznamka"] = f"chyba: {str(e)}"

    return result


# ─────────────────────────────────────────────
# SEKCE 3: Načtení souborů (jeden / složka)
# ─────────────────────────────────────────────

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tiff", ".tif")


def get_image_files(path):
    """
    Přijme cestu k souboru nebo složce.
    Vrátí seznam cest k fotografiím.
    """
    if os.path.isfile(path):
        # Uživatel zadal konkrétní soubor
        if path.lower().endswith(SUPPORTED_EXTENSIONS):
            return [path]
        else:
            print(f"[VAROVÁNÍ] Nepodporovaný formát: {path}")
            return []

    elif os.path.isdir(path):
        # Uživatel zadal složku — projde všechny soubory
        files = []
        for filename in sorted(os.listdir(path)):
            if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                full_path = os.path.join(path, filename)
                files.append(full_path)
        return files

    else:
        print(f"[CHYBA] Cesta neexistuje: {path}")
        return []


# ─────────────────────────────────────────────
# SEKCE 4: Výstup — terminál a CSV
# ─────────────────────────────────────────────

def print_result(result):
    """Vypíše výsledek jedné fotografie do terminálu."""
    print(f"\n{'─' * 50}")
    print(f"  Soubor:    {result['soubor']}")
    print(f"  Datum/čas: {result['datum_cas'] or '—'}")
    print(f"  Zařízení:  {result['vyrobce']} {result['model_zarizeni']}".strip())
    print(f"  Software:  {result['software'] or '—'}")

    if result["gps_lat"] and result["gps_lon"]:
        print(f"  GPS:       {result['gps_lat']}, {result['gps_lon']}")
        print(f"  Maps:      {result['gps_maps_url']}")
    else:
        print(f"  GPS:       —")

    if result["poznamka"]:
        print(f"  Poznámka:  {result['poznamka']}")


def save_to_csv(results, output_dir="."):
    """
    Uloží výsledky do CSV souboru.
    Název obsahuje timestamp, aby se soubory nepřepisovaly.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"metadata_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    fieldnames = [
        "soubor", "cesta", "datum_cas", "vyrobce", "model_zarizeni",
        "software", "gps_lat", "gps_lon", "gps_maps_url", "poznamka"
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    return filepath


# ─────────────────────────────────────────────
# SEKCE 5: Hlavní funkce — spuštění skriptu
# ─────────────────────────────────────────────

def main():
    # Definice přepínačů příkazové řádky
    parser = argparse.ArgumentParser(
        description="OSINT Skript 4a — Extrakce EXIF metadat z fotografií"
    )

    # Skupina: buď -f (soubor) nebo -d (složka), ne obojí najednou
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-f", "--file",
        help="Cesta k jedné fotografii (např. -f foto.jpg)"
    )
    group.add_argument(
        "-d", "--directory",
        help="Cesta ke složce s fotografiemi (např. -d /Users/jmeno/fotky)"
    )

    # Volitelný přepínač pro výstupní složku CSV
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Složka pro uložení CSV (výchozí: aktuální složka)"
    )

    args = parser.parse_args()

    # Určení vstupní cesty
    input_path = args.file if args.file else args.directory

    # Načtení seznamu souborů
    image_files = get_image_files(input_path)

    if not image_files:
        print("[INFO] Žádné fotografie k zpracování.")
        sys.exit(0)

    print(f"\n[INFO] Nalezeno {len(image_files)} fotografie/fotografií.")
    print(f"[INFO] Zpracování...\n")

    # Zpracování každé fotografie
    results = []
    for image_path in image_files:
        result = extract_metadata(image_path)
        print_result(result)
        results.append(result)

    # Uložení do CSV
    csv_path = save_to_csv(results, args.output)

    print(f"\n{'═' * 50}")
    print(f"[HOTOVO] Zpracováno: {len(results)} souborů")
    print(f"[CSV]    Uloženo: {csv_path}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
