"""Build clean, analysis-ready tables for the Sweden EV adoption project.

Inputs  (data/raw/, untouched downloads):
  trafa_t10030_county_monthly_raw.csv   Trafikanalys t10030 - new registrations, passenger cars,
                                        month x county (lan) x fuel x owner category, 2021-01 onwards
                                        (2017-2020 only annual national/county totals)
  trafa_t10036_national_monthly_raw.csv Trafikanalys t10036 - new registrations, passenger cars,
                                        month x fuel, national, 2006-01 onwards
  trafa_t10026_county_annual_raw.csv    Trafikanalys t10026 - passenger cars per county x year x fuel:
                                        new registrations during year + cars in traffic at year end
  scb_region_context_raw.csv            SCB BE0101C (population, land area, density) and
                                        HE0110A/SamForvInk1 (mean/median earned income, age 20-64, tkr)

Outputs (data/processed/ + data/ev_sweden.sqlite).
Run from the repo root:  python src/build_dataset.py
"""
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

FUEL = {  # Trafikanalys drivmedel code -> (short code, English label)
    "101": ("PETROL", "Petrol (incl. mild hybrids)"),
    "102": ("DIESEL", "Diesel (incl. mild hybrids)"),
    "103": ("BEV", "Battery electric"),
    "104": ("HEV", "Hybrid electric (non plug-in)"),
    "105": ("PHEV", "Plug-in hybrid"),
    "106": ("ETHANOL", "Ethanol/E85"),
    "107": ("GAS", "Gas (CNG/biogas/LPG)"),
    "109": ("OTHER", "Other"),
}
OWNER = {"10": "private", "20": "company", "30": "dealer"}
COUNTY = {
    "01": "Stockholm", "03": "Uppsala", "04": "Södermanland", "05": "Östergötland",
    "06": "Jönköping", "07": "Kronoberg", "08": "Kalmar", "09": "Gotland", "10": "Blekinge",
    "12": "Skåne", "13": "Halland", "14": "Västra Götaland", "17": "Värmland", "18": "Örebro",
    "19": "Västmanland", "20": "Dalarna", "21": "Gävleborg", "22": "Västernorrland",
    "23": "Jämtland", "24": "Västerbotten", "25": "Norrbotten", "aa": "Unknown",
}
BONUS_END = pd.Timestamp("2022-11-01")  # climate bonus abolished 8 Nov 2022


def read(name):
    return pd.read_csv(RAW / name, dtype=str, encoding="utf-8-sig")


def shares(wide, total_col="total"):
    for f in ["BEV", "PHEV", "HEV", "PETROL", "DIESEL"]:
        wide[f"{f.lower()}_share"] = (wide[f] / wide[total_col]).round(5)
    wide["plugin_share"] = ((wide["BEV"] + wide["PHEV"]) / wide[total_col]).round(5)
    return wide


# ---------- 1. County x month x fuel x owner fact table (2021-) ----------
c = read("trafa_t10030_county_monthly_raw.csv")
c["nyreg"] = c["nyreg"].astype(int)
detail = c[(c.manad != "t1") & (c.lan != "t1") & (c.drivm != "t1") & (c.agarkat != "t1")].copy()
detail["month"] = pd.to_datetime(detail.ar + "-" + detail.manad + "-01")
detail["county_code"] = detail.lan.replace({"aa": "99"})
detail["county_name"] = detail.lan.map(COUNTY)
detail["fuel_type"] = detail.drivm.map(lambda x: FUEL[x][0])
detail["owner_type"] = detail.agarkat.map(OWNER)
fact = (detail.rename(columns={"nyreg": "registrations"})
        [["month", "county_code", "county_name", "fuel_type", "owner_type", "registrations"]]
        .sort_values(["month", "county_code", "fuel_type", "owner_type"]))
fact["month"] = fact.month.dt.strftime("%Y-%m-%d")
fact.to_csv(OUT / "fact_registrations_county_monthly.csv", index=False)

# Validation against the published totals in the same extract
tot = c[(c.manad != "t1") & (c.lan == "t1") & (c.drivm == "t1") & (c.agarkat == "t1")]
tot = tot.assign(month=(tot.ar + "-" + tot.manad + "-01")).set_index("month")["nyreg"]
chk = fact.groupby("month").registrations.sum()
assert (chk - tot.reindex(chk.index)).abs().max() == 0, "county fact does not sum to national total"
assert (fact.registrations >= 0).all()
assert fact[fact.county_code != "99"].groupby("month").county_code.nunique().min() == 21

