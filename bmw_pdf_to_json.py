"""
BMW Group CDP Questionnaire PDF -> JSON extraction.
====================================================
Clone of apple_pdf_to_json.py for the BMW Group CDP responses (2021-2025).

Two physical formats exist in BMW_GROUP/:
  * 2021-2023 : legacy "C"-prefixed question codes  (C0.1, C1.1a, C-TO0.7/C-TS0.7)
  * 2024-2025 : new numeric codes                    (1.1, 7.6.1, ...) from the
                CDP Corporate Questionnaire export, which also covers the
                Water Security (C9), Plastics (C10) and Biodiversity (C11)
                modules in addition to Climate Change.

As in the Apple clone, the "C" prefix is stripped for legacy codes so the
`id` field is numeric everywhere (C6.1 -> "6.1"). The one compound code
C-TO0.7/C-TS0.7 is kept verbatim. Output schema matches Apple_CDP_*.json:

    {
      "year": 2024,
      "source": "...pdf",
      "questions": [
        {
          "id": "7.6.1",
          "parent": "7.6",
          "section": "C7. Environmental performance - Climate Change",
          "question": "Gross global Scope 1 emissions (metric tons CO2e)",
          "row_label": "",
          "response": "55200"
        }, ...
      ]
    }
"""

import json
import re
from pathlib import Path

import fitz

BMW_DIR = Path(__file__).resolve().parent / "BMW_GROUP"

FILES = {
    2021: "CDP-Questionaire-2021.pdf",
    2022: "BMW-Group-CDP-2022.pdf",
    2023: "BMW_Group_CDP_Climate_Change_Questionnaire_2023.pdf",
    2024: "BMW-Group-CDP-Climate-and-Water-Security-Questionnaire-2024.pdf",
    2025: "BMW-Group-CDP-Climate-and-Water-Security-Questionnaire-2025.pdf",
}

# ------------------------------------------------------------- noise ------
LEGACY_NOISE = [
    re.compile(r"^BMW AG CDP Climate Change Questionnaire \d{4}.*$"),
    re.compile(r"^Welcome to your CDP Climate Change Questionnaire \d{4}$"),
    re.compile(r"^CDP$"),
    re.compile(r"^Page\s*$"),
    re.compile(r"^Page\s+of\s+\d{1,3}$"),
    re.compile(r"^of \d{1,3}$"),
    re.compile(r"^\d{1,3}$"),
    re.compile(r"^[\u200b\u200c\u200d\ufeff]+$"),
    re.compile(r"^\d{1,3}\s*\.{3,}"),                 # dotted TOC page entries
    re.compile(r"^C\d{1,2}\s*$"),                      # standalone "C0" line
    re.compile(r"^C\d{1,2}\.\d+[a-z]?$"),              # standalone "C0.1" line
    re.compile(r"^C-TO\d+\.\d+/C-TS\d+\.\d+$"),        # standalone compound line
    re.compile(r"^C-TO\d+\.\d+/C-TS\d+\.\d+\s+\(C-.*$"),
]
NEW_NOISE = [
    re.compile(r"^CONFIDENTIAL$"),
    re.compile(r"^BMW AG$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}, \d{1,2}:\d{2} (am|pm)$"),
    re.compile(r"^\d{4} CDP Corporate Questionnaire \d{4}$"),
    re.compile(r"^CDP Corporate Questionnaire \d{4}$"),
    re.compile(r"^(Climate Change, Water Security)$"),
    re.compile(r"^Covering FY \d{4}$"),
    re.compile(r"^Word version$"),
    re.compile(r"^Important: this export excludes unanswered questions$"),
    re.compile(r"^This document is an export of your organization.*$"),
    re.compile(r"^There may be questions or data points.*$"),
    re.compile(r"^Please note that it is your responsibility.*$"),
    re.compile(r"^CDP will not be liable for any failure to do so\.$"),
    re.compile(r"^Terms of disclosure for corporate questionnaire \d{4} - CDP$"),
    re.compile(r"^Read full terms of disclosure$"),
    re.compile(r"^Contents\s*$"),
    re.compile(r"^\d{1,3}\s*$"),
    re.compile(r"^\d{1,3}\s*\.{3,}"),                  # dotted TOC page entries
    re.compile(r"^[CI]\d{1,2}\.\s+[A-Z].*\.{3,}$"),    # dotted TOC section headers
    re.compile(r"^\(\d+\.\d+.*\.{3,}\s*\d*\s*$"),      # dotted TOC question entries
    re.compile(r"^\.{3,}\s*\d*\s*$"),                  # dotted leaders + page no
]

