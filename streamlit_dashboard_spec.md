
# Streamlit Dashboard Spec — St. Petersburg Climate Disclosure (2021–2025)

Spec only. Data model, page structure, indicators, and the exact row locators for each panel.
Implementation (widgets, styling, caching) left to the coding agent.

---

## 0. The one structural fact that drives everything

The source sheet is **long format**, one row per answered sub-field:

| Column                      | Type | Notes                                                            |
| --------------------------- | ---- | ---------------------------------------------------------------- |
| `Question`                | str  | e.g.`Q2.2 – Row 1`. **Numbering changes across years.** |
| `Year`                    | int  | 2021–2025                                                       |
| `Question Text`           | str  | Full question wording, also changes year to year                 |
| `Sub-fields`              | str  | The column label within the question's table                     |
| `St. Petersburg Response` | str  | Everything is a string, including numbers                        |

**Do not join on `Question`.** Question IDs were renumbered twice (2021 legacy → 2022–23 → 2024–25). Join on a **normalised `Sub-fields` label via regex**, which is stable across all five years for ~90% of indicators. This is the single most important design decision in the app.

Also note: 2021–2023 write unanswered fields as the literal string `"Question not applicable"`; 2024–2025 **omit them entirely**. Any completeness metric must handle both, or it will show a fake improvement.

---

## 1. Data layer

Build these four tables once, cache them, drive every page off them.

### 1.1 `raw` — the sheet, lightly cleaned

```
question_id, question_root, row_index, year, question_text, subfield, response
```

- `question_root` = `Question` with ` – Row N` / ` – <label>` suffix stripped → e.g. `Q2.2`
- `row_index` = the N from `Row N`, else null (needed because hazards/projects/actions are repeating tables)
- `response_clean` = strip, collapse whitespace, normalise curly quotes
- `is_placeholder` = response in `{"Question not applicable", "This data is not available to report", "Data not available", ""}`
- `is_notation_key` = response in `{"NE", "IE", "NO", "Not Estimated (NE)", "Included Elsewhere (IE)", "Not Occurring (NO)"}`
- `numeric_value` = float if parseable after stripping `, % $`, else null
- `char_len` = len(response_clean)

### 1.2 `indicators` — tidy long panel of scalar metrics

```
indicator_key, year, value_num, value_str, question_id, subfield_matched
```

Built by applying the regex crosswalk in §6 against `raw.subfield` (lowercased). One row per indicator per year. This is what every KPI card and trend line reads from.

### 1.3 `repeating` — the row-level tables

```
table_key, year, row_index, field_key, value
```

`table_key` ∈ `{hazards, adaptive_capacity, projects, engagement, collaboration, targets_energy, actions_adaptation, actions_mitigation, plans}`.
Pivot `field_key` → columns per table. This powers the hazard matrix, project pipeline, and engagement views.

### 1.4 `text_fingerprints` — for the recycling analysis

```
year, question_id, subfield, response_clean, norm_hash, char_len
```

`norm_hash` = md5 of lowercased, whitespace-collapsed, quote-normalised text. Restrict to `char_len > 80` and `not is_placeholder`. Self-join across years on `norm_hash` to compute first-appearance year and reuse count.

---

## 2. Page structure

Six pages. Sidebar carries a global **year multiselect** (default all) and a **"treat omitted fields as unanswered"** toggle that switches the completeness denominator between *rows present* and *union of all questions ever asked*.

| # | Page                              | Question it answers                                        |
| - | --------------------------------- | ---------------------------------------------------------- |
| 1 | **Overview**                | What happened across five years, in ten seconds            |
| 2 | **Hazards & Risk**          | What is the city exposed to, and has that assessment moved |
| 3 | **Targets & Progress**      | What did it promise, how far has it got                    |
| 4 | **Disclosure Quality**      | Is this real reporting or a re-filing                      |
| 5 | **Governance & Engagement** | Who owns this, who are they talking to                     |
| 6 | **Finance & Pipeline**      | What is it trying to fund, and does the money move         |

Optional 7th: **Field Explorer** — searchable raw table with year filter, for anyone who wants to check a claim.

---

## 3. Page-by-page panels

### Page 1 — Overview

**KPI strip (5 cards, current year vs prior year delta):**

