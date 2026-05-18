#!/usr/bin/env python3
"""
OSINT Skript 5 — Report Generator (aktualizováno: wayback_checker, duplicate_detector, reverse_image_search)
Generuje strukturovaný report z výstupů skriptů 4a, 4b, 4c, 6a, 6b, 6c.
Výstup: Markdown (.md) + HTML (.html)

Použití — automatický režim (najde nejnovější soubory):
  python report_generator.py --auto \
    --meta-dir     /cesta/Metadata_Extractor/output \
    --screen-dir   /cesta/Screenshot_Archiver/output \
    --net-dir      /cesta/Network_Mapper/output \
    --wayback-dir  /cesta/Wayback_Checker/output \
    --dupl-dir     /cesta/Duplicate_Detector/output \
    --revimg-dir   /cesta/Reverse_Image_Search/output

Použití — manuální režim (zadáš konkrétní soubory):
  python report_generator.py \
    --meta-csv     metadata_20260508.csv \
    --screen-csv   screenshots_20260508.csv \
    --net-csv      network_edges_20260508.csv \
    --wayback-csv  wayback_checker_20260508.csv \
    --dupl-csv     duplicate_detector_20260508.csv \
    --revimg-csv   reverse_image_search_20260508.csv
"""

import os
import sys
import csv
import json
import argparse
import glob
from datetime import datetime


# ─────────────────────────────────────────────
# SEKCE 1: Načtení dat ze vstupních souborů
# ─────────────────────────────────────────────

def find_latest_file(directory, pattern):
    """
    V zadané složce najde nejnovější soubor odpovídající vzoru.
    Vrátí cestu k souboru nebo None.
    """
    if not directory or not os.path.isdir(directory):
        return None

    matches = glob.glob(os.path.join(directory, pattern))
    if not matches:
        return None

    return max(matches, key=os.path.getmtime)


def load_csv(filepath, label):
    """
    Načte CSV soubor a vrátí seznam řádků jako slovníky.
    Přeskočí řádky začínající # (komentáře v CSV skriptů 6a/6b/6c).
    Pokud soubor neexistuje, vrátí prázdný seznam.
    """
    if not filepath or not os.path.isfile(filepath):
        print(f"[VAROVÁNÍ] {label}: soubor nenalezen → {filepath}")
        return []

    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        # Přeskoč řádky začínající # (metadata komentáře)
        filtered = (line for line in f if not line.startswith("#"))
        reader = csv.DictReader(filtered)
        for row in reader:
            rows.append(dict(row))

    print(f"[INFO] {label}: načteno {len(rows)} řádků → {os.path.basename(filepath)}")
    return rows


def load_screen_json(filepath):
    """
    Načte JSON soubor ze Skriptu 4b (screenshoty).
    Vrátí seznam záznamů nebo prázdný seznam.
    """
    if not filepath or not os.path.isfile(filepath):
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# SEKCE 2: Sestavení dat pro report
# ─────────────────────────────────────────────

