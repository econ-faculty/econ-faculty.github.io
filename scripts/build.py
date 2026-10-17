"""Build the Econ Faculty site.

  python scripts/build.py --import ../raw   # normalize scraper output into data/faculty/<university>.json
  python scripts/build.py                   # build site/data.js (compact index) + site/people/<university>.json
  python scripts/build.py --check           # also print validation warnings

data/faculty/<university>.json is the canonical, hand-editable data (one JSON array per university).
"""
import glob, gzip, json, os, re, sys, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")

RANKS = ["Professor", "Associate Professor", "Assistant Professor", "Faculty"]   # "Faculty" = tenure-line, rank not stated by the university
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
        "google_scholar_url", "orcid", "year_joined", "source_url", "notes",
        "ba_country", "phd_advisors", "first_job_after_phd", "prior_positions", "year_current_rank", "cv_date", "detail_source"]
ENRICH_KEYS = ["ba_institution", "ba_year", "ba_field", "ba_country", "ma_institution", "ma_year", "ma_field",
               "phd_institution", "phd_year", "phd_field", "phd_advisors", "first_job_after_phd", "prior_positions",
               "year_joined", "year_current_rank", "homepage_url", "cv_url", "google_scholar_url", "orcid", "fields_raw", "cv_date",
               "fields_std"]

warnings = []

# ---------------------------------------------------------------- primary field ("Group: Sub") per unit type
ECON_SUB = [  # (field_std or keyword regex, label) — first match wins
    (r"microeconomic theory|game theory|mechanism design|contract theory|decision theory|social choice|matching", "Microeconomic Theory"),
    (r"macroeconomics|monetary|business cycle|growth", "Macro & Monetary"),
    (r"econometrics|statistic", "Econometrics"),
    (r"labor|labour|migration|personnel", "Labor"),
    (r"public economics|public finance|taxation|fiscal", "Public"),
    (r"industrial organization|competition|antitrust|regulation", "Industrial Organization"),
    (r"international trade|international finance|international", "International"),
    (r"development", "Development"),
    (r"health", "Health"),
    (r"education", "Education"),
    (r"environment|energy|climate|agricultur|resource", "Environment, Energy & Agriculture"),
    (r"urban|regional|spatial|real estate|housing", "Urban & Regional"),
    (r"economic history|history", "Economic History"),
    (r"political economy|politic", "Political Economy"),
    (r"behavioral|experimental|psycholog", "Behavioral & Experimental"),
    (r"financial economics|finance|asset pricing|corporate finance|banking", "Financial Economics"),
    (r"law", "Law & Economics"),
]
BIZ_TOP = [  # (area/raw regex, group)
    (r"financ|banking|investment", "Finance"),
    (r"account", "Accounting"),
    (r"marketing", "Marketing"),
    (r"real estate", "Real Estate"),
    (r"health care|healthcare|health policy", "Health Care Management"),
    (r"legal|law|ethic", "Business Law & Ethics"),
    (r"statistic|data science|econometric", "Statistics & Data Science"),
    (r"operation|information|decision|technolog|isom|\bdot\b|\boid\b|supply chain|analytics|management science|\bmeds\b", "Operations & IS"),
    (r"economics|\bbepp\b|business and public policy|business economics|political economy|global economy", "Business Economics"),
    (r"strateg|organi[sz]ation|management|leadership|entrepreneur|behavio|work and|innovation", "Management"),
]
BIZ_SUB = {
    "Finance": [(r"asset pricing|investment|portfolio|microstructure|derivative|fixed income|behavioral finance|empirical finance|market", "Asset Pricing"),
                (r"corporate|governance|merger|capital structure|private equity|venture|payout|ipo", "Corporate Finance"),
                (r"bank|intermediat|credit|fintech|household|mortgage|insurance", "Banking & Intermediation")],
    "Marketing": [(r"consumer|psycholog|judgment|behavio|persuasion|emotion", "Consumer Behavior"),
                  (r"quantitative|empirical|model|econometric|pricing|advertising|digital|platform|structural|analytics|machine learning|economics", "Quantitative Marketing")],
    "Management": [(r"strateg|competitive|industry", "Strategy"),
                   (r"entrepreneur|innovation|technology|venture", "Entrepreneurship & Innovation"),
                   (r"organizational behavior|negotiation|leadership|team|psycholog|diversity|motivation|\bob\b", "Organizational Behavior"),
                   (r"organi[sz]ation|sociolog|institution|management theory|work", "Organizations")],
    "Operations & IS": [(r"information system|digital|platform|it\b|technology|e-commerce", "Information Systems"),
                        (r"decision|analytics|optimi[sz]ation|data|statistic|risk", "Decision Sciences & Analytics"),
                        (r"operation|supply|service|healthcare operations|inventory|logistics", "Operations Management")],
}
POLICY_SUB = [
    (r"environment|energy|climate|resource|agricultur", "Environmental & Energy Policy"),
    (r"development|poverty|global", "International Development"),
    (r"health|education|labor|labour|social|inequality|welfare", "Social Policy"),
    (r"management|organi[sz]ation|behavior|negotiation|leadership|decision|psycholog", "Public Management & Behavior"),
]
FIELD_ORDER = ["Economics", "Finance", "Accounting", "Marketing", "Management", "Operations & IS",
               "Real Estate", "Health Care Management", "Business Law & Ethics", "Statistics & Data Science",
               "Public Policy", "Law", "Public Health"]