| Card                    | Metric                                                                                | Computation                              |
| ----------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------- |
| Fields filed            | count of`raw` rows                                                                  | by year                                  |
| Substantive answer rate | `1 - (placeholders / rows)`                                                         | flag the 2024 discontinuity in a caption |
| Quantification rate     | `numeric_value.notna() / rows`                                                      | 5.6% → 33% story                        |
| Narrative recycled      | share of`char_len>80` answers whose `norm_hash` first appeared in an earlier year | the headline number                      |
| Emissions vs base year  | `target_recent_emissions / target_base_emissions - 1`                               |                                          |

**Charts:**

1. Stacked bar, fields per year split by `substantive / placeholder / notation_key` — the completeness story
2. Line, quantification rate by year, with a vertical annotation at 2024 (framework change)
3. Small-multiple sparklines for the five "frozen facts": population, area, food insecurity %, projected population, hazard count

**Callout box:** a hardcoded list of the framework changes (2022, 2024) so every chart on the site inherits the caveat.

### Page 2 — Hazards & Risk

Source: `repeating[table_key='hazards']`

**Fields to pivot per row:** `hazard_name`, `probability`, `magnitude`, `pop_share_exposed`, `intensity_change`, `frequency_change`, `timeframe`, `vulnerable_groups` (pipe/semicolon/comma-delimited — **delimiter changes by year**, split on `[;|,](?![^(]*\))` or normalise per-year), `sectors_exposed`, `impact_narrative`

**Panels:**

1. **Hazard × Year heatmap** — cell colour = ordinal severity, cell value = probability/magnitude pair. Ordinal encoding: `Low=1, Medium Low=2, Medium=3, Medium High=4, High=5`. The visual point is that it is a flat block of identical colour.
2. **Composite risk score** = `probability_ord × magnitude_ord`, plotted per hazard per year. Flat lines.
3. **Hazard presence Gantt** — which hazards appear in which years. Makes the disappearance of *coastal flooding* and *saltwater intrusion* after 2021 immediately visible.
4. **Vulnerable groups / exposed sectors** — set difference between consecutive years, rendered as added/removed chips. This is where genuine year-on-year edits do show up.
5. **Assessment vintage panel** — publication year of the underlying vulnerability assessment vs reporting year, as an "age of evidence" bar (2017/2019 assessment, still cited in 2025).

**Derived flag:** `narrative_unchanged_since` per hazard — pull from `text_fingerprints`.

### Page 3 — Targets & Progress

Source: `indicators` + `repeating[table_key='targets_energy']`

**Target register table** (one row per target, columns = years):

| target | type | established | base_year | target_year | base_value | latest_value | target_value | pct_achieved |
| ------ | ---- | ----------- | --------- | ----------- | ---------- | ------------ | ------------ | ------------ |

Five targets to track: GHG 80%/2050, clean energy 100%/2035, zero waste 2050, buildings 80%/2050, tree canopy 30%.

**Panels:**

1. **Bullet chart per target** — base, current, target on one axis, with `% achieved` label. The clean-energy bullet (0.06%) is the whole point.
2. **Target-year change tracker** — line of `target_year` per target across filings. Surfaces the tree canopy 2032→2030 revision automatically.
3. **Emissions trajectory** — actual inventory points (2016: 3.00 Mt / 2.69 Mt, 2019: 2.23 Mt) vs required linear path to 0.6 Mt by 2050. Show the gap.
4. **Inventory freshness gauge** — `reporting_year - inventory_year` (currently 6 years).
5. **Consistency flag panel** — automated check: does `target_recent_emissions` equal the TOTAL BASIC of the inventory reported in the same filing? Currently fails for 2024 and 2025.

### Page 4 — Disclosure Quality

The analytically richest page. All computed, none hardcoded.

**Panels:**