def build_report_data(meta_rows, screen_rows, net_rows,
                      wayback_rows, dupl_rows, revimg_rows):
    """
    Ze všech vstupních dat sestaví strukturovaný slovník pro report.
    """
    now = datetime.now()

    # ── Metadata (Skript 4a) ──
    meta_total    = len(meta_rows)
    meta_with_gps = sum(1 for r in meta_rows if r.get("gps_lat"))
    meta_no_exif  = sum(1 for r in meta_rows if "no EXIF" in r.get("poznamka", ""))
    meta_devices  = list({r.get("model_zarizeni", "").strip()
                          for r in meta_rows if r.get("model_zarizeni", "").strip()})

    # ── Screenshoty (Skript 4b) ──
    screen_total  = len(screen_rows)
    screen_ok     = sum(1 for r in screen_rows if r.get("poznamka") == "ok")
    screen_errors = screen_total - screen_ok

    # ── Síťová data (Skript 4c) ──
    net_total = len(net_rows)
    nodes = set()
    for r in net_rows:
        if r.get("zdroj"): nodes.add(r["zdroj"])
        if r.get("cil"):   nodes.add(r["cil"])

    node_degree = {}
    for r in net_rows:
        for key in ("zdroj", "cil"):
            n = r.get(key, "")
            if n:
                node_degree[n] = node_degree.get(n, 0) + 1
    top_nodes = sorted(node_degree.items(), key=lambda x: x[1], reverse=True)[:10]

    # ── Wayback Checker (Skript 6a) ──
    wayback_total      = len(wayback_rows)
    wayback_ok         = sum(1 for r in wayback_rows if not r.get("error"))
    wayback_suspicious = sum(1 for r in wayback_rows
                             if not r.get("error") and
                             r.get("similarity_pct") and
                             float(r.get("similarity_pct", 100)) < 50)

    # ── Duplicate Detector (Skript 6b) ──
    dupl_total    = len(dupl_rows)
    dupl_high     = sum(1 for r in dupl_rows
                        if not r.get("error") and
                        r.get("similarity_pct") and
                        float(r.get("similarity_pct", 0)) >= 60)
    dupl_medium   = sum(1 for r in dupl_rows
                        if not r.get("error") and
                        r.get("similarity_pct") and
                        40 <= float(r.get("similarity_pct", 0)) < 60)

    # ── Reverse Image Search (Skript 6c) ──
    revimg_total    = len(revimg_rows)
    revimg_sources  = list({r.get("image_source", "").strip()
                            for r in revimg_rows if r.get("image_source", "").strip()})
    revimg_platforms = list({r.get("platform", "").strip()
                             for r in revimg_rows if r.get("platform", "").strip()})

    return {
        "datum":     now.strftime("%Y-%m-%d"),
        "cas":       now.strftime("%H:%M:%S"),
        "timestamp": now.strftime("%Y%m%d_%H%M%S"),

        "meta": {
            "rows": meta_rows, "total": meta_total,
            "with_gps": meta_with_gps, "no_exif": meta_no_exif,
            "devices": meta_devices,
        },
        "screen": {
            "rows": screen_rows, "total": screen_total,
            "ok": screen_ok, "errors": screen_errors,
        },
        "net": {
            "rows": net_rows, "total_edges": net_total,
            "total_nodes": len(nodes), "top_nodes": top_nodes,
        },
        "wayback": {
            "rows": wayback_rows, "total": wayback_total,
            "ok": wayback_ok, "suspicious": wayback_suspicious,
        },
        "dupl": {
            "rows": dupl_rows, "total": dupl_total,
            "high": dupl_high, "medium": dupl_medium,
        },
        "revimg": {
            "rows": revimg_rows, "total": revimg_total,
            "sources": revimg_sources, "platforms": revimg_platforms,
        },
    }


# ─────────────────────────────────────────────
# SEKCE 3: Markdown výstup
# ─────────────────────────────────────────────

