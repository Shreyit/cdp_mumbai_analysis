# CDP Mumbai Analysis

Extracts **Mumbai's responses** from the CDP (Carbon Disclosure Project) **Cities** dataset and writes them to a clean, readable Excel workbook.

## Overview

Mumbai is a *city*, so its data lives in the **CDP Cities** dataset (not the States & Regions file). The notebook `CDP_Mumbai_Analysis.ipynb`:

1. Installs dependencies (`openpyxl`, `pandas`).
2. Reads a CDP Cities Excel file (one sheet per question, wide format).
3. Keeps only the rows where the disclosing organization is Mumbai.
4. Saves Mumbai's answers to a styled Excel file.

## Configuration

Edit the Config cell in the notebook:

| Setting | Value | Meaning |
|---|---|---|
| `INPUT_FILE` | `cdp_cities_data/2025_Full_Cities_Public_Data_Separated_by_Question.xlsx` | CDP Cities input file |
| `MUMBAI_DISC_NO` | `31178` | Mumbai's `cdp_disclosing_org_number` |
| `OUTPUT_FILE` | `Mumbai_Responses.xlsx` | Output workbook |
| `SKIP_SHEETS` | `{"Introduction", "Summary"}` | Non-question sheets to ignore |

## How to run

```bash
# 1. Create the environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install pandas openpyxl

# 2. Open and run the notebook
.venv/bin/jupyter lab CDP_Mumbai_Analysis.ipynb
```

Run all cells in order. Step 1 installs dependencies, Step 2 sets the config,
Step 3 extracts Mumbai's rows, and Step 4 writes the output file.

## Output

`Mumbai_Responses.xlsx` — sheet **"Mumbai Responses"** with the columns:

- **Question** — question number (+ row name when present)
- **Question Text** — the question as asked
- **Sub-fields** — numbered response fields (`col1_…`, `col2_…` prefixes stripped)
- **Mumbai Response** — numbered answers

The workbook uses a dark blue header, alternating row shading, and text wrapping
so multi-line responses read cleanly.
