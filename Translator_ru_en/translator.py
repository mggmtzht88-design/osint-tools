#!/usr/bin/env python3
"""
translator.py — Překladač čeština ↔ ruština
Podporuje: DeepL API (primární) + LibreTranslate (lokální fallback)

Použití:
  python translator.py "Text k překladu"
  python translator.py -f soubor.txt
  python translator.py -f soubor.txt -o                  # uloží výsledek
  python translator.py --engine libretranslate "Text"    # vynutí LibreTranslate
  python translator.py --lang cs-ru "Text"               # směr překladu
  python translator.py --lang ru-cs "Текст"              # ruština → čeština
"""

import argparse
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── Barvy pro terminál ───────────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    DIM    = "\033[2m"

def info(msg):    print(f"{C.CYAN}ℹ {msg}{C.RESET}")
def ok(msg):      print(f"{C.GREEN}✓ {msg}{C.RESET}")
def warn(msg):    print(f"{C.YELLOW}⚠ {msg}{C.RESET}")
def error(msg):   print(f"{C.RED}✗ {msg}{C.RESET}", file=sys.stderr)
def header(msg):  print(f"\n{C.BOLD}{msg}{C.RESET}")

# ─── Konfigurace ──────────────────────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".translator_config.json"

LANG_MAP = {
    "cs-ru": {"deepl_src": "CS", "deepl_tgt": "RU", "libre_src": "cs", "libre_tgt": "ru",
               "label": "čeština → ruština"},
    "ru-cs": {"deepl_src": "RU", "deepl_tgt": "CS", "libre_src": "ru", "libre_tgt": "cs",
               "label": "ruština → čeština"},
    "ru-en": {"deepl_src": "RU", "deepl_tgt": "EN-GB", "libre_src": "ru", "libre_tgt": "en",
               "label": "ruština → angličtina"},
    "en-ru": {"deepl_src": "EN", "deepl_tgt": "RU", "libre_src": "en", "libre_tgt": "ru",
               "label": "angličtina → ruština"},
}

LIBRETRANSLATE_URL = "http://localhost:5001/translate"
OUTPUT_DIR = Path("/Volumes/OSINT/OSINT/PY/Translator_ru_en/Translated")

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ─── DeepL překladač ──────────────────────────────────────────────────────────
def translate_deepl(text: str, lang: str, api_key: str) -> str:
    try:
        import deepl
    except ImportError:
        raise RuntimeError("deepl není nainstalovaný. Spusť: pip install deepl")

    cfg = LANG_MAP[lang]
    translator = deepl.Translator(api_key)
    result = translator.translate_text(
        text,
        source_lang=cfg["deepl_src"],
        target_lang=cfg["deepl_tgt"]
    )
    return result.text

def check_deepl_quota(api_key: str) -> str:
    try:
        import deepl
        translator = deepl.Translator(api_key)
        usage = translator.get_usage()
        used = usage.character.count
        limit = usage.character.limit
        pct = (used / limit * 100) if limit else 0
        return f"{used:,} / {limit:,} znaků ({pct:.1f}%)"
    except Exception as e:
        return f"nelze zjistit ({e})"

# ─── LibreTranslate překladač ─────────────────────────────────────────────────
def translate_libretranslate(text: str, lang: str) -> str:
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests není nainstalovaný. Spusť: pip install requests")

    cfg = LANG_MAP[lang]
    app_cfg = load_config()
    libre_key = app_cfg.get("libretranslate_api_key") or os.environ.get("LIBRETRANSLATE_API_KEY", "")
    payload = {
        "q": text,
        "source": cfg["libre_src"],
        "target": cfg["libre_tgt"],
        "format": "text"
    }
    if libre_key:
        payload["api_key"] = libre_key
    try:
        r = requests.post(LIBRETRANSLATE_URL, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["translatedText"]
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "LibreTranslate neběží lokálně.\n"
            "  Spusť ho příkazem:\n"
            "    pip install libretranslate\n"
            "    libretranslate --load-only cs,ru\n"
            "  (první spuštění stáhne ~500 MB jazykové modely)"
        )
    except Exception as e:
        raise RuntimeError(f"LibreTranslate chyba: {e}")

