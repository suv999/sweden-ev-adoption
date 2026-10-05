"""Export tidy CSVs for the Power BI project (powerbi/SwedenEV.*).

Reads data/processed/ (built by src/build_dataset.py) and writes powerbi/data/:
  national_monthly_long.csv  month, fuel_type, registrations              (2006-01 onwards, all owners)
  fact_county_monthly.csv    month, county_code, fuel_type, owner_type,
                             registrations                                (2021-01 onwards)
  dim_county.csv             county_code, county_name, map_name, region
  county_year_panel.csv      county_year_panel.csv + median_income_lag_tkr (income t-1, as in notebook 02)
  regression_results.csv     notebook 02's county panel regressions, rescaled to pp
  regional_key_numbers.csv   headline regional findings from notebook 02

The regressions repeat the specification in notebooks/02_regional.ipynb (section 5) so the
dashboard shows the same numbers; the asserts below fail if they drift apart.

Run from the repo root:  python src/export_powerbi.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "data" / "processed", ROOT / "powerbi" / "data"
OUT.mkdir(parents=True, exist_ok=True)

FUELS = ["BEV", "PHEV", "HEV", "PETROL", "DIESEL", "ETHANOL", "GAS", "OTHER"]
NORRLAND = ["21", "22", "23", "24", "25"]  # Gävleborg, Västernorrland, Jämtland, Västerbotten, Norrbotten

# ---------- national_monthly_long (2006-) ----------
nat = pd.read_csv(PROC / "national_monthly_by_fuel.csv")
nat_long = (nat.melt(id_vars="month", value_vars=FUELS, var_name="fuel_type", value_name="registrations")
               .sort_values(["month", "fuel_type"]))
nat_long = nat_long[nat_long.month >= "2006-01-01"]
nat_long["registrations"] = nat_long.registrations.astype(int)
nat_long.to_csv(OUT / "national_monthly_long.csv", index=False)

# ---------- fact_county_monthly (2021-) ----------
fact = pd.read_csv(PROC / "fact_registrations_county_monthly.csv", dtype={"county_code": str})
fact = fact[fact.month >= "2021-01-01"]
fact = fact[["month", "county_code", "fuel_type", "owner_type", "registrations"]]
fact.to_csv(OUT / "fact_county_monthly.csv", index=False)

# ---------- dim_county ----------
dim = pd.read_csv(PROC / "dim_county.csv", dtype={"county_code": str})[["county_code", "county_name"]]
dim["map_name"] = (dim.county_name + " County, Sweden").where(dim.county_code != "99", "")
dim["region"] = np.where(dim.county_code.isin(NORRLAND), "Norrland", "Rest of Sweden")
dim.loc[dim.county_code == "99", "region"] = ""  # Unknown is outside every regional comparison
dim.to_csv(OUT / "dim_county.csv", index=False, encoding="utf-8")

# ---------- county_year_panel (+ income t-1) ----------
panel = pd.read_csv(PROC / "county_year_panel.csv", dtype={"county_code": str}).sort_values(["county_code", "year"])
panel["median_income_lag_tkr"] = panel.groupby("county_code").median_income_tkr.shift(1)
panel.to_csv(OUT / "county_year_panel.csv", index=False, encoding="utf-8")

# ---------- regressions (notebook 02, section 5) ----------
LAST_FULL = int(fact.month.max()[:4]) - 1          # 2025
p = panel[panel.year.between(2021, LAST_FULL)].copy()
p["ln_inc"], p["ln_dens"] = np.log(p.median_income_lag_tkr), np.log(p.pop_per_km2)
p["norrland"] = p.county_code.isin(NORRLAND).astype(int)
p["post"] = (p.year >= 2023).astype(int)
p["plugin_share"] = p.private_bev_share + p.private_phev_share
assert p[["ln_inc", "private_bev_share"]].notna().all().all() and len(p) == 105


def fit(formula):
    return smf.ols(formula, p).fit(cov_type="cluster", cov_kwds={"groups": p.county_code})


INC10, DENS2 = np.log(1.10) * 100, np.log(2) * 100  # coefficient -> pp per +10% income / per doubling of density
bev = fit("private_bev_share ~ ln_inc + ln_dens + C(year)")
plug = fit("plugin_share ~ ln_inc + ln_dens + C(year)")
inter = fit("private_bev_share ~ ln_inc + ln_dens + norrland + ln_inc:post + ln_dens:post + norrland:post + C(year)")


def stars(pv):
    return "p < 0.01" if pv < 0.01 else "p < 0.05" if pv < 0.05 else "p < 0.1" if pv < 0.1 else f"p = {pv:.2f}, not significant"


rows = []
for res, outcome, var, scale, term, what in [
    (bev, "BEV", "ln_inc", INC10, "BEV share: +10% median income", "10% higher median income (previous year)"),
    (bev, "BEV", "ln_dens", DENS2, "BEV share: 2× population density", "twice the population density"),
    (plug, "plug-in", "ln_inc", INC10, "Plug-in share: +10% median income", "10% higher median income (previous year)"),
    (plug, "plug-in", "ln_dens", DENS2, "Plug-in share: 2× population density", "twice the population density"),
    (inter, "BEV", "ln_dens:post", DENS2, "BEV share: 2× density × post-bonus (2023+)",
     "twice the population density, after the bonus ended compared with before"),
]:
    b, se, pv = res.params[var] * scale, res.bse[var] * scale, res.pvalues[var]
    text = (f"After the bonus ended, each doubling of population density is worth {abs(b):.1f} pp "
            f"{'more' if b >= 0 else 'less'} private BEV share than before ({stars(pv)})." if ":post" in var else
            f"A county with {what} has a private {outcome} share {abs(b):.1f} pp "
            f"{'higher' if b >= 0 else 'lower'}, same year ({stars(pv)}).")
    rows.append({"term": term, "coefficient": round(b, 2), "std_error": round(se, 2), "p_value": round(pv, 4),
                 "interpretation": text})
reg = pd.DataFrame(rows)
reg.to_csv(OUT / "regression_results.csv", index=False, encoding="utf-8")
# Must match the figures quoted in notebook 02
assert round(reg.coefficient[0], 1) == 3.5 and round(reg.coefficient[2], 1) == 5.6 and round(reg.coefficient[4], 1) == 0.9

# ---------- regional_key_numbers ----------
c25 = p[p.year == LAST_FULL].set_index("county_name").private_bev_share
spread = (c25.max() - c25.min()) * 100
comp, priv = fact[fact.owner_type == "company"], fact[fact.owner_type == "private"]
sthlm_comp = comp[comp.county_code == "01"].registrations.sum() / comp.registrations.sum()
sthlm_priv = priv[priv.county_code == "01"].registrations.sum() / priv.registrations.sum()
r2_year = smf.ols("private_bev_share ~ C(year)", p).fit().rsquared
x = p.pivot(index="county_code", columns="year", values=["private_bev_share", "ln_dens", "ln_inc"])
xs = pd.DataFrame({"fall": (x.private_bev_share[2024] - x.private_bev_share[2022]) * 100,
                   "ln_dens": x.ln_dens[2024], "ln_inc22": x.ln_inc[2022]})
fall_per_halving = smf.ols("fall ~ ln_dens + ln_inc22", xs).fit(cov_type="HC3").params["ln_dens"] * np.log(2)
keys = pd.DataFrame([
    {"metric": f"County spread in private BEV share, {LAST_FULL}", "value": round(spread, 1), "unit": "pp",
     "note": f"{c25.idxmax()} {c25.max():.1%} (highest) vs {c25.idxmin()} {c25.min():.1%} (lowest); "
             "mid-table ranks are within noise"},
    {"metric": "Stockholm's share of company registrations", "value": round(sthlm_comp * 100, 1), "unit": "%",
     "note": f"vs {sthlm_priv:.1%} of private registrations: leasing cars are booked to the lessor's county"},
    {"metric": "Variation explained by year alone", "value": round(r2_year * 100, 0), "unit": "%",
     "note": f"R² of county BEV share on year effects; income and density add ~{(bev.rsquared - r2_year) * 100:.0f} points"},
    {"metric": "Extra post-bonus fall per halving of density", "value": round(fall_per_halving, 2), "unit": "pp",
     "note": "Change 2022→2024, controlling for income; sparse counties reacted more to the bonus ending"},
])
keys.to_csv(OUT / "regional_key_numbers.csv", index=False, encoding="utf-8")

# ---------- checks ----------
nt = nat_long.groupby("month").registrations.sum()
ft = fact.groupby("month").registrations.sum()
assert (nt.reindex(ft.index) - ft).abs().max() == 0, "county fact does not sum to national total"
assert (nat_long.registrations >= 0).all() and (fact.registrations >= 0).all()
assert dim.county_code.nunique() == 22 and set(fact.county_code) <= set(dim.county_code)
assert set(panel.county_code) <= set(dim.county_code)
assert nat_long.month.nunique() * len(FUELS) == len(nat_long)

y25 = nat_long[nat_long.month.str[:4] == "2025"]
bev25 = y25[y25.fuel_type == "BEV"].registrations.sum() / y25.registrations.sum()
p12 = priv[priv.month > (pd.Timestamp(priv.month.max()) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")]
r12 = p12[p12.fuel_type == "BEV"].registrations.sum() / p12.registrations.sum()

print(f"national_monthly_long: {len(nat_long):,} rows ({nat_long.month.min()} -> {nat_long.month.max()})")
print(f"fact_county_monthly:   {len(fact):,} rows ({fact.month.min()} -> {fact.month.max()})")
print(f"dim_county:            {len(dim)} rows")
print(f"county_year_panel:     {len(panel)} rows ({panel.year.min()}-{panel.year.max()})")
print(f"2025 BEV share, all owners: {bev25:.1%}  |  private BEV share R12 to {priv.month.max()[:7]}: {r12:.1%}")
print("\nregression_results:\n" + reg[["term", "coefficient", "std_error", "p_value"]].to_string(index=False))
print("\nregional_key_numbers:\n" + keys[["metric", "value", "unit"]].to_string(index=False))