def first(rules, text):
    for pat, lab in rules:
        if re.search(pat, text):
            return lab
    return None


def econ_sub(r):
    """Primary econ subfield: first of the person's own listed fields that maps, else keyword match on raw text."""
    for f in r.get("fields_std") or []:
        lab = first(ECON_SUB, f.lower())
        if lab:
            return lab
    return first(ECON_SUB, (r.get("fields_raw") or "").lower())


def primary_field(r):
    ut = r.get("unit_type") or "other"
    area = (r.get("area") or "").lower()
    fs = " ; ".join(r.get("fields_std") or []).lower()
    raw = (r.get("fields_raw") or "").lower()
    text = f"{fs} ; {raw}"
    if ut == "business":
        top = first(BIZ_TOP, area) or first(BIZ_TOP, fs) or "Management"
        if top == "Business Economics":  # economists in business schools use the Economics fields
            sub = econ_sub(r)
            return f"Economics: {sub}" if sub else "Economics: General"
        if top in BIZ_SUB:
            sub = first(BIZ_SUB[top], f"{fs} ; {raw} ; {area}")
            return f"{top}: {sub or 'General'}"
        return top
    if ut == "public_policy":
        if re.search(r"management|organizational|negotiation|leadership|decision", fs + area):
            return "Public Policy: Public Management & Behavior"
        return "Public Policy: " + (first(POLICY_SUB, text) or "Economic Policy")
    if ut == "law":
        return "Law: Corporate & Financial Law" if re.search(r"corporate|securit|financ|bank", text) else "Law: Law & Economics"
    if ut == "public_health":
        return "Public Health: Health Economics & Policy"
    sub = econ_sub(r)
    if ut == "ag_resource_econ" and (not sub or sub in ("Microeconomic Theory", "Econometrics")):
        sub = sub or "Environment, Energy & Agriculture"
    return f"Economics: {sub}" if sub else "Economics: General"


BIZ_FIELD = {
    "Asset Pricing": "Finance: Asset Pricing", "Corporate Finance": "Finance: Corporate Finance",
    "Banking & Financial Intermediation": "Finance: Banking & Intermediation", "Accounting": "Accounting",
    "Strategy": "Management: Strategy", "Organizational Behavior": "Management: Organizational Behavior",
    "Management & Organizations": "Management: Organizations",
    "Entrepreneurship & Innovation": "Management: Entrepreneurship & Innovation",
    "Operations Management": "Operations & IS: Operations Management",
    "Information Systems": "Operations & IS: Information Systems", "Real Estate": "Real Estate",
    "Business Ethics & Society": "Business Law & Ethics",
}


