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

# BPL (birthplace) general codes. 001-056 follow STATEFIP numbering (confirmed
# against this data: 039/021/018 - Ohio/Kentucky/Indiana - are by far the most
# common, exactly as expected for Cincinnati). 099 = US, state not specified.
# 100+ are IPUMS's general (3-digit) foreign-country codes, cross-checked
# against IPUMS's published detailed (5-digit) BPL code list, where e.g.
# 45300 = Germany, 41400 = Ireland, 46500 = "Other USSR/Russia" (sources:
# usa.ipums.org/usa-action/variables/BPL and usa.ipums.org/usa/volii/00birthplace.shtml).
BPL_US_STATES = {
    '001':'Alabama','002':'Alaska','004':'Arizona','005':'Arkansas','006':'California',
    '008':'Colorado','009':'Connecticut','010':'Delaware','011':'DC','012':'Florida',
    '013':'Georgia','015':'Hawaii','016':'Idaho','017':'Illinois','018':'Indiana',
    '019':'Iowa','020':'Kansas','021':'Kentucky','022':'Louisiana','023':'Maine',
    '024':'Maryland','025':'Massachusetts','026':'Michigan','027':'Minnesota',
    '028':'Mississippi','029':'Missouri','030':'Montana','031':'Nebraska','032':'Nevada',
    '033':'New Hampshire','034':'New Jersey','035':'New Mexico','036':'New York',
    '037':'North Carolina','038':'North Dakota','039':'Ohio','040':'Oklahoma',
    '041':'Oregon','042':'Pennsylvania','044':'Rhode Island','045':'South Carolina',
    '046':'South Dakota','047':'Tennessee','048':'Texas','049':'Utah','050':'Vermont',
    '051':'Virginia','053':'Washington','054':'West Virginia','055':'Wisconsin','056':'Wyoming',
    '099':'United States (state n.s.)',
}
BPL_FOREIGN = {
    '150':'Canada','160':'Atlantic Islands','199':'North America, n.s.',
    '200':'Mexico','210':'Central America','250':'Cuba','260':'West Indies',
    '300':'South America',
    '410':'England','411':'Scotland','412':'Wales','413':'United Kingdom, n.s.',
    '414':'Ireland','420':'Netherlands','421':'France','422':'Belgium','423':'Luxembourg',
    '425':'Switzerland','426':'Switzerland','430':'Germany','433':'Greece','434':'Italy',
    '435':'Portugal','436':'Spain','440':'Poland','450':'Austria','451':'Hungary',
    '452':'Czechoslovakia','453':'Germany','460':'Yugoslavia','461':'Romania',
    '462':'Bulgaria','465':'Russia/USSR','499':'Europe, n.s.',
    '500':'China','501':'Japan','502':'Philippines','520':'Other Asia',
    '600':'Africa','700':'Australia/New Zealand/Pacific','900':'Abroad (American parents)',
}
def bpl_label(code):
    if not code: return None
    code = code.strip()
    if code in ('', '000', '997', '998', '999'): return None
    if code in BPL_US_STATES: return BPL_US_STATES[code]
    if code in BPL_FOREIGN: return BPL_FOREIGN[code]
    try:
        v = int(code)
    except ValueError:
        return None
    if v <= 56: return 'Other US state'
    return 'Other foreign country'
def is_foreign_bpl(code):
    if not code: return False
    code = code.strip()
    if code in BPL_US_STATES: return False
    try:
        v = int(code)
    except ValueError:
        return False
    return v >= 100 and code != '099'

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
    # full occupation distribution (all buckets with >0, for a share-of-workers chart)
    occ_distribution = sorted(
        [[label, round(100*count/n_occ_known, 1)] for label, count in occ_counts.items()],
        key=lambda kv: -kv[1]
    ) if n_occ_known else []

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

    # monthly rent (IPUMS RENT - only meaningfully reported in the 1940 sample;
    # 0/9998/9999 are N/A-type codes)
    rents = []
    for r in recs:
        try:
            v = int(r.get('rent') or 0)
        except ValueError:
            v = 0
        if 0 < v < 9998:
            rents.append(v)
    avg_rent = round(sum(rents)/len(rents), 0) if rents else None

    # birthplace / country of origin (household heads + all residents; BPL covers
    # all 5 census years in this extract). "n_foreign" = share born outside the US.
    bpl_counts = defaultdict(int)
    n_bpl_known = 0
    n_foreign = 0
    for r in recs:
        lbl = bpl_label(r.get('bpl'))
        if lbl:
            bpl_counts[lbl] += 1
            n_bpl_known += 1
            if is_foreign_bpl(r.get('bpl')):
                n_foreign += 1
    # collapse native-state detail into one "Native-born (US)" bucket for the
    # top-origins list, so the list highlights immigrant origin countries
    native_n = sum(c for lbl,c in bpl_counts.items() if lbl in BPL_US_STATES.values() or lbl=='Other US state')
    foreign_counts = {lbl:c for lbl,c in bpl_counts.items() if lbl not in BPL_US_STATES.values() and lbl!='Other US state'}
    top_origins = sorted(foreign_counts.items(), key=lambda kv: -kv[1])[:5]
    top_origins = [[lbl, round(100*c/n_bpl_known,1)] for lbl,c in top_origins] if n_bpl_known else []
    pct_foreign_born = round(100*n_foreign/n_bpl_known, 1) if n_bpl_known else None

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
            'origin': bpl_label(r.get('bpl')),
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
        'occ_distribution': occ_distribution,
        'n_occ_known': n_occ_known,
        'median_income': median_income,
        'avg_rent': avg_rent,
        'avg_occscore': avg_occscore,
        'pct_foreign_born': pct_foreign_born,
        'top_origins': top_origins,
        'n_bpl_known': n_bpl_known,
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
    "vol025_sheet135.jpg": {"w":1652,"h":1949,"code":"135a"},
}

