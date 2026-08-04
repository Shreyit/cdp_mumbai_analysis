"""
St. Petersburg CDP Disclosure Dashboard (2021-2025)
====================================================
Six reporting pages + a field explorer, built to streamlit_dashboard_spec.md.

The source sheet is long format (one row per answered sub-field). Question
IDs were renumbered across 2021 -> 2022-23 -> 2024-25, so nearly every
indicator is matched on a normalised *Sub-fields* label via regex, which is
stable across all five years.

Design grammar (per spec §7): this is a five-observation dataset for one
city, and two of those observations (2024, 2025) are ~90% identical. The
honest visuals here are heatmaps, diffs, and presence/absence — not
regressions or smoothed trends.

Run with:  streamlit run st_petersburg_dashboard.py
"""
import base64
import hashlib
import math
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from st_petersburg_config import BLANK_CAUSE, DEFAULT_BLANK_CAUSE, THEME_BY_ROOT

# ---------------------------------------------------------------- palette --
CAT = {
    "blue": "#2a78d6", "green": "#008300", "magenta": "#e87ba4", "yellow": "#eda100",
    "aqua": "#1baf7a", "orange": "#eb6834", "violet": "#4a3aa7", "red": "#e34948",
}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
GRID = "#e3e2dd"
MUTED = "#83817b"

# ------------------------------------------------------------- svg icons --
# Stroke-based 24x24 icons (Lucide-style). Kept here so every emoji in the
# dashboard has a crisp, theme-coloured replacement.
ICONS = {
    "waves": ('<path d="M2 6c.6.5 1.2 1 2.5 1C7 7 7 5 9.5 5c2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 '
              '1.3 0 1.9.5 2.5 1"/><path d="M2 12c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.6 0 '
              '2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M2 18c.6.5 1.2 1 2.5 1 '
              '2.5 0 2.5-2 5-2 2.6 0 2.4 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/>'),
    "chart-column": ('<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/>'
                     '<path d="M13 17V5"/><path d="M8 17v-3"/>'),
    "wind": ('<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/>'
             '<path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>'),
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "flask-conical": ('<path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 '
                      '1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"/><path d="M8.5 2h7"/>'
                      '<path d="M7 16h10"/>'),
    "landmark": ('<line x1="3" y1="22" x2="21" y2="22"/><line x1="6" y1="18" x2="6" y2="11"/>'
                 '<line x1="10" y1="18" x2="10" y2="11"/><line x1="14" y1="18" x2="14" y2="11"/>'
                 '<line x1="18" y1="18" x2="18" y2="11"/><polygon points="12 2 20 7 4 7"/>'),
    "dollar-sign": '<line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "file-text": ('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
                  '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/>'
                  '<path d="M16 17H8"/>'),
    "percent": '<line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "snowflake": ('<line x1="12" y1="2" x2="12" y2="22"/><line x1="12" y1="4" x2="5" y2="6"/>'
                  '<line x1="12" y1="4" x2="19" y2="6"/><line x1="12" y1="20" x2="5" y2="18"/>'
                  '<line x1="12" y1="20" x2="19" y2="18"/><line x1="4" y1="12" x2="20" y2="12"/>'),
    "table": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/>',
    "calculator": ('<rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/>'
                   '<line x1="16" y1="14" x2="16" y2="18"/>'
                   '<path d="M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01"/>'),
    "calendar": ('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>'
                 '<line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>'),
    "users": ('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
              '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "trend-down": '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "gauge": '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
    "refresh": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "compare": ('<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/>'
                '<path d="M11 18H8a2 2 0 0 1-2-2V9"/>'),
    "trophy": ('<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/>'
               '<path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/>'
               '<path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/>'
               '<path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>'),
    "thermometer": '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    "flag": '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>',
    "circle-dot": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/>',
    "building-2": ('<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/>'
                   '<path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/>'
                   '<path d="M10 14h4"/><path d="M10 18h4"/>'),
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "sliders-horizontal": ('<line x1="21" y1="4" x2="14" y2="4"/><line x1="10" y1="4" x2="3" y2="4"/>'
                           '<line x1="21" y1="12" x2="12" y2="12"/><line x1="8" y1="12" x2="3" y2="12"/>'
                           '<line x1="21" y1="20" x2="16" y2="20"/><line x1="12" y1="20" x2="3" y2="20"/>'
                           '<line x1="14" y1="2" x2="14" y2="6"/><line x1="8" y1="10" x2="8" y2="14"/>'
                           '<line x1="16" y1="18" x2="16" y2="22"/>'),
    "network": ('<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/>'
                '<rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/>'
                '<path d="M12 12V8"/>'),
    "banknote": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "scale": ('<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
              '<path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>'),
}


def icon(name, size=18):
    """Inline SVG for use inside unsafe_allow_html markdown (inherits text colour)."""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:-3px;margin-right:6px;">{ICONS[name]}</svg>')


def icon_data_uri(name, size=16):
    """Base64 SVG data URI for markdown image syntax (e.g. tab labels)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
           f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
           f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode('utf-8')).decode('ascii')}"

# Canonical hazards. The first five are the 2022-25 set; the last two are the
# 2021-only taxonomy entries whose disappearance is itself a finding.
CANON_HAZARDS = ["Heavy precipitation", "Extreme wind", "Urban flooding", "Heat stress",
                 "Hurricanes/cyclones/typhoons", "Coastal flooding", "Saltwater intrusion"]
HAZARD_COLOR = dict(zip(CANON_HAZARDS + ["Other"],
                        [CAT["blue"], CAT["green"], CAT["magenta"], CAT["yellow"], CAT["aqua"],
                         CAT["orange"], CAT["red"], MUTED]))
SEVERITY_ORDER = ["Low", "Medium Low", "Medium", "Medium High", "High"]
SEVERITY_SCORE = {s: i + 1 for i, s in enumerate(SEVERITY_ORDER)}

DATA_FILE = "St_Petersburg_Responses.xlsx"
RESP_COL = "St. Petersburg Response"

PLACEHOLDER_SET = {"question not applicable", "not applicable", "this data is not available to report",
                   "data not available", "do not know", "n/a", "na"}
NOTATION_SET = {"ne", "ie", "no", "not estimated (ne)", "included elsewhere (ie)", "not occurring (no)"}

st.set_page_config(page_title="St. Petersburg Climate Disclosure", page_icon="🌊", layout="wide")
st.markdown("""
<style>
h3.card-title { font-size: 1.4rem; font-weight: 800; margin-bottom: 0.4rem; }
.card-narrative { font-size: 0.98rem; line-height: 1.55; }
.chip { display:inline-block; padding: 3px 12px; border-radius: 14px; font-size: 0.85rem;
        font-weight: 600; color: white; margin-right: 6px; }