# ─── Hlavní překladová funkce s fallback logikou ─────────────────────────────
def translate(text: str, lang: str, engine: str, api_key: Optional[str]) -> tuple:
    """
    Vrací (přeložený_text, použitý_engine)
    Fallback logika: deepl → libretranslate (pokud engine='auto')
    """
    if engine == "deepl":
        if not api_key:
            error("DeepL API klíč není nastaven. Použij --set-key nebo -e libretranslate")
            sys.exit(1)
        return translate_deepl(text, lang, api_key), "DeepL"

    if engine == "libretranslate":
        return translate_libretranslate(text, lang), "LibreTranslate"

    # engine == "auto" — zkus DeepL, při selhání přejdi na LibreTranslate
    if api_key:
        try:
            result = translate_deepl(text, lang, api_key)
            return result, "DeepL"
        except Exception as e:
            warn(f"DeepL selhal ({e}), přepínám na LibreTranslate…")

    try:
        result = translate_libretranslate(text, lang)
        return result, "LibreTranslate"
    except Exception as e:
        error(f"Všechny překladače selhaly.\nLibreTranslate: {e}")
        sys.exit(1)

# ─── Zpracování souborů ───────────────────────────────────────────────────────
def translate_file(path: Path, lang: str, engine: str, api_key: str | None, save: bool):
    if not path.exists():
        error(f"Soubor nenalezen: {path}")
        sys.exit(1)

    suffix = path.suffix.lower()
    lines = []

    if suffix == ".txt":
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    elif suffix == ".csv":
        import csv
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            lines = [",".join(row) + "\n" for row in reader]
    else:
        # Pokus o čtení jako plain text
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

    if not lines:
        warn("Soubor je prázdný.")
        return

    header(f"Překládám soubor: {path.name} ({len(lines)} řádků)")
    translated_lines = []
    errors = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            translated_lines.append("\n")
            continue
        try:
            result, used_engine = translate(stripped, lang, engine, api_key)
            translated_lines.append(result + "\n")
            # Progress každých 10 řádků nebo na posledním
            if i % 10 == 0 or i == len(lines):
                print(f"  {C.DIM}[{i}/{len(lines)}] engine: {used_engine}{C.RESET}")
        except SystemExit:
            raise
        except Exception as e:
            warn(f"Řádek {i} přeskočen: {e}")
            translated_lines.append(f"[CHYBA: {e}]\n")
            errors += 1

    # Výpis výsledku
    print(f"\n{C.BOLD}{'─'*60}{C.RESET}")
    print("".join(translated_lines))
    print(f"{C.BOLD}{'─'*60}{C.RESET}")

    if errors:
        warn(f"{errors} řádků se nepodařilo přeložit.")

    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / (path.stem + "_translated" + path.suffix)
        with open(out_path, "w", encoding="utf-8") as f:
            f.writelines(translated_lines)
        ok(f"Uloženo: {out_path}")

# ─── Interaktivní režim ───────────────────────────────────────────────────────
def interactive_mode(lang: str, engine: str, api_key: str | None, save: bool):
    cfg = LANG_MAP[lang]
    header(f"Interaktivní překladač — {cfg['label']}")
    info("Zadej text k překladu (prázdný řádek = konec, Ctrl+C = ukončit)")
    if save:
        info("Výsledky budou ukládány do translation_log.txt")

    log_file = (OUTPUT_DIR / "translation_log.txt") if save else None
    session_lines = []

    while True:
        try:
            print(f"\n{C.CYAN}▶ Text:{C.RESET} ", end="")
            text = input().strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}Ukončeno.{C.RESET}")
            break

        if not text:
            break

        result, used_engine = translate(text, lang, engine, api_key)
        print(f"{C.GREEN}▶ Překlad ({used_engine}):{C.RESET} {result}")

        if save:
            entry = f"[{datetime.now().strftime('%H:%M:%S')}] [{used_engine}]\nVSTUP: {text}\nVÝSTUP: {result}\n{'─'*40}\n"
            session_lines.append(entry)

    if save and session_lines:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'═'*40}\nRelace: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{'═'*40}\n")
            f.writelines(session_lines)
        ok(f"Relace uložena do: {log_file}")

