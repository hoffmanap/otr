#!/usr/bin/env python3
"""
Append a fresh export from anchor_picker.html onto your growing master
anchors file. Use this every time you close and reopen the picker for a
new sheet -- each export only has that session's points, so you merge
instead of overwrite.

    python merge_anchors.py otr_anchors.csv "otr_anchors (2).csv"

This adds every row from the second file into the first, in place.
If the new file has no rows for a sheet already in the master, nothing
about that sheet changes. If it has rows for a sheet ALREADY in the
master (e.g. you're redoing a sheet), those rows are added alongside
the old ones -- so if you're correcting a sheet rather than adding a
new one, delete that sheet's old rows from the master first (or just
tell me and I'll do it), otherwise you'll end up with duplicates.

The merged result is written back to the first file (the master), so
after running this, your master file is up to date and you run
number_lots.py on it as usual -- no extra steps.
"""
import csv
import sys


def main():
    if len(sys.argv) != 3:
        print('usage: python merge_anchors.py otr_anchors.csv "otr_anchors (2).csv"')
        sys.exit(1)
    master_path, new_path = sys.argv[1], sys.argv[2]

    with open(master_path, newline="", encoding="utf-8") as f:
        master_rows = list(csv.DictReader(f))
    with open(new_path, newline="", encoding="utf-8") as f:
        new_rows = list(csv.DictReader(f))

    master_sheets = {r["sheet"] for r in master_rows}
    new_sheets = {r["sheet"] for r in new_rows}
    overlap = master_sheets & new_sheets
    if overlap:
        print(f"  ! heads up: {sorted(overlap)} already have rows in the master. "
              f"The new rows will be added alongside them, not replace them -- "
              f"if you're correcting a sheet rather than adding new points to it, "
              f"check the master for duplicates afterward.")

    combined = master_rows + new_rows
    with open(master_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sheet", "block_id", "street", "address", "x", "y"])
        w.writeheader()
        w.writerows(combined)

    print(f"{len(master_rows)} existing + {len(new_rows)} new = {len(combined)} rows "
          f"-> {master_path}")
    print(f"Sheets in master now: {sorted(master_sheets | new_sheets)}")


if __name__ == "__main__":
    main()
