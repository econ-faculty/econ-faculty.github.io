"""Author matching: Crossref journal corpus (data/paperdb/corpus/*.jsonl.gz) -> directory faculty.
Called by build.py on every build, so newly added faculty are matched automatically.
Evidence: title in the person's CV list (strong); CV coauthor (initial+surname, non-common surname); another directory
coauthor; name-only only for rare surnames or matching middle initial. Natural-science / other-discipline journals need
evidence and a non-common surname. Papers with >30 authors give no coauthor evidence. Year >= PhD year - 5."""
import collections, functools, glob, gzip, json, os, re, unicodedata

BRIT = {"labour": "labor", "behaviour": "behavior", "behavioural": "behavioral", "organisation": "organization", "organisations": "organizations",
        "favour": "favor", "colour": "color", "neighbourhood": "neighborhood", "neighbourhoods": "neighborhoods", "programme": "program",
        "programmes": "programs", "centre": "center", "analysing": "analyzing", "modelling": "modeling", "optimisation": "optimization"}
PART = {"van", "von", "de", "der", "den", "del", "della", "di", "da", "dos", "du", "la", "le", "st", "ter", "ten", "mac", "al", "el", "bin"}


@functools.lru_cache(maxsize=None)
def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return tuple(BRIT.get(w, w) for w in re.sub(r"[^a-z ]+", " ", s.replace("-", " ").replace("'", "")).split())


norm = lambda s: list(_norm(s or ""))
tkey = lambda t: "".join(_norm(t or ""))[:60]
WORDS = lambda t: frozenset(w for w in _norm(t or "") if len(w) > 2)

NICK = {"bill": "william", "will": "william", "bob": "robert", "rob": "robert", "jim": "james", "jimmy": "james", "mike": "michael",
        "dick": "richard", "rick": "richard", "rich": "richard", "tom": "thomas", "tim": "timothy", "dan": "daniel", "dave": "david",
        "steve": "stephen", "matt": "matthew", "andy": "andrew", "drew": "andrew", "alex": "alexander", "nick": "nicholas",
        "sam": "samuel", "joe": "joseph", "tony": "anthony", "ted": "edward", "ed": "edward", "jack": "john", "jon": "jonathan",
        "kate": "katherine", "katie": "katherine", "liz": "elizabeth", "beth": "elizabeth", "jen": "jennifer", "jenny": "jennifer",
        "sue": "susan", "peggy": "margaret", "meg": "margaret", "pat": "patricia", "chuck": "charles", "charlie": "charles",
        "greg": "gregory", "jeff": "jeffrey", "larry": "lawrence", "jerry": "gerald", "fred": "frederick", "hank": "henry",
        "ken": "kenneth", "ben": "benjamin", "chris": "christopher", "phil": "philip", "doug": "douglas", "ron": "ronald"}
NICK2 = {"josh": "joshua", "steve": "steven", "pete": "peter", "mel": "melvin", "brad": ("bradley", "bradford"), "alex": ("alexandre", "alexandra", "alejandro"),
         "rod": "rodney", "zach": "zachary", "stan": ("stanley", "stanislav"), "russ": "russell", "don": "donald", "ray": "raymond", "subra": "subrahmaniam",
         "bhash": "bhashkar", "shiva": "shivaram", "raj": ("rajesh", "rajiv", "raja"), "arun": "arunava", "blake": "blakeley", "ben": "bennett",
         "matt": "matthias", "nick": "nicolas", "tom": "tomas", "andy": "andreas", "sasha": "alexander", "kim": "kimberly", "vicky": "victoria",
         "becky": "rebecca", "cathy": "catherine", "kathy": "kathleen", "jon": "johnathan", "frank": "francis", "gene": "eugene", "larry": "laurence",
         "jerry": "jerome", "nate": "nathaniel", "chris": ("christian", "christine", "christina"), "max": "maximilian", "fred": "fredrik"}
ALIAS = collections.defaultdict(set)
for k, v in list(NICK.items()) + list(NICK2.items()):
    for x in (v if isinstance(v, tuple) else (v,)):
        ALIAS[k].add(x); ALIAS[x].add(k)


def same_first(a, b):
    return a == b or b in ALIAS.get(a, ()) or NICK.get(a, a) == NICK.get(b, b)


def load_corpus(d):
    P = []
    for f in sorted(glob.glob(os.path.join(d, "*.jsonl.gz"))):
        for line in gzip.open(f, "rt", encoding="utf-8"):
            P.append(json.loads(line))
    return P