# ─── CLI ──────────────────────────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        description="Překladač čeština ↔ ruština (DeepL + LibreTranslate)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  python translator.py "Министерство обороны"
  python translator.py --lang ru-cs "Санкции введены"
  python translator.py -f osint_queries.txt -o
  python translator.py -e libretranslate "citlivý text"
  python translator.py --set-key TVUJ_DEEPL_API_KLIC
  python translator.py --status
        """
    )
    parser.add_argument("text", nargs="?", help="Text k překladu (volitelné)")
    parser.add_argument("-f", "--file", type=Path, help="Vstupní soubor (.txt nebo .csv)")
    parser.add_argument("-o", "--output", action="store_true", help="Uložit výsledek do souboru")
    parser.add_argument("-e", "--engine", choices=["auto", "deepl", "libretranslate"],
                        default="auto", help="Překladač (výchozí: auto)")
    parser.add_argument("--lang", choices=list(LANG_MAP.keys()),
                        default="cs-ru", help="Směr překladu (výchozí: cs-ru)")
    parser.add_argument("--set-key", metavar="API_KEY", help="Uloží DeepL API klíč do ~/.translator_config.json")
    parser.add_argument("--set-libre-key", metavar="API_KEY", help="Uloží LibreTranslate API klíč do ~/.translator_config.json")
    parser.add_argument("--status", action="store_true", help="Zobrazí stav překladačů a kvótu DeepL")
    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = load_config()

    # ── Nastavení API klíče ──────────────────────────────────────────────────
    if args.set_key:
        cfg["deepl_api_key"] = args.set_key
        save_config(cfg)
        ok(f"DeepL API klíč uložen do {CONFIG_FILE}")
        return

    if args.set_libre_key:
        cfg["libretranslate_api_key"] = args.set_libre_key
        save_config(cfg)
        ok(f"LibreTranslate API klíč uložen do {CONFIG_FILE}")
        return

    api_key = cfg.get("deepl_api_key") or os.environ.get("DEEPL_API_KEY")

    # ── Status ───────────────────────────────────────────────────────────────
    if args.status:
        header("Stav překladačů")
        if api_key:
            quota = check_deepl_quota(api_key)
            ok(f"DeepL API klíč: nastaven | Kvóta: {quota}")
        else:
            warn("DeepL API klíč: není nastaven (použij --set-key nebo env DEEPL_API_KEY)")

        try:
            import requests
            r = requests.get("http://localhost:5001/languages", timeout=5)
            if r.status_code == 200:
                ok("LibreTranslate: běží lokálně na :5000")
            else:
                warn("LibreTranslate: odpovídá, ale s chybou")
        except Exception:
            warn("LibreTranslate: neběží (nebo není nainstalovaný)")

        return

    # ── Překlad souboru ──────────────────────────────────────────────────────
    if args.file:
        translate_file(args.file, args.lang, args.engine, api_key, args.output)
        return

    # ── Překlad textu z argumentu ────────────────────────────────────────────
    if args.text:
        result, used_engine = translate(args.text, args.lang, args.engine, api_key)
        cfg_lang = LANG_MAP[args.lang]
        print(f"\n{C.DIM}[{used_engine} | {cfg_lang['label']}]{C.RESET}")
        print(f"{C.BOLD}{result}{C.RESET}\n")

        if args.output:
            out = OUTPUT_DIR / f"translation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            out.write_text(f"VSTUP [{args.lang}]: {args.text}\nVÝSTUP [{used_engine}]: {result}\n", encoding="utf-8")
            ok(f"Uloženo: {out}")
        return

    # ── Interaktivní režim ───────────────────────────────────────────────────
    interactive_mode(args.lang, args.engine, api_key, args.output)


if __name__ == "__main__":
    main()
