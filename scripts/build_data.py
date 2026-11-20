import csv
import json
from collections import defaultdict

RELATED = {
 '0101':'Head/Householder','0201':'Spouse','0301':'Child','0302':'Adopted Child','0303':'Stepchild',
 '0401':'Child-in-law','0501':'Parent','0601':'Parent-in-Law','0701':'Sibling','0801':'Sibling-in-Law',
 '0901':'Grandchild','1001':'Other Relatives','1011':'Grandparent','1021':'Aunt or Uncle',
 '1031':'Nephew, Niece','1041':'Cousin','1051':'Great Grandchild','1061':'Other relatives, nec',
 '1111':'Friend','1112':'Partner','1114':'Unmarried Partner','1131':'Visitor',
 '1201':'Roomer/boarder/lodger','1202':'Boarder','1203':'Lodger','1204':'Roomer','1205':'Tenant',
 '1206':'Foster child','1211':'Servant','1212':'Housekeeper','1213':'Maid','1214':'Cook','1215':'Nurse',
 '1216':'Domestic employee','1217':'Other employee','1221':'Military','1222':'Student',
 '1223':'Religious order member','1230':'Other non-relative','1241':'Roomer/boarder/lodger',
 '1251':'Domestic employee','1252':'Non-domestic employee','1281':'Head of group quarters',
 '1282':'Group quarters employee','1291':'Military','1292':'College dormitory',
 '1293':'Rooming house resident','1301':'Institutional inmate',
 '9996':'Unclassifiable','9997':'Unknown','9998':'Illegible','9999':'Missing',
}
LODGER_CODES = {'1201','1202','1203','1204','1205','1241','1293'}
EMPLOYEE_CODES = {'1211','1212','1213','1214','1215','1216','1217','1251','1252'}
RACE = {'1':'White','2':'Black','3':'American Indian/Alaska Native','4':'Chinese',
        '5':'Japanese','6':'Other Asian/Pacific Islander','7':'Other race','8':'Two major races','9':'Three+ major races'}
GQ = {'3':'Group quarters--Institution','4':'Other group quarters'}
OWNERSHP = {'1':'Owned','2':'Rented'}

YEARS = ['1900', '1910', '1920', '1930', '1940']

# Run this from the scripts/ folder: python3 build_data.py
# Reads from ../data/, writes otr_data.json to ../ (repo root, beside index.html).
addr_rows = list(csv.DictReader(open('../data/otr_addresses_3sheets.csv')))
ipums_rows = list(csv.DictReader(open('../data/otr_ipums_all_years.csv')))

by_addr_year = defaultdict(list)
for r in ipums_rows:
    key = (r['sheet'], r['block_id'], r['address'], r['year'])
    by_addr_year[key].append(r)

SHEET_DIMS = {
    'vol025_sheet101.jpg': {'w': 1637, 'h': 1949, 'img': 'sheet101.jpg'},
    'vol025_sheet102.jpg': {'w': 1634, 'h': 1949, 'img': 'sheet102.jpg'},
    'vol025_sheet103.jpg': {'w': 1637, 'h': 1949, 'img': 'sheet103.jpg'},
}


def summarize(recs):
    n = len(recs)
    n_lodger = sum(1 for r in recs if r['related'] in LODGER_CODES)
    n_employee = sum(1 for r in recs if r['related'] in EMPLOYEE_CODES)
    households = set(r['b_hh'] for r in recs if r.get('b_hh'))
    n_households = len(households) or 1  # guard div-by-zero; shouldn't happen if n>0

    race_counts = defaultdict(int)
    for r in recs:
        race_counts[RACE.get(r['race'], r['race'])] += 1
    n_white = race_counts.get('White', 0)
    n_black = race_counts.get('Black', 0)
    n_other_race = n - n_white - n_black

    owner_counts = defaultdict(int)
    for r in recs:
        owner_counts[OWNERSHP.get(r['ownershp'], 'N/A')] += 1
    n_owned = owner_counts.get('Owned', 0)
    n_rented = owner_counts.get('Rented', 0)
    tenure_known = n_owned + n_rented
    pct_rented = round(100 * n_rented / tenure_known, 1) if tenure_known else None

    gqs = sorted(set(GQ.get(r['gq'], '') for r in recs if r['gq'] in GQ))

    residents = []
    for r in recs:
        residents.append({
            'relate': RELATED.get(r['related'], r['related']),
            'race': RACE.get(r['race'], r['race']),
            'ownership': OWNERSHP.get(r['ownershp'], 'N/A'),
            'is_lodger': r['related'] in LODGER_CODES,
            'is_employee': r['related'] in EMPLOYEE_CODES,
        })

    return {
        'n_residents': n,
        'n_households': n_households,
        'persons_per_household': round(n / n_households, 2),
        'n_white': n_white, 'n_black': n_black, 'n_other_race': n_other_race,
        'pct_black': round(100 * n_black / n, 1) if n else 0,
        'pct_white': round(100 * n_white / n, 1) if n else 0,
        'n_owned': n_owned, 'n_rented': n_rented, 'pct_rented': pct_rented,
        'n_lodger': n_lodger, 'n_employee': n_employee,
        'lodger_pct': round(100 * n_lodger / n, 1) if n else 0,
        'group_quarters': gqs,
        'residents': residents,
    }


out_addresses = []
n_with_any = 0
n_with_multi = 0
for a in addr_rows:
    entry = {
        'sheet': a['sheet'], 'block_id': a['block_id'], 'street': a['street'],
        'address': a['address'], 'x': float(a['x']), 'y': float(a['y']),
        'point_source': a.get('source', ''),
    }
    census_by_year = {}
    for year in YEARS:
        key = (a['sheet'], a['block_id'], a['address'], year)
        recs = by_addr_year.get(key, [])
        if recs:
            census_by_year[year] = summarize(recs)
    if census_by_year:
        entry['census_by_year'] = census_by_year
        n_with_any += 1
        if len(census_by_year) > 1:
            n_with_multi += 1
    out_addresses.append(entry)

out = {'sheets': SHEET_DIMS, 'years': YEARS, 'addresses': out_addresses}
with open('../otr_data.json', 'w') as f:
    json.dump(out, f)

print(f"{len(out_addresses)} addresses; {n_with_any} matched in >=1 census year; "
      f"{n_with_multi} matched in >=2 years (longitudinal)")
import os
print(f"{os.path.getsize('../otr_data.json')/1024:.1f} KB")
