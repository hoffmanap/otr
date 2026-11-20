#!/usr/bin/env python3
"""
Join your Sanborn/OTR addresses to IPUMS's full-count person-level data
via histid, going through GRF as the address-to-household bridge.

    python merge_ipums.py otr_anchors.csv path/to/CincinnatiOH usa_00008.dat usa_00008.do otr_ipums_merged.csv

Why go through GRF at all, instead of joining IPUMS straight to your
addresses? IPUMS's extract (as pulled) doesn't carry a clean street
name / house number -- GRF already did the work of parsing and
standardizing those from the same underlying household records, and
histid is what ties a GRF row to its IPUMS sibling row for the same
person. So: Sanborn address -> (street+housenumber match) -> GRF row
-> (histid match) -> IPUMS row.

The .do file is read to find the column layout automatically (the
`infix` block Stata uses), so this keeps working if you add more
years or variables to future IPUMS extracts without needing the
column positions hand-edited here.

Output is one row per matched PERSON (not aggregated to building
level like merge_census.py's output) -- building-level rollups lose
exactly the kind of detail (who specifically was a lodger, what this
one person's occupation was) that's the whole reason to pull IPUMS
variables in the first place.

Runs across every census year GRF covers (1900-1940) in one pass,
joining each year's GRF rows to that SAME year's IPUMS rows (histid
is only unique within a census year, so the join key is (year,
histid), never histid alone).
"""
import csv
import glob
import os
import re
import sys
from collections import Counter, defaultdict

GRF_YEARS = ["1900", "1910", "1920", "1930", "1940"]


def norm_street(street):
    toks = re.sub(r"[.,]", "", street).strip().lower().split()
    DIR_MAP = {"e": "E", "east": "E", "w": "W", "west": "W",
               "n": "N", "north": "N", "s": "S", "south": "S"}
    SUFFIXES = {"st", "street", "ave", "avenue", "pkwy", "parkway", "blvd",
                "boulevard", "rd", "road", "dr", "drive", "pl", "place",
                "ln", "lane", "ter", "terrace", "sq", "square"}
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


def parse_do_layout(do_path):
    """Pull (name, start, end) column specs out of Stata's `infix` block."""
    text = open(do_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"infix\s+(.*?)\s+using", text, re.S)
    if not m:
        raise ValueError("couldn't find an `infix ... using` block in the .do file")
    block = m.group(1)
    specs = []
    for line in block.splitlines():
        m2 = re.match(r"\s*\S+\s+(\w+)\s+(\d+)-(\d+)", line)
        if m2:
            name, start, end = m2.group(1), int(m2.group(2)), int(m2.group(3))
            specs.append((name, start - 1, end))  # 0-indexed slice [start:end]
    if not specs:
        raise ValueError("found an infix block but couldn't parse any variable lines")
    return specs


