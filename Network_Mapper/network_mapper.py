#!/usr/bin/env python3
"""
OSINT Skript 4c — Network Mapper
Mapuje vazby mezi zdroji na základě sdílených klíčových slov.
Vizualizuje IO sítě jako PNG (statický) a HTML (interaktivní).

Použití:
  python network_mapper.py -l rss_alerts.log          # log ze Skriptu 2
  python network_mapper.py -c vazby.csv               # manuální CSV
  python network_mapper.py -l rss_alerts.log -o /výstup
"""

import os
import sys
import csv
import argparse
import re
from collections import defaultdict
from datetime import datetime

import networkx as nx
import matplotlib
matplotlib.use("Agg")  # Bez GUI — kreslí do souboru, ne na obrazovku
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pyvis.network import Network


# ─────────────────────────────────────────────
# SEKCE 1: Parsování log souboru ze Skriptu 2
# ─────────────────────────────────────────────

def parse_log_file(filepath):
    """
    Načte rss_alerts.log ze Skriptu 2 a vytáhne z něj záznamy.
    Každý záznam obsahuje: zdroj, klíčová slova, titulek, URL.

    Formát logu:
    ======...
    [ALERT] datum čas
    Zdroj:      TASS
    Klíčová slova: СВО
    Titulek:    ...
    Publikováno:...
    URL:        ...
    ======...
    """
    if not os.path.isfile(filepath):
        print(f"[CHYBA] Soubor nenalezen: {filepath}")
        sys.exit(1)

    records = []
    current = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Začátek nového záznamu
            if line.startswith("[ALERT]"):
                current = {"datum": "", "zdroj": "", "klic_slova": [], "titulek": "", "url": ""}
                # Vytáhne datum z řádku "[ALERT] 2026-05-07 23:30:13"
                match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line)
                if match:
                    current["datum"] = match.group()

            elif line.startswith("Zdroj:") and current:
                current["zdroj"] = line.replace("Zdroj:", "").strip()

            elif line.startswith("Klíčová slova:") and current:
                # Klíčová slova mohou být oddělena čárkou
                kw_str = line.replace("Klíčová slova:", "").strip()
                current["klic_slova"] = [k.strip() for k in kw_str.split(",")]

            elif line.startswith("Titulek:") and current:
                current["titulek"] = line.replace("Titulek:", "").strip()

            elif line.startswith("URL:") and current:
                current["url"] = line.replace("URL:", "").strip()

            # Konec záznamu — uloží ho pokud má zdroj
            elif line.startswith("=" * 10) and current.get("zdroj"):
                records.append(current)
                current = {}

    print(f"[INFO] Načteno záznamů z logu: {len(records)}")
    return records


# ─────────────────────────────────────────────
# SEKCE 2: Parsování manuálního CSV
# ─────────────────────────────────────────────

def parse_manual_csv(filepath):
    """
    Načte manuální CSV s vazbami.
    Očekávaný formát sloupců: zdroj, cil, typ_vazby
    Příklad:
      TASS,RIA,citace
      TASS,RT,sdilene_kw
    """
    if not os.path.isfile(filepath):
        print(f"[CHYBA] Soubor nenalezen: {filepath}")
        sys.exit(1)

    edges = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges.append({
                "zdroj": row.get("zdroj", "").strip(),
                "cil": row.get("cil", "").strip(),
                "typ": row.get("typ_vazby", "vazba").strip(),
                "pocet": int(row.get("pocet", 1))
            })

    print(f"[INFO] Načteno vazeb z CSV: {len(edges)}")
    return edges


# ─────────────────────────────────────────────
# SEKCE 3: Sestavení sítě vazeb z log záznamů
# ─────────────────────────────────────────────

def build_edges_from_log(records):
    """
    Z log záznamů sestaví seznam vazeb mezi zdroji.

    Logika:
    - Pokud dva různé zdroje sdílejí stejné klíčové slovo → vazba "sdilene_kw"
    - Síla vazby = počet sdílených klíčových slov

    Vrátí seznam: [{zdroj, cil, typ, pocet, klic_slova}, ...]
    """
    # Sestaví slovník: klíčové slovo → seznam zdrojů které ho použily
    kw_to_sources = defaultdict(set)
    for record in records:
        for kw in record["klic_slova"]:
            if kw:
                kw_to_sources[kw].add(record["zdroj"])

    # Pro každé klíčové slovo najde všechny páry zdrojů
    edge_data = defaultdict(lambda: {"pocet": 0, "klic_slova": set()})

    for kw, sources in kw_to_sources.items():
        sources = list(sources)
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                # Seřazený pár aby TASS-RIA a RIA-TASS byly stejná vazba
                pair = tuple(sorted([sources[i], sources[j]]))
                edge_data[pair]["pocet"] += 1
                edge_data[pair]["klic_slova"].add(kw)

    # Převede na seznam slovníků
    edges = []
    for (zdroj, cil), data in edge_data.items():
        edges.append({
            "zdroj": zdroj,
            "cil": cil,
            "typ": "sdilene_kw",
            "pocet": data["pocet"],
            "klic_slova": ", ".join(sorted(data["klic_slova"]))
        })

    print(f"[INFO] Sestaveno vazeb ze sdílených klíčových slov: {len(edges)}")
    return edges


