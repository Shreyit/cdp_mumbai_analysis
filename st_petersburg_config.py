"""
St. Petersburg CDP Dashboard — hand-authored configuration.

The spec (streamlit_dashboard_spec.md) asks for the "persistent blanks" cause
mapping to live in a config file, not in code. This is that config.

Only edit this file to change labels, colours, and the cause lookup. The
dashboard reads everything else from St_Petersburg_Responses.xlsx.
"""

# ------------------------------------------------------------------------
# Theme  (mirrors the palette in the dashboard)
# ------------------------------------------------------------------------
CAT = {
    "blue": "#2a78d6", "green": "#008300", "magenta": "#e87ba4", "yellow": "#eda100",
    "aqua": "#1baf7a", "orange": "#eb6834", "violet": "#4a3aa7", "red": "#e34948",
}

# ------------------------------------------------------------------------
# Question-theme labels, grouped by the leading question code
# ------------------------------------------------------------------------
THEME_BY_ROOT = {
    "Q0": "General info & governance",
    "Q1": "Risk & vulnerability assessment",
    "Q2": "Hazards & emissions inventory",
    "Q3": "Energy & emissions data",
    "Q4": "Detailed emissions & waste",
    "Q5": "Targets & goals",
    "Q6": "Adaptation & financing",
    "Q7": "Planning & targets",
    "Q8": "Adaptation actions & plans",
    "Q9": "Actions",
    "Q10": "Transport & air quality",
    "Q11": "Transit accessibility",
    "Q12": "Food systems",
    "Q13": "Waste",
    "Q14": "Water",
}

# ------------------------------------------------------------------------
# Persistent-blank cause lookup.
#
# key  -> root prefix
# value -> (cause, colour)
#
# causes: "county/utility data"  — figures owned by Pinellas County / Duke
#                                 Energy that the city cannot release
#         "capacity"             — the city has never built the capability
#         "question retired"     — field existed once, dropped from the form
#         "not collected"        — optional module the city skipped
# ------------------------------------------------------------------------
BLANK_CAUSE = {
    "Q10": ("county/utility data", CAT["violet"]),
    "Q11": ("county/utility data", CAT["violet"]),
    "Q12": ("capacity", CAT["orange"]),
    "Q14": ("capacity", CAT["orange"]),
    "Q5": ("question retired", CAT["blue"]),
    "Q13": ("question retired", CAT["blue"]),
}
DEFAULT_BLANK_CAUSE = ("not collected", CAT["magenta"])