def field_labels(r, k=3):
    """Up to k site field labels ('Group: Sub'), from the person's own ordered fields_std, mapped by school type.
    Economics topics -> 'Economics: ...' everywhere (incl. business-school economists)."""
    ut = r.get("unit_type") or "other"
    area = (r.get("area") or "").lower()
    raw = (r.get("fields_raw") or "").lower()
    labels = []
    if ut in ("public_policy", "law", "public_health"):
        labels.append(primary_field(r))
    elif ut == "business":
        base = primary_field(r)  # the area the person is appointed in (Finance, Marketing, ...)
        if not base.startswith("Economics"):
            labels.append(base)
    for f in r.get("fields_std") or []:
        lab = None
        if f in BIZ_FIELD:
            lab = BIZ_FIELD[f]
        elif f == "Marketing":
            lab = "Marketing: " + (first(BIZ_SUB["Marketing"], raw + " ; " + area) or "General")
        elif f == "Data Science & Analytics":
            lab = "Statistics & Data Science" if re.search(r"statistic", area) else "Operations & IS: Decision Sciences & Analytics"
        elif f == "Financial Economics":
            lab = "Finance: General" if (ut == "business" and re.search(r"financ", area)) else "Economics: Financial Economics"
        elif f == "Public Policy":
            lab = "Public Policy: " + (first(POLICY_SUB, raw) or "Economic Policy")
        elif f == "Law & Economics":
            lab = "Law: Law & Economics" if ut == "law" else "Economics: Law & Economics"
        elif f != "Other":
            sub = first(ECON_SUB, f.lower())
            lab = f"Economics: {sub}" if sub else None
        if lab and lab not in labels:
            labels.append(lab)
    if not labels:
        labels.append(primary_field(r))
    # drop 'X: General' when a specific sub-field of the same group is present
    groups_specific = {l.split(":")[0] for l in labels if ":" in l and not l.endswith(": General")}
    labels = [l for l in labels if not (l.endswith(": General") and l.split(":")[0] in groups_specific)]
    return labels[:k]


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


ROMAN = {"II", "III", "IV", "JR", "SR"}


def _is_caps(t):
    if "." in t:  # initials like 'Y.C.' stay as they are
        return False
    core = re.sub(r"[^A-Za-z]", "", t)
    return len(core) >= 2 and core.isupper() and core.upper() not in ROMAN


def _title(t):
    return "-".join("'".join(x[:1].upper() + x[1:].lower() for x in part.split("'")) for part in t.split("-"))


