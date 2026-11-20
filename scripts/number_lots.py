#!/usr/bin/env python3
"""
Turn hand-entered block-face anchors into a full address list.

You read the low and high (and, where a row of buildings bends, any
in-between) address numbers off each block face by eye, and the pixel
position of each one, into one CSV (see otr_anchors_template.csv for the
format and column names). This script connects the anchors you gave for
each sheet + block_id, in address order, and fills in every address in
between at the position a straight line between its two neighbors
predicts.

This is NOT run once per sheet -- put every sheet's anchors into one CSV
and run this once over all of them:

    python number_lots.py otr_anchors.csv otr_addresses_full.csv

Unlike fill_gaps.py (which bridges gaps in noisy OCR output), every anchor
here is something you read yourself, so there's no guessing about whether
an anchor is real. The only uncertainty is the ADDRESSES IN BETWEEN,
which this fills by straight-line position -- flagged as such -- same as
fill_gaps.py did, just anchored on numbers you trust instead of OCR.
"""
import csv
import sys
from collections import defaultdict


def load_anchors(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    for r in rows:
        try:
            addr = int(r["address"])
            x, y = float(r["x"]), float(r["y"])
        except (ValueError, KeyError, TypeError):
            print(f"  ! skipping unreadable row: {r}")
            continue
        key = (r["sheet"], r["block_id"])
        groups[key].append({
            "address": addr, "x": x, "y": y,
            "street": r.get("street", ""),
        })
    return groups


def number_block(sheet, block_id, anchors):
    anchors = sorted(anchors, key=lambda a: a["address"])
    street = anchors[0]["street"]
    out = []
    for a in anchors:
        out.append({
            "sheet": sheet, "block_id": block_id, "street": street,
            "address": a["address"], "x": round(a["x"], 1), "y": round(a["y"], 1),
            "source": "anchor",
        })
    for a, b in zip(anchors, anchors[1:]):
        step = b["address"] - a["address"]
        if step <= 0:
            print(f"  ! {sheet}/{block_id}: addresses not increasing "
                  f"({a['address']} -> {b['address']}) -- skipping this pair, "
                  f"check your rows are sorted by true address order")
            continue
        parity = step % 2
        if parity != 0:
            print(f"  ! {sheet}/{block_id}: odd gap between {a['address']} and "
                  f"{b['address']} ({step}) -- Sanborn numbers normally step by "
                  f"2, so one of these two may be misread. Filling anyway.")
        n_steps = step // 2 if parity == 0 else step
        inc = 2 if parity == 0 else 1
        for i in range(1, n_steps):
            addr = a["address"] + i * inc
            t = i * inc / step
            x = a["x"] + t * (b["x"] - a["x"])
            y = a["y"] + t * (b["y"] - a["y"])
            out.append({
                "sheet": sheet, "block_id": block_id, "street": street,
                "address": addr, "x": round(x, 1), "y": round(y, 1),
                "source": "filled",
            })
    return out


def main():
    if len(sys.argv) != 3:
        print("usage: python number_lots.py otr_anchors.csv otr_addresses_full.csv")
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]
    groups = load_anchors(in_path)

    all_rows = []
    n_anchor = n_filled = 0
    for (sheet, block_id), anchors in groups.items():
        if len(anchors) < 2:
            # a single anchor usually means one building occupies the whole
            # block face (e.g. a courthouse, a school) -- nothing to
            # interpolate, but the one address you read is still real
            a = anchors[0]
            all_rows.append({
                "sheet": sheet, "block_id": block_id, "street": a["street"],
                "address": a["address"], "x": round(a["x"], 1), "y": round(a["y"], 1),
                "source": "anchor",
            })
            n_anchor += 1
            print(f"  i {sheet}/{block_id}: only 1 anchor ({a['address']}) -- "
                  f"kept as a single address (no block face to fill)")
            continue
        rows = number_block(sheet, block_id, anchors)
        all_rows.extend(rows)
        n_anchor += sum(1 for r in rows if r["source"] == "anchor")
        n_filled += sum(1 for r in rows if r["source"] == "filled")

    all_rows.sort(key=lambda r: (r["sheet"], r["block_id"], r["address"]))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sheet", "block_id", "street", "address",
                                           "x", "y", "source"])
        w.writeheader()
        w.writerows(all_rows)

    print(f"\n{len(groups)} block face(s), {n_anchor} addresses you entered, "
          f"{n_filled} filled in between ({n_anchor + n_filled} total) -> {out_path}")


if __name__ == "__main__":
    main()