1. **Recycling matrix** — heatmap, rows = filing year, cols = year of first appearance, cell = count of narrative answers. Shows 2025's 66% inherited from 2022–23.
2. **Field-level diff (year A vs year B selector)** — three columns: *unchanged*, *changed*, *new/dropped*. Match on `question_root + subfield`. Default A=2024, B=2025 → 377/417 unchanged.
3. **Longest-unchanged answers** — table sorted by consecutive years identical, with the text. The three five-year survivors surface at the top.
4. **Frozen numerics detector** — any `indicator_key` whose `value_num` is identical for ≥3 consecutive years. Auto-flags population, food insecurity, all three project costs, the $1,387,354.19 action cost.
5. **Anomaly flags** — rule-based, each rendered as a card with severity:
   - year-on-year change in a numeric indicator > 90% → *energy consumption 3,096,835 → 73,044 MWh*
   - same `value_num` in two sub-fields with different denominators within one question → *20.13% waste duplication*
   - `population_year` more than 2 years older than filing year
   - `projected_population_year` changed while `projected_population` did not
   - a value flagged implausible against a magnitude band → *1.22 MWh for a utility MOU*
6. **Persistent blanks** — bar of question themes never answered in any year they were asked, colour-coded by inferred cause: `county/utility data`, `capacity`, `question retired`. The cause mapping is a small hand-authored lookup; keep it in a config file, not in code.

### Page 5 — Governance & Engagement

Source: `repeating[table_key='engagement']` and `[collaboration]`

**Panels:**

1. **Engagement network graph** — nodes = counterparties (Pinellas County, Tampa Bay Regional Resiliency Coalition, FSDN, PSRN, US EPA, Duke Energy, EDF), edges appear/disappear by year. Slider or animation over years. The 2024 addition of federal + state-network nodes is the visual payoff.
2. **Engagement level stack** — count of entries per year by `government_level` (lower / state-regional / higher / federal).
3. **Institutional continuity timeline** — OSR (2015–), HERS Committee, mayor field (present 2021, absent 2022–25). A gap band on the mayor track makes the disclosure discontinuity legible.
4. **Oversight processes** — the four selected process types, as a constant-across-years strip.

### Page 6 — Finance & Pipeline

Source: `repeating[table_key='projects']`, `[actions_*]`

**Panels:**

1. **Pipeline waterfall / stacked bar by year** — $83M → $113M → $43.3M → $43.3M → $43.0M, segmented by project. Dropped projects (REIF $60M, Solar PV $10M) render as explicit exits.
2. **Project lifecycle Sankey or dot-plot** — `stage_of_development` × `status_of_financing` per project per year. Shows the $30M green infrastructure project stuck at *feasibility / not funded* for four years.
3. **Financing model mix** — share of projects naming grants / own budget / bonds / PPP, by year. The drift toward grant dependence.
4. **Never-answered finance block** — a deliberate "empty state" panel listing credit rating, access-to-finance mechanisms, and investment decarbonisation with their asked-years and retirement year. Absence is the finding; render it rather than hiding it.
5. **Cost-of-action vs cost-of-risk** — a single card stating that zero monetised risk estimates exist across 3,277 fields. No chart needed.

---

## 4. Cross-cutting derived variables

Compute once, reuse everywhere:

| Variable                      | Definition                                                   | Used by |
| ----------------------------- | ------------------------------------------------------------ | ------- |
| `substantive_rate`          | non-placeholder, non-notation rows / total rows              | p1, p4  |
| `quant_rate`                | rows with`numeric_value` / total rows                      | p1, p4  |
| `recycle_rate`              | narrative answers reused from prior year / narrative answers | p1, p4  |
| `identical_field_rate(A,B)` | matched fields identical / matched fields                    | p4      |
| `risk_score`                | `prob_ord × mag_ord`                                      | p2      |
| `evidence_age`              | `filing_year - source_document_year`                       | p2, p3  |
| `target_attainment`         | `(latest - base) / (target - base)`                        | p3      |
| `freeze_length`             | consecutive years a value is unchanged                       | p4      |
| `pipeline_total`            | sum of`total cost of project` per year                     | p6      |

---

## 5. Conventions the agent must handle

1. **Multi-select delimiters change by year.** 2021–23 use `; `, 2024 uses `,` (which collides with commas inside option labels such as *"Electricity, gas, steam and air conditioning supply"*), 2025 uses `|`. Normalise to `|` per year; for 2024 match against a known option vocabulary rather than naive splitting.
2. **Numbers arrive as strings and sometimes as floats-with-`.0`** — `2021.0`, `2016.0` are years, not measurements. Cast year-like fields to int.
3. **Trailing `^` and `^^` on sub-field labels** are footnote markers introduced in 2024. Strip before matching.
4. **Missing row indices are meaningful.** 2024 hazards run Rows 1, 2, 4, 5, 6 — Row 3 was deleted. Do not reindex; show the gap.
5. **Curly apostrophes** (`’`) appear in 2022–23 and straight ones later. Normalise before hashing.
6. **Every chart needs the framework-change annotation.** Build one reusable `add_framework_markers(fig)` helper that drops vertical rules at 2022 and 2024.

