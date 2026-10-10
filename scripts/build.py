"""Build the Econ Faculty site.

  python scripts/build.py --import ../raw   # normalize scraper output into data/faculty/<university>.json
  python scripts/build.py                   # build site/data.js (compact index) + site/people/<university>.json
  python scripts/build.py --check           # also print validation warnings

data/faculty/<university>.json is the canonical, hand-editable data (one JSON array per university).
"""
import glob, json, os, re, sys, unicodedata
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")

RANKS = ["Professor", "Associate Professor", "Assistant Professor"]
UNIT_TYPES = ["economics", "business", "public_policy", "ag_resource_econ", "environment", "law", "public_health", "other"]
FIELDS = [
    "Microeconomic Theory", "Macroeconomics", "Monetary Economics", "Econometrics", "Labor Economics", "Public Economics",
    "Industrial Organization", "International Trade", "International Finance", "Development Economics", "Health Economics",
    "Economics of Education", "Environmental & Energy Economics", "Agricultural & Resource Economics",
    "Urban & Regional Economics", "Economic History", "Political Economy", "Behavioral Economics", "Experimental Economics",
    "Law & Economics", "Financial Economics",
    "Asset Pricing", "Corporate Finance", "Banking & Financial Intermediation", "Accounting", "Marketing", "Strategy",
    "Organizational Behavior", "Management & Organizations", "Operations Management", "Information Systems",
    "Entrepreneurship & Innovation", "Real Estate", "Business Ethics & Society", "Data Science & Analytics",
    "Public Policy", "Other",
]
FIELD_GROUP = {f: ("Economics" if i < 21 else "Business" if i < 35 else "Other") for i, f in enumerate(FIELDS)}
KEEP = ["name", "rank_std", "title", "unit", "unit_type", "area", "other_units", "fields_raw", "fields_std",
        "phd_institution", "phd_year", "phd_field", "ma_institution", "ma_year", "ma_field",
        "ba_institution", "ba_year", "ba_field", "education_raw", "homepage_url", "profile_url", "cv_url",
        "google_scholar_url", "orcid", "year_joined", "source_url", "notes"]

warnings = []


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slug(s):
    return re.sub(r"\s+", "-", norm(s))


def load_unis():
    unis = json.load(open(os.path.join(DATA, "universities.json"), encoding="utf-8"))
    alias = {}
    for u in unis:
        for k in [u["id"], u["name"], u["short"]] + u.get("aliases", []):
            alias[norm(k).replace(" ", "")] = u["id"]
    alias.update({"londonschoolofeconomics": "london-school-of-economics", "lse": "london-school-of-economics",
                  "hkust": "hong-kong-university-of-science-and-technology"})
    return unis, alias


def clean_rank(r, title):
    t = (r or title or "").lower()
    if "assistant" in t or re.search(r"\blecturer\b", t) and "senior" not in t:
        return "Assistant Professor"
    if "associate" in t or "reader" in t or "senior lecturer" in t:
        return "Associate Professor"
    if "professor" in t:
        return "Professor"
    return r if r in RANKS else None


def year(v):
    m = re.search(r"(19|20)\d\d", str(v or ""))
    return int(m.group(0)) if m else None


