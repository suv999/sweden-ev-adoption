# How fast is Sweden going electric? BEV adoption among private car buyers

## The question
How fast is Sweden shifting to battery-electric cars among private buyers, where is it
fastest or slowest and why, and what BEV share is plausible by 2028?

_TODO: why it matters (end of the climate bonus on 8 Nov 2022, 2030 transport targets)._

## Key findings
_Placeholder: filled in after notebooks 01–04._

1. **Speed:** private BEV share went from __% (2021) to __% (2025 / last 12 months)…
2. **Where:** fastest __, slowest __; strongest correlates __…
3. **Policy:** estimated effect of the bonus end: __ pp…
4. **2028:** plausible range __–__%…

## Data
Trafikanalys (t10030, t10036, t10026) and SCB, extracted 2026-09-28, registrations through Aug 2026.
Full dictionary and source quirks: [data/SOURCES.md](data/SOURCES.md).

Note: Mobility Sweden's published shares differ slightly (e.g. 2023: 38.7% vs 37.8%) because of timing and definitions.

## Method
| Notebook | Question | Method |
|---|---|---|
| `01_eda` | How fast? | Trends, YoY change, seasonality |
| `02_regional` | Where and why? | County panel (private buyers), regression on income and density |
| `03_policy` | Did the bonus end matter? | Interrupted time series (segmented regression) |
| `04_forecast` | What's plausible by 2028? | Prophet vs. statsmodels baseline, scenarios |

Power BI dashboard: [`powerbi/`](powerbi/) (screenshots in [`docs/figures/`](docs/figures/)).

## How to reproduce
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/build_dataset.py
jupyter lab   # run notebooks 01 → 04 in order
```

## Limitations
- The private-buyer split only exists from 2021. Earlier county data covers all owners.
- No municipality-level registrations or charging-point data (see SOURCES.md).
- Registrations are not orders or sales. Leasing cars are registered in the lessor's county.
- Ecological inference: county-level correlations don't describe household behaviour.
- The forecast horizon is long relative to the post-bonus history.