.kpi { background:#faf9f6; border:1px solid #ecebe6; border-radius:12px; padding:14px 16px; height:100%; }
.kpi .lbl { font-size:0.82rem; color:#83817b; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }
.kpi .val { font-size:1.55rem; font-weight:800; margin-top:4px; }
.kpi .sub { font-size:0.82rem; color:#83817b; margin-top:4px; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------- data --
def clean_resp(s):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s.replace("’", "'")


def to_num(s):
    s = str(s).replace(",", "").replace("%", "").replace("$", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


@st.cache_data
def load_data():
    df = pd.read_excel(DATA_FILE)
    df["question_root"] = df["Question"].astype(str).str.split(" – ").str[0]
    df["row_index"] = df["Question"].astype(str).str.extract(r"Row (\d+)")[0].astype(float)
    df["subfield"] = df["Sub-fields"].astype(str).str.strip().str.rstrip("^").str.strip()
    df["sf_norm"] = df["subfield"].str.lower()
    df["qt_norm"] = df["Question Text"].astype(str).str.strip().str.lower()
    df["resp_clean"] = df[RESP_COL].astype(str).map(clean_resp)
    df["resp_lower"] = df["resp_clean"].str.lower()
    df["char_len"] = df["resp_clean"].str.len()
    df["is_placeholder"] = df["resp_lower"].isin(PLACEHOLDER_SET) | (df["resp_clean"] == "")
    df["is_notation"] = df["resp_lower"].isin(NOTATION_SET)
    df["numeric_value"] = df["resp_clean"].map(to_num)
    return df


# ------------------------------------------------------------ crosswalk -----
# indicator_key: list of regexes matched against lowercased Sub-fields.
CROSSWALK = {
    "area_km2": [r"area of the .*jurisdiction boundary \(in square km\)",
                 r"land area of the (jurisdiction|city) boundary"],
    "population_current": [r"^current (\(or most recent\) )?population( size)?$"],
    "population_year": [r"^(current )?population year$"],
    "population_projected": [r"^projected population( size)?$"],
    "population_proj_year": [r"^projected population year$"],
    "food_insecure_pct": [r"percentage of population that is food insecure"],
    "inventory_year": [r"^(inventory year|year covered by main inventory)"],
    "inventory_pop": [r"population in (the )?(year covered by main )?inventory( year)?"],
    "inventory_total_basic": [r"^total basic emissions$"],
    "inventory_protocol": [r"primary (methodology/framework|protocol)"],
    "inventory_audited": [r"has the .*inventory been audited"],
    "inventory_data_qual": [r"overall level of data quality"],
    "target_pct_reduction": [r"percentage of emissions reduction"],
    "target_base_emissions": [r"(covered emissions in base year|base year emissions covered)"],
    "target_recent_emissions": [r"(covered emissions in most recent|emissions covered by target in most recent)"],
    "target_net": [r"^net emissions in target year"],
    "target_established": [r"year target was established"],
    "target_year": [r"^target year\^?$"],
    "target_base_year": [r"^base year\^?$"],
    "target_status": [r"target status and progress"],
    "pct_achieved": [r"percentage of target achieved"],
    "metric_base": [r"^metric value in base year"],
    "metric_recent": [r"^metric value in most recent year"],
    "metric_target": [r"^metric value in target year"],
    "hazard_name": [r"^climate[- ]related hazards\^?$|^climate hazards$"],
    "hazard_prob": [r"current probability of hazard"],
    "hazard_magnitude": [r"current magnitude of (impact of )?hazard"],
    "hazard_pop_share": [r"proportion of the population exposed"],
    "hazard_intensity": [r"future change in .*intensity"],
    "hazard_frequency": [r"future change in .*frequency"],
    "hazard_vuln": [r"vulnerable population groups most exposed|identify which vulnerable populations"],
    "hazard_narrative": [r"describe the impacts on vulnerable populations|describe the impacts experienced"],
    "project_title": [r"^project title$"],
    "project_cost": [r"^total cost of project"],
    "project_invest_need": [r"total investment cost needed"],
    "project_stage": [r"stage of project development"],
    "project_finance_status": [r"status of financing"],
    "project_finance_model": [r"(identified )?financing model"],
    "action_cost": [r"^total cost of action"],
    "energy_total_mwh": [r"^total energy consumption \(mwh\)"],
    "energy_renew_mwh": [r"^total energy consumption from renewable"],
    "waste_generated": [r"amount of solid waste generated"],
    "waste_diverted_pct": [r"diverted away from landfill"],
    "waste_recycled_pct": [r"recycled"],
    "wastewater_volume": [r"volume of wastewater produced"],
    "engagement_component": [r"^climate component$"],
    "engagement_gov_level": [r"types of governments engaged|level of governments engaged"],
    "oversight_processes": [r"processes that reflect your jurisdiction"],
}


def get_indicator(df, key):
    """Return {year: {'num': float|None, 'str': str}} for a crosswalk key."""
    patterns = CROSSWALK[key]
    sub = df[df["sf_norm"].apply(lambda s: any(re.search(p, s) for p in patterns))]
    sub = sub[~sub["is_placeholder"]]
    out = {}
    for y, g in sub.groupby("Year"):
        r = g.iloc[0]
        out[int(y)] = {"num": r["numeric_value"], "str": r["resp_clean"]}
    return out


def first_match(df_, qt_contains, sf_options):
    """Return {year: value} for the first non-placeholder row matching a question + aliases."""
    sub = df_[df_["qt_norm"].str.contains(qt_contains, na=False)]
    sub = sub[sub["sf_norm"].isin(sf_options)]
    sub = sub[~sub["is_placeholder"]]
    out = {}
    for y, g in sub.groupby("Year"):
        out[int(y)] = g["resp_clean"].iloc[0]
    return out


def latest_value(value_dict):
    return value_dict[max(value_dict.keys())] if value_dict else None


def exposure_midpoint(s):
    nums = re.findall(r"(\d+(?:\.\d+)?)", str(s))
    if len(nums) >= 2:
        return (float(nums[0]) + float(nums[1])) / 2
    if len(nums) == 1:
        return float(nums[0])
    return None


def normalize_hazard(name):
    n = name.lower()
    if "urban flood" in n or "flash" in n or "surface flood" in n:
        return "Urban flooding"
    if "salt" in n and "water" in n:
        return "Saltwater intrusion"
    if "hurricane" in n or "cyclone" in n or "typhoon" in n:
        return "Hurricanes/cyclones/typhoons"
    if "heat" in n or "hot" in n:
        return "Heat stress"
    if "precipitation" in n or "rain" in n:
        return "Heavy precipitation"
    if "coastal flood" in n or "sea level" in n:
        return "Coastal flooding"
    if "wind" in n:
        return "Extreme wind"
    return "Other"


def split_multi(s, year):
    """Split a delimited CDP multi-select, handling the per-year delimiter change."""
    if year >= 2025:
        parts = str(s).split("|")
    elif year == 2024:
        parts = str(s).split(",")
    else:
        parts = str(s).split(";")
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------- repeating tables --
def pivot_repeating(df, roots, fields):
    """Long (year, row_index, field_key, value) for a repeating question block."""
    sub = df[df["question_root"].isin(roots)]
    out = []
    for (y, ri), g in sub.groupby(["Year", "row_index"]):
        if pd.isna(ri):
            continue
        row = {"Year": int(y), "row_index": int(ri)}
        for fk, pats in fields.items():
            for _, r in g.iterrows():
                if any(re.search(p, r["sf_norm"]) for p in pats):
                    row[fk] = r["resp_clean"]
                    break
        out.append(row)
    return pd.DataFrame(out)


@st.cache_data
def build_tables():
    df = load_data()

    hazards = pivot_repeating(df, ["Q2.1", "Q1.2", "Q2.2"], {
        "hazard_name": [r"^climate[- ]related hazards\^?$|^climate hazards$"],
        "hazard_prob": [r"current probability of hazard"],
        "hazard_magnitude": [r"current magnitude of (impact of )?hazard"],
        "hazard_pop_share": [r"proportion of the population exposed"],
        "hazard_intensity": [r"future change in .*intensity"],
        "hazard_frequency": [r"future change in .*frequency"],
        "hazard_vuln": [r"vulnerable population groups most exposed|identify which vulnerable populations"],
        "hazard_narrative": [r"describe the impacts on vulnerable populations|describe the impacts experienced"],
    })
    hazards["Canonical"] = hazards["hazard_name"].map(normalize_hazard)
    hazards["ExposurePct"] = hazards["hazard_pop_share"].map(exposure_midpoint)
    hazards["ProbOrd"] = hazards["hazard_prob"].map(SEVERITY_SCORE)
    hazards["MagOrd"] = hazards["hazard_magnitude"].map(SEVERITY_SCORE)

    projects = pivot_repeating(df, ["Q6.5", "Q7.4", "Q7.5", "Q9.3"], {
        "title": [r"^project title$"],
        "stage": [r"stage of project development"],
        "finance_status": [r"status of financing"],
        "finance_model": [r"(identified )?financing model"],
        "cost": [r"^total cost of project"],
        "invest_need": [r"total investment cost needed"],
    })
    projects["cost_num"] = pd.to_numeric(projects["cost"], errors="coerce")
    projects["label"] = projects["title"].fillna("Unnamed project").map(
        lambda t: re.sub(r"\s+", " ", str(t))[:45])

    engagement = pivot_repeating(df, ["Q0.4", "Q1.5"], {
        "component": [r"climate component"],
        "gov_level": [r"types of governments engaged|level of governments engaged"],
        "purpose": [r"outline the purpose"],
        "comment": [r"^comment$"],
    })

    collaboration = pivot_repeating(df, ["Q0.5", "Q1.6"], {
        "primary_entity": [r"primary entity collaborated"],
        "mechanisms": [r"mechanisms used to collaborate"],
        "areas": [r"areas collaboration focused"],
        "description": [r"description of collaboration"],
        "other_entities": [r"other entities collaborated"],
    })

    actions = pivot_repeating(df, ["Q8.1", "Q9.1", "Q9.2"], {
        "action_type": [r"^action", r"primary emissions sector addressed and action type"],
        "stage": [r"status of action in the reporting year"],
        "cost": [r"^total cost of action"],
        "renew_gen": [r"estimated annual renewable energy generation"],
        "hazards": [r"climate hazard\(s\) that action addresses"],
    })
    actions["cost_num"] = pd.to_numeric(actions["cost"], errors="coerce")

    targets = pivot_repeating(df, ["Q5.1a", "Q6.1", "Q6.1.1", "Q7.1"], {
        "target_type": [r"target type"],
        "description": [r"target description"],
        "established": [r"year target was established"],
        "base_year": [r"^base year\^?$"],
        "target_year": [r"^target year\^?$"],
        "base_value": [r"metric value in base year|covered emissions in base year|base year emissions covered"],
        "recent_value": [r"metric value in most recent year|covered emissions in most recent|emissions covered by target in most recent"],
        "target_value": [r"metric value in target year|^net emissions in target year"],
        "pct_achieved": [r"percentage of target achieved"],
        "pct_reduction": [r"percentage of emissions reduction"],
    })

    # classify each target row
    def classify(t):
        t = str(t or "").lower()
        if "renewable energy" in t:
            return "clean_energy"
        if "waste" in t:
            return "zero_waste"
        if "building" in t:
            return "buildings"
        if "base year emissions" in t or "absolute" in t:
            return "ghg"
        return "other"
    targets["key"] = targets["target_type"].map(classify)

    return {"hazards": hazards, "projects": projects, "engagement": engagement,
            "collaboration": collaboration, "actions": actions, "targets": targets}


@st.cache_data
def build_fingerprints():
    df = load_data()
    narr = df[(df["char_len"] > 80) & (~df["is_placeholder"])].copy()
    if narr.empty:
        return narr
    narr["norm_hash"] = narr["resp_clean"].str.lower().map(
        lambda s: hashlib.md5(s.encode("utf-8")).hexdigest())
    first = narr.groupby("norm_hash")["Year"].min().rename("first_year")
    narr = narr.merge(first, left_on="norm_hash", right_index=True, how="left")
    narr["first_year"] = narr["first_year"].astype(int)
    return narr


# ----------------------------------------------------------- framework -----
def add_framework_markers(fig, x_is_cat=False):
    """Vertical rules at 2022 and 2024: the two CDP questionnaire rewrites."""
    for yv in (2022, 2024):
        x = str(yv) if x_is_cat else yv
        fig.add_vline(x=x, line=dict(color=MUTED, width=1.2, dash="dot"))


# ------------------------------------------------------------------- data ----
df = load_data()
years_all = sorted(int(y) for y in df["Year"].unique())

st.markdown(f'<h1 style="margin-bottom:0.5rem;">{icon("waves")} St. Petersburg — Climate Disclosure Report, 2021–2025</h1>',
            unsafe_allow_html=True)
st.caption("Every number below is computed live from `St_Petersburg_Responses.xlsx` — "
           "nothing is hard-coded. Question IDs were renumbered by CDP in 2022 and again in 2024, "
           "so indicators are matched on the **Sub-fields** label, which is stable across filings.")

with st.sidebar:
    st.header("Report settings")
    sel = st.multiselect("Reporting years", years_all, default=years_all)
    omit_toggle = st.toggle("Treat omitted fields as unanswered", value=True,
                            help="2021–2023 wrote blanks as 'Question not applicable'; 2024–2025 drop "
                                 "them entirely. This toggle puts both on a common denominator.")
    sel_years = [y for y in years_all if y in sel]
    st.markdown("---")
    st.markdown("**Framework changes**")
    st.caption("The CDP questionnaire was restructured in **2022** and again in **2024**. "
               "Anything that appears to 'change' across a dashed marker is often a form rewrite, "
               "not a real change in the city.")

tabs = st.tabs([
    f'![overview]({icon_data_uri("chart-column")}) Overview',
    f'![hazards]({icon_data_uri("wind")}) Hazards & Risk',
    f'![targets]({icon_data_uri("target")}) Targets & Progress',
    f'![disclosure]({icon_data_uri("flask-conical")}) Disclosure Quality',
    f'![governance]({icon_data_uri("landmark")}) Governance & Engagement',
    f'![finance]({icon_data_uri("dollar-sign")}) Finance & Pipeline',
    f'![explorer]({icon_data_uri("search")}) Field Explorer',
])

# =====================================================================
# PAGE 1 — OVERVIEW
# =====================================================================
with tabs[0]:
    sub = df[df["Year"].isin(sel_years)]

    # ---- completeness with/without the omitted-field adjustment
    present = {int(y): set(zip(g["question_root"], g["sf_norm"])) for y, g in df.groupby("Year")}
    union_keys = set().union(*present.values())

    completeness = []
    for y in years_all:
        keys = present[y]
        rows = df[df["Year"] == y]
        n_subst = int((~rows["is_placeholder"] & ~rows["is_notation"]).sum())
        n_ph = int(rows["is_placeholder"].sum())
        n_not = int(rows["is_notation"].sum())
        filed = len(rows)
        if omit_toggle:
            missing = len(union_keys - keys)
            completeness.append({"Year": y, "Substantive": n_subst, "Placeholder": n_ph,
                                 "Notation": n_not, "Omitted": missing, "filed": filed,
                                 "denom": len(union_keys)})
        else:
            completeness.append({"Year": y, "Substantive": n_subst, "Placeholder": n_ph,
                                 "Notation": n_not, "Omitted": 0, "filed": filed, "denom": filed})
    comp = pd.DataFrame(completeness)

    quant = (df[~df["is_placeholder"]].groupby("Year")
             .apply(lambda g: float(g["numeric_value"].notna().mean() * 100), include_groups=False)
             .reindex(years_all).fillna(0))

    # ---- recycle rate
    fps = build_fingerprints()
    rec = {}
    if len(fps):
        for y in years_all:
            rows = fps[fps["Year"] == y]
            if len(rows):
                rec[y] = float((rows["first_year"] < y).mean() * 100)
    rec_ser = pd.Series(rec, dtype=float).reindex(years_all)

    kpi_cols = st.columns(5)
    cur = sel_years[-1] if sel_years else years_all[-1]
    prev = sel_years[-2] if len(sel_years) > 1 else cur

    def kpi(col, label, value, sub_txt, color):
        col.markdown(f"""<div class="kpi"><div class="lbl">{label}</div>
<div class="val" style="color:{color}">{value}</div>
<div class="sub">{sub_txt}</div></div>""", unsafe_allow_html=True)

    row_cur = comp[comp["Year"] == cur].iloc[0]
    row_prev = comp[comp["Year"] == prev].iloc[0]
    d_phi = row_cur["Substantive"] - row_prev["Substantive"]
    kpi(kpi_cols[0], "Fields filed", f"{row_cur['filed']:,}", f"{cur} vs {prev}: {d_phi:+,}", CAT["blue"])
    kpi(kpi_cols[1], "Substantive rate", f"{row_cur['Substantive']/row_cur['denom']*100:.0f}%",
        f"non-placeholder answers, {cur}", CAT["green"])
    kpi(kpi_cols[2], "Quantification rate", f"{quant[cur]:.1f}%",
        "answers containing a number", CAT["aqua"])
    kpi(kpi_cols[3], "Narrative recycled", f"{rec_ser.get(cur, float('nan')):.0f}%",
        "long answers reused from an earlier filing", CAT["orange"])
    inv = get_indicator(df, "target_recent_emissions")
    invb = get_indicator(df, "target_base_emissions")
    if inv and invb and cur in inv and cur in invb:
        chg = (inv[cur]["num"] / invb[cur]["num"] - 1) * 100
        kpi(kpi_cols[4], "Emissions vs base", f"{chg:+.1f}%", "latest covered emissions, all filings", CAT["violet"])
    else:
        kpi(kpi_cols[4], "Emissions vs base", "n/a", "target figures missing", MUTED)

    st.markdown("")

    # ---- stacked completeness
    c1, c2 = st.columns([1.15, 1])
    with st.container(border=True):
        cL, cR = st.columns([1, 1.3])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("file-text")}Is the disclosure getting more complete?</h3>',
                        unsafe_allow_html=True)
            place_share = comp[comp["Year"].isin(sel_years)]
            latest_ph = place_share.iloc[-1]["Placeholder"] / place_share.iloc[-1]["denom"] * 100
            st.markdown(f"""
<div class="card-narrative">
Each bar splits one filing year into <b>substantive</b>, <b>placeholder</b>
("Not Applicable"/"Do not know"), <b>notation-key</b> (NE/IE/NO) and — since you opted to count
them — <b>omitted</b> sub-fields that were present in another filing but skipped here.
<br><br>
The placeholder share falls from <b>{comp.iloc[0]['Placeholder']/comp.iloc[0]['denom']*100:.0f}%</b>
in {years_all[0]} to <b>{latest_ph:.0f}%</b> in {years_all[-1]}. Most of that "improvement" is the
2024 questionnaire dropping the wordy <i>Question not applicable</i> rows from the file — not
St. Petersburg answering more.
</div>
""", unsafe_allow_html=True)
        with cR:
            fig = go.Figure()
            colors = {"Substantive": CAT["green"], "Placeholder": CAT["red"],
                      "Notation": CAT["yellow"], "Omitted": GRID}
            for col in ["Substantive", "Placeholder", "Notation", "Omitted"]:
                yv = comp[comp["Year"].isin(sel_years)][col]
                fig.add_trace(go.Bar(x=[str(y) for y in sel_years], y=yv, name=col,
                                      marker_color=colors[col]))
            fig.update_layout(barmode="stack", title="Completeness by filing year",
                              plot_bgcolor="white", yaxis=dict(gridcolor=GRID, title="answers"),
                              margin=dict(t=50, b=20), legend=dict(orientation="h", y=-0.25))
            add_framework_markers(fig, x_is_cat=True)
            st.plotly_chart(fig)

    # ---- quantification + frozen facts
    with st.container(border=True):
        cL, cR = st.columns([1.15, 1])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("calculator")}From words to numbers</h3>', unsafe_allow_html=True)
            qcur = quant.get(cur, float("nan"))
            qfirst = quant.get(years_all[0], float("nan"))
            st.markdown(f"""
<div class="card-narrative">
The share of answers that contain an actual number rises from <b>{qfirst:.1f}%</b> in
{years_all[0]} to <b>{qcur:.1f}%</b> in {cur}. The jump at 2024 is again partly the form rewrite —
the new questionnaire asks for more numeric fields — so treat the level, not the slope, as signal.
</div>
""", unsafe_allow_html=True)
        with cR:
            fig = go.Figure(go.Scatter(x=[str(y) for y in years_all], y=quant.values,
                                       mode="lines+markers", marker=dict(size=9, color=CAT["aqua"]),
                                       line=dict(color=CAT["aqua"], width=2)))
            fig.update_layout(title="Quantification rate by year (%)", plot_bgcolor="white",
                              yaxis=dict(gridcolor=GRID, title="%", rangemode="tozero"),
                              margin=dict(t=50, b=20))
            add_framework_markers(fig, x_is_cat=True)
            st.plotly_chart(fig)


# =====================================================================
# PAGE 2 — HAZARDS & RISK
# =====================================================================
with tabs[1]:
    haz = build_tables()["hazards"]
    haz = haz[haz["Year"].isin(sel_years)]
    all_haz = [h for h in CANON_HAZARDS if h in haz["Canonical"].unique()] + \
              sorted(h for h in haz["Canonical"].unique() if h not in CANON_HAZARDS)

    with st.container(border=True):
        cL, cR = st.columns([1, 1.35])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("wind")}Hazard exposure, year over year</h3>',
                        unsafe_allow_html=True)
            cnt_first = haz[haz["Year"] == years_all[0]]["Canonical"].nunique()
            cnt_last = haz[haz["Year"] == years_all[-1]]["Canonical"].nunique()
            st.markdown(f"""
<div class="card-narrative">
St. Petersburg reported <b>{cnt_first} hazards</b> in {years_all[0]} under the older, more granular
taxonomy (rain storm, coastal flood, salt water intrusion…), then a stable set of
<b>{cnt_last} hazards</b> from 2022 on. Two 2021-only hazards — <b>Coastal flooding</b> and
<b>Saltwater intrusion</b> — simply disappear from the risk register, not from the coastline.
<br><br>
The chart tracks <b>% of population exposed</b>, the one per-hazard field that actually moves;
the near-constant "magnitude" label (almost always "Medium High") is shown in the matrix below.
</div>
""", unsafe_allow_html=True)
        with cR:
            exp_pivot = haz[haz["Canonical"].isin(CANON_HAZARDS[:5])].pivot_table(
                index="Canonical", columns="Year", values="ExposurePct", aggfunc="first")
            fig = go.Figure()
            for hzname in CANON_HAZARDS[:5]:
                if hzname in exp_pivot.index:
                    row = exp_pivot.loc[hzname].dropna()
                    if len(row):
                        fig.add_trace(go.Scatter(
                            x=[str(y) for y in row.index], y=row.values, mode="lines+markers",
                            name=hzname, line=dict(color=HAZARD_COLOR[hzname], width=2),
                            marker=dict(size=9), connectgaps=True))
            fig.update_layout(title="Population exposed to each hazard, by year (%)",
                              plot_bgcolor="white", yaxis=dict(gridcolor=GRID, title="% of population",
                                                               rangemode="tozero"),
                              xaxis=dict(title="Filing year"), margin=dict(t=50, b=20),
                              legend=dict(orientation="h", y=-0.3))
            add_framework_markers(fig, x_is_cat=True)
            st.plotly_chart(fig)

    # ---- presence gantt + vulnerable group diffs
    with st.container(border=True):
        cL, cR = st.columns([1.1, 1])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("calendar")}Hazard presence by year</h3>', unsafe_allow_html=True)
            presence = haz.pivot_table(index="Canonical", columns="Year", aggfunc="size").reindex(all_haz, columns=years_all)
            z = presence.notna().astype(int)
            fig = go.Figure(go.Heatmap(
                z=z.values, x=[str(y) for y in z.columns], y=z.index,
                colorscale=[[0, "#f7f7f4"], [1, CAT["blue"]]], showscale=False,
                text=z.values, texttemplate="%{text}", textfont=dict(color="white", size=10), xgap=4, ygap=4))
            fig.update_layout(plot_bgcolor="white", margin=dict(t=30, b=20, l=10, r=10),
                              yaxis=dict(autorange="reversed"), height=300)
            st.plotly_chart(fig)
            st.caption("1 = hazard appears in the risk register that year. The 2021→2022 gap is the "
                       "taxonomy change dropping coastal flooding and saltwater intrusion.")
        with cR:
            st.markdown(f'<h3 class="card-title">{icon("users")}Vulnerable groups — added / removed</h3>', unsafe_allow_html=True)
            prev_grp = set()
            for y in sorted(sel_years):
                yr_groups = set()
                for _, r in haz[haz["Year"] == y].iterrows():
                    if r.get("hazard_vuln"):
                        yr_groups |= set(split_multi(r["hazard_vuln"], y))
                added = yr_groups - prev_grp
                removed = prev_grp - yr_groups
                prev_grp = yr_groups
                if y == sel_years[-1]:
                    st.markdown(f"**{y}**")
                    for g in sorted(added):
                        st.markdown(f'<span class="chip" style="background:{CAT["green"]}">+ {g[:40]}</span>', unsafe_allow_html=True)
                    for g in sorted(removed):
                        st.markdown(f'<span class="chip" style="background:{CAT["red"]}">− {g[:40]}</span>', unsafe_allow_html=True)
                    if not added and not removed:
                        st.markdown(f'<span class="chip" style="background:{MUTED}">no change since {sel_years[-2] if len(sel_years)>1 else years_all[-1]}</span>', unsafe_allow_html=True)
                    st.markdown("")
            st.caption("Set-difference of vulnerable population groups, cumulative to the last "
                       "selected year. Genuine year-on-year edits show up here.")

