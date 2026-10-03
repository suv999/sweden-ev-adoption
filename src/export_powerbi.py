"""Export tidy CSVs for the Power BI project (powerbi/SwedenEV.*).

Reads data/processed/ (built by src/build_dataset.py) and writes powerbi/data/:
  national_monthly_long.csv  month, fuel_type, registrations              (2006-01 onwards, all owners)
  fact_county_monthly.csv    month, county_code, fuel_type, owner_type,
                             registrations                                (2021-01 onwards)
  dim_county.csv             county_code, county_name, map_name

Run from the repo root:  python src/export_powerbi.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "data" / "processed", ROOT / "powerbi" / "data"
OUT.mkdir(parents=True, exist_ok=True)

FUELS = ["BEV", "PHEV", "HEV", "PETROL", "DIESEL", "ETHANOL", "GAS", "OTHER"]

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
dim.to_csv(OUT / "dim_county.csv", index=False, encoding="utf-8")

# ---------- checks ----------
nt = nat_long.groupby("month").registrations.sum()
ft = fact.groupby("month").registrations.sum()
assert (nt.reindex(ft.index) - ft).abs().max() == 0, "county fact does not sum to national total"
assert (nat_long.registrations >= 0).all() and (fact.registrations >= 0).all()
assert dim.county_code.nunique() == 22 and set(fact.county_code) <= set(dim.county_code)
assert nat_long.month.nunique() * len(FUELS) == len(nat_long)

y25 = nat_long[nat_long.month.str[:4] == "2025"]
bev25 = y25[y25.fuel_type == "BEV"].registrations.sum() / y25.registrations.sum()
p = fact[fact.owner_type == "private"]
p12 = p[p.month > (pd.Timestamp(p.month.max()) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")]
r12 = p12[p12.fuel_type == "BEV"].registrations.sum() / p12.registrations.sum()

print(f"national_monthly_long: {len(nat_long):,} rows ({nat_long.month.min()} -> {nat_long.month.max()})")
print(f"fact_county_monthly:   {len(fact):,} rows ({fact.month.min()} -> {fact.month.max()})")
print(f"dim_county:            {len(dim)} rows")
print(f"2025 BEV share, all owners: {bev25:.1%}  |  private BEV share R12 to {p.month.max()[:7]}: {r12:.1%}")
