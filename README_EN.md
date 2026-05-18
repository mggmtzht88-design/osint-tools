# OSINT Toolkit

A collection of Python scripts for open-source intelligence (OSINT) analysis, focused on monitoring information operations and disinformation in Russian-language media.

Part of a larger OSINT research project.

---

## Scripts

| Script | Description |
|--------|-------------|
| **RSS Monitor** | Monitors Russian-language RSS feeds for keyword alerts (30-min cycle) |
| **Keyword Frequency Analyzer** | Statistical analysis of keyword trends from RSS Monitor logs |
| **Metadata Extractor** | Extracts EXIF metadata (GPS, device, timestamp) from photographs |
| **Network Mapper** | Visualises relationships between information sources and narrative hubs |
| **Screenshot Archiver** | Full-page web archival with timestamp for evidence chains |
| **Report Generator** | Aggregates all tool outputs into a structured Markdown/HTML report |
| **Translator ru↔en** | Russian–English translation via DeepL API + LibreTranslate (offline) |
| **Translator ru↔cs** | Offline Czech–Russian translation via Argos Translate |
| **Duplicate Detector** | Detects duplicate content across sources |
| **Wayback Checker** | Checks URL availability via Wayback Machine |

---

## Technologies

Python 3 · feedparser · Playwright · networkx · pyvis · Pillow · DeepL API · LibreTranslate · Argos Translate · Docker

---

## Context

These tools were developed for independent OSINT analysis of Russian-language information operations,
with a focus on disinformation, narrative tracking, and digital evidence preservation.

Operational security is a core design principle — sensitive material can be processed entirely offline
using local translation engines and isolated storage.

---

## Author

[mggmtzht88-design](https://github.com/mggmtzht88-design)