def generate_markdown(data):
    """Sestaví Markdown report jako jeden dlouhý řetězec."""
    d = data
    lines = []

    # ── Hlavička ──
    lines += [
        f"# OSINT Report",
        f"",
        f"**Datum:** {d['datum']}  ",
        f"**Čas:** {d['cas']}  ",
        f"**Generováno:** OSINT Report Generator  ",
        f"",
        f"---",
        f"",
    ]

    # ── Shrnutí ──
    lines += [
        f"## Shrnutí",
        f"",
        f"| Oblast | Hodnota |",
        f"|--------|---------|",
        f"| Analyzované fotografie | {d['meta']['total']} |",
        f"| Fotografie s GPS | {d['meta']['with_gps']} |",
        f"| Archivované URL | {d['screen']['total']} |",
        f"| Úspěšné screenshoty | {d['screen']['ok']} |",
        f"| Zdrojů v síti | {d['net']['total_nodes']} |",
        f"| Vazeb v síti | {d['net']['total_edges']} |",
        f"| Zkontrolováno Wayback | {d['wayback']['total']} |",
        f"| Podezřelé změny (< 50%) | {d['wayback']['suspicious']} |",
        f"| Domén pro detekci duplikátů | {d['dupl']['total']} |",
        f"| Vysoká shoda duplikátů (≥ 60%) | {d['dupl']['high']} |",
        f"| Nálezů reverse image search | {d['revimg']['total']} |",
        f"",
        f"---",
        f"",
    ]

    # ── Sekce 4a: Metadata ──
    lines += [
        f"## Metadata Extractor",
        f"",
        f"- Celkem fotografií: **{d['meta']['total']}**",
        f"- S GPS souřadnicemi: **{d['meta']['with_gps']}**",
        f"- Bez EXIF dat: **{d['meta']['no_exif']}**",
    ]
    if d['meta']['devices']:
        lines.append(f"- Identifikovaná zařízení: {', '.join(d['meta']['devices'])}")
    lines.append("")

    if d['meta']['rows']:
        lines += [
            f"### Tabulka metadat",
            f"",
            f"| Soubor | Datum/čas | Zařízení | GPS | Maps | Poznámka |",
            f"|--------|-----------|----------|-----|------|----------|",
        ]
        for r in d['meta']['rows']:
            gps      = f"{r.get('gps_lat', '')} {r.get('gps_lon', '')}".strip() or "—"
            maps     = f"[odkaz]({r.get('gps_maps_url', '')})" if r.get('gps_maps_url') else "—"
            zarizeni = f"{r.get('vyrobce', '')} {r.get('model_zarizeni', '')}".strip() or "—"
            lines.append(
                f"| {r.get('soubor', '—')} "
                f"| {r.get('datum_cas', '—')} "
                f"| {zarizeni} "
                f"| {gps} "
                f"| {maps} "
                f"| {r.get('poznamka', '—')} |"
            )

    lines += ["", "---", ""]

    # ── Sekce 4b: Screenshoty ──
    lines += [
        f"## Screenshot Archiver",
        f"",
        f"- Celkem URL: **{d['screen']['total']}**",
        f"- Úspěšně archivováno: **{d['screen']['ok']}**",
        f"- Chyby: **{d['screen']['errors']}**",
        f"",
    ]
    if d['screen']['rows']:
        lines += [
            f"### Archivované URL",
            f"",
            f"| URL | Titulek | HTTP | Soubor | Timestamp | Poznámka |",
            f"|-----|---------|------|--------|-----------|----------|",
        ]
        for r in d['screen']['rows']:
            url       = r.get('url', '—')
            url_short = url[:60] + "..." if len(url) > 60 else url
            lines.append(
                f"| {url_short} "
                f"| {r.get('titulek_stranky', '—')[:50]} "
                f"| {r.get('http_status', '—')} "
                f"| {r.get('screenshot_soubor', '—')} "
                f"| {r.get('timestamp', '—')} "
                f"| {r.get('poznamka', '—')} |"
            )

    lines += ["", "---", ""]

    # ── Sekce 4c: Síť ──
    lines += [
        f"## Network Mapper",
        f"",
        f"- Uzlů v síti: **{d['net']['total_nodes']}**",
        f"- Vazeb celkem: **{d['net']['total_edges']}**",
        f"",
    ]
    if d['net']['top_nodes']:
        lines += [
            f"### Top uzly (nejvíce vazeb)",
            f"",
            f"| Zdroj | Počet vazeb |",
            f"|-------|-------------|",
        ]
        for node, degree in d['net']['top_nodes']:
            lines.append(f"| {node} | {degree} |")
    if d['net']['rows']:
        lines += [
            f"",
            f"### Tabulka vazeb",
            f"",
            f"| Zdroj | Cíl | Typ | Počet | Klíčová slova |",
            f"|-------|-----|-----|-------|---------------|",
        ]
        for r in d['net']['rows']:
            lines.append(
                f"| {r.get('zdroj', '—')} "
                f"| {r.get('cil', '—')} "
                f"| {r.get('typ', '—')} "
                f"| {r.get('pocet', '—')} "
                f"| {r.get('klic_slova', '—')} |"
            )

    lines += ["", "---", ""]

    # ── Sekce 6a: Wayback Checker ──
    lines += [
        f"## Wayback Checker",
        f"",
        f"- Zkontrolovaných URL: **{d['wayback']['total']}**",
        f"- Úspěšně porovnáno: **{d['wayback']['ok']}**",
        f"- Podezřelé změny (podobnost < 50 %): **{d['wayback']['suspicious']}**",
        f"",
    ]
    if d['wayback']['rows']:
        lines += [
            f"### Výsledky",
            f"",
            f"| URL | Datum archivu | Podobnost | Hodnocení | Přidáno (náhled) | Odebráno (náhled) | Chyba |",
            f"|-----|---------------|-----------|-----------|-----------------|-------------------|-------|",
        ]
        for r in d['wayback']['rows']:
            url       = r.get('url', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            sim       = f"{r.get('similarity_pct', '—')} %" if r.get('similarity_pct') else "—"
            lines.append(
                f"| {url_short} "
                f"| {r.get('archive_date', '—')} "
                f"| {sim} "
                f"| {r.get('summary', '—')} "
                f"| {r.get('added_words_preview', '—')[:40]} "
                f"| {r.get('removed_words_preview', '—')[:40]} "
                f"| {r.get('error', '—')} |"
            )

    lines += ["", "---", ""]

    # ── Sekce 6b: Duplicate Detector ──
    lines += [
        f"## Duplicate Detector",
        f"",
        f"- Zkontrolovaných domén: **{d['dupl']['total']}**",
        f"- Vysoká shoda (≥ 60 %): **{d['dupl']['high']}**",
        f"- Střední shoda (40–59 %): **{d['dupl']['medium']}**",
        f"",
    ]
    if d['dupl']['rows']:
        lines += [
            f"### Výsledky",
            f"",
            f"| Doména | Zkontrolovaná URL | Podobnost | Klasifikace | Chyba |",
            f"|--------|-------------------|-----------|-------------|-------|",
        ]
        # Seřaď sestupně podle podobnosti
        sorted_rows = sorted(
            d['dupl']['rows'],
            key=lambda r: float(r.get('similarity_pct', 0) or 0),
            reverse=True
        )
        for r in sorted_rows:
            sim = f"{r.get('similarity_pct', '—')} %" if r.get('similarity_pct') else "—"
            url = r.get('url_checked', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            lines.append(
                f"| {r.get('domain', '—')} "
                f"| {url_short} "
                f"| {sim} "
                f"| {r.get('classification', '—')} "
                f"| {r.get('error', '—')} |"
            )

    lines += ["", "---", ""]

    # ── Sekce 6c: Reverse Image Search ──
    lines += [
        f"## Reverse Image Search",
        f"",
        f"- Celkem nálezů: **{d['revimg']['total']}**",
    ]
    if d['revimg']['sources']:
        lines.append(f"- Prohledané obrázky: {', '.join(d['revimg']['sources'])}")
    if d['revimg']['platforms']:
        lines.append(f"- Platformy: {', '.join(d['revimg']['platforms'])}")
    lines.append("")

    if d['revimg']['rows']:
        lines += [
            f"### Nálezy",
            f"",
            f"| Obrázek | Platforma | Nalezená URL | Datum výskytu | Poznámka |",
            f"|---------|-----------|--------------|---------------|----------|",
        ]
        for r in d['revimg']['rows']:
            src       = r.get('image_source', '—')
            src_short = src[:40] + "..." if len(src) > 40 else src
            url       = r.get('found_url', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            lines.append(
                f"| {src_short} "
                f"| {r.get('platform', '—')} "
                f"| {url_short} "
                f"| {r.get('found_date', '—')} "
                f"| {r.get('note', '—')} |"
            )

    lines += ["", "---", ""]
    lines += [f"*Report vygenerován: {d['datum']} {d['cas']}*", ""]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# SEKCE 4: HTML výstup
# ─────────────────────────────────────────────

def generate_html(data):
    """Sestaví HTML report se stylingem. Čitelný v prohlížeči, lze tisknout."""
    d = data

    def table_row(*cells):
        return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

    def th_row(*cells):
        return "<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>"

    # ── Tabulka metadat ──
    meta_table = ""
    if d['meta']['rows']:
        rows_html = ""
        for r in d['meta']['rows']:
            gps      = f"{r.get('gps_lat', '')} {r.get('gps_lon', '')}".strip() or "—"
            maps_url = r.get('gps_maps_url', '')
            maps     = f'<a href="{maps_url}" target="_blank">odkaz</a>' if maps_url else "—"
            zarizeni = f"{r.get('vyrobce', '')} {r.get('model_zarizeni', '')}".strip() or "—"
            rows_html += table_row(
                r.get('soubor', '—'), r.get('datum_cas', '—'),
                zarizeni, gps, maps, r.get('poznamka', '—')
            )
        meta_table = f"<table>{th_row('Soubor','Datum/čas','Zařízení','GPS','Maps','Poznámka')}{rows_html}</table>"

    # ── Tabulka screenshotů ──
    screen_table = ""
    if d['screen']['rows']:
        rows_html = ""
        for r in d['screen']['rows']:
            url       = r.get('url', '—')
            url_short = url[:60] + "..." if len(url) > 60 else url
            rows_html += table_row(
                f'<a href="{url}" target="_blank">{url_short}</a>',
                r.get('titulek_stranky', '—')[:60],
                r.get('http_status', '—'),
                r.get('screenshot_soubor', '—'),
                r.get('timestamp', '—'),
                r.get('poznamka', '—')
            )
        screen_table = f"<table>{th_row('URL','Titulek','HTTP','Soubor','Timestamp','Poznámka')}{rows_html}</table>"

    # ── Tabulka top uzlů ──
    top_nodes_table = ""
    if d['net']['top_nodes']:
        rows_html = "".join(table_row(n, deg) for n, deg in d['net']['top_nodes'])
        top_nodes_table = f"<table>{th_row('Zdroj','Počet vazeb')}{rows_html}</table>"

    # ── Tabulka vazeb ──
    net_table = ""
    if d['net']['rows']:
        rows_html = ""
        for r in d['net']['rows']:
            rows_html += table_row(
                r.get('zdroj','—'), r.get('cil','—'),
                r.get('typ','—'), r.get('pocet','—'), r.get('klic_slova','—')
            )
        net_table = f"<table>{th_row('Zdroj','Cíl','Typ','Počet','Klíčová slova')}{rows_html}</table>"

    # ── Tabulka Wayback Checker ──
    wayback_table = ""
    if d['wayback']['rows']:
        rows_html = ""
        for r in d['wayback']['rows']:
            url       = r.get('url', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            sim       = f"{r.get('similarity_pct', '—')} %" if r.get('similarity_pct') else "—"
            # Barevné zvýraznění podezřelých řádků
            sim_val   = float(r.get('similarity_pct', 100) or 100)
            color     = "#f85149" if sim_val < 50 else ("#e3b341" if sim_val < 75 else "#3fb950")
            sim_cell  = f'<span style="color:{color};font-weight:bold">{sim}</span>'
            rows_html += table_row(
                f'<a href="{url}" target="_blank">{url_short}</a>',
                r.get('archive_date', '—'),
                sim_cell,
                r.get('summary', '—'),
                r.get('added_words_preview', '—')[:40],
                r.get('removed_words_preview', '—')[:40],
                r.get('error', '—')
            )
        wayback_table = f"<table>{th_row('URL','Datum archivu','Podobnost','Hodnocení','Přidáno','Odebráno','Chyba')}{rows_html}</table>"

    # ── Tabulka Duplicate Detector ──
    dupl_table = ""
    if d['dupl']['rows']:
        rows_html = ""
        sorted_rows = sorted(
            d['dupl']['rows'],
            key=lambda r: float(r.get('similarity_pct', 0) or 0),
            reverse=True
        )
        for r in sorted_rows:
            sim_val  = float(r.get('similarity_pct', 0) or 0)
            color    = "#f85149" if sim_val >= 80 else ("#e3b341" if sim_val >= 60 else ("#8b949e" if sim_val >= 40 else "#484f58"))
            sim_cell = f'<span style="color:{color};font-weight:bold">{sim_val} %</span>' if r.get('similarity_pct') else "—"
            url      = r.get('url_checked', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            rows_html += table_row(
                r.get('domain', '—'),
                f'<a href="{url}" target="_blank">{url_short}</a>',
                sim_cell,
                r.get('classification', '—'),
                r.get('error', '—')
            )
        dupl_table = f"<table>{th_row('Doména','Zkontrolovaná URL','Podobnost','Klasifikace','Chyba')}{rows_html}</table>"

    # ── Tabulka Reverse Image Search ──
    revimg_table = ""
    if d['revimg']['rows']:
        rows_html = ""
        for r in d['revimg']['rows']:
            src       = r.get('image_source', '—')
            src_short = src[:40] + "..." if len(src) > 40 else src
            url       = r.get('found_url', '—')
            url_short = url[:50] + "..." if len(url) > 50 else url
            rows_html += table_row(
                src_short,
                r.get('platform', '—'),
                f'<a href="{url}" target="_blank">{url_short}</a>',
                r.get('found_date', '—'),
                r.get('note', '—')
            )
        revimg_table = f"<table>{th_row('Obrázek','Platforma','Nalezená URL','Datum výskytu','Poznámka')}{rows_html}</table>"

    html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OSINT Report — {d['datum']}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Courier New', monospace;
    background: #0d1117;
    color: #c9d1d9;
    padding: 40px 20px;
    line-height: 1.6;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{
    font-size: 2em;
    color: #58a6ff;
    border-bottom: 2px solid #21262d;
    padding-bottom: 15px;
    margin-bottom: 10px;
  }}
  .meta-header {{ color: #8b949e; font-size: 0.9em; margin-bottom: 30px; }}
  h2 {{
    font-size: 1.3em;
    color: #58a6ff;
    margin: 35px 0 15px 0;
    padding: 8px 15px;
    background: #161b22;
    border-left: 4px solid #58a6ff;
    border-radius: 0 6px 6px 0;
  }}
  h3 {{
    font-size: 1em;
    color: #8b949e;
    margin: 20px 0 10px 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 15px;
    margin: 20px 0;
  }}
  .stat-card {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 15px;
    text-align: center;
  }}
  .stat-number {{ font-size: 2em; font-weight: bold; color: #58a6ff; }}
  .stat-label  {{ font-size: 0.8em; color: #8b949e; margin-top: 5px; }}
  .stat-number.warn {{ color: #e3b341; }}
  .stat-number.danger {{ color: #f85149; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
    margin: 15px 0;
    background: #161b22;
    border-radius: 8px;
    overflow: hidden;
  }}
  th {{
    background: #21262d;
    color: #58a6ff;
    padding: 10px 12px;
    text-align: left;
    font-weight: bold;
    text-transform: uppercase;
    font-size: 0.8em;
    letter-spacing: 0.05em;
  }}
  td {{
    padding: 8px 12px;
    border-top: 1px solid #21262d;
    color: #c9d1d9;
    word-break: break-all;
  }}
  tr:hover td {{ background: #1c2128; }}
  a {{ color: #58a6ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .section {{ margin-bottom: 40px; }}
  .stats-inline {{
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    margin: 10px 0 20px 0;
  }}
  .stat-inline {{
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 0.9em;
  }}
  .stat-inline span {{ color: #58a6ff; font-weight: bold; }}
  .stat-inline span.warn {{ color: #e3b341; }}
  .stat-inline span.danger {{ color: #f85149; }}
  hr {{ border: none; border-top: 1px solid #21262d; margin: 30px 0; }}
  footer {{
    text-align: center;
    color: #484f58;
    font-size: 0.8em;
    margin-top: 50px;
    padding-top: 20px;
    border-top: 1px solid #21262d;
  }}
</style>
</head>
<body>
<div class="container">

  <h1>OSINT Report</h1>
  <div class="meta-header">
    Datum: {d['datum']} &nbsp;|&nbsp; Čas: {d['cas']} &nbsp;|&nbsp;
    Generováno: OSINT Report Generator
  </div>

  <hr>

  <h2>Shrnutí</h2>
  <div class="summary-grid">
    <div class="stat-card">
      <div class="stat-number">{d['meta']['total']}</div>
      <div class="stat-label">Fotografií</div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{d['meta']['with_gps']}</div>
      <div class="stat-label">S GPS</div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{d['screen']['total']}</div>
      <div class="stat-label">Archivovaných URL</div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{d['net']['total_nodes']}</div>
      <div class="stat-label">Zdrojů v síti</div>
    </div>
    <div class="stat-card">
      <div class="stat-number {'danger' if d['wayback']['suspicious'] > 0 else ''}">{d['wayback']['suspicious']}</div>
      <div class="stat-label">Podezřelých změn</div>
    </div>
    <div class="stat-card">
      <div class="stat-number {'danger' if d['dupl']['high'] > 0 else ''}">{d['dupl']['high']}</div>
      <div class="stat-label">Vysokých shod</div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{d['revimg']['total']}</div>
      <div class="stat-label">Image nálezů</div>
    </div>
  </div>

  <hr>

  <div class="section">
    <h2>Metadata Extractor</h2>
    <div class="stats-inline">
      <div class="stat-inline">Fotografií: <span>{d['meta']['total']}</span></div>
      <div class="stat-inline">S GPS: <span>{d['meta']['with_gps']}</span></div>
      <div class="stat-inline">Bez EXIF: <span>{d['meta']['no_exif']}</span></div>
    </div>
    <h3>Tabulka metadat</h3>
    {meta_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <div class="section">
    <h2>Screenshot Archiver</h2>
    <div class="stats-inline">
      <div class="stat-inline">Celkem URL: <span>{d['screen']['total']}</span></div>
      <div class="stat-inline">Úspěšně: <span>{d['screen']['ok']}</span></div>
      <div class="stat-inline">Chyby: <span class="{'danger' if d['screen']['errors'] > 0 else ''}">{d['screen']['errors']}</span></div>
    </div>
    <h3>Archivované URL</h3>
    {screen_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <div class="section">
    <h2>Network Mapper</h2>
    <div class="stats-inline">
      <div class="stat-inline">Zdrojů: <span>{d['net']['total_nodes']}</span></div>
      <div class="stat-inline">Vazeb: <span>{d['net']['total_edges']}</span></div>
    </div>
    <h3>Top uzly</h3>
    {top_nodes_table or "<p style='color:#8b949e'>Žádná data.</p>"}
    <h3>Tabulka vazeb</h3>
    {net_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <div class="section">
    <h2>Wayback Checker</h2>
    <div class="stats-inline">
      <div class="stat-inline">Zkontrolováno: <span>{d['wayback']['total']}</span></div>
      <div class="stat-inline">Úspěšně: <span>{d['wayback']['ok']}</span></div>
      <div class="stat-inline">Podezřelé změny: <span class="{'danger' if d['wayback']['suspicious'] > 0 else ''}">{d['wayback']['suspicious']}</span></div>
    </div>
    <h3>Výsledky</h3>
    {wayback_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <div class="section">
    <h2>Duplicate Detector</h2>
    <div class="stats-inline">
      <div class="stat-inline">Domén: <span>{d['dupl']['total']}</span></div>
      <div class="stat-inline">Vysoká shoda (≥ 60 %): <span class="{'danger' if d['dupl']['high'] > 0 else ''}">{d['dupl']['high']}</span></div>
      <div class="stat-inline">Střední shoda (40–59 %): <span class="{'warn' if d['dupl']['medium'] > 0 else ''}">{d['dupl']['medium']}</span></div>
    </div>
    <h3>Výsledky</h3>
    {dupl_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <div class="section">
    <h2>Reverse Image Search</h2>
    <div class="stats-inline">
      <div class="stat-inline">Nálezů: <span>{d['revimg']['total']}</span></div>
      <div class="stat-inline">Platforem: <span>{len(d['revimg']['platforms'])}</span></div>
    </div>
    <h3>Nálezy</h3>
    {revimg_table or "<p style='color:#8b949e'>Žádná data.</p>"}
  </div>

  <footer>
    OSINT Report Generator — {d['datum']} {d['cas']}
  </footer>

</div>
</body>
</html>"""

    return html


# ─────────────────────────────────────────────
# SEKCE 5: Uložení reportů
# ─────────────────────────────────────────────

def save_reports(md_content, html_content, output_dir, timestamp_str):
    """Uloží Markdown do output/md/ a HTML do output/html/."""
    md_dir   = os.path.join(output_dir, "md")
    html_dir = os.path.join(output_dir, "html")
    os.makedirs(md_dir,   exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)

    md_path   = os.path.join(md_dir,   f"osint_report_{timestamp_str}.md")
    html_path = os.path.join(html_dir, f"osint_report_{timestamp_str}.html")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[✓] Markdown uložen: md/osint_report_{timestamp_str}.md")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[✓] HTML uložen:     html/osint_report_{timestamp_str}.html")

    return md_path, html_path


# ─────────────────────────────────────────────
# SEKCE 6: Hlavní funkce
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OSINT Report Generator — generuje report ze všech skriptů"
    )

    parser.add_argument(
        "--auto", action="store_true",
        help="Automaticky najde nejnovější soubory ve výstupních složkách"
    )

    # Automatický režim — složky
    parser.add_argument("--meta-dir",    help="Složka output/ Metadata Extractor")
    parser.add_argument("--screen-dir",  help="Složka output/ Screenshot Archiver")
    parser.add_argument("--net-dir",     help="Složka output/ Network Mapper")
    parser.add_argument("--wayback-dir", help="Složka output/ Wayback Checker")
    parser.add_argument("--dupl-dir",    help="Složka output/ Duplicate Detector")
    parser.add_argument("--revimg-dir",  help="Složka output/ Reverse Image Search")

    # Manuální režim — konkrétní soubory
    parser.add_argument("--meta-csv",    help="CSV soubor z Metadata Extractor")
    parser.add_argument("--screen-csv",  help="CSV soubor z Screenshot Archiver")
    parser.add_argument("--screen-json", help="JSON soubor z Screenshot Archiver")
    parser.add_argument("--net-csv",     help="CSV soubor z Network Mapper")
    parser.add_argument("--wayback-csv", help="CSV soubor z Wayback Checker")
    parser.add_argument("--dupl-csv",    help="CSV soubor z Duplicate Detector")
    parser.add_argument("--revimg-csv",  help="CSV soubor z Reverse Image Search")

    parser.add_argument(
        "-o", "--output", default=".",
        help="Složka pro uložení reportů (výchozí: aktuální složka)"
    )

    args = parser.parse_args()

    print(f"\n[INFO] Výstupní složka: {args.output}")

    if args.auto:
        print("[INFO] Režim: automatický — hledám nejnovější soubory\n")
        meta_csv    = find_latest_file(args.meta_dir,    "metadata_*.csv")
        screen_csv  = find_latest_file(args.screen_dir,  "screenshots_*.csv")
        screen_json = find_latest_file(args.screen_dir,  "screenshots_*.json")
        net_csv     = find_latest_file(args.net_dir,     "network_edges_*.csv")
        wayback_csv = find_latest_file(args.wayback_dir, "wayback_checker_*.csv")
        dupl_csv    = find_latest_file(args.dupl_dir,    "duplicate_detector_*.csv")
        revimg_csv  = find_latest_file(args.revimg_dir,  "reverse_image_search_*.csv")
    else:
        print("[INFO] Režim: manuální — používám zadané soubory\n")
        meta_csv    = args.meta_csv
        screen_csv  = args.screen_csv
        screen_json = args.screen_json
        net_csv     = args.net_csv
        wayback_csv = args.wayback_csv
        dupl_csv    = args.dupl_csv
        revimg_csv  = args.revimg_csv

    # Načtení dat
    meta_rows   = load_csv(meta_csv,    "Metadata Extractor")
    screen_rows = load_csv(screen_csv,  "Screenshot Archiver")
    net_rows    = load_csv(net_csv,     "Network Mapper")
    wayback_rows = load_csv(wayback_csv, "Wayback Checker")
    dupl_rows   = load_csv(dupl_csv,    "Duplicate Detector")
    revimg_rows = load_csv(revimg_csv,  "Reverse Image Search")

    # JSON screenshoty doplní screen_rows pokud CSV chybí
    if not screen_rows and screen_json:
        screen_rows = load_screen_json(screen_json)
        print(f"[INFO] Screenshot Archiver JSON: načteno {len(screen_rows)} záznamů")

    # Sestavení dat a generování
    report_data  = build_report_data(meta_rows, screen_rows, net_rows,
                                     wayback_rows, dupl_rows, revimg_rows)

    print(f"\n[INFO] Generuji reporty...\n")
    md_content   = generate_markdown(report_data)
    html_content = generate_html(report_data)

    md_path, html_path = save_reports(
        md_content, html_content,
        args.output, report_data["timestamp"]
    )

    print(f"\n{'═' * 50}")
    print(f"[HOTOVO] Report vygenerován")
    print(f"[MD]     {md_path}")
    print(f"[HTML]   {html_path}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
