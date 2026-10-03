# Data sources and dictionary

Extracted 2026-09-28 from the official open APIs. Registration data runs through **August 2026**.
Rebuild the processed files with `python src/build_dataset.py` (pandas only).

## Raw files (`data/raw/`, don't edit)

| File | Source | Query | Coverage |
|---|---|---|---|
| `trafa_t10030_county_monthly_raw.csv` | Trafikanalys API, product **t10030** (Nyregistreringar) | `t10030\|ar\|manad\|fslag:01\|drivm\|agarkat\|lan\|nyreg` | Month × county × fuel × owner category, **Jan 2021 – Aug 2026**. For 2017–2020 the table only has annual totals (`manad = t1`). |
| `trafa_t10036_national_monthly_raw.csv` | Trafikanalys API, product **t10036** (Fordon på väg, månadsstatistik, personbilar) | `t10036\|ar\|manad\|drivm\|nyreg` | Month × fuel, national, **Jan 2006 – Aug 2026** |
| `trafa_t10026_county_annual_raw.csv` | Trafikanalys API, product **t10026** (Fordon i län och kommuner, personbilar) | `t10026\|ar\|drivmedel\|reglan\|nyregunder\|itrfslut` | Year × county × fuel, **2010–2025**: new registrations and cars in traffic at year end |
| `scb_region_context_raw.csv` | SCB PxWeb API: **BE0101C/BefArealTathetKon** and **HE0110A/SamForvInk1** | Both sexes. Income is for ages 20–64, all income classes | County and municipality × year. Population, land area and density for 2010–2025; income (tkr) for 2010–2024 |

API base URLs: `https://api.trafa.se/api/data?query=...` and `https://api.scb.se/OV0104/v1/doris/sv/ssd/...`

### Source quirks handled in cleaning
- In Trafikanalys tables, `–` means zero. It's converted to 0.
- `t1` = total. Totals are removed from the fact table and used only for validation.
- County `aa` ("Okänt län", unknown) is kept as county code `99`, name `Unknown`, and excluded from the county panel.
- Owner category (`agarkat`) has three additive groups: `10` private person, `20` legal entity (company/leasing), `30` car dealers (bilhandeln). They sum exactly to the total.
- Petrol and diesel **include mild hybrids** (Trafikanalys definition). HEV = full hybrids that aren't plug-in.
- The owner split by county is only published monthly **from 2021**. Before that, county data is annual and covers all owners.

## Processed files (`data/processed/`)

### `fact_registrations_county_monthly.csv`: main fact table (24,675 rows)
| column | description |
|---|---|
| month | First day of month (YYYY-MM-01), 2021-01 → 2026-08 |
| county_code | Two-digit län code (01 Stockholm … 25 Norrbotten, 99 unknown) |
| county_name | English/ASCII-friendly county name |
| fuel_type | BEV, PHEV, HEV, PETROL, DIESEL, ETHANOL, GAS, OTHER |
| owner_type | private, company, dealer |
| registrations | New passenger car registrations |

Zero cells aren't returned by the API. Treat a missing combination as 0.

### `national_monthly_by_fuel.csv`: national time series for trend, ITS and forecasting (248 months)
Wide format: `total` plus one count column per fuel type. `*_share` columns are fractions of the total. `plugin_share` = BEV + PHEV.
`private_total` and `private_bev_share` come from the county fact table and are only filled from 2021.
`post_bonus_end` = 1 from Nov 2022. `pull_forward_window` = 1 for Sep–Nov 2022. Both are ready-made dummies for the interrupted time series.

### `county_annual_by_fuel.csv`: long format, 2010–2025
year, county_code, fuel_type, new_registrations, fleet_in_traffic (stock at 31 Dec).

### `county_year_panel.csv`: one row per county × year, for the regional regression (21 counties × 16 years)
| column | description |
|---|---|
| new_regs_total, new_bev, new_phev | New registrations (all owners) |
| bev_share_all_owners, phev_share_all_owners | Share of new registrations |
| fleet_total, fleet_bev, fleet_bev_share | Cars in traffic at year end |
| private_new_regs, private_bev_share, private_phev_share | Private buyers only. Full years 2021–2025 only (NaN otherwise) |
| company_new_regs, company_bev_share | Legal-entity buyers. 2021–2025 |
| private_owner_pct | Private buyers' share of all new registrations in the county |
| population, land_km2, pop_per_km2 | SCB |
| median_income_tkr, mean_income_tkr | SCB, earned income, age 20–64, thousand SEK. 2025 not yet published |
| new_regs_per_1000_pop, bev_fleet_per_1000_pop | Derived |

### `scb_region_context.csv`
All 290 municipalities and 21 counties plus the national total, 2010–2025. `level` ∈ {national, county, municipality}. `county_code` lets you join municipalities to their county.

### `dim_county.csv`
County code, English name, Swedish name, land area.

### `_validation_national_vs_county.csv`
Monthly totals from t10036 (national) compared with the sum of t10030 (county). They match exactly for every month from 2021-01 to 2026-08.

## `ev_sweden.sqlite`
The same tables loaded into SQLite, plus `dim_fuel` (code → label). Ready for the SQL phase.

## Not included, and why
- **Municipality-level registrations**: the Trafikanalys API returns nothing for municipality filters on these products. Use the PxWeb interface on trafa.se manually if you want the 290-municipality version.
- **Charging points per county**: there's no open API. Power Circle's statistics tool (powercircle.org/elbilsstatistik) or the NOBIL API (needs a free key) are the options. It's easiest to add as a small manual CSV of county × year.
- **Mobility Sweden figures**: published as PDFs and press releases. Their BEV shares differ slightly from Trafikanalys's (e.g. 2023: MS ≈ 38.7%, Trafa 37.8%) because of timing and definitions. Worth one line in the README.