def load_ipums(dat_path, do_path):
    """Load every row in the extract, keyed by (year, histid).

    histid is only unique WITHIN a census year (it's that year's person
    identifier), so a 1900 histid and a 1920 histid can collide as bare
    strings -- keying by (year, histid) avoids silently overwriting one
    year's person with another's.
    """
    specs = parse_do_layout(do_path)
    year_spec = next((s for s in specs if s[0] == "year"), None)
    histid_spec = next((s for s in specs if s[0] == "histid"), None)
    if not year_spec or not histid_spec:
        raise ValueError("'year' or 'histid' column not found in the .do layout")

    by_year_histid = {}
    years_seen = Counter()
    n_total = n_usable = 0
    with open(dat_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            n_total += 1
            yr = line[year_spec[1]:year_spec[2]].strip()
            hid = line[histid_spec[1]:histid_spec[2]].strip().upper()
            if not hid:
                continue
            n_usable += 1
            years_seen[yr] += 1
            row = {}
            for name, s, e in specs:
                row[name] = line[s:e].strip()
            by_year_histid[(yr, hid)] = row
    print(f"  IPUMS file: {n_total} total rows, {n_usable} have a usable histid, "
          f"by year: {dict(sorted(years_seen.items()))}")
    return by_year_histid


def load_grf_matches(addr_rows, grf_folder, year):
    path_candidates = glob.glob(os.path.join(grf_folder, f"*{year}.csv"))
    if not path_candidates:
        raise FileNotFoundError(f"no GRF file found for {year} in {grf_folder}")
    grf_path = path_candidates[0]

    wanted = defaultdict(list)  # (dir, core, hn) -> [sanborn address rows]
    for a in addr_rows:
        try:
            hn = int(a["address"])
        except (ValueError, KeyError):
            continue
        d, core = norm_street(a["street"])
        wanted[(d, core, hn)].append(a)
        if d:
            wanted[("", core, hn)]  # ensure fallback key exists even if empty

    matches = []  # (sanborn_row, grf_row)
    with open(grf_path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            hn = row.get("b_hn") or row.get("m_hn") or ""
            if not hn.isdigit():
                continue
            hn = int(hn)
            d, core = norm_grf(row.get("b_stdir"), row.get("b_stname"))
            key = (d, core, hn)
            sanborn_rows = wanted.get(key)
            if not sanborn_rows and d:
                sanborn_rows = wanted.get(("", core, hn))
            if not sanborn_rows:
                continue
            for a in sanborn_rows:
                matches.append((a, row))
    return matches


def main():
    if len(sys.argv) != 6:
        print("usage: python merge_ipums.py otr_anchors.csv path/to/CincinnatiOH "
              "usa_00009.dat usa_00009.do otr_ipums_merged.csv")
        sys.exit(1)
    addr_path, grf_folder, dat_path, do_path, out_path = sys.argv[1:6]

    with open(addr_path, newline="", encoding="utf-8") as f:
        addr_rows = list(csv.DictReader(f))

    print(f"Loading IPUMS extract (all years)...")
    ipums_by_year_histid = load_ipums(dat_path, do_path)

    ipums_fields = [name for name, _, _ in parse_do_layout(do_path)
                     if name not in ("year", "histid")]
    out_fields = (["sheet", "block_id", "street", "address", "source", "year",
                    "b_hh", "b_head", "histid"] + ipums_fields)

    out_rows = []
    n_no_ipums_by_year = Counter()
    n_grf_matches_by_year = Counter()
    for year in GRF_YEARS:
        print(f"Matching Sanborn addresses to GRF {year} records...")
        try:
            grf_matches = load_grf_matches(addr_rows, grf_folder, year)
        except FileNotFoundError as e:
            print(f"  ! {e}")
            continue
        n_grf_matches_by_year[year] = len(grf_matches)
        print(f"  {len(grf_matches)} Sanborn-address-to-GRF-household matches")

        for sanborn_row, grf_row in grf_matches:
            hid = grf_row.get("histid", "").strip().upper()
            ipums_row = ipums_by_year_histid.get((year, hid))
            if not ipums_row:
                n_no_ipums_by_year[year] += 1
                continue
            out = {
                "sheet": sanborn_row["sheet"], "block_id": sanborn_row["block_id"],
                "street": sanborn_row["street"], "address": sanborn_row["address"],
                "source": sanborn_row.get("source", ""), "year": year,
                "b_hh": grf_row.get("b_hh", ""), "b_head": grf_row.get("b_head", ""),
                "histid": hid,
            }
            for field in ipums_fields:
                out[field] = ipums_row.get(field, "")
            out_rows.append(out)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\n{len(out_rows)} person-level rows written across {len(GRF_YEARS)} years "
          f"-> {out_path}")
    print(f"  GRF matches by year: {dict(n_grf_matches_by_year)}")
    print(f"  GRF matches with no corresponding IPUMS histid, by year "
          f"(unexpected if large): {dict(n_no_ipums_by_year)}")


if __name__ == "__main__":
    main()
