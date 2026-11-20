#!/usr/bin/env python3
"""
Link Sanborn addresses to Logan's GRF census household data by street +
house number, for every decade GRF covers (1900-1940) in one pass.

    python merge_census.py otr_addresses.csv path/to/CincinnatiOH building_census.csv

The second argument is the FOLDER containing CincinnatiOH_1900.csv,
CincinnatiOH_1910.csv, etc. (all five years are read automatically).

For each Sanborn address, for each census year, this looks up every GRF
household record at that same street + house number and rolls them up
into one row: how many households, how many people, how many were
Black vs White (per IPUMS's simplified race recode: 1=White, 2=Black,
3=Other -- flag if you want this checked against GRF's own documentation,
I'm going by the values actually in the file, not a codebook), whether
the building was recorded as multifamily, and which enumeration district
it fell in that year.

Matching is on direction + core street name + house number (GRF keeps
the street suffix separate, e.g. "St"/"Ave"/"Pkwy", and that suffix can
change across decades for the same street -- Central Ave became Central
Pkwy once the canal was filled in the late 1920s -- so suffix is
intentionally ignored here).

This does NOT try to resolve a renumbering: if a street's house numbers
actually changed between census years (unlike the ones checked so far),
a given 1950 address may legitimately find nothing in an earlier decade
even though a building stood there -- that's a real historical gap, not
a bug, and worth spot-checking against ward/ED boundaries if a street
you're using is known to have been renumbered.
"""
import csv
import glob
import os
import re
import sys
from collections import defaultdict

YEARS = ["1900", "1910", "1920", "1930", "1940"]

DIR_MAP = {"e": "E", "east": "E", "w": "W", "west": "W",
           "n": "N", "north": "N", "s": "S", "south": "S"}
SUFFIXES = {"st", "street", "ave", "avenue", "pkwy", "parkway", "blvd",
            "boulevard", "rd", "road", "dr", "drive", "pl", "place",
            "ln", "lane", "ter", "terrace", "sq", "square"}


def norm_ours(street):
    toks = re.sub(r"[.,]", "", street).strip().lower().split()
    if not toks:
        return "", ""
    d = ""
    if toks[0] in DIR_MAP:
        d = DIR_MAP[toks[0]]
        toks = toks[1:]
    if len(toks) > 1 and toks[-1] in SUFFIXES:
        toks = toks[:-1]
    return d, " ".join(toks)


def norm_grf(stdir, stname):
    d = (stdir or "").strip().upper()
    core = re.sub(r"[.,]", "", (stname or "")).strip().lower()
    return d, core


def load_grf_year(folder, year):
    path_candidates = glob.glob(os.path.join(folder, f"*{year}.csv"))
    if not path_candidates:
        print(f"  ! no GRF file found for {year} in {folder}")
        return {}
    path = path_candidates[0]
    idx = defaultdict(list)
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            hn = row.get("b_hn") or row.get("m_hn") or ""
            if not hn.isdigit():
                continue
            hn = int(hn)
            d, core = norm_grf(row.get("b_stdir"), row.get("b_stname"))
            idx[(d, core, hn)].append(row)
    return idx


def summarize(records):
    households = set()
    race_counts = defaultdict(int)
    multifam = 0
    eds = defaultdict(int)
    for r in records:
        hh = r.get("b_hh")
        if hh:
            households.add(hh)
        race_counts[r.get("b_race", "")] += 1
        if r.get("b_multifam") == "1":
            multifam = 1
        ed = r.get("b_ed")
        if ed:
            eds[ed] += 1
    best_ed = max(eds, key=eds.get) if eds else ""
    return {
        "n_households": len(households),
        "n_residents": len(records),
        "n_white": race_counts.get("1", 0),
        "n_black": race_counts.get("2", 0),
        "n_other_race": sum(v for k, v in race_counts.items() if k not in ("1", "2")),
        "multifamily": multifam,
        "enumeration_district": best_ed,
    }


def main():
    if len(sys.argv) != 4:
        print("usage: python merge_census.py otr_addresses.csv path/to/CincinnatiOH building_census.csv")
        sys.exit(1)
    addr_path, grf_folder, out_path = sys.argv[1:4]

    with open(addr_path, newline="", encoding="utf-8") as f:
        addresses = list(csv.DictReader(f))

    print("Loading GRF years (this reads ~2M rows total, takes a bit)...")
    year_idx = {}
    for year in YEARS:
        year_idx[year] = load_grf_year(grf_folder, year)
        print(f"  {year}: {len(year_idx[year])} distinct street+housenumber keys loaded")

    out_fields = ["sheet", "block_id", "street", "address", "source", "year",
                  "n_households", "n_residents", "n_white", "n_black",
                  "n_other_race", "multifamily", "enumeration_district"]
    out_rows = []
    matched_any = 0
    for a in addresses:
        try:
            hn = int(a["address"])
        except (ValueError, KeyError):
            continue
        d, core = norm_ours(a["street"])
        found_this_address = False
        for year in YEARS:
            records = list(year_idx[year].get((d, core, hn), []))
            # GRF doesn't always tag direction consistently (e.g. Central
            # Pkwy is tagged "E" in some years, blank in others, for the
            # same real stretch) -- if our directional lookup comes up
            # empty, also check the untagged version of the same street.
            # Never falls back to the OPPOSITE direction, so east/west
            # addresses don't get mixed up.
            if not records and d:
                records = list(year_idx[year].get(("", core, hn), []))
            if not records:
                continue
            found_this_address = True
            s = summarize(records)
            out_rows.append({
                "sheet": a["sheet"], "block_id": a["block_id"], "street": a["street"],
                "address": a["address"], "source": a.get("source", ""), "year": year,
                **s,
            })
        if found_this_address:
            matched_any += 1

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\n{matched_any} of {len(addresses)} Sanborn addresses matched in at least one "
          f"census year; {len(out_rows)} address-year rows total -> {out_path}")


if __name__ == "__main__":
    main()
