import csv, difflib, re

BOYS = """
6A|6A-1 Portland Interscholastic League|Benson;Cleveland;Franklin;Grant;Ida B. Wells;Lincoln;McDaniel;Roosevelt
6A|6A-2 Metro League|Beaverton;Jesuit;Mountainside;Southridge;Sunset;Westview
6A|6A-3 Pacific Conference|Century;Forest Grove;Glencoe;McMinnville;Newberg;Sherwood
6A|6A-4 Mt. Hood Conference|Barlow;Central Catholic;Clackamas;David Douglas;Gresham;Nelson;Reynolds
6A|6A-5 Three Rivers League|Lake Oswego;Lakeridge;Tigard;Tualatin;West Linn
6A|6A-6 Central Valley Conference|McKay;McNary;North Salem;South Salem;Sprague;West Salem
6A|6A-SD1 Special District 1|Grants Pass;North Medford;Roseburg;Sheldon;South Eugene;South Medford
5A|5A-1 Northwest Oregon Conference|Centennial;Hood River Valley;Milwaukie;Milwaukie Acad. of the Arts;Parkrose;Putnam;Sandy;St. Helens
5A|5A-2 Greater Metro Conference|Aloha;Canby;Hillsboro;La Salle Prep;Liberty;Wilsonville;Woodburn
5A|5A-3 Mid-Willamette Conference|Corvallis;Crescent Valley;Dallas;Lebanon;Silverton;South Albany;West Albany
5A|5A-4 Intermountain Conference|Bend;Caldera;Crook County;Mountain View;Redmond;Ridgeview;Summit
5A|5A-SD1 Special District 1|Ashland;Churchill;North Eugene;Springfield;Thurston;Willamette
4A/3A/2A/1A|4A/3A/2A/1A-SD1 Special District 1|Blanchet Catholic;Catlin Gabel;Oregon Episcopal;Riverdale;Riverside, WLWV;Trinity Acad.;Valley Catholic;Westside Christian
4A/3A/2A/1A|4A/3A/2A/1A-SD2 Special District 2|Cascade;Central;Estacada;Junction City;Madras;Marist Catholic;Molalla;North Marion;Philomath;Stayton;Sweet Home
4A/3A/2A/1A|4A/3A/2A/1A-SD3 Special District 3|Cascade Christian;Creswell;Henley;Hidden Valley;Klamath Union;Marshfield;Mazama;North Valley;St. Mary's, Medford
4A/3A/2A/1A|4A/3A/2A/1A-SD4 Special District 4|Arlington;Condon;Echo;Ione;Irrigon;Riverside;Sherman;Sisters;Stanfield;The Dalles;Umatilla;Weston-McEwen
4A/3A/2A/1A|4A/3A/2A/1A-SD5 Special District 5|Baker;Four Rivers;La Grande;McLoughlin;Nyssa;Ontario;Pendleton;Powder Valley;Vale
"""
GIRLS_EXTRA = {
    "4A/3A/2A/1A-SD1 Special District 1": ["Tillamook"],
    "4A/3A/2A/1A-SD3 Special District 3": ["Phoenix"],
    "6A-5 Three Rivers League": ["St. Mary's Acad."],
}
SUB = {"Milwaukie Acad. of the Arts":"3A","Blanchet Catholic":"3A","Catlin Gabel":"3A",
"Oregon Episcopal":"3A","Riverdale":"3A","Riverside, WLWV":"2A","Trinity Acad.":"1A",
"Valley Catholic":"4A","Westside Christian":"3A","Tillamook":"4A","Cascade":"4A",
"Central":"4A","Estacada":"4A","Junction City":"4A","Madras":"4A","Marist Catholic":"4A",
"Molalla":"4A","North Marion":"4A","Philomath":"4A","Stayton":"4A","Sweet Home":"3A",
"Cascade Christian":"4A","Creswell":"3A","Henley":"4A","Hidden Valley":"4A",
"Klamath Union":"4A","Marshfield":"4A","Mazama":"4A","North Valley":"4A","Phoenix":"4A",
"St. Mary's, Medford":"3A","Arlington":"1A","Condon":"1A","Echo":"1A","Ione":"1A",
"Irrigon":"2A","Riverside":"3A","Sherman":"1A","Sisters":"3A","Stanfield":"2A",
"The Dalles":"4A","Umatilla":"3A","Weston-McEwen":"2A","Baker":"4A","Four Rivers":"1A",
"La Grande":"4A","McLoughlin":"3A","Nyssa":"3A","Ontario":"4A","Pendleton":"4A",
"Powder Valley":"1A","Vale":"3A"}