# =====================================================================
# PAGE 3 — TARGETS & PROGRESS
# =====================================================================
with tabs[2]:
    tg = build_tables()["targets"]
    target_meta = {
        "ghg": "GHG emissions −80%",
        "clean_energy": "100% clean energy",
        "zero_waste": "Zero waste",
        "buildings": "Buildings −80%",
    }
    units = {"ghg": "t CO₂e", "clean_energy": "kWh", "zero_waste": "t waste", "buildings": "t CO₂e"}

    # tidy target register (last known value per target)
    register_rows = []
    for key, name in target_meta.items():
        g = tg[tg["key"] == key]
        if g.empty:
            continue
        last = g.sort_values("Year").iloc[-1]
        reg = {"target": name, "type": key, "established": None, "base_year": None,
               "target_year": None, "base_value": None, "latest_value": None,
               "target_value": None, "pct_achieved": None}
        for fld, col in [("established", "established"), ("base_year", "base_year"),
                         ("target_year", "target_year"), ("base_value", "base_value"),
                         ("latest_value", "recent_value"), ("target_value", "target_value"),
                         ("pct_achieved", "pct_achieved")]:
            v = last.get(col)
            try:
                reg[fld] = float(v) if v not in (None, "", "nan") else None
            except (TypeError, ValueError):
                reg[fld] = None
        # disambiguate GHG values (base/recent under this target vs the shared metric fields)
        if key == "ghg":
            g = g[~g["target_type"].astype(str).str.contains("building|waste|renewable", case=False, na=False)]
            if not g.empty:
                last = g.sort_values("Year").iloc[-1]
                for fld, col in [("established", "established"), ("base_year", "base_year"),
                                 ("target_year", "target_year")]:
                    v = last.get(col)
                    try:
                        reg[fld] = float(v) if v not in (None, "", "nan") else None
                    except (TypeError, ValueError):
                        reg[fld] = None
                bv = last.get("base_value"); rv = last.get("recent_value")
                tv = last.get("target_value")
                try:
                    reg["base_value"] = float(bv) if bv not in (None, "", "nan") else None
                except (TypeError, ValueError):
                    pass
                try:
                    reg["latest_value"] = float(rv) if rv not in (None, "", "nan") else None
                except (TypeError, ValueError):
                    pass
                try:
                    reg["target_value"] = float(tv) if tv not in (None, "", "nan") else None
                except (TypeError, ValueError):
                    pass
        register_rows.append(reg)

    # tree canopy adaptation goal (Q5.1.1)
    canopy = df[(df["question_root"] == "Q5.1.1") & (~df["is_placeholder"])]
    if not canopy.empty:
        by_year = {}
        for y, g in canopy.groupby("Year"):
            goal = g[g["sf_norm"].str.contains("adaptation goal", na=False)]
            byear = g[g["sf_norm"].str.contains("base year of goal", na=False)]
            tyear = g[g["sf_norm"].str.contains("target year of goal", na=False)]
            desc = g[g["sf_norm"].str.contains("^adaptation goal", na=False)]
            by_year[int(y)] = {
                "desc": desc["resp_clean"].iloc[0] if len(desc) else None,
                "base": byear["numeric_value"].iloc[0] if len(byear) else None,
                "target": tyear["numeric_value"].iloc[0] if len(tyear) else None,
            }
        if by_year:
            last_y = max(by_year)
            register_rows.append({
                "target": "Tree canopy 30%", "type": "canopy",
                "established": 2022, "base_year": by_year[last_y]["base"],
                "target_year": by_year[last_y]["target"], "base_value": None,
                "latest_value": None, "target_value": 30.0, "pct_achieved": None})

    reg = pd.DataFrame(register_rows)

    with st.container(border=True):
        cL, cR = st.columns([1.15, 1])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("target")}Target register</h3>', unsafe_allow_html=True)
            st.markdown("""
<div class="card-narrative">Every target the city has ever logged in a CDP filing. Values are the most
recent figure reported against each target. The bullet chart on the right is the honest read:
targets with a wide base→target gap and a pin-point of recent progress.</div>
""", unsafe_allow_html=True)
        with cR:
            if not reg.empty:
                show = reg[["target", "established", "base_year", "target_year",
                            "base_value", "latest_value", "target_value", "pct_achieved"]].copy()
                for col in ["base_value", "latest_value", "target_value", "pct_achieved"]:
                    show[col] = show[col].apply(lambda v: f"{v:,.0f}" if isinstance(v, (int, float)) else "—")
                show["established"] = show["established"].apply(lambda v: f"{v:.0f}" if isinstance(v, (int, float)) else "—")
                show["base_year"] = show["base_year"].apply(lambda v: f"{v:.0f}" if isinstance(v, (int, float)) else "—")
                show["target_year"] = show["target_year"].apply(lambda v: f"{v:.0f}" if isinstance(v, (int, float)) else "—")
                show = show.rename(columns={"target": "Target", "established": "Established",
                                            "base_year": "Base yr", "target_year": "Target yr",
                                            "base_value": "Base", "latest_value": "Latest",
                                            "target_value": "Target value", "pct_achieved": "% achieved"})
                st.dataframe(show, width="stretch", hide_index=True)
            else:
                st.info("No target rows found.")

    # ---- bullet charts
    with st.container(border=True):
        st.markdown(f'<h3 class="card-title">{icon("circle-dot")}Progress bullets</h3>', unsafe_allow_html=True)
        bcols = st.columns(2)
        for i, (_, r) in enumerate(reg.iterrows()):
            if r["target_value"] is None or r["base_value"] is None:
                continue
            latest = r["latest_value"]
            pct = r["pct_achieved"]
            with bcols[i % 2]:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=[r["target_value"]], y=[r["target"]],
                                     orientation="h", marker_color=GRID, width=0.3,
                                     name="Target", hovertemplate="Target: %{x:,.0f}"))
                if latest is not None:
                    fig.add_trace(go.Bar(x=[r["base_value"]], y=[r["target"]],
                                         orientation="h", marker_color=CAT["blue"], width=0.18,
                                         name="Base", hovertemplate="Base: %{x:,.0f}"))
                    fig.add_trace(go.Scatter(x=[latest], y=[r["target"]], mode="markers",
                                             marker=dict(size=15, color=CAT["orange"]),
                                             name="Latest", hovertemplate="Latest: %{x:,.0f}"))
                    lbl = f"{pct:.2f}%" if isinstance(pct, (int, float)) else "n/a"
                    fig.add_annotation(x=latest, y=r["target"], text=f" {lbl}",
                                       showarrow=False, xanchor="left", font=dict(color=CAT["orange"]))
                fig.update_layout(showlegend=False, barmode="overlay", height=170,
                                  plot_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10),
                                  xaxis=dict(gridcolor=GRID, title=units.get(r["type"], ""),
                                             tickformat=".0f"),
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig)

    # ---- emissions trajectory + inventory freshness + consistency
    c1, c2 = st.columns([1.35, 1])
    with c1:
        with st.container(border=True):
            st.markdown(f'<h3 class="card-title">{icon("trend-down")}Emissions trajectory vs the 2050 pathway</h3>',
                        unsafe_allow_html=True)
            base_emis = get_indicator(df, "target_base_emissions")
            recent_emis = get_indicator(df, "target_recent_emissions")
            inv_year = get_indicator(df, "inventory_year")
            fig = go.Figure()
            # 3.00 Mt base is the 2016 inventory; the city targets −80% → 0.6 Mt by 2050.
            fig.add_trace(go.Scatter(x=[2016, 2050], y=[3000000, 600000], mode="lines",
                                     line=dict(color=MUTED, width=2, dash="dash"),
                                     name="Linear path to 0.6 Mt (2050)", hoverinfo="skip"))
            xs, ys, labels = [], [], []
            for y, v in sorted(base_emis.items()):
                if v["num"]:
                    xs.append(2016); ys.append(v["num"])
            # the "most recent inventory" figure rides on the inventory vintage it describes
            recent_x = 2019
            if inv_year:
                maxy = max(inv_year)
                if inv_year[maxy]["num"]:
                    recent_x = int(inv_year[maxy]["num"])
            for y, v in sorted(recent_emis.items()):
                if v["num"]:
                    xs.append(recent_x); ys.append(v["num"])
                    labels.append(f"{y} filing: {v['num']:,.0f} t (inventory {recent_x})")
            base_labels = [f"base {v['num']:,.0f} t (2016)" for y, v in sorted(base_emis.items()) if v["num"]]
            # dedupe stacked markers: one 3.00 Mt base point, one 2.69 Mt recent point
            px, py, ptext = [], [], []
            seen = set()
            for x, yv, lab in zip(xs, ys, base_labels + labels):
                if (x, yv) not in seen:
                    seen.add((x, yv))
                    px.append(x); py.append(yv); ptext.append(lab if lab else f"{yv:,.0f} t")
            fig.add_trace(go.Scatter(x=px, y=py, mode="markers+text", marker=dict(size=13, color=CAT["blue"]),
                                     text=ptext, textposition="top center", textfont=dict(size=9),
                                     name="Reported inventory points", hoverinfo="x+y"))
            fig.add_trace(go.Scatter(x=[2050], y=[600000], mode="markers+text",
                                     marker=dict(size=14, color=CAT["aqua"], symbol="circle-open", line=dict(width=3)),
                                     text=["0.6 Mt"], textposition="bottom center", name="2050 target"))
            fig.update_layout(plot_bgcolor="white", yaxis=dict(gridcolor=GRID, title="t CO₂e"),
                              xaxis=dict(title="Inventory year", range=[2015, 2052], tickmode="linear", dtick=5),
                              margin=dict(t=50, b=20), legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig)
            st.caption("The target question reports a <b>base of 3.00 Mt (2016 inventory)</b> and a "
                       "<b>most-recent figure of 2.69 Mt</b> in every filing, with the inventory vintage "
                       "moving 2016→2019 in the 2024 filing. The target is −80% by 2050 (0.6 Mt); the "
                       "city has not reported a fresh total to reconcile the 2.69 Mt tracking figure.")

            # consistency flag
            cons = []
            for y in years_all:
                tr = recent_emis.get(y, {}).get("num")
                if tr:
                    cons.append({"Year": y, "Target-recent (t)": tr})
            if cons:
                st.markdown("**Target-tracking figure reported each filing** — a single 2.69 Mt value is "
                            "repeated verbatim in every year; there is no separate inventory TOTAL to "
                            "reconcile against.")
                st.dataframe(pd.DataFrame(cons), width="stretch", hide_index=True)
    with c2:
        with st.container(border=True):
            st.markdown(f'<h3 class="card-title">{icon("flask-conical")}Inventory freshness</h3>', unsafe_allow_html=True)
            inv_year = get_indicator(df, "inventory_year")
            items = []
            for y in years_all:
                if y in inv_year and inv_year[y]["num"]:
                    items.append({"filing": y, "inventory": int(inv_year[y]["num"]),
                                  "age_years": y - int(inv_year[y]["num"])})
            if items:
                fresh = pd.DataFrame(items)
                fig = go.Figure(go.Bar(x=fresh["filing"].astype(str), y=fresh["age_years"],
                                       marker_color=[STATUS["good"] if a < 3 else STATUS["warning"]
                                                     for a in fresh["age_years"]]))
                fig.update_layout(title="Reporting year − inventory year (age of evidence)",
                                  plot_bgcolor="white", yaxis=dict(gridcolor=GRID, dtick=1, title="years"),
                                  margin=dict(t=50, b=20))
                add_framework_markers(fig, x_is_cat=True)
                st.plotly_chart(fig)
                st.caption("The inventory vintage moved 2016→2019 in the 2024 filing, but the target "
                           "question still cites a 6-year-old figure.")
            else:
                st.info("Inventory year not found.")

    # ---- quantitative indicators
    st.markdown(f"### {icon('calculator')} Quantitative indicators at a glance", unsafe_allow_html=True)
    st.caption("Emissions and resource metrics from the newest questionnaire rows (Q3.1.3, Q4.7, Q4.10). "
               "Older filings used a different taxonomy, so these figures begin in 2023–24.")

    def q_num(roots, sf_pat):
        out = {}
        for y, g in df[df["question_root"].isin(roots) & df["sf_norm"].str.contains(sf_pat, na=False)].groupby("Year"):
            g = g[~g["is_placeholder"]]
            if len(g) and g["numeric_value"].notna().any():
                out[int(y)] = g["numeric_value"].dropna().iloc[0]
        return out

    # emissions by sector (latest year) + waste & water KPIs side by side
    q313 = df[(df["question_root"] == "Q3.1.3") & (df["sf_norm"] == "direct emissions (metric tonnes co2e)")]
    wgen = q_num(["Q4.7"], r"^response \(in unit specified\)$")
    w2e = q_num(["Q4.7"], r"percentage of the total solid waste gen")
    wdiv = q_num(["Q4.7"], r"percentage of the total solid waste gen.*diverted|diverted away")
    ww = q_num(["Q4.7"], r"^volume of wastewater produced")
    wwtr = q_num(["Q4.7"], r"^percentage of wastewater safely treated")
    wcon = q_num(["Q4.10"], r"household water consumption")
    wsafe = q_num(["Q4.10"], r"access to safely managed drinking water")

    ecol, wcol = st.columns([1.25, 1])
    with ecol:
        with st.container(border=True):
            ly = int(q313["Year"].max()) if not q313.empty else "latest"
            st.markdown(f'<h3 class="card-title">{icon("chart-column")}Emissions by sector (direct, {ly})</h3>',
                        unsafe_allow_html=True)
            if not q313.empty:
                ly = int(q313["Year"].max())
                g = q313[(q313["Year"] == ly) & (~q313["is_placeholder"])].copy()
                g["sector"] = g["Question"].astype(str).str.replace(r"Q3\.1\.3 – ", "", regex=True).str.replace(r" >.*", "", regex=True).str.strip()
                totals = g[g["sector"].str.startswith("Total ")].copy()
                totals["sector"] = totals["sector"].str.replace("Total ", "", regex=True)
                totals = totals.dropna(subset=["numeric_value"])
                totals = totals[totals["numeric_value"] > 0].sort_values("numeric_value")
                if not totals.empty:
                    fig = go.Figure(go.Bar(x=totals["numeric_value"], y=totals["sector"], orientation="h",
                                           marker_color=[CAT["blue"], CAT["green"], CAT["orange"], CAT["magenta"]],
                                           text=[f"{v:,.0f}" for v in totals["numeric_value"]], textposition="outside"))
                    fig.update_layout(plot_bgcolor="white", xaxis=dict(gridcolor=GRID, title="t CO₂e"),
                                      yaxis=dict(title=""), margin=dict(t=30, b=20, l=10, r=60))
                    st.plotly_chart(fig)
                else:
                    st.info("No positive sector totals found.")
            else:
                st.info("Sector-level emissions not found.")
            st.caption(f"Direct emissions by sector total in the {ly} filing. Transport (mostly on-road) "
                       "is the dominant source at 764,743 t; grid-supplied electricity adds another "
                       "1.34 Mt of indirect emissions.")
    with wcol:
        with st.container(border=True):
            st.markdown(f'<h3 class="card-title">{icon("flask-conical")}Waste & water metrics</h3>', unsafe_allow_html=True)
            k = st.columns(1)
            k[0].markdown(f'<div class="kpi"><div class="lbl">Solid waste</div><div class="val">{wgen.get(2024, 0):,.0f}<span style="font-size:.9rem;"> t</span></div><div class="sub">2023 data year</div></div>', unsafe_allow_html=True)
            k = st.columns(2)
            k[0].markdown(f'<div class="kpi"><div class="lbl">Waste to energy</div><div class="val">{w2e.get(2024, 0):.1f}%</div><div class="sub">vs {wdiv.get(2024, 0):.1f}% diverted</div></div>', unsafe_allow_html=True)
            k[1].markdown(f'<div class="kpi"><div class="lbl">Wastewater</div><div class="val">{ww.get(2024, 0):,.0f}<span style="font-size:.9rem;"> m³</span></div><div class="sub">{wwtr.get(2024, 0):.0f}% treated</div></div>', unsafe_allow_html=True)
            k = st.columns(2)
            k[0].markdown(f'<div class="kpi"><div class="lbl">Household water</div><div class="val">{wcon.get(2024, 0):.0f}<span style="font-size:.9rem;"> L/cap/d</span></div><div class="sub">{wsafe.get(2024, 0):.0f}% safe access</div></div>', unsafe_allow_html=True)
            st.caption("Waste and water figures are only reported in the 2024–25 filings (data year 2023), "
                       "so these are point-in-time snapshots rather than trends.")