# ---------- 2. National monthly by fuel (2006-) ----------
n = read("trafa_t10036_national_monthly_raw.csv")
n = n[n.manad.str.fullmatch(r"\d{2}") & n.drivm.isin(FUEL)].copy()
n["registrations"] = pd.to_numeric(n.nyreg.str.replace("–", "0"), errors="raise").astype(int)  # "–" = zero in Trafa tables
n["month"] = pd.to_datetime(n.ar + "-" + n.manad + "-01")
n["fuel_type"] = n.drivm.map(lambda x: FUEL[x][0])
nat_long = n[["month", "fuel_type", "registrations"]].sort_values(["month", "fuel_type"])
nat = nat_long.pivot_table(index="month", columns="fuel_type", values="registrations", aggfunc="sum").fillna(0).astype(int)
for f in [v[0] for v in FUEL.values()]:
    if f not in nat:
        nat[f] = 0
nat["total"] = nat[[v[0] for v in FUEL.values()]].sum(axis=1)
nat = shares(nat)
nat["post_bonus_end"] = (nat.index >= BONUS_END).astype(int)
nat["pull_forward_window"] = nat.index.isin(pd.date_range("2022-09-01", "2022-11-01", freq="MS")).astype(int)

# Private-buyer national series from the county extract (2021-)
priv = (fact[fact.owner_type == "private"].assign(month=lambda d: pd.to_datetime(d.month))
        .pivot_table(index="month", columns="fuel_type", values="registrations", aggfunc="sum"))
nat["private_total"] = priv.sum(axis=1).reindex(nat.index)
nat["private_bev_share"] = (priv["BEV"] / priv.sum(axis=1)).round(5).reindex(nat.index)
nat = nat.reset_index()
nat["month"] = nat.month.dt.strftime("%Y-%m-%d")
cols = ["month", "total", "BEV", "PHEV", "HEV", "PETROL", "DIESEL", "ETHANOL", "GAS", "OTHER",
        "bev_share", "phev_share", "plugin_share", "hev_share", "petrol_share", "diesel_share",
        "private_total", "private_bev_share", "post_bonus_end", "pull_forward_window"]
nat[cols].to_csv(OUT / "national_monthly_by_fuel.csv", index=False)

# Cross-check t10036 (national) against t10030 (county sum) where they overlap
xc = nat.set_index("month")["total"].reindex(chk.index)
diff = ((xc - chk) / chk).abs()
xcheck = pd.DataFrame({"t10036_national": xc, "t10030_county_sum": chk, "abs_pct_diff": diff.round(4)})
xcheck.to_csv(OUT / "_validation_national_vs_county.csv")

# ---------- 3. County x year (2010-2025): new regs + fleet ----------
a = read("trafa_t10026_county_annual_raw.csv")
a = a[(a.reglan != "t1") & a.drivmedel.isin(FUEL)].copy()
a["year"] = a.ar.astype(int)
a["county_code"] = a.reglan.replace({"aa": "99"})
a["fuel_type"] = a.drivmedel.map(lambda x: FUEL[x][0])
a["new_registrations"] = pd.to_numeric(a.nyregunder, errors="coerce").fillna(0).astype(int)
a["fleet_in_traffic"] = pd.to_numeric(a.itrfslut, errors="coerce").fillna(0).astype(int)
ann = a[["year", "county_code", "fuel_type", "new_registrations", "fleet_in_traffic"]]
ann = ann.sort_values(["year", "county_code", "fuel_type"])
ann.to_csv(OUT / "county_annual_by_fuel.csv", index=False)

# ---------- 4. SCB context ----------
s = pd.read_csv(RAW / "scb_region_context_raw.csv", dtype={"region": str}, encoding="utf-8-sig")
s = s.rename(columns={"mean_inc": "mean_income_tkr", "median_inc": "median_income_tkr",
                      "density": "pop_per_km2"})
s["level"] = np.where(s.region == "00", "national", np.where(s.region.str.len() == 2, "county", "municipality"))
s["county_code"] = s.region.str[:2].where(s.region != "00")
s[["region", "region_name", "level", "county_code", "year", "population", "land_km2", "pop_per_km2",
   "mean_income_tkr", "median_income_tkr"]].to_csv(OUT / "scb_region_context.csv", index=False)

