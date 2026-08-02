"""
================================================================================
  GRI Standards Repository Builder
================================================================================
  Reads every GRI standard PDF in a folder and converts them to structured
  JSON files stored in gri_repo/standards/.

  Run:
      pip install pdfplumber PyMuPDF
      python gri_standards_builder.py

  Output:
      gri_repo/standards/GRI_1_Foundation_2021.json
      gri_repo/standards/GRI_2_General_Disclosures_2021.json
      ...
      gri_repo/index.json   ← master registry
================================================================================
"""

from __future__ import annotations

import os
import re
import json
import datetime
import pdfplumber
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent.parent              # project root
PDF_DIR    = BASE_DIR / "pdfs" / "standards"          # universal/ sector/ topic/ subdirs
REPO_DIR   = BASE_DIR / "gri_repo" / "standards"
INDEX_PATH = BASE_DIR / "gri_repo" / "index.json"

# Known GRI standard metadata (id → pillar, category, effective_date)
STANDARD_META = {
    "GRI 1":   {"pillar": "universal",    "category": "universal", "effective_date": "2023-01-01"},
    "GRI 2":   {"pillar": "universal",    "category": "universal", "effective_date": "2023-01-01"},
    "GRI 3":   {"pillar": "universal",    "category": "universal", "effective_date": "2023-01-01"},
    "GRI 11":  {"pillar": "sector",       "category": "sector",    "effective_date": "2024-01-01"},
    "GRI 12":  {"pillar": "sector",       "category": "sector",    "effective_date": "2024-01-01"},
    "GRI 13":  {"pillar": "sector",       "category": "sector",    "effective_date": "2024-01-01"},
    "GRI 14":  {"pillar": "sector",       "category": "sector",    "effective_date": "2026-01-01"},
    "GRI 101": {"pillar": "environment",  "category": "topic",     "effective_date": "2026-01-01"},
    "GRI 102": {"pillar": "environment",  "category": "topic",     "effective_date": "2026-01-01"},
    "GRI 103": {"pillar": "environment",  "category": "topic",     "effective_date": "2026-01-01"},
    "GRI 201": {"pillar": "economic",     "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 202": {"pillar": "economic",     "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 203": {"pillar": "economic",     "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 204": {"pillar": "economic",     "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 205": {"pillar": "governance",   "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 206": {"pillar": "governance",   "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 207": {"pillar": "governance",   "category": "topic",     "effective_date": "2020-01-01"},
    "GRI 301": {"pillar": "environment",  "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 302": {"pillar": "environment",  "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 303": {"pillar": "environment",  "category": "topic",     "effective_date": "2019-01-01"},
    "GRI 305": {"pillar": "environment",  "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 306": {"pillar": "environment",  "category": "topic",     "effective_date": "2022-01-01"},
    "GRI 308": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 401": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 402": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 403": {"pillar": "social",       "category": "topic",     "effective_date": "2021-01-01"},
    "GRI 404": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 405": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 406": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 407": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 408": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 409": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 410": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 411": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 413": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 414": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 415": {"pillar": "governance",   "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 416": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 417": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
    "GRI 418": {"pillar": "social",       "category": "topic",     "effective_date": "2018-07-01"},
}


# ──────────────────────────────────────────────────────────────────────────────
# PDF HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def extract_full_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber, fallback to PyMuPDF."""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(pages)
    except Exception:
        try:
            import fitz
            doc  = fitz.open(str(pdf_path))
            text = "\n".join(doc[i].get_text() for i in range(len(doc)))
            doc.close()
            return text
        except Exception as e:
            print(f"    [ERROR] Could not extract text: {e}")
            return ""


def extract_page_count(pdf_path: Path) -> int:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            return len(pdf.pages)
    except Exception:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            n   = len(doc)
            doc.close()
            return n
        except Exception:
            return 0


# ──────────────────────────────────────────────────────────────────────────────
# PARSE HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def parse_standard_id_from_filename(filename: str) -> tuple[str, str, str]:
    """
    Returns (standard_id, name, version) from a filename like:
      'GRI 305_ Emissions 2016.pdf'  →  ('GRI 305', 'Emissions', '2016')
    """
    stem = Path(filename).stem
    # Match patterns like "GRI 14_ Mining Sector 2024 V1.1" or "GRI 305_ Emissions 2016"
    # [\d.]+ instead of [\w.]+ so underscore from filename is excluded from the standard ID
    m = re.match(r"(GRI\s+[\d.]+)[_\s]+(.+?)[\s_]+(\d{4}).*", stem, re.I)
    if m:
        sid  = re.sub(r"\s+", " ", m.group(1)).strip()
        name = m.group(2).strip().strip("_").strip()
        ver  = m.group(3).strip()
        return sid, name, ver

    # Fallback: try to find at least the standard ID
    m2 = re.match(r"(GRI\s+[\w.]+)", stem, re.I)
    if m2:
        return m2.group(1).strip(), stem, "unknown"
    return "unknown", stem, "unknown"


def extract_disclosures(text: str, standard_id: str) -> list[dict]:
    """
    GRI PDFs format each disclosure as a heading on ONE line:
      'Disclosure 305-1 Direct (Scope 1) GHG emissions'
    Match that line directly with MULTILINE so ^ and $ work per-line.
    """
    # Clean standard number: "GRI 305" → "305", "GRI 11" → "11"
    num = re.sub(r"[^\d.]", "", standard_id.replace("GRI ", "").split()[0])

    # Primary: "Disclosure 305-1 Some title here"
    primary = re.compile(r"^Disclosure\s+([\d][\d\.\-]+)\s+(.+)$", re.MULTILINE)
    # Fallback for sector codes like "14.6.2  Tailings disposal methods"
    fallback = re.compile(r"^(\d{2,3}\.\d+(?:\.\d+)?)\s{2,}(.+)$", re.MULTILINE)

    seen: set = set()
    disclosures = []

    for pattern in (primary, fallback):
        for m in pattern.finditer(text):
            code  = m.group(1).strip()
            title = m.group(2).strip()
            if code in seen or not code.startswith(num):
                continue
            seen.add(code)
            disclosures.append({
                "code":  code,
                "title": title[:120],
                "type":  "quantitative" if any(
                    w in title.lower()
                    for w in ["gross", "total", "volume", "number", "percentage", "rate", "amount", "metric"]
                ) else "qualitative",
                "requirements": [],
                "guidance":     "",
                "related_sdgs": extract_sdgs(text, code),
            })

    return disclosures


def extract_sdgs(text: str, code: str) -> list[str]:
    """Find SDG references near a disclosure code in the text."""
    idx = text.find(code)
    if idx == -1:
        return []
    window = text[max(0, idx - 200) : idx + 500]
    return list(set(re.findall(r"SDG\s+\d+(?:\.\d+)?", window, re.I)))[:4]


def extract_purpose(text: str) -> str:
    """Extract the 'Topic Standard' or 'Introduction' summary sentence."""
    for heading in ["Introduction\n", "1. Topic management\n", "About this Standard\n"]:
        idx = text.find(heading)
        if idx != -1:
            snippet = text[idx + len(heading) : idx + len(heading) + 600]
            first_para = snippet.split("\n\n")[0].replace("\n", " ").strip()
            if len(first_para) > 30:
                return first_para[:500]
    return ""


# ──────────────────────────────────────────────────────────────────────────────
# FILENAME FILTER — only process GRI standard PDFs, not company reports
# ──────────────────────────────────────────────────────────────────────────────

def is_gri_standard_pdf(filename: str) -> bool:
    return filename.endswith(".pdf") and filename.startswith("GRI ")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN BUILDER
# ──────────────────────────────────────────────────────────────────────────────

def build_standard_json(pdf_path: Path) -> dict | None:
    """Parse one GRI standard PDF and return a structured dict."""
    sid, name, version = parse_standard_id_from_filename(pdf_path.name)
    if sid == "unknown":
        print(f"  [SKIP] Cannot parse standard ID from: {pdf_path.name}")
        return None

    print(f"  [PARSE] {sid} — {name} ({version})")
    text       = extract_full_text(pdf_path)
    page_count = extract_page_count(pdf_path)
    meta       = STANDARD_META.get(sid.split(" V")[0], {})

    disclosures = extract_disclosures(text, sid)
    purpose     = extract_purpose(text)

    return {
        "standard_id":    sid,
        "name":           name,
        "version":        version,
        "effective_date": meta.get("effective_date", ""),
        "category":       meta.get("category", "topic"),
        "pillar":         meta.get("pillar", "unknown"),
        "sector_applicability": ["all"],
        "page_count":     page_count,
        "source_file":    pdf_path.name,
        "purpose":        purpose,
        "disclosures":    disclosures,
        "management_approach": {
            "code":    "3-3",
            "applies": meta.get("category") == "topic",
        },
        "indexed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "raw_text_length": len(text),
    }


def run():
    REPO_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(
        p for p in PDF_DIR.rglob("*.pdf")   # walks universal/ sector/ topic/ subdirs
        if is_gri_standard_pdf(p.name)
    )
    print(f"\n{'='*60}")
    print(f"  GRI Standards Repository Builder")
    print(f"  Found {len(pdf_files)} GRI standard PDFs to process")
    print(f"{'='*60}\n")

    index_entries = []
    built, skipped = 0, 0

    for pdf_path in pdf_files:
        result = build_standard_json(pdf_path)
        if result is None:
            skipped += 1
            continue

        # Filename: GRI_305_Emissions_2016.json
        slug     = result["standard_id"].replace(" ", "_").replace(".", "_")
        out_name = f"{slug}_{result['name'].replace(' ', '_')}_{result['version']}.json"
        out_path = REPO_DIR / out_name

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"    → saved: {out_name}  ({len(result['disclosures'])} disclosures found)")
        built += 1

        index_entries.append({
            "standard_id":    result["standard_id"],
            "name":           result["name"],
            "version":        result["version"],
            "category":       result["category"],
            "pillar":         result["pillar"],
            "effective_date": result["effective_date"],
            "disclosure_count": len(result["disclosures"]),
            "file":           f"standards/{out_name}",
        })

    # Write index.json
    index = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "total_standards": built,
        "standards": sorted(index_entries, key=lambda x: x["standard_id"]),
        "companies": [],   # populated by sustainability_extractor.py runs
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  Done: {built} standards built, {skipped} skipped")
    print(f"  Standards : {REPO_DIR}")
    print(f"  Index     : {INDEX_PATH}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run()