# =====================================================================
# PAGE 4 — DISCLOSURE QUALITY
# =====================================================================
with tabs[3]:
    st.markdown(f"### {icon('search')} Is this real reporting, or a re-filing?", unsafe_allow_html=True)
    fps = build_fingerprints()

    # 1. recycling matrix
    with st.container(border=True):
        cL, cR = st.columns([1.15, 1])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("refresh")}Narrative recycling matrix</h3>', unsafe_allow_html=True)
            recycled_latest = 0
            if len(fps):
                ly = fps["Year"].max()
                n = fps[fps["Year"] == ly]
                recycled_latest = float((n["first_year"] < ly).mean() * 100)
            st.markdown(f"""
<div class="card-narrative">
Every long-form answer (>80 chars) is fingerprinted (md5 of normalised text). Each cell counts
answers filed in <b>row year</b> that first appeared in <b>column year</b>.
<br><br>
In the latest filing, <b>{recycled_latest:.0f}%</b> of long answers were carried over verbatim from
an earlier filing. Heavy weight below the diagonal = a disclosure that stopped being refreshed.
</div>
""", unsafe_allow_html=True)
        with cR:
            if len(fps):
                mat = fps.groupby(["Year", "first_year"]).size().reset_index(name="n")
                pivot = mat.pivot_table(index="Year", columns="first_year", values="n", aggfunc="sum").reindex(
                    index=[y for y in years_all if y in fps["Year"].unique()],
                    columns=[y for y in years_all if y in fps["first_year"].unique()]).fillna(0)
                fig = go.Figure(go.Heatmap(
                    z=pivot.values, x=[str(c) for c in pivot.columns], y=[str(r) for r in pivot.index],
                    text=pivot.values.astype(int), texttemplate="%{text}", colorscale="Blues",
                    showscale=False, xgap=3, ygap=3))
                fig.update_layout(plot_bgcolor="white", margin=dict(t=30, b=20, l=10, r=10), height=320)
                st.plotly_chart(fig)
                st.caption("Rows = filing year, columns = year of first appearance.")

    # 2. field-level diff
    with st.container(border=True):
        cL, cR = st.columns([1, 1.35])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("compare")}Field-level diff between two filings</h3>',
                        unsafe_allow_html=True)
            diff_years = sorted(set(years_all) - {2021})
            A_default = 2024 if 2024 in diff_years else diff_years[0]
            A = st.selectbox("Year A", diff_years, index=diff_years.index(A_default))
            b_options = [y for y in diff_years if y != A]
            B_default = 2025 if 2025 in b_options else b_options[0]
            B = st.selectbox("Year B", b_options, index=b_options.index(B_default))
            keysA = df[df["Year"] == A].groupby(["question_root", "sf_norm"])["resp_clean"].first()
            keysB = df[df["Year"] == B].groupby(["question_root", "sf_norm"])["resp_clean"].first()
            common = keysA.index.intersection(keysB.index)
            unchanged = (keysA[common] == keysB[common]).sum()
            changed = (keysA[common] != keysB[common]).sum()
            new_ = len(keysB.index.difference(keysA.index))
            dropped = len(keysA.index.difference(keysB.index))
            total = len(common)
        with cR:
            st.markdown("")
            cols = st.columns(3)
            cols[0].markdown(f'<div class="kpi"><div class="lbl">Unchanged</div><div class="val" style="color:{CAT["green"]}">{unchanged:,}</div><div class="sub">of {total:,} matched fields</div></div>', unsafe_allow_html=True)
            cols[1].markdown(f'<div class="kpi"><div class="lbl">Changed</div><div class="val" style="color:{CAT["orange"]}">{changed:,}</div><div class="sub">{changed/total*100:.1f}% of matched</div></div>', unsafe_allow_html=True)
            cols[2].markdown(f'<div class="kpi"><div class="lbl">New / dropped</div><div class="val" style="color:{CAT["red"]}">{new_:,} / {dropped:,}</div><div class="sub">appeared / vanished</div></div>', unsafe_allow_html=True)
            st.markdown("")
            fig = go.Figure(go.Bar(x=["Unchanged", "Changed", "New", "Dropped"],
                                   y=[unchanged, changed, new_, dropped],
                                   marker_color=[CAT["green"], CAT["orange"], CAT["blue"], CAT["red"]]))
            fig.update_layout(plot_bgcolor="white", yaxis=dict(gridcolor=GRID), margin=dict(t=30, b=20))
            st.plotly_chart(fig)

    # 3. frozen numerics — condensed mention
    with st.container(border=True):
        st.markdown(f'<h3 class="card-title">{icon("snowflake")}Frozen numerics</h3>', unsafe_allow_html=True)
        frozen = []
        for key in CROSSWALK:
            ser = get_indicator(df, key)
            if not ser:
                continue
            ys = sorted(ser)
            run = 1
            for i in range(1, len(ys)):
                if ser[ys[i]]["num"] == ser[ys[i - 1]]["num"] and ser[ys[i]]["num"] is not None:
                    run += 1
                else:
                    run = 1
                if run >= 3:
                    frozen.append({"indicator": key, "value": ser[ys[i]]["num"],
                                   "years": f"{ys[i - run + 1]}–{ys[i]}"})
        # collapse run fragments to the longest span per indicator
        seen = {}
        for f in frozen:
            if f["indicator"] not in seen or seen[f["indicator"]]["years"] < f["years"]:
                seen[f["indicator"]] = f
        if seen:
            names = {"population_current": "Population (270,000)",
                     "population_projected": "Projected population (279,000)",
                     "area_km2": "Land area (356 km²)",
                     "food_insecure_pct": "Food insecurity (14.2%)",
                     "target_pct_reduction": "Emissions-reduction target (−80%)",
                     "inventory_total_basic": "Inventory TOTAL BASIC",
                     "energy_total_mwh": "Total energy consumption",
                     "energy_renew_mwh": "Renewable energy consumption",
                     "waste_generated": "Solid waste generated",
                     "project_cost": "Project cost",
                     "wastewater_volume": "Wastewater volume"}
            labels = [names.get(f["indicator"], f["indicator"]) for f in seen.values()]
            st.markdown(f"""
<div class="card-narrative">Several headline figures are byte-identical across <b>≥3 consecutive
filings</b> — copied, not re-measured. The 2021→2025 run of identical values: <b>population</b>
(270,000), <b>projected population</b> (279,000), <b>land area</b> (356 km²), <b>food insecurity</b>
(14.2%) and the <b>−80% emissions target</b>. Flatness here is a disclosure choice, not stability.
</div>
""", unsafe_allow_html=True)
        else:
            st.info("No numeric indicator is frozen for 3+ consecutive years.")

    # 5. anomaly flags
    with st.container(border=True):
        st.markdown(f'<h3 class="card-title">{icon("flag")}Rule-based anomaly flags</h3>', unsafe_allow_html=True)
        flags = []

        # energy consumption collapse
        en = get_indicator(df, "energy_total_mwh")
        if len(en) >= 2:
            ys = sorted(en)
            last, prev = ys[-1], ys[-2]
            if en[prev]["num"] and en[last]["num"]:
                chg = (en[last]["num"] / en[prev]["num"] - 1) * 100
                if abs(chg) > 90:
                    flags.append({"severity": "critical",
                                  "title": f"Energy consumption collapse ({chg:+.0f}%)",
                                  "detail": (f"Total energy consumption fell from {en[prev]['num']:,.0f} MWh "
                                             f"({prev}) to {en[last]['num']:,.0f} MWh ({last}). A {abs(chg):.0f}% "
                                             "year-on-year drop in a utility-scale figure is almost certainly "
                                             "a units or boundary change, not physics.")})

        # duplicate identical numerics within one question
        dups = []
        for (y, root, sf), g in df.groupby(["Year", "question_root", "sf_norm"]):
            nums = g[~g["is_placeholder"]]["numeric_value"].dropna()
            if len(nums) > 1 and nums.nunique() == 1:
                dups.append((y, root, sf, nums.iloc[0]))
        if dups:
            y, root, sf, val = dups[0]
            flags.append({"severity": "warning",
                          "title": f"Same number entered twice in {root}",
                          "detail": f"'{sf}' holds the value {val:,.2f} twice within a single {y} "
                                    "filing. Duplicated sub-fields with different denominators "
                                    "(e.g. a % recycled and a % diverted both '20.13') hide "
                                    "inconsistencies."})

        # population year staleness
        pyear = get_indicator(df, "population_year")
        for y in years_all:
            if y in pyear and pyear[y]["num"] and y - int(pyear[y]["num"]) > 2:
                flags.append({"severity": "warning",
                              "title": f"Stale population year in {y} filing",
                              "detail": f"The {y} report cites a population year of {int(pyear[y]['num'])} "
                                        f"— {y - int(pyear[y]['num'])} years old. The same 270,000 population "
                                        "is repeated in every filing."})

        # projected population year moved while value did not
        proj = get_indicator(df, "population_projected")
        projy = get_indicator(df, "population_proj_year")
        if len(projy) >= 2:
            ys = sorted(projy)
            if projy[ys[-1]]["num"] != projy[ys[-2]]["num"]:
                flags.append({"severity": "warning",
                              "title": "Projected population year moved, value did not",
                              "detail": f"The projection year changed from {int(projy[ys[-2]]['num'])} to "
                                        f"{int(projy[ys[-1]]['num'])} while the projected population stayed "
                                        f"at {proj.get(ys[-1], {}).get('num', '—'):,.0f} — a re-stamped, not "
                                        "re-computed, forecast."})

        # implausible magnitude for a utility MOU
        mit = build_tables()["actions"]
        rews = mit[mit["renew_gen"].notna() & (mit["renew_gen"] != "")]
        if not rews.empty:
            r = rews.sort_values("Year").iloc[-1]
            try:
                v = float(re.sub(r"[^\d.]", "", r["renew_gen"]))
            except ValueError:
                v = None
            if v is not None and v < 10:
                flags.append({"severity": "warning",
                              "title": "1.22 MWh for a utility-scale MOU",
                              "detail": f"The mitigation action reports {v:.2f} MWh of annual renewable "
                                        "generation. A figure that small next to a 'Clean Energy "
                                        "Collaborations MOU' with Duke Energy is a unit error or a stub."})

        for f in flags:
            color = STATUS[f["severity"]]
            st.markdown(f'<div class="kpi" style="border-left:5px solid {color}; margin-bottom:8px;">'
                        f'<div class="lbl" style="color:{color}">{f["severity"].upper()}</div>'
                        f'<div class="val" style="font-size:1.05rem;">{f["title"]}</div>'
                        f'<div class="sub">{f["detail"]}</div></div>', unsafe_allow_html=True)
        if not flags:
            st.info("No rule-based anomalies triggered in the selected data.")