# ─────────────────────────────────────────────
# SEKCE 4: Sestavení NetworkX grafu
# ─────────────────────────────────────────────

def build_graph(edges):
    """
    Sestaví NetworkX graf z vazeb.
    Uzly = zdroje, hrany = vazby se silou (počtem sdílení).
    """
    G = nx.Graph()

    for edge in edges:
        zdroj = edge["zdroj"]
        cil = edge["cil"]
        pocet = edge.get("pocet", 1)
        typ = edge.get("typ", "vazba")
        klic_slova = edge.get("klic_slova", "")

        # Přidá hranu — pokud už existuje, zvýší váhu
        if G.has_edge(zdroj, cil):
            G[zdroj][cil]["weight"] += pocet
        else:
            G.add_edge(zdroj, cil, weight=pocet, typ=typ, klic_slova=klic_slova)

    # Přidá uzlům atribut "stupen" — počet přímých vazeb
    for node in G.nodes():
        G.nodes[node]["degree"] = G.degree(node)

    print(f"[INFO] Graf: {G.number_of_nodes()} uzlů, {G.number_of_edges()} hran")
    return G


# ─────────────────────────────────────────────
# SEKCE 5: PNG vizualizace (matplotlib)
# ─────────────────────────────────────────────

def save_png(G, output_dir, timestamp_str):
    """
    Uloží statický PNG graf.
    Velikost uzlu odpovídá počtu vazeb (důležitější uzly jsou větší).
    Tloušťka hrany odpovídá síle vazby.
    """
    if G.number_of_nodes() == 0:
        print("[VAROVÁNÍ] Graf je prázdný, PNG nebude vytvořen.")
        return None

    fig, ax = plt.subplots(figsize=(14, 10))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Rozložení uzlů — spring_layout simuluje fyzikální odpuzování
    # seed zajistí stejné rozložení při každém spuštění
    pos = nx.spring_layout(G, weight="weight", seed=42, k=2.0)

    # Velikost uzlů podle počtu vazeb
    node_sizes = [300 + G.nodes[n]["degree"] * 200 for n in G.nodes()]

    # Barvy uzlů podle počtu vazeb (čím více vazeb, tím světlejší)
    degrees = [G.nodes[n]["degree"] for n in G.nodes()]
    max_deg = max(degrees) if degrees else 1

    node_colors = []
    for d in degrees:
        intensity = 0.3 + 0.7 * (d / max_deg)
        node_colors.append((0.2, intensity * 0.6, intensity))

    # Tloušťka hran podle váhy
    edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_weight = max(edge_weights) if edge_weights else 1
    edge_widths = [1 + 4 * (w / max_weight) for w in edge_weights]

    # Kreslení
    nx.draw_networkx_edges(G, pos, width=edge_widths,
                           edge_color="#4a9eff", alpha=0.6, ax=ax)
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes,
                           node_color=node_colors, alpha=0.9, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=9,
                            font_color="white", font_weight="bold", ax=ax)

    # Popisky hran — zobrazí klíčové slovo pokud je jen jedno
    edge_labels = {}
    for u, v, data in G.edges(data=True):
        kw = data.get("klic_slova", "")
        # Zobrazí jen pokud je kratší než 20 znaků (přehlednost)
        if kw and len(kw) < 20:
            edge_labels[(u, v)] = kw

    if edge_labels:
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                     font_size=7, font_color="#aaaaaa", ax=ax)

    ax.set_title("OSINT Network Map — Vazby mezi zdroji",
                 color="white", fontsize=14, pad=20)
    ax.axis("off")

    # Legenda
    legend_elements = [
        mpatches.Patch(color="#4a9eff", alpha=0.6, label="Sdílené klíčové slovo"),
    ]
    ax.legend(handles=legend_elements, loc="lower left",
              facecolor="#2a2a4a", labelcolor="white", fontsize=9)

    filename = f"network_map_{timestamp_str}.png"
    filepath = os.path.join(output_dir, filename)
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e", edgecolor="none")
    plt.close()

    print(f"[✓] PNG uloženo: {filename}")
    return filepath


