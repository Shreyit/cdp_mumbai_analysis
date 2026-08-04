"""
Apple CDP Questionnaire PDF -> JSON extraction.
===============================================
Parses Apple's corporate CDP Climate Change questionnaires (2021-2024) and
the CDP Corporate questionnaire (2025) into one JSON file per year.

Two different physical formats exist in this folder:
  * 2021-2023 : the legacy "C"-prefixed question codes  (C0.1, C6.1a, ...)
  * 2024-2025 : the new numeric codes                    (1.1, 7.6.1, ...)

For 2021-2023 the "C" prefix is stripped so the output `id` field is a plain
numeric code everywhere (e.g. C6.1 -> "6.1", C6.1a -> "6.1a"). This keeps the
`id` column consistent with the 2024/2025 numbering style.

The new-format (2024-25) questionnaires nest sub-fields below parent
questions (7.6 -> 7.6.1 -> 7.6.1.1) and repeat those fields once per table
row. To keep one JSON file useful for both formats, every code occurrence is
kept as its own record, and each record also carries the `parent` id of the
closest two-part question (e.g. 7.6.1.1 -> parent 7.6) plus the `row_label`
of the repeating-table row it belongs to (e.g. "Purchased goods and
services"), when one can be inferred. Legacy years set `parent` from the
letter-suffix (6.1a -> 6.1) and leave `row_label` empty.

Output schema (one JSON file per year):

    {
      "year": 2024,
      "source": "Apple_CDP-Climate-Change-Questionnaire_2024.pdf",
      "questions": [
        {
          "id": "7.6.1",
          "parent": "7.6",
          "section": "C7. ...",
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

APPLE_DIR = Path(__file__).resolve().parent / "apple_cdp_report"

FILES = {
    2021: "Apple_CDP-Climate-Change-Questionnaire_2021.pdf",
    2022: "Apple_CDP-Climate-Change-Questionnaire_2022.pdf",
    2023: "Apple_CDP-Climate-Change-Questionnaire_2023.pdf",
    2024: "Apple_CDP-Climate-Change-Questionnaire_2024.pdf",
    2025: "Apple_CDP-Corporate-Questionnaire_2025.pdf",
}

# ----------------------------------------------------------------- noise ---
LEGACY_NOISE = [
    re.compile(r"^Apple Inc\.( - Climate Change \d{4})?$"),
    re.compile(r"^CDP$"),
    re.compile(r"^Page\s*$"),
    re.compile(r"^Page\s+of\s+\d{1,3}$"),
    re.compile(r"^of \d{1,3}$"),
    re.compile(r"^\d{1,3}$"),
    re.compile(r"^C\d{1,2}\s*$"),
    re.compile(r"^C\d{1,2}\.\d+[a-z]?$"),
    re.compile(r"^[\u200b\u200c\u200d\ufeff]+$"),
    re.compile(r"^\d{1,3}\s*\.{3,}"),            # dotted TOC page entries
]
NEW_NOISE = [
    re.compile(r"^Apple(,? Inc\.)?$"),
    re.compile(r"^Apple, Inc\s*$"),
    re.compile(r"^\d{4} CDP (Corporate )?Questionnaire$"),
    re.compile(r"^Terms of disclosure for corporate questionnaire \d{4} - CDP$"),
    re.compile(r"^Contents\s*$"),
    re.compile(r"^\d{1,3}\s*$"),
    re.compile(r"^[CI]\d{1,2}\.\s+[A-Z].*\.{3,}$"),   # TOC section headers (dotted)
]

LEGACY_Q = re.compile(r"^\(C(\d+\.\d+[a-z]?)\)\s*(.*)$")
NEW_Q = re.compile(r"^\((\d+\.\d+(?:\.\d+)*)\)\s*(.*)$")
SECTION = re.compile(r"^(C\d{1,2})\.\s+(.*)$")
# A line that looks like a repeating-table row label: short, no punctuation,
# not a "Select from:" instruction or a checkbox value.
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
    """Skip the TOC / front matter.

    Legacy years (2021-23) have no TOC: their body begins at the first
    section header (index 0 of the cleaned lines).
    New-format years (2024-25) start with a TOC that repeats every section
    header once; the body is the LAST occurrence of each header, so we scan
    the section headers backwards and pick the one followed by a question.
    """
    if legacy:
        for i, ln in enumerate(lines):
            if qpat.match(ln) or SECTION.match(ln):
                return i
        return 0
    # New format: the TOC repeats every section header WITH dotted leaders.
    # The body begins at the first section header WITHOUT dotted leaders.
    for i, ln in enumerate(lines):
        if SECTION.match(ln) and not re.search(r"\.{3,}", ln):
            return i
    for i, ln in enumerate(lines):
        if qpat.match(ln):
            return i
    return 0


def parent_of(qid: str, legacy: bool) -> str:
    if legacy:
        # "6.1a" -> "6.1"
        m = re.match(r"^(\d+\.\d+)[a-z]$", qid)
        return m.group(1) if m else ""
    parts = qid.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else ""


def parse_year(year: int, pdf_name: str) -> dict:
    path = APPLE_DIR / pdf_name
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
        qm = qpat.match(ln)
        if qm:
            flush()
            qid = qm.group(1)
            qtext = qm.group(2).strip()
            current = {
                "id": qid,
                "parent": parent_of(qid, legacy),
                "section": current_section,
                "question": qtext,
                "row_label": pending_row_label,
                "response": "",
            }
            continue
        # Row label capture (new-format repeating tables only): a short
        # capitalised line immediately followed by a question marker becomes
        # that marker's (and any following same-block marker's) row_label.
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
    out_dir = Path(__file__).resolve().parent / "apple_cdp_report"
    for year, pdf_name in FILES.items():
        data = parse_year(year, pdf_name)
        out_path = out_dir / f"Apple_CDP_{year}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        nq = len(data["questions"])
        nchar = sum(len(q["response"]) for q in data["questions"])
        print(f"{year}: {nq:>4} questions, {nchar:>7} response chars -> {out_path.name}")
    print("done")


if __name__ == "__main__":
    main()