def do_import(raw_dir):
    unis, alias = load_unis()
    buckets = {u["id"]: [] for u in unis}
    for f in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        if f.endswith("_screening.json") or os.path.basename(f).startswith("_"):
            continue
        try:
            recs = json.load(open(f, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{os.path.basename(f)}: unreadable ({e})")
            continue
        if isinstance(recs, dict):
            recs = recs.get("records") or recs.get("people") or []
        for r in recs:
            uid = alias.get(norm(r.get("university")).replace(" ", "")) or alias.get(norm(os.path.basename(f)[:-5]).replace(" ", ""))
            if not uid:
                warnings.append(f"{os.path.basename(f)}: unknown university '{r.get('university')}'")
                continue
            buckets[uid].append(r)
    os.makedirs(os.path.join(DATA, "faculty"), exist_ok=True)
    for uid, recs in buckets.items():
        if not recs:
            continue
        out, seen = [], {}
        for r in recs:
            rec = {k: r.get(k) for k in KEEP}
            rec["rank_std"] = clean_rank(r.get("rank_std"), r.get("title"))
            if rec["rank_std"] is None:
                warnings.append(f"{uid}: {r.get('name')}: unrecognized rank '{r.get('title')}' (dropped)")
                continue
            ut = (rec.get("unit_type") or "other").strip()
            rec["unit_type"] = ut if ut in UNIT_TYPES else "other"
            fs = rec.get("fields_std") or []
            if isinstance(fs, str):
                fs = [x.strip() for x in re.split(r"[;,]", fs)]
            rec["fields_std"] = [x for x in fs if x in FIELDS][:5]
            for k in ("phd_year", "ba_year", "year_joined"):
                rec[k] = year(rec.get(k))
            key = norm(rec["name"])
            if key in seen:  # same person in two units -> merge
                prev = out[seen[key]]
                prev["other_units"] = "; ".join(x for x in [prev.get("other_units"), rec.get("unit")] if x)
                for k, v in rec.items():
                    if not prev.get(k) and v:
                        prev[k] = v
                continue
            rec["id"] = slug(rec["name"])
            seen[key] = len(out)
            out.append(rec)
        out.sort(key=lambda r: (UNIT_TYPES.index(r["unit_type"]), r.get("unit") or "", r.get("area") or "", RANKS.index(r["rank_std"]), r["name"]))
        with open(os.path.join(DATA, "faculty", uid + ".json"), "w", encoding="utf-8") as g:
            json.dump(out, g, ensure_ascii=False, indent=1)
        print(f"imported {uid}: {len(out)}")


def build(check):
    unis, _ = load_unis()
    uidx = {u["id"]: i for i, u in enumerate(unis)}
    people, ids = [], Counter()
    os.makedirs(os.path.join(SITE, "people"), exist_ok=True)
    for f in glob.glob(os.path.join(SITE, "people", "*.json")):
        os.remove(f)
    for u in unis:
        path = os.path.join(DATA, "faculty", u["id"] + ".json")
        recs = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
        detail = {}
        cnt = Counter()
        for r in recs:
            pid = f"{r.get('id') or slug(r['name'])}--{u['short'].lower().replace(' ', '')}"
            ids[pid] += 1
            if ids[pid] > 1:
                pid += f"-{ids[pid]}"
            if r.get("rank_std") not in RANKS:
                warnings.append(f"{u['id']}: {r.get('name')}: bad rank")
                continue
            fs = [FIELDS.index(x) for x in r.get("fields_std") or [] if x in FIELDS]
            people.append([pid, r["name"], RANKS.index(r["rank_std"]), uidx[u["id"]], r.get("unit") or "",
                           UNIT_TYPES.index(r.get("unit_type") if r.get("unit_type") in UNIT_TYPES else "other"),
                           r.get("area") or "", fs, r.get("phd_institution") or "", r.get("phd_year") or 0,
                           1 if r.get("homepage_url") else 0])
            detail[pid] = {k: v for k, v in r.items() if v not in (None, "", [])}
            cnt[r.get("unit_type")] += 1
        u["n"] = len(detail)
        u["by_unit_type"] = dict(cnt)
        with open(os.path.join(SITE, "people", u["id"] + ".json"), "w", encoding="utf-8") as g:
            json.dump(detail, g, ensure_ascii=False, separators=(",", ":"))
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "universities": unis, "ranks": RANKS,
           "unit_types": UNIT_TYPES, "fields": FIELDS, "field_group": [FIELD_GROUP[f] for f in FIELDS],
           "cols": ["id", "name", "rank", "uni", "unit", "unit_type", "area", "fields", "phd", "phd_year", "has_home"],
           "people": people}
    with open(os.path.join(SITE, "data.js"), "w", encoding="utf-8") as g:
        g.write("window.EF = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"{len(people)} people at {sum(1 for u in unis if u['n'])} universities -> site/data.js")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--import" in a:
        do_import(a[a.index("--import") + 1])
    build("--check" in a)
    if "--check" in a or warnings:
        for w in warnings[:200]:
            print("WARN", w)
