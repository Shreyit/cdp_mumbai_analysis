# CDP Analysis

Extracts **CDP (Carbon Disclosure Project)** questionnaire responses from corporate PDFs and city Excel files, normalizes them into JSON + Excel, builds analysis notebooks and reports, and serves an interactive dashboard on Streamlit.

## Dashboard

**Live dashboard (St. Petersburg): https://cdpanalysis-stpetersburg.streamlit.app/**

Interactive exploration of St. Petersburg's CDP Cities responses — hazard/emissions data, persistent-blank causes, and question-theme breakdowns. Light mode by default.

- `st_petersburg_dashboard.py` — the Streamlit app
- `st_petersburg_config.py` — labels, colours, and the persistent-blank cause mapping (hand-edited only here)
- `streamlit_dashboard_spec.md` — original dashboard spec
- `.streamlit/config.toml` — forces `base = "light"` theme
- `requirements.txt` — `pandas`, `openpyxl`, `streamlit`, `plotly`

## What's in the repo

### Corporate CDP questionnaires (PDF → JSON → Excel)

Three companies share one pipeline cloned from `apple_pdf_to_json.py`. Two physical formats exist for each:

- **Legacy** years (`C`-prefixed codes, e.g. `C6.1`) — the `C` is stripped so `id` is numeric everywhere (`6.1`).
- **New** years (numeric codes, e.g. `7.6.1`) — the CDP "Word version" corporate questionnaire export, which can also cover Water Security, Plastics and Biodiversity modules.

| Company   | Years                          | PDF source                          | Scripts                                            | Outputs                                    |
| --------- | ------------------------------ | ----------------------------------- | -------------------------------------------------- | ------------------------------------------ |
| Apple     | 2021–2025 (2021–23 legacy, 24–25 new) | `apple_cdp_report/`          | `apple_pdf_to_json.py`, `apple_json_to_excel.py`    | `apple_cdp_report/Apple_CDP_*.json`, `Apple_Responses.xlsx` |
| BMW Group | 2021–2025 (2021–23 legacy, 24–25 new) | `BMW_GROUP/`                 | `bmw_pdf_to_json.py`, `bmw_json_to_excel.py`        | `BMW_GROUP/BMW_CDP_*.json`, `BMW_GROUP/BMW_Responses.xlsx` |
| Unilever  | 2020–2024 (2020–23 legacy, 24 new)     | `unilever-cdp-report/`       | `unilever_pdf_to_json.py`, `unilever_json_to_excel.py` | `unilever-cdp-report/Unilever_CDP_*.json`, `unilever-cdp-report/Unilever_Responses.xlsx` |

JSON schema (one file per year):

```json
{
  "year": 2024,
  "source": "….pdf",
  "questions": [
    {
      "id": "7.6.1",
      "parent": "7.6",
      "section": "C7. Environmental performance - Climate Change",
      "question": "Gross global Scope 1 emissions (metric tons CO2e)",
      "row_label": "",
      "response": "55200"
    }
  ]
}
```

Excel workbook columns (long format, one row per question per year):

`str`, `year`, `parent`, `section`, `row_label`, `question`, `response`

### Reports & notebooks

- `Apple_CDP_Analysis.ipynb` — Apple figures 1–6 and tables 1–2 from `Apple_Responses.xlsx`; full notebook of the underlying analysis.
- `Apple_CDP_report.docx` — Apple CDP analysis report.
- `St_petersberg_cdp_analysis.ipynb` + `St. Petersberg CDP report.docx` — St. Petersburg CDP Cities analysis.
- `CDP_Mumbai_Analysis.ipynb` — Mumbai CDP Cities extraction (see below).

### Mumbai CDP Cities

Mumbai is a *city*, so its data lives in the **CDP Cities** dataset. `CDP_Mumbai_Analysis.ipynb`:

1. Installs dependencies (`openpyxl`, `pandas`).
2. Reads a CDP Cities Excel file (one sheet per question, wide format).
3. Keeps only rows where the disclosing organization is Mumbai.
4. Saves Mumbai's answers to a styled Excel workbook.

Configuration is in the notebook's Config cell:

| Setting            | Value                                                                       | Meaning                               |
| ------------------ | --------------------------------------------------------------------------- | ------------------------------------- |
| `INPUT_FILE`     | `cdp_cities_data/2025_Full_Cities_Public_Data_Separated_by_Question.xlsx` | CDP Cities input file                 |
| `MUMBAI_DISC_NO` | `31178`                                                                   | Mumbai's `cdp_disclosing_org_number`  |
| `OUTPUT_FILE`    | `Mumbai_Responses.xlsx`                                                   | Output workbook                       |
| `SKIP_SHEETS`    | `{"Introduction", "Summary"}`                                             | Non-question sheets to ignore         |

`Mumbai_Responses.xlsx` — sheet **"Mumbai Responses"** with columns Question, Question Text, Sub-fields, Mumbai Response. Uses a dark blue header, alternating row shading, and text wrapping.

## Setup

```bash
# 1. Create the environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Run a PDF -> JSON -> Excel pipeline
.venv/bin/python bmw_pdf_to_json.py
.venv/bin/python bmw_json_to_excel.py

# 3. Run the dashboard locally
.venv/bin/streamlit run st_petersburg_dashboard.py
```

## How to run the notebooks

```bash
.venv/bin/jupyter lab CDP_Mumbai_Analysis.ipynb
.venv/bin/jupyter lab Apple_CDP_Analysis.ipynb
```

Run all cells in order.