LEGACY_Q = re.compile(r"^\(C(\d+\.\d+[a-z]?)\)\s*(.*)$")
BMW_SPECIAL_Q = re.compile(r"^\((C-[^)]+)\)\s*(.*)$")
NEW_Q = re.compile(r"^\((\d+\.\d+(?:\.\d+)*)\)\s*(.*)$")
SECTION = re.compile(r"^(C\d{1,2})\.\s+(.*)$")
ROW_LABEL = re.compile(r"^[A-Z][A-Za-z0-9&,\-\(\)\.' /]{1,80}$")


def pdf_text(path: Path) -> str:
    doc = fitz.open(str(path))
    return "\n".join(page.get_text() for page in doc)


def is_noise(line: str, noise: list) -> bool:
    s = line.strip().rstrip("\xa0")
    if not s:
        return False
    for pat in noise:
        if pat.match(s):
            return True
    return False


def clean_lines(text: str, year: int) -> list:
    """Return body lines with page furniture removed and whitespace collapsed."""
    noise = LEGACY_NOISE if year <= 2023 else NEW_NOISE
    out = []
    for raw in text.splitlines():
        line = raw.replace("\xa0", " ").strip()
        if not line:
            continue
        if is_noise(line, noise):
            continue
        line = re.sub(r"\s{2,}", " ", line)
        if line:
            out.append(line)
    return out


def find_body_start(lines: list, qpat, legacy: bool) -> int:
    if legacy:
        for i, ln in enumerate(lines):
            if qpat.match(ln) or BMW_SPECIAL_Q.match(ln) or SECTION.match(ln):
                return i
        return 0
    for i, ln in enumerate(lines):
        if SECTION.match(ln) and not re.search(r"\.{3,}", ln):
            return i
    for i, ln in enumerate(lines):
        if qpat.match(ln):
            return i
    return 0


def parent_of(qid: str, legacy: bool) -> str:
    if legacy:
        m = re.match(r"^(\d+\.\d+)[a-z]$", qid)
        return m.group(1) if m else ""
    parts = qid.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else ""


def parse_year(year: int, pdf_name: str) -> dict:
    path = BMW_DIR / pdf_name
    text = pdf_text(path)
    lines = clean_lines(text, year)
    legacy = year <= 2023
    qpat = LEGACY_Q if legacy else NEW_Q

    start = find_body_start(lines, qpat, legacy)
    body = lines[start:]

    questions = []
    current_section = ""
    current = None
    pending_row_label = ""

    def flush():
        nonlocal current
        if current is not None:
            questions.append(current)
            current = None

    for i, ln in enumerate(body):
        sm = SECTION.match(ln)
        if sm:
            current_section = ln
            continue
        qid = None
        qtext = ""
        qm = qpat.match(ln)
        if qm:
            qid, qtext = qm.group(1), qm.group(2).strip()
        elif legacy:
            sm2 = BMW_SPECIAL_Q.match(ln)
            if sm2:
                qid, qtext = sm2.group(1), sm2.group(2).strip()
        if qid is not None:
            flush()
            current = {
                "id": qid,
                "parent": parent_of(qid, legacy),
                "section": current_section,
                "question": qtext,
                "row_label": pending_row_label,
                "response": "",
            }
            continue
        if not legacy and current is not None and ROW_LABEL.match(ln) and \
           not ln.startswith("Select") and not ln.startswith("☑"):
            nxt = body[i + 1] if i + 1 < len(body) else ""
            if qpat.match(nxt):
                pending_row_label = ln
                continue
        if current is not None:
            current["response"] = (current["response"] + "\n" + ln).strip()
    flush()

    return {
        "year": year,
        "source": pdf_name,
        "questions": questions,
    }


def main():
    out_dir = Path(__file__).resolve().parent / "BMW_GROUP"
    for year, pdf_name in FILES.items():
        data = parse_year(year, pdf_name)
        out_path = out_dir / f"BMW_CDP_{year}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        nq = len(data["questions"])
        nchar = sum(len(q["response"]) for q in data["questions"])
        print(f"{year}: {nq:>4} questions, {nchar:>7} response chars -> {out_path.name}")
    print("done")


if __name__ == "__main__":
    main()