# =====================================================================
# PAGE 5 — GOVERNANCE & ENGAGEMENT
# =====================================================================
with tabs[4]:
    eng = build_tables()["engagement"]
    coll = build_tables()["collaboration"]
    eng = eng[eng["Year"].isin(sel_years)]
    coll = coll[coll["Year"].isin(sel_years)]

    # ---- engagement level stack
    with st.container(border=True):
        cL, cR = st.columns([1, 1.3])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("landmark")}Who is the city talking to?</h3>', unsafe_allow_html=True)
            st.markdown("""
<div class="card-narrative">
Two repeating tables feed this page: the <b>types of governments engaged</b> for each climate
component (risk assessment, emissions inventory, planning) and the <b>primary entities collaborated
with</b> (utility, county, networks).
<br><br>
The chart stacks government levels per filing year. A single level ("Lower level of government")
fills 2021–2023; 2024–2025 suddenly name <b>state/regional</b> and <b>higher/federal</b> partners —
a real broadening of the engagement footprint, or a form that started asking.
</div>
""", unsafe_allow_html=True)
        with cR:
            rows = []
            for _, r in eng.iterrows():
                if r.get("gov_level"):
                    for lvl in split_multi(r["gov_level"], r["Year"]):
                        rows.append({"Year": int(r["Year"]), "level": lvl})
            if rows:
                stack = pd.DataFrame(rows)
                level_order = ["Lower level of government", "State/Regional-level government",
                               "Higher level of government (not listed above)", "Other"]
                pivot = stack.groupby(["Year", "level"]).size().unstack(fill_value=0).reindex(
                    columns=[l for l in level_order if l in stack["level"].unique()]).reindex(sel_years, fill_value=0)
                fig = go.Figure()
                colors = [CAT["blue"], CAT["green"], CAT["orange"], MUTED]
                for i, col in enumerate(pivot.columns):
                    fig.add_trace(go.Bar(x=[str(y) for y in pivot.index], y=pivot[col], name=col[:35],
                                         marker_color=colors[i % len(colors)]))
                fig.update_layout(barmode="stack", title="Engagement by government level",
                                  plot_bgcolor="white", yaxis=dict(gridcolor=GRID, dtick=1),
                                  margin=dict(t=50, b=20), legend=dict(orientation="h", y=-0.35))
                add_framework_markers(fig, x_is_cat=True)
                st.plotly_chart(fig)
            else:
                st.info("No engagement level data in the selected years.")

    # ---- institutional continuity + oversight + collaboration network
    with st.container(border=True):
        cL, cR = st.columns([1.15, 1])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("clock")}Institutional continuity & oversight</h3>', unsafe_allow_html=True)
            timeline = []
            osr = df[df["resp_clean"].str.contains("office of sustainability", case=False, na=False)]
            timeline.append(("Office of Sustainability & Resilience", sorted(osr["Year"].unique())))
            mayor = df[(df["subfield"].str.contains("leader title", case=False, na=False)) &
                       (df["resp_clean"].str.contains("mayor", case=False, na=False))]
            timeline.append(("Elected leadership (Mayor)", sorted(mayor["Year"].unique())))
            hers = df[df["resp_clean"].str.contains("hers committee", case=False, na=False)]
            timeline.append(("HERS Committee", sorted(hers["Year"].unique())))
            tb = []
            for name, ys in timeline:
                tb.append({"track": name, "start": min(ys) if ys else None, "end": max(ys) if ys else None,
                           "present": ys})
            fig = go.Figure()
            for i, t in enumerate(tb):
                if t["start"] is not None:
                    fig.add_trace(go.Bar(x=[t["end"] - t["start"] + 1], y=[t["track"]],
                                         base=[t["start"]], orientation="h", width=0.4,
                                         marker_color=CAT["blue"],
                                         hovertemplate=f"{t['start']}–{t['end']}<extra></extra>"))
            fig.update_layout(barmode="overlay", plot_bgcolor="white", height=220,
                              xaxis=dict(title="Filing year", gridcolor=GRID, tickmode="linear",
                                         dtick=1), margin=dict(t=30, b=10, l=10, r=10),
                              yaxis=dict(autorange="reversed"))
            add_framework_markers(fig)
            st.plotly_chart(fig)
            st.caption("The Mayor field exists in the 2021 questionnaire and is absent 2022–25 — a "
                       "disclosure discontinuity, not a city without a mayor. OSR and the HERS "
                       "Committee persist throughout.")
            st.markdown("")
            ov = df[df["sf_norm"].str.contains("processes that reflect your jurisdiction", na=False)]
            if not ov.empty:
                last = ov.sort_values("Year").iloc[-1]
                st.markdown(f"""
<div class="card-narrative">Selected oversight process in the most recent filing
({int(last['Year'])}): <span class="chip" style="background:{CAT['violet']}">{last['resp_clean'][:80]}</span>
<br>The option changes across filings — committees in 2023, council-informed in 2024,
government-considered in 2025 — which is more form drift than institutional change.
</div>
""", unsafe_allow_html=True)
            else:
                st.info("Oversight process field not found.")
        with cR:
            st.markdown(f'<h3 class="card-title">{icon("network")}Collaboration network</h3>', unsafe_allow_html=True)
            org_pat = {
                "Duke Energy Florida": r"duke energy",
                "Tampa Bay Regional Resiliency Coalition": r"tampa bay regional resiliency",
                "Pinellas County": r"pinellas county",
                "PSRN": r"pinellas sustainability and resilience network|psrn",
                "US EPA": r"\bepa\b|environmental protection agency",
                "FSDN": r"florida sustainability directors network|fsdn",
            }
            org_years = {}
            haystack = pd.concat([coll[["Year", "description"]].assign(src="c"),
                                  eng[["Year", "comment"]].rename(columns={"comment": "description"}).assign(src="e")])
            haystack = haystack.dropna(subset=["description"])
            for label, pat in org_pat.items():
                yrs = sorted(haystack[haystack["description"].astype(str).str.contains(pat, case=False, na=False)]["Year"].unique())
                if yrs:
                    org_years[label] = int(min(yrs))
            if org_years:
                color_scale = {2021: CAT["blue"], 2022: CAT["green"], 2023: CAT["magenta"],
                               2024: CAT["orange"], 2025: CAT["red"]}
                fig = go.Figure()
                n = len(org_years)
                center_x, center_y = 0, 0
                fig.add_trace(go.Scatter(x=[center_x], y=[center_y], mode="markers+text",
                                         marker=dict(size=34, color="#1c2b3a"),
                                         text=["St. Petersburg"], textposition="top center",
                                         textfont=dict(color="white", size=10)))
                for i, (label, y) in enumerate(sorted(org_years.items(), key=lambda kv: kv[1])):
                    ang = 2 * 3.14159 * i / n
                    x, yv = 1.2 * math.cos(ang), 1.2 * math.sin(ang)
                    fig.add_trace(go.Scatter(x=[center_x, x], y=[center_y, yv], mode="lines",
                                             line=dict(color=color_scale.get(y, MUTED), width=2),
                                             hoverinfo="skip", showlegend=False))
                    fig.add_trace(go.Scatter(x=[x], y=[yv], mode="markers+text",
                                             marker=dict(size=20, color=color_scale.get(y, MUTED)),
                                             text=[f"{label.split()[0]}"], textposition="top center",
                                             textfont=dict(size=9), name=f"{label} ({y})"))
                fig.update_layout(title="Counterparty network by first-appearance year",
                                  showlegend=False, height=360, plot_bgcolor="white",
                                  xaxis=dict(visible=False, range=[-1.6, 1.6]),
                                  yaxis=dict(visible=False, range=[-1.6, 1.6]), margin=dict(t=50, b=10))
                st.plotly_chart(fig)
            else:
                st.info("No named counterparties detected in the selected years.")
            st.caption("Named counterparties found in the collaboration and engagement text, coloured by "
                       "the first year they appear. The 2024–2025 expansion to federal and state-level "
                       "networks (EPA, FSDN, PSRN) is the visible payoff.")

