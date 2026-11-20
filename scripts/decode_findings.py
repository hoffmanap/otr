import csv
from collections import Counter, defaultdict

RELATED = {
 '0101':'Head/Householder','0201':'Spouse','0301':'Child','0302':'Adopted Child','0303':'Stepchild',
 '0401':'Child-in-law','0501':'Parent','0601':'Parent-in-Law','0701':'Sibling','0801':'Sibling-in-Law',
 '0901':'Grandchild','1001':'Other Relatives','1011':'Grandparent','1021':'Aunt or Uncle',
 '1031':'Nephew, Niece','1041':'Cousin','1051':'Great Grandchild','1061':'Other relatives, nec',
 '1111':'Friend','1112':'Partner','1114':'Unmarried Partner','1131':'Visitor',
 '1201':'Roomers/boarders/lodgers','1202':'Boarders','1203':'Lodgers','1204':'Roomer','1205':'Tenant',
 '1206':'Foster child','1211':'Servant','1212':'Housekeeper','1213':'Maid','1214':'Cook','1215':'Nurse',
 '1216':'Other probable domestic employee','1217':'Other employee','1221':'Military','1222':'Students',
 '1223':'Members of religious orders','1230':'Other non-relatives','1241':'Roomers/boarders/lodgers',
 '1251':'Domestic employees','1252':'Non-domestic employees','1281':'Head of group quarters',
 '1282':'Employees of group quarters','1291':'Military','1292':'College dormitories',
 '1293':'Residents of rooming houses','1301':'Institutional inmates',
 '9996':'Unclassifiable','9997':'Unknown','9998':'Illegible','9999':'Missing',
}
RACE = {'1':'White','2':'Black/African American','3':'American Indian or Alaska Native','4':'Chinese',
        '5':'Japanese','6':'Other Asian or Pacific Islander','7':'Other race, nec','8':'Two major races','9':'Three or more major races'}
GQTYPE = {'0':'NA (non-group quarters)','1':'Institution','2':'Correctional institution',
          '3':'Mental institution','4':'Institution (elderly/handicapped/poor)','5':'Non-institutional GQ',
          '6':'Military','7':'College dormitory','8':'Rooming house','9':'Other non-institutional GQ/unknown'}
GQ = {'0':'Vacant unit','1':'Households (1970 def)','2':'Additional households (1990 def)',
      '3':'Group quarters--Institutions','4':'Other group quarters','5':'Additional households (2000 def)','6':'Fragment'}
OWNERSHP = {'0':'N/A','1':'Owned','2':'Rented'}

rows = list(csv.DictReader(open('otr_ipums_merged.csv')))
addr_keys = sorted(set((r['sheet'], r['block_id'], r['address']) for r in rows), key=lambda k:(k[0],k[1],int(k[2])))
print(f"{len(rows)} residents across {len(addr_keys)} matched addresses (1900)\n")

print("=== Relationship to household head ===")
c = Counter(RELATED.get(r['related'], r['related']) for r in rows)
for label, n in c.most_common():
    print(f"  {n:3d}  {label}")

print("\n=== Race ===")
c = Counter(RACE.get(r['race'], r['race']) for r in rows)
for label, n in c.most_common():
    print(f"  {n:3d}  {label}")

print("\n=== Group quarters status (gq) ===")
c = Counter(GQ.get(r['gq'], r['gq']) for r in rows)
for label, n in c.most_common():
    print(f"  {n:3d}  {label}")

print("\n=== Group quarters type (gqtype), where gq != households ===")
c = Counter(GQTYPE.get(r['gqtype'], r['gqtype']) for r in rows if r['gqtype'] != '0')
for label, n in c.most_common():
    print(f"  {n:3d}  {label}")

print("\n=== Ownership ===")
c = Counter(OWNERSHP.get(r['ownershp'], r['ownershp']) for r in rows)
for label, n in c.most_common():
    print(f"  {n:3d}  {label}")

# per-address summary: household size, boarders present, race mix
print("\n=== Per matched address ===")
by_addr = defaultdict(list)
for r in rows:
    by_addr[(r['sheet'], r['block_id'], r['address'])].append(r)
for key in addr_keys:
    recs = by_addr[key]
    n = len(recs)
    n_lodger = sum(1 for r in recs if r['related'] in ('1201','1202','1203','1204','1205','1241'))
    n_employee = sum(1 for r in recs if r['related'] in ('1211','1212','1213','1214','1215','1216','1217','1251','1252'))
    races = Counter(RACE.get(r['race'], r['race']) for r in recs)
    race_str = ", ".join(f"{v} {k}" for k, v in races.items())
    flags = []
    if n_lodger: flags.append(f"{n_lodger} lodger/boarder")
    if n_employee: flags.append(f"{n_employee} employee")
    gqs = set(r['gq'] for r in recs)
    if gqs != {'1'} and gqs != {'2'}:
        flags.append(f"gq={','.join(gqs)}")
    flag_str = (" -- " + "; ".join(flags)) if flags else ""
    print(f"  {key[2]:>5} {key[2] and ''} {key[0]:25s} {key[1]:20s} {n:3d} residents  [{race_str}]{flag_str}")