def match(people, P, tier_of, natural=()):
    """people: [{pid, name, phd, cv: [{t, a}]}]; P: corpus; tier_of: journal -> tier. Returns {pid: {doi: author_index}}."""
    FAC = {}
    for x in people:
        tk = norm(x["name"])
        if len(tk) < 2:
            continue
        first = tk[0] if len(tk[0]) > 1 or len(tk) < 3 else tk[1]          # "J. Bradford DeLong" -> bradford
        fams = {tk[-1]} | {"".join(tk[-k:]) for k in (2, 3) if len(tk) > k}
        f = FAC[x["pid"]] = {"first": first, "given": "".join(tk[:-1]), "fams": fams, "name": x["name"], "phd": x.get("phd") or None,
                             "mids": [w[0] for w in tk[1:-1] if w != first and w not in PART],
                             "g2": {w for w in tk[1:-1] if len(w) > 1 and w != first},
                             "cvt": set(), "cvw": [], "cof": set()}
        for q in x.get("cv") or []:
            f["cvt"].add(tkey(q.get("t"))); f["cvt"].add(tkey(q.get("t"))[:30]); f["cvw"].append(WORDS(q.get("t")))
            for a in q.get("a") or []:
                t = norm(a)
                if t and t[-1] not in fams:
                    f["cof"].add((t[0][0], t[-1]))
    FAM1 = {pid: norm(f["name"])[-1] for pid, f in FAC.items()}
    BYFAM = collections.defaultdict(list)
    for pid, f in FAC.items():
        for k in f["fams"]:
            BYFAM[k].append(pid)
    famfirst = collections.defaultdict(set)              # surname commonness: distinct first names seen with it
    for p in P:                                          # counted on social-science journals only (natural-science author pool is huge)
        if p["j"] in natural:
            continue
        for g, fa, _ in p["a"]:
            gt, ft = _norm(g), _norm(fa)
            if gt and ft and len(gt[0]) > 1:
                famfirst["".join(ft)].add(gt[0])
    nfirst = {k: len(v) for k, v in famfirst.items()}
    del famfirst
    RARE = lambda fam: nfirst.get(fam, 0) <= 12
    COMMON = lambda fam: nfirst.get(fam, 0) > 40

    def cands(g, fa):
        gt, ft = _norm(g), _norm(fa)
        if not ft or not gt:
            return []
        out = []
        for fam in {"".join(ft), ft[-1]}:
            for pid in BYFAM.get(fam, ()):
                f = FAC[pid]
                gt2 = [w for w in gt[1:] if len(w) > 1]
                full = (same_first(gt[0], f["first"]) and (not gt2 or gt2[0] in f["g2"])) or "".join(gt) == f["given"] or                     (len(gt) > 1 and len(gt[0]) == 1 and gt[1] == f["first"])
                init = len(gt[0]) == 1 and gt[0] == f["first"][0]
                loose = same_first(gt[0], f["first"])     # extra given part: accepted only with CV-title evidence
                if not (full or init or loose):
                    continue
                cm = [w[0] for w in gt[1:] if w != f["first"]]
                if cm and f["mids"] and cm[0] != f["mids"][0]:
                    continue                                 # middle-initial conflict
                out.append((pid, full, "".join(ft)))
        return out

    M = collections.defaultdict(dict)
    for rnd in range(2):
        for p in P:
            cl = [(i, c) for i, (g, fa, o) in enumerate(p["a"]) for c in cands(g, fa)]
            if not cl:
                continue
            tk, pw, sci, big = tkey(p["t"]), WORDS(p["t"]), tier_of.get(p["j"]) == "science", len(p["a"]) > 30
            dir_auth = {pid for _, (pid, _, _) in cl}
            fulldir = {pid: full for _, (pid, full, _) in cl}
            for i, (pid, full, fam) in cl:
                f = FAC[pid]
                if f["phd"] and p["y"] < f["phd"] - 5:
                    continue
                cof = {(_norm(g)[0][0], _norm(fa)[-1]) for j, (g, fa, o) in enumerate(p["a"])
                       if j != i and _norm(fa) and _norm(g) and not COMMON(_norm(fa)[-1])}
                strong = tk in f["cvt"] or tk[:30] in f["cvt"] or                     (len(pw) >= 4 and any(len(pw & w) / len(pw | w) >= 0.75 for w in f["cvw"]))
                medium = bool(cof & f["cof"]) or any(d != pid and fulldir.get(d) and not COMMON(FAM1[d]) for d in dir_auth)
                cm = [w[0] for w in _norm(p["a"][i][0])[1:]]
                midok = bool(cm and f["mids"] and cm[0] == f["mids"][0]) and not COMMON(fam)
                if sci:
                    ok = strong or (full and medium and not big and not COMMON(fam))
                else:
                    ok = strong or (full and medium and not big) or (full and (RARE(fam) or midok))
                if ok:
                    M[pid][p["doi"]] = i
        if rnd == 0:                                     # grow coauthor sets from accepted papers
            byd = {p["doi"]: p for p in P}
            for pid, ds in M.items():
                for d in ds:
                    for g, fa, o in byd[d]["a"]:
                        t, gt = norm(fa), norm(g)
                        if t and gt and t[-1] not in FAC[pid]["fams"]:
                            FAC[pid]["cof"].add((gt[0][0], t[-1]))
            del byd
    return {pid: dict(sorted(ds.items())) for pid, ds in M.items()}