def affine_latlon(u, v, corners):
    tl, tr, bl = corners["topleft"], corners["topright"], corners["bottomleft"]
    lat = tl[0] + u*(tr[0]-tl[0]) + v*(bl[0]-tl[0])
    lon = tl[1] + u*(tr[1]-tl[1]) + v*(bl[1]-tl[1])
    return [lat, lon]

# Sheets 102/103 only have a georeference for the "a" split-piece image (a
# crop of the original full sheet used for the transparency fix), not the
# full sheet. Addresses were anchored in the FULL sheet's pixel space, so
# they must first be remapped into the piece's own local pixel space before
# applying the piece's corners. These affine matrices (full-sheet px -> piece
# px) were recovered via ORB feature matching between the full sheet and the
# piece image (60/60 RANSAC inliers, near-pure uniform scale, no rotation) -
# see /tmp/.../scratchpad/geo_ledger notes. Addresses whose remapped pixel
# falls outside the piece's own image bounds aren't covered by this crop and
# are dropped rather than placed with a guess.
FULL_TO_PIECE_PX = {
    "vol025_sheet102.jpg": [[1.4356275680693806, 9.232909612842442e-05, 491.0218592636508],
                            [-9.232909612842442e-05, 1.4356275680693806, 155.83920075592837]],
    "vol025_sheet103.jpg": [[1.4279275104029436, -0.00018404918506584545, 433.2172451178396],
                             [0.00018404918506584545, 1.4279275104029436, 245.13729780896122]],
    "vol025_sheet135.jpg": [[1.2352470241611107, -0.00010939004087052401, 180.63988693987704],
                             [0.00010939004087052401, 1.2352470241611107, 314.9480510686093]],
}
def invert_affine(M):
    a,b,tx = M[0]; c,d,ty = M[1]
    det = a*d - b*c
    ai, bi, ci, di = d/det, -b/det, -c/det, a/det
    txi = -(ai*tx + bi*ty)
    tyi = -(ci*tx + di*ty)
    return [[ai,bi,txi],[ci,di,tyi]]
FULL_TO_PIECE_PX_INV = {k: invert_affine(v) for k,v in FULL_TO_PIECE_PX.items()}

from PIL import Image as _PILImage
_piece_px_dims = {}  # code -> (w, h), lazily loaded
def piece_dims(code, img_rel_path):
    if code not in _piece_px_dims:
        with _PILImage.open(f"{GEO_DIR}/publish/{img_rel_path}") as im:
            _piece_px_dims[code] = im.size
    return _piece_px_dims[code]

out_addresses = []
n_dropped_uncovered = 0
for a in addr_rows:
    sheet_info = old_sheets[a['sheet']]
    code = sheet_info['code']
    corners = manifest[code]
    x, y = float(a['x']), float(a['y'])
    if a['sheet'] in FULL_TO_PIECE_PX_INV:
        # remap full-sheet pixel -> this split piece's own local pixel space
        Mi = FULL_TO_PIECE_PX_INV[a['sheet']]
        px = Mi[0][0]*x + Mi[0][1]*y + Mi[0][2]
        py = Mi[1][0]*x + Mi[1][1]*y + Mi[1][2]
        pw, ph = piece_dims(code, f"geo/vol_{code}.png")
        if not (0 <= px <= pw and 0 <= py <= ph):
            n_dropped_uncovered += 1
            continue  # this address falls outside the georeferenced split piece
        u, v = px / pw, py / ph
    else:
        u = x / sheet_info['w']
        v = y / sheet_info['h']
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
if n_dropped_uncovered:
    print(f"dropped {n_dropped_uncovered} addresses outside the georeferenced split-piece crop")

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
    if info['code'] in ('102a', '103a', '135a'):
        continue
    corners = manifest[info['code']]
    img_name = {"vol025_sheet101.jpg":"sheet101.jpg","vol025_sheet102.jpg":"sheet102.jpg","vol025_sheet103.jpg":"sheet103.jpg"}[key]
    sheets_out[f"full_{info['code']}"] = {"img": img_name, "topleft": corners["topleft"],
                                            "topright": corners["topright"], "bottomleft": corners["bottomleft"]}

out = {"years": YEARS, "sheets": sheets_out, "addresses": out_addresses}
json.dump(out, open(f"{GEO_DIR}/publish/otr_geo_data.json", "w"))
n_with_census = sum(1 for a in out_addresses if 'census_by_year' in a)
print(f"{len(out_addresses)} addresses, {n_with_census} with census data, {len(sheets_out)} sheets")