dim_county = (s[(s.level == "county") & (s.year == s.year.max())]
              [["region", "land_km2"]].rename(columns={"region": "county_code"}))
dim_county["county_name"] = dim_county.county_code.map(COUNTY)
dim_county["county_name_sv"] = s[(s.level == "county") & (s.year == s.year.max())].region_name.values
dim_county = pd.concat([dim_county, pd.DataFrame([{"county_code": "99", "county_name": "Unknown",
                                                    "county_name_sv": "Okänt län"}])])
dim_county[["county_code", "county_name", "county_name_sv", "land_km2"]].to_csv(OUT / "dim_county.csv", index=False)

# ---------- 5. County x year analysis panel ----------
w = ann[ann.county_code != "99"].pivot_table(index=["county_code", "year"], columns="fuel_type",
                                             values=["new_registrations", "fleet_in_traffic"], aggfunc="sum").fillna(0)
panel = pd.DataFrame(index=w.index)
nr, fl = w["new_registrations"], w["fleet_in_traffic"]
panel["new_regs_total"] = nr.sum(axis=1).astype(int)
panel["new_bev"] = nr["BEV"].astype(int)
panel["new_phev"] = nr["PHEV"].astype(int)
panel["bev_share_all_owners"] = (nr["BEV"] / nr.sum(axis=1)).round(5)
panel["phev_share_all_owners"] = (nr["PHEV"] / nr.sum(axis=1)).round(5)
panel["fleet_total"] = fl.sum(axis=1).astype(int)
panel["fleet_bev"] = fl["BEV"].astype(int)
panel["fleet_bev_share"] = (fl["BEV"] / fl.sum(axis=1)).round(5)
panel = panel.reset_index()

f2 = pd.read_csv(OUT / "fact_registrations_county_monthly.csv", dtype={"county_code": str})
f2["year"] = f2.month.str[:4].astype(int)
full_years = f2.groupby("year").month.nunique()
f2 = f2[f2.year.isin(full_years[full_years == 12].index)]
pv = f2.pivot_table(index=["county_code", "year"], columns=["owner_type", "fuel_type"],
                    values="registrations", aggfunc="sum").fillna(0)
own = pd.DataFrame(index=pv.index)
for o in ["private", "company"]:
    own[f"{o}_new_regs"] = pv[o].sum(axis=1).astype(int)
    own[f"{o}_bev_share"] = (pv[o]["BEV"] / pv[o].sum(axis=1)).round(5)
own["private_phev_share"] = (pv["private"]["PHEV"] / pv["private"].sum(axis=1)).round(5)
own["private_owner_pct"] = (pv["private"].sum(axis=1) / pv.sum(axis=1)).round(4)
panel = panel.merge(own.reset_index(), on=["county_code", "year"], how="left")

ctx = s[s.level == "county"].drop(columns="county_code").rename(columns={"region": "county_code"})
panel = panel.merge(ctx[["county_code", "year", "population", "land_km2", "pop_per_km2",
                         "median_income_tkr", "mean_income_tkr"]], on=["county_code", "year"], how="left")
panel.insert(1, "county_name", panel.county_code.map(COUNTY))
panel["new_regs_per_1000_pop"] = (panel.new_regs_total / panel.population * 1000).round(2)
panel["bev_fleet_per_1000_pop"] = (panel.fleet_bev / panel.population * 1000).round(2)
panel = panel.sort_values(["year", "county_code"])
panel.to_csv(OUT / "county_year_panel.csv", index=False)

# ---------- 6. SQLite ----------
db = ROOT / "data" / "ev_sweden.sqlite"
db.unlink(missing_ok=True)
with sqlite3.connect(db) as con:
    for name in ["fact_registrations_county_monthly", "national_monthly_by_fuel", "county_annual_by_fuel",
                 "scb_region_context", "dim_county", "county_year_panel"]:
        pd.read_csv(OUT / f"{name}.csv", dtype={"county_code": str, "region": str}).to_sql(name, con, index=False)
    pd.DataFrame([{"fuel_type": v[0], "trafa_code": k, "label": v[1]} for k, v in FUEL.items()]).to_sql("dim_fuel", con, index=False)

print("fact rows", len(fact), "| national months", len(nat), "| panel rows", len(panel))
print("max |national vs county| diff:", diff.max())