# ─────────────────────────────────────────────
# SEKCE 6: HTML vizualizace (pyvis — interaktivní)
# ─────────────────────────────────────────────

def save_html(G, output_dir, timestamp_str):
    """
    Uloží interaktivní HTML graf.
    Uzly lze přetahovat, přibližovat, klikat na ně.
    """
    if G.number_of_nodes() == 0:
        print("[VAROVÁNÍ] Graf je prázdný, HTML nebude vytvořen.")
        return None

    # Vytvoří pyvis síť — directed=False = neorientovaný graf
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        notebook=False
    )

    # Fyzikální simulace — Barnes-Hut je rychlý pro střední sítě
    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=150,
        spring_strength=0.05,
        damping=0.09
    )

    # Přidá uzly s velikostí podle stupně
    max_deg = max([G.nodes[n]["degree"] for n in G.nodes()], default=1)

    for node in G.nodes():
        degree = G.nodes[node]["degree"]
        size = 15 + (degree / max_deg) * 35

        # Tooltip zobrazí při najetí myší
        title = f"<b>{node}</b><br>Počet vazeb: {degree}"

        net.add_node(
            node,
            label=node,
            size=size,
            title=title,
            color={
                "background": "#2a7fff" if degree > max_deg / 2 else "#1a5fbf",
                "border": "#4a9eff",
                "highlight": {"background": "#ff6b35", "border": "#ff9c6e"}
            }
        )

    # Přidá hrany
    max_weight = max([G[u][v]["weight"] for u, v in G.edges()], default=1)

    for u, v, data in G.edges(data=True):
        weight = data.get("weight", 1)
        width = 1 + 5 * (weight / max_weight)
        kw = data.get("klic_slova", "")

        title = f"Sdílená klíčová slova: {kw}<br>Počet: {weight}"

        net.add_edge(u, v, width=width, title=title,
                     color={"color": "#4a9eff", "opacity": 0.7})

    filename = f"network_map_{timestamp_str}.html"
    filepath = os.path.join(output_dir, filename)
    net.save_graph(filepath)

    print(f"[✓] HTML uloženo: {filename}")
    return filepath


# ─────────────────────────────────────────────
# SEKCE 7: Uložení CSV s vazbami
# ─────────────────────────────────────────────

def save_edges_csv(edges, output_dir, timestamp_str):
    """
    Uloží seznam vazeb do CSV pro další zpracování (Skript 5).
    """
    filename = f"network_edges_{timestamp_str}.csv"
    filepath = os.path.join(output_dir, filename)

    fieldnames = ["zdroj", "cil", "typ", "pocet", "klic_slova"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edge in edges:
            # Zajistí že všechny klíče existují
            row = {k: edge.get(k, "") for k in fieldnames}
            writer.writerow(row)

    print(f"[✓] CSV vazeb uloženo: {filename}")
    return filepath


# ─────────────────────────────────────────────
# SEKCE 8: Hlavní funkce
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OSINT Skript 4c — Network Mapper"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-l", "--log",
        help="Log soubor ze Skriptu 2 (rss_alerts.log)"
    )
    group.add_argument(
        "-c", "--csv",
        help="Manuální CSV s vazbami (sloupce: zdroj, cil, typ_vazby, pocet)"
    )

    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Složka pro uložení výstupů (výchozí: aktuální složka)"
    )

    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n[INFO] Výstupní složka: {args.output}")

    # Načtení dat podle zdroje
    if args.log:
        print(f"[INFO] Vstup: log soubor → {args.log}")
        records = parse_log_file(args.log)
        edges = build_edges_from_log(records)
    else:
        print(f"[INFO] Vstup: manuální CSV → {args.csv}")
        edges = parse_manual_csv(args.csv)

    if not edges:
        print("[INFO] Žádné vazby nenalezeny. Zkontroluj vstupní data.")
        sys.exit(0)

    # Sestavení grafu
    G = build_graph(edges)

    # Výstupy
    print(f"\n[INFO] Generuji vizualizace...\n")
    save_png(G, args.output, timestamp_str)
    save_html(G, args.output, timestamp_str)
    save_edges_csv(edges, args.output, timestamp_str)

    # Shrnutí — nejdůležitější uzly (nejvíce vazeb)
    print(f"\n{'═' * 50}")
    print(f"[HOTOVO] Graf: {G.number_of_nodes()} zdrojů, {G.number_of_edges()} vazeb")
    print(f"\n[TOP UZLY podle počtu vazeb:]")
    sorted_nodes = sorted(G.nodes(), key=lambda n: G.nodes[n]["degree"], reverse=True)
    for node in sorted_nodes[:10]:  # Top 10
        print(f"  {G.nodes[node]['degree']:3d} vazeb — {node}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