def fix_name(name):
    """Unify to 'Given Surname' with only initial capitals.
    'LIN Shu' -> 'Shu Lin'; 'SONG Zheng, Michael' -> 'Michael Zheng Song'; 'Albert PARK' -> 'Albert Park'."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    name = re.sub(r",?\s*\b(SBS|JP|BBS|MH|GBS|OBE|CBE|MBE|FBA|FRS)\b\.?", "", name).strip(" ,")  # honorifics
    english = ""
    if "," in name:
        name, english = [x.strip() for x in name.split(",", 1)]
    toks = name.split(" ")
    if not any(_is_caps(t) for t in toks):
        return (english + " " + name).strip() if english else name
    lead = 0
    while lead < len(toks) and _is_caps(toks[lead]):
        lead += 1
    if 0 < lead < len(toks):  # surname-first: SURNAME Given
        surname, given = toks[:lead], toks[lead:]
        toks = given + surname
    elif lead == 0 and len(toks) >= 3 and _is_caps(toks[1]) and not any(_is_caps(t) for t in toks[2:]):
        toks = [toks[0]] + toks[2:] + [toks[1]]  # 'Bart ZHOU Yueshen' -> 'Bart Yueshen Zhou'

    toks = [_title(t) if _is_caps(t) else t for t in toks]
    return " ".join(([english] if english else []) + toks)


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


def same_person(a, b):
    """Two records with the same name at one university are the same person unless their PhDs disagree."""
    pa, pb = norm(a.get("phd_institution")), norm(b.get("phd_institution"))
    if pa and pb and pa != pb and pa not in pb and pb not in pa:
        return False
    ya, yb = year(a.get("phd_year")), year(b.get("phd_year"))
    return not (ya and yb and abs(ya - yb) > 1)


def do_import(raw_dir):
    unis, alias = load_unis()
    dp = os.path.join(DATA, "drop_people.json")
    DROP = {(d["university"], norm(d["name"])) for d in json.load(open(dp, encoding="utf-8"))} if os.path.exists(dp) else set()
    buckets = {u["id"]: [] for u in unis}
    for f in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        if os.path.basename(f).startswith("_") or re.search(r"_(screening|domestic|domestic_decision|phd_unknown)\.json$", f):
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
            if uid and (uid, norm(fix_name(r.get("name")))) in DROP:   # same person listed at another university
                continue
            if not uid:
                warnings.append(f"{os.path.basename(f)}: unknown university '{r.get('university')}'")
                continue
            buckets[uid].append(r)
    # detailed CV-level enrichment: raw/enrich/<batch>.json, matched by id or normalized name
    # each file applies only to its own university (same-name people at different schools must not collide)
    legacy = {"cornell": "cornell-university", "hku": "university-of-hong-kong",
              "cuhk": "chinese-university-of-hong-kong", "hkust": "hong-kong-university-of-science-and-technology",
              "nus": "national-university-of-singapore", "ntu": "nanyang-technological-university",
              "smu": "singapore-management-university"}

    def fulls_of(uid):  # merge files are named from raw ids, which may keep "the-"
        return [uid] + (["the-" + uid] if os.path.exists(os.path.join(raw_dir, f"the-{uid}.json")) else [])

    def enrich_unis(fname):
        """universities an enrich file may belong to: exact full-id tag first, else the short 'first_last' prefix
        (several universities can share it, e.g. universite-de-montreal / universite-du-quebec-a-montreal)"""
        stem = os.path.basename(fname)[:-5]
        exact = [uid for uid in buckets for full in fulls_of(uid) if stem.startswith(full.replace("-", "_") + "_")]
        if exact:
            return exact[:1]
        short = [uid for uid in buckets for full in fulls_of(uid)
                 if stem.startswith(full.split("-")[0] + "_" + full.split("-")[-1] + "_")]
        if short:
            return list(dict.fromkeys(short))
        return [legacy[stem.split("_")[0]]] if stem.split("_")[0] in legacy else []

    roster_names = {uid: {norm(r.get("name")) for r in recs} for uid, recs in buckets.items()}
    enrich = defaultdict(dict)
    enrich_pid = defaultdict(list)   # pid-tagged entries (same-name colleagues at one university), chosen by unit/PhD
    for f in sorted(glob.glob(os.path.join(raw_dir, "enrich", "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        us = enrich_unis(f)
        if not us:
            warnings.append(f"enrich file {os.path.basename(f)}: cannot map to a university (skipped)")
            continue
        for e in json.load(open(f, encoding="utf-8")):
            k = norm(e.get("name"))
            if e.get("pid") and len(us) == 1:
                enrich_pid[us[0]].append(e)
                continue
            if len(us) == 1:
                enrich[us[0]][k] = e
                continue
            # ambiguous short prefix: assign each record to the one university whose roster has this name
            hit = [u for u in us if k in roster_names[u]]
            if len(hit) == 1:
                enrich[hit[0]][k] = e
    os.makedirs(os.path.join(DATA, "faculty"), exist_ok=True)
    for uid, recs in buckets.items():
        if not recs:
            continue
        out, seen, namesake = [], {}, set()
        for r in recs:
            rec = {k: r.get(k) for k in KEEP}
            orig_key = norm(r.get("name"))
            rec["name"] = fix_name(r.get("name"))
            rec["rank_std"] = clean_rank(r.get("rank_std"), r.get("title"))
            if rec["rank_std"] is None and r.get("rank_unknown"):
                rec["rank_std"] = "Faculty"
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
            if key in seen and not same_person(out[seen[key]], rec):  # namesakes at one university: keep both
                warnings.append(f"{uid}: two different people named {rec['name']} ({out[seen[key]].get('unit')} / {rec.get('unit')}) kept apart")
                key = key + " #2"
                namesake.add(norm(rec["name"]))
            if key in seen:  # same person in two units -> merge
                prev = out[seen[key]]
                prev["other_units"] = "; ".join(x for x in [prev.get("other_units"), rec.get("unit")] if x)
                for k, v in rec.items():
                    if not prev.get(k) and v:
                        prev[k] = v
                continue
            rec["id"] = slug(rec["name"])
            cands = [x for x in enrich_pid[uid] if norm(x.get("name")) == norm(rec["name"])]
            if cands:   # namesakes: take the entry from this person's own page (same PhD, then same unit)
                good = [x for x in cands if same_person(x, rec) and norm(x.get("phd_institution")) and norm(rec.get("phd_institution"))]
                good = good or [x for x in cands if same_person(x, rec)]
                if len(good) > 1:
                    good = [x for x in good if norm(x.get("unit")) == norm(rec.get("unit"))]
                e = good[0] if len(good) == 1 else None
            else:
                e = enrich[uid].get(key) or enrich[uid].get(orig_key)
            if e and not cands and norm(rec["name"]) in namesake | {k[:-3] for k in seen if k.endswith(" #2")} and not same_person(e, rec):
                e = None                       # enrichment is keyed by name; never copy it onto the wrong namesake
            if e:
                for k in ENRICH_KEYS:
                    if e.get(k) not in (None, "", []):
                        rec[k] = e[k]
                for k in ("phd_year", "ba_year", "year_joined", "year_current_rank"):
                    rec[k] = year(rec.get(k))
                rec["detail_source"] = e.get("source")
                if e.get("notes"):
                    rec["notes"] = "; ".join(x for x in [rec.get("notes"), e["notes"]] if x)
            if isinstance(rec.get("fields_raw"), list):  # some extraction agents emit a list
                rec["fields_raw"] = "; ".join(str(x) for x in rec["fields_raw"] if x) or None
            seen[key] = len(out)
            out.append(rec)
        out.sort(key=lambda r: (UNIT_TYPES.index(r["unit_type"]), r.get("unit") or "", r.get("area") or "", RANKS.index(r["rank_std"]), r["name"]))
        with open(os.path.join(DATA, "faculty", uid + ".json"), "w", encoding="utf-8") as g:
            json.dump(out, g, ensure_ascii=False, indent=1)
        print(f"imported {uid}: {len(out)}")


# ---------------------------------------------------------------- papers: one schema for curated and extracted lists
# pubs/<pid>.json rows: t title, a authors, y year, c category (pub|rr|wp), j journal/series, v/i/p volume/issue/pages,
# n note (e.g. Forthcoming), l link, lt link type (pub|wp), r journal index into D.journals (leading journals only)
JR = json.load(open(os.path.join(DATA, "journals.json"), encoding="utf-8"))
TIERS = [t for t, _ in JR["tiers"]]
JTOPICS = JR["topics"]
JOURNALS = [[j, TIERS.index(t), JTOPICS.index(JR["journal_topic"][j])] for t in TIERS for j in JR["journals"][t]]


def jkey(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"^\s*the\s+|\s+the\s*$", " ", s)
    return re.sub(r"\s+", " ", s).strip()


JKEY = {jkey(j[0]): i for i, j in enumerate(JOURNALS)}
for a, j in JR["aliases"].items():
    JKEY[jkey(a)] = JKEY[jkey(j)]
NOTE_RE = re.compile(r"^\s*(forthcoming|accepted|conditionally accepted|to appear|r\s*&\s*r|revise and resubmit|reject and resubmit|revision requested|under review)\s*(in|at|,|:)?\s*", re.I)


def journal_idx(venue):
    v = NOTE_RE.sub("", venue or "")
    v = re.split(r",\s*(?:vol|no\.|\d)|\s+\d|\(", v, maxsplit=1)[0]
    return JKEY.get(jkey(v))


def paper_extracted(q):
    st = q.get("status") or ""
    c = "rr" if st == "revise_resubmit" else "wp" if st == "working_paper" else "pub"
    venue = (q.get("venue") or "").strip()
    if c == "wp" and jkey(venue) in ("working paper", "working papers", "mimeo", ""):
        venue = ""
    r = journal_idx(venue) if c != "wp" else None
    out = {"t": q.get("title"), "a": q.get("authors") or [], "y": q.get("year"), "c": c,
           "j": JOURNALS[r][0] if r is not None else venue or None, "r": r}
    if st == "forthcoming":
        out["n"] = "Forthcoming"
    if q.get("doi"):
        out["l"], out["lt"] = "https://doi.org/" + q["doi"], "pub"
    if q.get("abstract"):
        out["abs"] = q["abstract"]
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def paper_curated(q):
    c = {"publication": "pub", "rr": "rr", "wp": "wp"}[q["category"]]
    r = journal_idx(q.get("journal")) if c != "wp" else None
    out = {"t": q.get("title"), "a": q.get("authors") or [], "y": q.get("year"), "c": c,
           "j": (JOURNALS[r][0] if r is not None else q.get("journal")) if c != "wp" else (q.get("series") or "").rstrip(".") or None,
           "v": q.get("volume"), "i": q.get("issue"), "p": q.get("pages"), "r": r,
           "n": {"forthcoming": "Forthcoming", "accepted": "Accepted"}.get(q.get("status_note") or "", q.get("status_note")),
           "l": q.get("link"), "lt": {"published": "pub", "wp": "wp"}.get(q.get("link_type"))}
    return {k: v for k, v in out.items() if v not in (None, "", [])}


# ---- journal-article database (data/paperdb/corpus: Crossref 2000+ for every whitelist journal; matched to faculty at build time)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_match
from wp_series import wp_official   # working papers: official/institutional series only (user rule 2026-10-17)
CORPUS_DIR = os.path.join(DATA, "paperdb", "corpus")
NATURAL = {"Science", "Nature", "Proceedings of the National Academy of Sciences", "Nature Communications", "Science Advances",
           "Nature Human Behaviour"}   # shown only when a directory member is an author
PDB, PMATCH = {}, {}
TWORDS = lambda s: frozenset(re.findall(r"[a-z]{3,}", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
                                        .replace("labour", "labor").replace("behaviour", "behavior")))
tsim = lambda a, b: bool(a and b) and len(a & b) / len(a | b) >= 0.6


def paper_db(p):
    r = JKEY.get(jkey(p["j"]))
    out = {"t": p["t"], "a": [f"{g} {f}".strip() for g, f, _ in p["a"]], "y": p["y"], "c": "pub", "j": p["j"],
           "v": p.get("v"), "i": p.get("i"), "p": p.get("p"), "r": r, "n": p.get("n"),
           "l": "https://doi.org/" + p["doi"], "lt": "pub", "doi": p["doi"]}
    return {k: v for k, v in out.items() if v not in (None, "", [])}


def merge_db(pid, ps):
    """Journal-database papers are the publication list; CV items are kept when not already covered
    (publications/R&R only in whitelist journals; working papers always, unless since published)."""
    db = [paper_db(PDB[d]) for d in PMATCH.get(pid, {}) if d in PDB]
    dbw = [TWORDS(q["t"]) for q in db]
    keep = []
    for q in ps:
        if any(tsim(TWORDS(q.get("t")), w) for w in dbw):
            continue
        if q["c"] in ("pub", "rr") and q.get("r") is None:
            continue
        keep.append(q)
    return db + keep


def paper_sort(ps):
    order = {"pub": 0, "rr": 1, "wp": 2}
    return sorted(ps, key=lambda q: (order[q["c"]], -(q.get("y") or 0)))


def build(check):
    unis, _ = load_unis()
    uidx = {u["id"]: i for i, u in enumerate(unis)}
    people, ids = [], Counter()
    pf_list = []
    pindex, ptitle = {}, {}
    pending, udetails = [], []
    lo = os.path.join(DATA, "link_overrides.json")   # {pid: {homepage_url|profile_url|cv_url: url or null}} (verified link fixes)
    LINKS = json.load(open(lo, encoding="utf-8")) if os.path.exists(lo) else {}
    os.makedirs(os.path.join(SITE, "people"), exist_ok=True)
    for f in glob.glob(os.path.join(SITE, "people", "*.json")):
        os.remove(f)
    os.makedirs(os.path.join(SITE, "pubs"), exist_ok=True)
    for f in glob.glob(os.path.join(SITE, "pubs", "*.json")):
        os.remove(f)
    for u in unis:
        pp = os.path.join(DATA, "papers", u["id"] + ".json")
        upapers = json.load(open(pp, encoding="utf-8")) if os.path.exists(pp) else {}
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
            for k, v in (LINKS.get(pid) or {}).items():
                if k in ("homepage_url", "profile_url", "cv_url"):
                    r[k] = v
            fs = [FIELDS.index(x) for x in r.get("fields_std") or [] if x in FIELDS]
            pf = field_labels(r)
            for x in pf:
                if x not in pf_list:
                    pf_list.append(x)
            people.append([pid, r["name"], RANKS.index(r["rank_std"]), uidx[u["id"]], r.get("unit") or "",
                           UNIT_TYPES.index(r.get("unit_type") if r.get("unit_type") in UNIT_TYPES else "other"),
                           r.get("area") or "", fs, r.get("phd_institution") or "", r.get("phd_year") or 0,
                           1 if r.get("homepage_url") else 0, pf])
            detail[pid] = {k: v for k, v in r.items() if v not in (None, "", [])}
            cp = os.path.join(DATA, "curated", pid + ".json")
            if os.path.exists(cp):
                cur = json.load(open(cp, encoding="utf-8"))
                ps = [paper_curated(q) for q in cur["papers"]]
                detail[pid]["papers_curated"] = cur.get("source_cv") or True
                pending.append((pid, r["name"], len(people) - 1, ps, detail, True))
            else:
                pv = upapers.get("pid:" + pid) or upapers.get(norm(r["name"])) or {}
                ps = [paper_extracted(q) for q in pv.get("papers") or [] if q.get("title")]
                pending.append((pid, r["name"], len(people) - 1, ps, detail, False))
            detail[pid]["fields"] = pf
            cnt[r.get("unit_type")] += 1
        u["n"] = len(detail)
        u["by_unit_type"] = dict(cnt)
        udetails.append((u, detail))
    # ---- match the journal corpus to all faculty (new faculty get linked automatically)
    corpus = paper_match.load_corpus(CORPUS_DIR)
    PDB.update((p["doi"], p) for p in corpus)
    tier_of = {j[0]: TIERS[j[1]] for j in JOURNALS}
    PMATCH.update(paper_match.match([{"pid": pid, "name": nm, "phd": people[ri][9], "cv": ps} for pid, nm, ri, ps, _, _ in pending],
                                    corpus, tier_of, NATURAL))
    # links verified by OpenAlex affiliations for faculty the name matcher could not link (pipeline/zerolink/verify.py)
    xp = os.path.join(DATA, "paperdb", "extra_links.json")
    if os.path.exists(xp):
        pids = {x[0] for x in pending}
        for pid, ds in json.load(open(xp)).items():
            if pid in pids:
                for d, ai in ds.items():
                    if d in PDB:
                        PMATCH.setdefault(pid, {}).setdefault(d, ai)
    # links confirmed wrong (namesakes) by manual / agent review: never shown, even if a matcher proposes them again
    ep = os.path.join(DATA, "paperdb", "exclude_links.json")
    if os.path.exists(ep):
        for pid, ds in json.load(open(ep)).items():
            for d in ds:
                PMATCH.get(pid, {}).pop(d, None)
    with open(os.path.join(DATA, "paperdb", "matched.json"), "w") as g:
        json.dump(PMATCH, g, separators=(",", ":"), sort_keys=True)
    print(f"{sum(map(len, PMATCH.values()))} paper-author links for {len(PMATCH)} faculty from {len(corpus)} journal articles")
    for pid, nm, pidx, ps, detail, curated in pending:
        if not curated:
            ps = merge_db(pid, ps)
        ps = paper_sort([q for q in ps if q["c"] != "wp" or wp_official(q.get("j"))])
        np_ = [sum(q["c"] == c for q in ps) for c in ("pub", "rr", "wp")]
        np_.append(sum(q["c"] == "pub" and q.get("r") is not None and JOURNALS[q["r"]][1] == 0 for q in ps))
        np_.append(sum(q["c"] == "pub" and q.get("r") is not None and JOURNALS[q["r"]][1] < 4 for q in ps))
        people[pidx] += [np_, sorted({q["r"] for q in ps if q["c"] == "pub" and q.get("r") is not None})]
        if not ps:
            continue
        detail[pid]["n_papers"] = len(ps)
        with open(os.path.join(SITE, "pubs", pid + ".json"), "w", encoding="utf-8") as g:
            json.dump(ps, g, ensure_ascii=False, separators=(",", ":"))
        fam = norm(nm).split()[-1] if norm(nm) else ""
        for q in ps:
            if q["c"] == "pub" and q.get("r") is None:
                continue
            tk = (q["c"], re.sub(r"[^a-z0-9]", "", (q["t"] or "").lower())[:60])
            key = ("doi", q["doi"]) if q.get("doi") else ptitle.get(tk, tk)
            ptitle.setdefault(tk, key)
            row = pindex.get(key)
            if row is None:
                row = pindex[key] = [q["t"], q.get("y") or 0, "pub rr wp".split().index(q["c"]), q.get("r", -1), q.get("l") or "", list(q.get("a") or []), []]
            ai = PMATCH[pid][q["doi"]] if q.get("doi") else next((k for k, x in enumerate(row[5]) if norm(x).split()[-1:] == [fam]), -1)
            if [ai, pidx] not in row[6]:
                row[6].append([ai, pidx])
    for u, detail in udetails:
        with open(os.path.join(SITE, "people", u["id"] + ".json"), "w", encoding="utf-8") as g:
            json.dump(detail, g, ensure_ascii=False, separators=(",", ":"))
    # ---- all other journal articles (authors not in the directory), sharded by year, loaded on demand
    shard = defaultdict(list)
    for p in corpus:
        if ("doi", p["doi"]) in pindex or p["j"] in NATURAL:
            continue
        shard[p["y"]].append([p["t"], p["y"], 0, JKEY.get(jkey(p["j"]), -1), "https://doi.org/" + p["doi"],
                              [f"{g} {f}".strip() for g, f, _ in p["a"]], []])
    adir = os.path.join(SITE, "papers_all")
    os.makedirs(adir, exist_ok=True)
    for f in glob.glob(os.path.join(adir, "*.json")):
        os.remove(f)
    for y, rows in shard.items():
        with open(os.path.join(adir, f"{y}.json"), "w", encoding="utf-8") as g:
            json.dump(rows, g, ensure_ascii=False, separators=(",", ":"))
    n_all = sum(map(len, shard.values()))
    print(f"{n_all} other journal articles -> site/papers_all/<year>.json ({len(shard)} years)")
    pf_list.sort(key=lambda x: (FIELD_ORDER.index(x.split(":")[0]) if x.split(":")[0] in FIELD_ORDER else 99, x))
    pfi = {x: i for i, x in enumerate(pf_list)}
    for row in people:
        row[11] = [pfi[x] for x in row[11]]
    ver = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    out = {"pfields": pf_list, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "v": ver, "universities": unis, "ranks": RANKS,
           "unit_types": UNIT_TYPES, "fields": FIELDS, "field_group": [FIELD_GROUP[f] for f in FIELDS],
           "cols": ["id", "name", "rank", "uni", "unit", "unit_type", "area", "fields", "phd", "phd_year", "has_home", "pfield", "np", "jr"],
           "journals": JOURNALS, "tiers": JR["tiers"], "jtopics": JTOPICS, "n_pindex": len(pindex), "n_all": n_all, "all_years": sorted(shard),
           "people": people}
    with open(os.path.join(SITE, "data.js"), "w", encoding="utf-8") as g:
        g.write("window.EF = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    with open(os.path.join(SITE, "papers.json"), "w", encoding="utf-8") as g:
        json.dump(list(pindex.values()), g, ensure_ascii=False, separators=(",", ":"))
    # version-tag static assets so browsers never mix an old app.js with new data after a deploy
    ip = os.path.join(SITE, "index.html")
    with open(ip, encoding="utf-8") as g:
        html = g.read()
    html = re.sub(r'(href|src)="(style\.css|data\.js|app\.js)(\?v=\w+)?"', lambda m: f'{m[1]}="{m[2]}?v={ver}"', html)
    with open(ip, "w", encoding="utf-8") as g:
        g.write(html)
    print(f"{len(pindex)} papers in search index -> site/papers.json")
    print(f"{len(people)} people at {sum(1 for u in unis if u['n'])} universities -> site/data.js")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--import" in a:
        do_import(a[a.index("--import") + 1])
    build("--check" in a)
    if "--check" in a or warnings:
        for w in warnings[:200]:
            print("WARN", w)
