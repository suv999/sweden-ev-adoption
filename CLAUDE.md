# EV-Sweden: BEV adoption among Swedish private buyers

## Business question
How fast is Sweden shifting to battery-electric cars among private buyers, where is it
fastest or slowest and why, and what BEV share is plausible by 2028?

## Metric definitions
- **BEV share (headline)** = BEV new registrations / all new passenger-car registrations
  (all 8 fuel types incl. OTHER), same period, same population of buyers.
  Monthly shares are ratios of sums. Never average monthly shares to get annual ones.
- **Private buyers** = owner_type `private` (Trafikanalys agarkat 10). Available Jan 2021 →.
  The headline national figure is the *private* BEV share. The all-owner share (2006 →)
  is used for long-run context and as a covariate/benchmark, and is always labelled "all owners".
- **Regional comparisons use private-buyer data only.** Company/leasing registrations
  are booked to the lessor's county (heavily Stockholm/Västra Götaland), and dealer
  registrations are demo/pre-registrations, so neither reflects where households buy.
- **PHEV share** is reported separately and is never added into the headline.
  `plugin_share` (BEV+PHEV) appears only where explicitly labelled.
- Petrol/diesel include mild hybrids. HEV = non-plug-in full hybrids (Trafikanalys definitions).
- **Climate bonus ended 8 Nov 2022.** Monthly data: `post_bonus_end` = 1 from 2022-11,
  `pull_forward_window` = Sep–Nov 2022 (Nov 2022 is in both, so state the encoding in every model).
- County `99` (Unknown) is excluded from county analyses but included in national totals.
- Last complete data month: 2026-08. Last complete year: 2025.

## Data
- Rebuild: `python src/build_dataset.py` (writes data/processed/*.csv and data/ev_sweden.sqlite).
- Data dictionary and source quirks: data/SOURCES.md.

## Project rules
- Never modify anything in data/raw/. All cleaning happens in src/build_dataset.py.
- Notebooks read from data/processed/ or data/ev_sweden.sqlite only, never from data/raw/.
- Every modelling choice (transform, dummies, priors, holdout, why this model) gets a
  markdown cell *before* the code that implements it, plus a sentence interpreting the result.
- Shares are bounded 0–1. Forecasts must stay in that range (e.g. logit transform or
  logistic growth with a cap) and always come with intervals or scenarios, not a single number.
- Commit after each step (one notebook section, one SQL file, one build change) with a
  message saying what changed and why. Rerun the notebook top to bottom before committing.
- Keep notebook outputs in git (the portfolio is read on GitHub).