ALIAS = {
 "Barlow":"Sam Barlow","Blanchet Catholic":"Blanchet School","Four Rivers":"Four Rivers Charter",
 "Ida B. Wells":"Ida B. Wells-Barnett High School","McDaniel":"McDaniel High School",
 "Milwaukie Acad. of the Arts":"Milwaukie / Milwaukie Acad. of the Arts",
 "Riverside, WLWV":"Riverside (West Linn - Wilsonville)","St. Mary's, Medford":"St Mary's of Medford",
 "Ione":"Ione-Heppner",
 "Central":"Central (Independence)",
 # Stanfield-Echo is one co-op program; the data carries it as Stanfield. OSAA
 # lists the two schools separately for classification, but they field one team.
 "Echo":"Stanfield",
 "Milwaukie":"Milwaukie / Milwaukie Acad. of the Arts",
}

master = list(csv.DictReader(open("master_school_list.csv")))
# Schools that played in 2026 without a league, so they never reached the
# master list. Their ids come from the results data.
master += [{"id": "75837", "name": "Sweet Home", "city": "", "state": "OR",
            "Classification": "4A/3A/2A/1A", "League": ""}]
by_name = {r["name"].strip(): r for r in master}
def norm(s):
    s = s.lower().replace("acad.","academy").replace("st.","st").replace("'","")
    s = re.sub(r"\b(high school|school|charter)\b"," ",s)
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9 ]"," ",s)).strip()
nmap = {}
for r in master: nmap.setdefault(norm(r["name"]), r)

def resolve(name, cls):
    if name in ALIAS and ALIAS[name] in by_name: return by_name[ALIAS[name]]
    if name in by_name: return by_name[name]
    hit = nmap.get(norm(name))
    if hit: return hit
    for cand in difflib.get_close_matches(name, list(by_name), n=6, cutoff=0.6):
        if by_name[cand]["Classification"].strip() == cls:
            return by_name[cand]
    return None

rows, unresolved = [], []
def add(gender, cls, league, school):
    m = resolve(school, cls)
    if not m: unresolved.append((gender, cls, league, school))
    rows.append({"year":2027,"gender":gender,"classification":cls,"league":league,
                 "school_id":(m["id"] if m else ""), "school_name":school,
                 "matched_name":(m["name"] if m else ""),
                 "sub_classification":SUB.get(school, cls)})

for line in BOYS.strip().splitlines():
    cls, league, schools = line.split("|")
    for school in schools.split(";"):
        for g in ("Boys","Girls"): add(g, cls, league, school)
for league, extras in GIRLS_EXTRA.items():
    cls = next(l.split("|")[0] for l in BOYS.strip().splitlines() if l.split("|")[1]==league)
    for school in extras: add("Girls", cls, league, school)

# Echo and Stanfield resolve to the same co-op team, so keep one row for it.
# Keep the row whose name the data actually uses, so the co-op stays Stanfield
# rather than becoming Echo on an alphabetical accident.
seen, deduped = set(), []
ordered = sorted(rows, key=lambda r: (r["gender"], r["classification"], r["league"],
                                      r["school_name"] != r["matched_name"],
                                      r["school_name"]))
for r in ordered:
    key = (r["gender"], r["school_id"]) if r["school_id"] else None
    if key and key in seen:
        continue
    if key: seen.add(key)
    deduped.append(r)
dropped = len(rows) - len(deduped)
rows = deduped

with open("leagues_2027.csv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["year","gender","classification","league",
        "school_id","school_name","matched_name","sub_classification"])
    w.writeheader()
    w.writerows(rows)

print(f"{len(rows)} rows after folding {dropped} co-op duplicate(s)")
print(f"{sum(1 for r in rows if r['school_id'])} carry a school id")
print(f"{len({u[3] for u in unresolved})} schools with no id yet (new to the data):")
for s in sorted({u[3] for u in unresolved}): print("   ", s)