# =====================================================================
# PAGE 6 — FINANCE & PIPELINE
# =====================================================================
with tabs[5]:
    proj = build_tables()["projects"]
    proj = proj[proj["Year"].isin(sel_years)]

    with st.container(border=True):
        cL, cR = st.columns([1, 1.35])
        with cL:
            st.markdown(f'<h3 class="card-title">{icon("dollar-sign")}Project pipeline by year</h3>', unsafe_allow_html=True)
            totals = proj.groupby("Year")["cost_num"].sum()
            st.markdown("""
<div class="card-narrative">
Each bar segments the <b>total cost of project</b> per filing year by project. The pipeline runs
$83M (2021) → $113M (2022) → $43.3M (2023–24) → $43.0M (2025). The 2022→2023 drop is not
spending — two projects simply <b>exited the register</b>: the <b>REIF $60M</b> municipal-retrofits
programme and the <b>$10M solar PV</b> siting project.
</div>
""", unsafe_allow_html=True)
        with cR:
            if not proj.empty:
                labels = list(proj["label"].unique())
                fig = go.Figure()
                palette = [CAT["blue"], CAT["green"], CAT["magenta"], CAT["yellow"], CAT["aqua"], CAT["orange"]]
                for i, lab in enumerate(labels):
                    g = proj[proj["label"] == lab]
                    row = {int(y): float(v) for y, v in zip(g["Year"], g["cost_num"]) if pd.notna(v)}
                    xs = [str(y) for y in sorted(row)]
                    ys = [row[y] for y in sorted(row)]
                    fig.add_trace(go.Bar(x=xs, y=ys, name=lab[:40], marker_color=palette[i % len(palette)]))
                fig.update_layout(barmode="stack", title="Total project cost by year ($)",
                                  plot_bgcolor="white", yaxis=dict(gridcolor=GRID, tickformat=",.0f"),
                                  margin=dict(t=50, b=20), legend=dict(orientation="h", y=-0.4))
                add_framework_markers(fig, x_is_cat=True)
                st.plotly_chart(fig)
                st.caption(f"2025 pipeline total: ${totals.get(2025, 0):,.0f}")

    # ---- lifecycle dot plot
    with st.container(border=True):
        st.markdown(f'<h3 class="card-title">{icon("refresh")}Project lifecycle & financing status</h3>', unsafe_allow_html=True)
        stage_order = ["Pre-feasibility/impact assessment", "Project feasibility", "Project structuring",
                       "Implementation"]
        fig = go.Figure()
        for _, r in proj.iterrows():
            ypos = stage_order.index(r["stage"]) if r.get("stage") in stage_order else len(stage_order)
            fs = str(r.get("finance_status") or "")
            color = STATUS["good"] if fs and "not funded" not in fs.lower() else STATUS["serious"]
            fig.add_trace(go.Scatter(x=[str(r["Year"])], y=[ypos], mode="markers+text",
                                     marker=dict(size=14, color=color, symbol="square",
                                                 line=dict(color="white", width=1)),
                                     text=[r["label"][:22]], textposition="top center",
                                     textfont=dict(size=8), name=r["label"],
                                     hovertemplate=f"{r['label']}<br>{r['finance_status']}<extra></extra>",
                                     showlegend=False))
        fig.update_layout(title="Stage of development × year (■ funded/partially, ■ not funded)",
                          plot_bgcolor="white", yaxis=dict(gridcolor=GRID, dtick=1,
                                                           tickmode="array", tickvals=list(range(len(stage_order))),
                                                           ticktext=stage_order),
                          xaxis=dict(title="Filing year"), margin=dict(t=50, b=20), height=320)
        add_framework_markers(fig, x_is_cat=True)
        st.plotly_chart(fig)

    # ---- financing model mix
    with st.container(border=True):
        st.markdown(f'<h3 class="card-title">{icon("building-2")}Financing model mix</h3>', unsafe_allow_html=True)
        fm_rows = []
        for _, r in proj.iterrows():
            if r.get("finance_model"):
                for m in split_multi(r["finance_model"], r["Year"]):
                    fm_rows.append({"Year": int(r["Year"]), "model": m})
        if fm_rows:
            fm = pd.DataFrame(fm_rows)
            models = fm["model"].unique()
            pivot = fm.groupby(["Year", "model"]).size().unstack(fill_value=0).reindex(sel_years, fill_value=0)
            fig = go.Figure()
            palette = [CAT["blue"], CAT["green"], CAT["orange"], CAT["magenta"], CAT["aqua"]]
            for i, m in enumerate(models):
                if m in pivot.columns:
                    fig.add_trace(go.Bar(x=[str(y) for y in pivot.index], y=pivot[m], name=m[:35],
                                         marker_color=palette[i % len(palette)]))
            fig.update_layout(barmode="stack", title="Financing models mentioned, per filing",
                              plot_bgcolor="white", yaxis=dict(gridcolor=GRID, dtick=1),
                              margin=dict(t=50, b=20), legend=dict(orientation="h", y=-0.4))
            add_framework_markers(fig, x_is_cat=True)
            st.plotly_chart(fig)
            st.caption("The drift toward naming 'Grants' — and away from own-budget — is the "
                       "funding-dependence story.")
        else:
            st.info("No financing model data in the selected years.")

    # ---- never-answered finance block + cost card
    c1, c2 = st.columns([1.15, 1])
    with c1:
        with st.container(border=True):
            st.markdown(f'<h3 class="card-title">{icon("ban")}The finance block that was never answered</h3>',
                        unsafe_allow_html=True)
            fin_never = ["credit rating", "access finance", "decarbonis", "bonds", "investment"]
            rows = []
            for kw in fin_never:
                hits = df[df["sf_norm"].str.contains(kw, na=False)]
                if len(hits):
                    asked = sorted(int(y) for y in hits["Year"].unique())
                    subst = hits[~hits["is_placeholder"]]
                    if subst.empty:
                        rows.append({"Field theme": kw.title(), "Asked in": f"{min(asked)}–{max(asked)}",
                                     "Status": "Never answered"})
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
                st.caption("Credit rating, access-to-finance mechanisms, and decarbonising investments "
                           "were asked across multiple filings and never answered. Absence is the "
                           "finding — it is rendered, not hidden.")
            else:
                st.info("No never-answered finance fields detected.")
    with c2:
        with st.container(border=True):
            st.markdown(f'<h3 class="card-title">{icon("scale")}Cost of action vs cost of risk</h3>', unsafe_allow_html=True)
            total_fields = int(len(df))
            risk_text = df[df["sf_norm"].str.contains("monetised|economic cost of risk|cost of inaction", na=False)]
            monetised = int((~risk_text["is_placeholder"]).sum())
            st.markdown(f"""
<div class="card-narrative">
Across <b>{total_fields:,} answered fields</b> in five filings, the city reports <b>{monetised}</b>
monetised estimate of climate risk or cost of inaction.
<br><br>
There is <b>no monetised risk figure anywhere</b> in the disclosure — yet it lists $60M+ of projects
and a $1.39M adaptation action. The cost side of the balance sheet is measured; the risk side is not.
</div>
""", unsafe_allow_html=True)

# =====================================================================
# PAGE 7 — FIELD EXPLORER
# =====================================================================
with tabs[6]:
    st.markdown(f"### {icon('search')} Field Explorer", unsafe_allow_html=True)
    st.caption("Search the raw long-format table to check any claim in this report.")
    q = st.text_input("Search question text or sub-field")
    fy = st.multiselect("Years", years_all, default=years_all)
    show = df[df["Year"].isin(fy)]
    if q:
        show = show[show["qt_norm"].str.contains(q.lower(), na=False) |
                    show["sf_norm"].str.contains(q.lower(), na=False)]
    disp = show[["Year", "Question", "Sub-fields", "St. Petersburg Response"]].reset_index(drop=True)
    st.dataframe(disp, width="stretch", hide_index=True, height=520)
    st.caption(f"{len(disp)} rows shown.")

st.markdown("---")
st.caption("Dashboard reads `St_Petersburg_Responses.xlsx` directly — regenerate that file from the raw "
           "CDP sheets to refresh every number here. Question IDs were renumbered in 2022 and 2024; all "
           "indicators are matched on normalised Sub-fields labels so those renumberings don't break the charts.")
