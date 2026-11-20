# The Lodging Ledger — Over-the-Rhine

A building-level history of population change in Cincinnati's Over-the-Rhine (OTR)
neighborhood, 1900–1940. It links 1950 Sanborn fire-insurance map addresses to
historical census households, then tracks race, tenure (own/rent), household
density, and group living (lodgers/boarders) at that address over five decades.

**[Open the interactive map →](./index.html)**

This is the Cincinnati/OTR chapter of a larger multi-city project
([hoffmanap/SRO](https://github.com/hoffmanap/SRO)) mapping lodging houses and
group living across historic Sanborn maps. This repo is self-contained for OTR.

## What's here

- Where group living (lodging houses, hotels, rooming houses) existed historically
  in OTR, building by building.
- How the neighborhood's racial composition, home-ownership rate, and household
  density changed between 1900 and 1940, at three levels: the whole neighborhood,
  a street segment or block face, or a single building.

## Status

**First version — proof of concept, 3 of 55 OTR sheets.** Covers Sanborn volume
025, sheets 101–103 only. The full OTR sheet list (55 sheets across volumes 025
and 026) is in [`data/otr_sheet_list.txt`](data/otr_sheet_list.txt) — use it as a
checklist when georeferencing/anchoring the remaining sheets.

Of the 574 addresses anchored on these 3 sheets, 200 matched to a census household
in at least one of the five census years (1900, 1910, 1920, 1930, 1940), and 131
of those matched in two or more years, giving real longitudinal data for roughly
a quarter of the mapped addresses so far. Match rate should improve as more sheets
and more careful block-face splitting are added.

Positions on the map are **pixel coordinates on the sheet image**, not yet real
geographic coordinates — georeferencing to true lat/long is a planned next step.

## How it works (pipeline)

```
 1. Sanborn sheet image (JPG)
        │  hand-click building addresses along a block face
        ▼
 2. anchor_picker.html  →  otr_anchors.csv
        │  merge new picker exports onto the running master file
        ▼
 3. merge_anchors.py    →  otr_anchors_master.csv
        │  interpolate missing house numbers along each block face
        ▼
 4. number_lots.py      →  otr_addresses.csv   (sheet, block_id, street, address, x, y)
        │  join to GRF census households by street + house number, per year
        ▼
 5. merge_census.py     →  otr_census_merged.csv   (building-level rollup, 1900-1940)
        │  OR, for person-level detail:
        ▼
 5b. merge_ipums.py     →  otr_ipums_merged.csv   (one row per matched resident)
        │  decode IPUMS's numeric codes into readable labels / print findings
        ▼
 6. decode_findings.py  (prints a text summary — optional, for exploration)
        │  build the dashboard's data file
        ▼
 7. build_data.py       →  otr_data.json
        │  the page reads this
        ▼
 8. index.html          (the published map/dashboard)
```

### 1–2. Anchoring addresses on a sheet

[`scripts/anchor_picker.html`](scripts/anchor_picker.html) is a self-contained
browser tool — open it locally (no server needed), load a Sanborn sheet image,
and click each visible house number along one straight, uninterrupted run of
building frontage (a "block face": one side of one street, no corner, no
cross-street). Give that run a `block_id` name (e.g. `ninth_odd`,
`vine_e_side`). Export when done; each export only contains that session's new
points, since the tool is typically closed and reopened per sheet.

**One block_id = one straight street frontage.** Don't lump multiple streets or
both sides of a street under one block_id — the interpolation step assumes
addresses within a block_id increase or decrease monotonically along that one
frontage.

### 3. Merging picker exports

```
python3 merge_anchors.py otr_anchors_master.csv new_export.csv
```

Appends the new export's rows onto the running master CSV (never overwrites).
If you re-anchor a sheet you've already done, delete its old rows from the
master first — this script only appends.

### 4. Filling in the gaps

```
python3 number_lots.py otr_anchors_master.csv otr_addresses.csv
```

For each `block_id`, sorts anchors by address and linearly interpolates the
house numbers in between (so you don't have to click literally every building —
just enough anchors to define the pattern). A `block_id` with only one anchor is
kept as a standalone single-building address (e.g. a courthouse) rather than
skipped.

### 5. Linking to census data

Two options, depending on what you need:

- **Building-level rollup** (household counts, race counts, enumeration
  district — no individual-level detail):
  ```
  python3 merge_census.py otr_addresses.csv path/to/CincinnatiOH_GRF_folder otr_census_merged.csv
  ```
- **Person-level detail** (who specifically was a lodger, occupation, etc.) —
  requires an IPUMS full-count extract in addition to GRF, joined via IPUMS's
  `histid`:
  ```
  python3 merge_ipums.py otr_addresses.csv path/to/CincinnatiOH_GRF_folder usa_000XX.dat usa_000XX.do otr_ipums_merged.csv
  ```

Both match Sanborn addresses to GRF rows by (direction, core street name, house
number), year by year, with a direction-tagging fallback (GRF is inconsistent
about whether a street's direction prefix is tagged, e.g. Central
Ave/Pkwy — the fallback tries the untagged version of the same core name, but
never falls back to the *opposite* direction).

`decode_findings.py` is a standalone exploration script — it decodes IPUMS's
numeric relate/race/gq/ownership codes into readable labels and prints a text
summary (overall + per-address). Useful for sanity-checking a merge; not part
of the pipeline that builds the page.

### 6–7. Building the page's data file

```
cd scripts && python3 build_data.py
```

Reads `data/otr_addresses_3sheets.csv` and `data/otr_ipums_all_years.csv`,
decodes IPUMS codes, and writes `otr_data.json` to the repo root — the file
`index.html` fetches at runtime. Re-run this any time the underlying address or
census data changes.

## Data sources

- **Sanborn Fire Insurance Maps**, Cincinnati, 1950 (Library of Congress /
  Ohio Web Library digitized volumes 025–026).
- **GRF (Geographic Reconciliation File)**, Brown University's S4/UTP project —
  historical census household-level data for Cincinnati, 1900–1940, with
  parsed street/house-number fields.
  ([S4 UTP project](https://s4.ad.brown.edu/Projects/UTP2/citymaps.htm))
- **IPUMS USA full-count extracts** — person-level 1900–1950 census microdata,
  joined to GRF via IPUMS's own `histid` identifier.
  ([IPUMS USA](https://usa.ipums.org))

Raw GRF and IPUMS extract files are **not included in this repo** (size and/or
usage-terms reasons — the IPUMS `.dat` extract alone runs several hundred MB).
`data/` holds only the derived, already-merged outputs needed to rebuild
`otr_data.json`.

## Repo layout

```
index.html                   the published page
otr_data.json                 data the page loads (built by scripts/build_data.py)
sheet101.jpg / 102 / 103.jpg  the 3 Sanborn sheet images this version covers
scripts/
  anchor_picker.html           browser tool: click addresses on a sheet image
  merge_anchors.py             append new picker exports to the master anchors file
  number_lots.py                interpolate full address lists along block faces
  merge_census.py               Sanborn address -> GRF census household (building-level)
  merge_ipums.py                 Sanborn address -> GRF -> IPUMS person (person-level)
  decode_findings.py            optional: decode IPUMS codes + print a findings summary
  build_data.py                  build otr_data.json for the page
data/
  otr_sheet_list.txt             full 55-sheet OTR boundary checklist (vol 025 + 026)
  otr_anchors_3sheets.csv        hand-clicked anchor points, sheets 101-103
  otr_addresses_3sheets.csv      interpolated full address list, sheets 101-103
  otr_census_merged.csv          building-level GRF rollup, sheets 101-103
  otr_ipums_all_years.csv        person-level GRF+IPUMS join, 1900-1940, sheets 101-103
```

## Known limitations

- **Pixel coordinates, not geo-coordinates.** Map positions are placed on the
  sheet image itself; a real lat/long georeference is planned but not yet done.
- **"Block face" ≠ city block.** A block_id is one straight side of one street
  between anchors, not a full four-sided block. The page's freeform
  drag-to-select tool is the current workaround for analyzing a real block or
  any other custom area.
- **3 of 55 sheets.** Everything here is a small, non-representative slice of
  the full OTR boundary.
- **Street renumbering isn't resolved.** A missing match in a given census year
  can mean the building wasn't matched for several different reasons — a real
  data gap, non-residential/commercial use that year, or a house-number change
  over time — not necessarily that the building didn't exist.