---

## 6. Indicator crosswalk (regex on lowercased `Sub-fields`)

Verified to resolve in all five years unless noted.

```yaml
area_km2:            'area of the .*jurisdiction boundary \(in square km\)|land area of the (jurisdiction|city) boundary'
population_current:  '^current (\(or most recent\) )?population( size)?$'
population_year:     '^(current )?population year$'
population_projected:'^projected population( size)?$'
population_proj_year:'^projected population year$'
food_insecure_pct:   'percentage of population that is food insecure'

inventory_year:      '^(inventory year|year covered by main inventory)'
inventory_pop:       'population in (the )?(year covered by main )?inventory( year)?'
inventory_total_basic: 'emissions \(metric tonnes co2e\)'   # filter question_root to the TOTAL BASIC line
inventory_protocol:  'primary protocol'
inventory_audited:   'has the .*inventory been audited'
inventory_data_qual: 'overall level of data quality'

target_pct_reduction:  'percentage of emissions reduction'
target_base_emissions: '(covered emissions in base year|base year emissions covered by target)'
target_recent_emissions:'(covered emissions in most recent inventory|emissions covered by target in most recent inventory)'
target_year:           '^target year\^?$'
target_base_year:      '^base year\^?$'
target_status:         'target status and progress'
pct_achieved:          'percentage of target achieved'
metric_base:           '^metric value in base year'
metric_recent:         '^metric value in most recent year'

hazard_name:        '^climate[- ]related hazards\^?$|^climate hazards$'
hazard_prob:        'current probability of hazard'
hazard_magnitude:   'current magnitude of (impact of )?hazard'
hazard_pop_share:   'proportion of the population exposed'      # absent 2021
hazard_intensity:   'future change in .*intensity|expected future change in hazard intensity'
hazard_frequency:   'future change in .*frequency|expected future change in hazard frequency'
hazard_timeframe:   'timeframe of expected future changes|when do you first expect'
hazard_narrative:   'describe the impacts on vulnerable populations|please describe the impacts experienced'

project_cost:       '^total cost of project'
project_invest_need:'total investment cost needed'
project_stage:      'stage of project development'
project_finance_status:'status of financing'
project_finance_model:'(identified )?financing model'
action_cost:        '^total cost of action'

energy_total_mwh:   '^total energy consumption \(mwh\)'          # 2023–2025 only
energy_renew_mwh:   '^total energy consumption from renewable'   # 2023–2025 only
waste_generated:    'amount of solid waste generated'
waste_diverted_pct: 'diverted away from landfill'
waste_recycled_pct: 'diverted solid waste generated that is recycled'
wastewater_volume:  'volume of wastewater produced'

engagement_component:'^climate component$'
engagement_gov_level:'types of governments engaged'
oversight_processes: 'processes that reflect your jurisdiction'
```

Indicators needing per-year special handling: `energy_*` (question absent before 2023), `hazard_pop_share` (absent 2021), `waste_*` (2021 sits under a different question block, `Q13.x`), and everything on the 2021 sheet generally — 2021 is best treated as a **baseline year shown separately** rather than as the first point of a continuous series.

---

## 7. Suggested build order

1. Data layer + crosswalk + `indicators` table — everything else is downstream
2. Page 4 (Disclosure Quality) — highest analytical value, purely computed, no design judgement needed
3. Page 1 (Overview) — once the metrics exist, the cards are trivial
4. Pages 2, 3 — need the `repeating` pivots
5. Pages 5, 6 — most bespoke, least reusable
6. Field Explorer last, as a debugging surface you keep

One caution on scope: this is a **five-observation dataset for one city**, and two of those observations (2024, 2025) are 90% identical. Resist building anything that implies statistical trend — no regressions, no forecasts, no smoothed lines. The honest visual grammar here is *heatmaps, diffs, and presence/absence*, not time series.
