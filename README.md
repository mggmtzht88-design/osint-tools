# OSINT Toolkit

Sada Python nástrojů pro analýzu informačních operací a dezinformací
v rusky psaných médiích a sociálních sítích.

Součást většího OSINT projektu zaměřeného na monitoring a dokumentaci
narativů ruských státních médií a Telegram kanálů.

---

## Nástroje

| Nástroj | Popis |
|---------|-------|
| **RSS Monitor** | Nepřetržitý monitoring ruských RSS zdrojů (TASS, RIA) — alerting při výskytu sledovaných klíčových slov |
| **Keyword Frequency Analyzer** | Statistická analýza frekvence klíčových slov — detekce koordinovaných narativních pushů |
| **Metadata Extractor** | Extrakce EXIF metadat z fotografií — GPS souřadnice, timestamp, zařízení — pro geolokaci a ověřování |
| **Network Mapper** | Vizualizace vztahů mezi zdroji — identifikace narativních hubů a koordinované amplifikace |
| **Screenshot Archiver** | Archivace webového obsahu s timestampem — důkazní řetězec před smazáním stránek |
| **Report Generator** | Agregace výstupů všech nástrojů do strukturovaného reportu (Markdown / HTML) |
| **Translator ru↔en** | Překlad ruština–angličtina přes DeepL API + LibreTranslate (offline režim pro citlivý materiál) |
| **Translator ru↔cs** | Offline překlad ruština–čeština přes Argos Translate — bez odesílání dat na externí servery |
| **Duplicate Detector** | Detekce duplicitního obsahu napříč zdroji |
| **Wayback Checker** | Ověření dostupnosti URL přes Wayback Machine |

---

## Technologie

Python 3 · feedparser · Playwright · networkx · pyvis · Pillow ·
DeepL API · LibreTranslate · Argos Translate · Docker

---

## Kontext

Nástroje jsou vyvíjeny pro nezávislou OSINT analýzu ruských informačních
operací se zaměřením na:

- sledování a dokumentaci dezinformačních narativů
- geolokaci a ověřování vizuálního materiálu
- budování důkazních řetězců pro analytické výstupy
- operační bezpečnost při práci s citlivým zdrojovým materiálem

Citlivý materiál lze zpracovávat výhradně offline — lokální překladové
enginy a izolované úložiště eliminují datový otisk.

---

## Anglická verze

[README in English](README_EN.md)

---

## Autor

[mggmtzht88-design](https://github.com/mggmtzht88-design)
