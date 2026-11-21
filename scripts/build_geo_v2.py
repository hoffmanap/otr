import csv, json, os
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

# OCC1950-style broad buckets by leading code range
def occ_bucket(occ):
    try:
        v = int(occ)
    except (ValueError, TypeError):
        return None
    if v >= 979:  # unemployed / NA / unknown codes in OCC1950 scheme
        return None
    if 0 <= v <= 99: return 'Professional/technical'
    if 100 <= v <= 123: return 'Managers/officials/proprietors'
    if 200 <= v <= 290: return 'Clerical'
    if 300 <= v <= 390: return 'Sales'
    if 400 <= v <= 490: return 'Craftsmen/foremen'
    if 500 <= v <= 595: return 'Operatives'
    if 600 <= v <= 690: return 'Service workers'
    if 700 <= v <= 790: return 'Laborers (non-farm)'
    if 800 <= v <= 890: return 'Farmers/farm laborers'
    return 'Other/unclassified'

def summarize(recs):
    n = len(recs)
    n_lodger = sum(1 for r in recs if r['related'] in LODGER_CODES)
    n_employee = sum(1 for r in recs if r['related'] in EMPLOYEE_CODES)
    households = set(r['b_hh'] for r in recs if r.get('b_hh'))
    n_households = len(households) or 1

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

    # occupation buckets (adults with a classifiable occupation)
    # occ1950 = IPUMS's harmonized occupation classification, populated 1900-1940
    # (the plain 'occ' field used previously is blank for 1900-1930 in this extract)
    occ_counts = defaultdict(int)
    n_occ_known = 0
    for r in recs:
        b = occ_bucket(r.get('occ1950') or r.get('occ'))
        if b:
            occ_counts[b] += 1
            n_occ_known += 1
    top_occs = sorted(occ_counts.items(), key=lambda kv: -kv[1])[:3]

    # income (only meaningfully present 1940+; IPUMS uses 9999999/999999 etc for N/A)
    incomes = []
    for r in recs:
        try:
            v = int(r.get('incwage') or 0)
        except ValueError:
            v = 0
        if 0 < v < 999998:
            incomes.append(v)
    median_income = None
    if incomes:
        s = sorted(incomes)
        mid = len(s) // 2
        median_income = s[mid] if len(s) % 2 else (s[mid-1] + s[mid]) // 2

    # occscore: occupational income score (median 1950 income by occ1950 bucket) -
    # available 1900-1940, used as an income *proxy* where incwage isn't (pre-1940)
    occscores = []
    for r in recs:
        try:
            v = int(r.get('occscore') or -1)
        except ValueError:
            v = -1
        if v >= 0:
            occscores.append(v)
    avg_occscore = round(sum(occscores) / len(occscores), 1) if occscores else None

    residents = []
    for r in recs:
        residents.append({
            'relate': RELATED.get(r['related'], r['related']),
            'race': RACE.get(r['race'], r['race']),
            'ownership': OWNERSHP.get(r['ownershp'], 'N/A'),
            'is_lodger': r['related'] in LODGER_CODES,
            'is_employee': r['related'] in EMPLOYEE_CODES,
            'occ_bucket': occ_bucket(r.get('occ1950') or r.get('occ')),
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
        'top_occupations': top_occs,
        'n_occ_known': n_occ_known,
        'median_income': median_income,
        'avg_occscore': avg_occscore,
        'residents': residents,
    }

GEO_DIR = "/tmp/claude-0/-home-claude/c86972de-12b7-563c-9738-b8020d1cd326/scratchpad/geo_ledger"
OTR_DIR = "/home/claude/otr"

addr_rows = list(csv.DictReader(open(f"{OTR_DIR}/data/otr_addresses_3sheets.csv")))
ipums_rows = list(csv.DictReader(open(f"{OTR_DIR}/data/otr_ipums_all_years.csv")))

by_addr_year = defaultdict(list)
for r in ipums_rows:
    key = (r['sheet'], r['block_id'], r['address'], r['year'])
    by_addr_year[key].append(r)

manifest = {e["sheet"]: e for e in json.load(open(f"{GEO_DIR}/manifest.json"))}
old_sheets = {
    "vol025_sheet101.jpg": {"w":1637,"h":1949,"code":"101"},
    "vol025_sheet102.jpg": {"w":1634,"h":1949,"code":"102a"},
    "vol025_sheet103.jpg": {"w":1637,"h":1949,"code":"103a"},
}

def affine_latlon(u, v, corners):
    tl, tr, bl = corners["topleft"], corners["topright"], corners["bottomleft"]
    lat = tl[0] + u*(tr[0]-tl[0]) + v*(bl[0]-tl[0])
    lon = tl[1] + u*(tr[1]-tl[1]) + v*(bl[1]-tl[1])
    return [lat, lon]

out_addresses = []
for a in addr_rows:
    sheet_info = old_sheets[a['sheet']]
    code = sheet_info['code']
    corners = manifest[code]
    u = float(a['x']) / sheet_info['w']
    v = float(a['y']) / sheet_info['h']
    entry = {
        'sheet': a['sheet'], 'block_id': a['block_id'], 'street': a['street'],
        'address': a['address'], 'latlon': affine_latlon(u, v, corners),
    }
    census_by_year = {}
    for year in YEARS:
        key = (a['sheet'], a['block_id'], a['address'], year)
        recs = by_addr_year.get(key, [])
        if recs:
            census_by_year[year] = summarize(recs)
    if census_by_year:
        entry['census_by_year'] = census_by_year
    out_addresses.append(entry)

geo_sheets = json.load(open(f"{GEO_DIR}/geo_sheets.json"))
sheets_out = {}
for code, info in geo_sheets.items():
    sheets_out[code] = {"img": f"geo/{info['img']}", "topleft": info["topleft"],
                         "topright": info["topright"], "bottomleft": info["bottomleft"]}
for key, info in old_sheets.items():
    # Skip 102/103: their "full" sheet corners are only approximated from the
    # 102a/103a split-piece manifest entry (no separate georeference exists for
    # the full sheet), so adding them here would stack an exact-duplicate image
    # on top of the real split-piece pieces and bury building detail. Only 101
    # has its own distinct georeference, so only it gets a "full_" entry.
    if info['code'] in ('102a', '103a'):
        continue
    corners = manifest[info['code']]
    img_name = {"vol025_sheet101.jpg":"sheet101.jpg","vol025_sheet102.jpg":"sheet102.jpg","vol025_sheet103.jpg":"sheet103.jpg"}[key]
    sheets_out[f"full_{info['code']}"] = {"img": img_name, "topleft": corners["topleft"],
                                            "topright": corners["topright"], "bottomleft": corners["bottomleft"]}

out = {"years": YEARS, "sheets": sheets_out, "addresses": out_addresses}
json.dump(out, open(f"{GEO_DIR}/publish/otr_geo_data.json", "w"))
n_with_census = sum(1 for a in out_addresses if 'census_by_year' in a)
print(f"{len(out_addresses)} addresses, {n_with_census} with census data, {len(sheets_out)} sheets")
