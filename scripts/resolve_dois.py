"""Find DOIs for index papers that have no source link, via the free Crossref API (no LLM, no key).

Reads site/papers.json (built index), queries Crossref for rows without a link, accepts a match only when the
normalized titles agree and an author surname matches. Results accumulate in data/doi_fill.json
(key = first 80 alnum chars of the lower-cased title); misses are cached in data/doi_miss.json so re-runs resume.

Usage: python scripts/resolve_dois.py [--workers 8] [--limit N]
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILL, MISS = os.path.join(ROOT, "data", "doi_fill.json"), os.path.join(ROOT, "data", "doi_miss.json")
UA = "EconFacultyDirectory/1.0 (mailto:zh443@cornell.edu)"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def key(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())[:80]


def surname(n):
    t = norm(n).split()
    while t and t[-1] in ("jr", "ii", "iii", "iv"):
        t.pop()
    return t[-1] if t else ""


def query(row):
    title, authors = row[0], row[5] or []
    sn = {surname(a) for a in authors if a}
    q = {"query.bibliographic": title[:300], "rows": 5, "select": "DOI,title,author,type"}
    if authors:
        q["query.author"] = authors[0][:80]
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                items = json.load(r)["message"]["items"]
            break
        except Exception:  # noqa: BLE001
            time.sleep(3 * (i + 1))
    else:
        return None  # request failed: retry next run
    k = norm(title)
    for it in items:
        ct = norm((it.get("title") or [""])[0])
        if not ct or not (ct == k or (len(k) > 40 and (ct.startswith(k) or k.startswith(ct)))):
            continue
        cs = {surname(f"{a.get('given', '')} {a.get('family', '')}") for a in it.get("author") or []}
        if sn and cs and not (sn & cs):
            continue
        return it["DOI"]
    return ""


def main():
    a = sys.argv[1:]
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 8
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 0
    rows = json.load(open(os.path.join(ROOT, "site", "papers.json"), encoding="utf-8"))
    fill = json.load(open(FILL, encoding="utf-8")) if os.path.exists(FILL) else {}
    miss = set(json.load(open(MISS, encoding="utf-8"))) if os.path.exists(MISS) else set()
    todo = [r for r in rows if not r[4] and len(norm(r[0])) > 15 and key(r[0]) not in fill and key(r[0]) not in miss]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} papers to resolve", flush=True)
    t0, found, n = time.time(), 0, 0
    with ThreadPoolExecutor(workers) as ex:
        for r, d in zip(todo, ex.map(query, todo)):
            n += 1
            if d:
                fill[key(r[0])] = d
                found += 1
            elif d == "":
                miss.add(key(r[0]))
            if n % 500 == 0:
                print(f"  {n}/{len(todo)} found {found} ({time.time() - t0:.0f}s)", flush=True)
                json.dump(fill, open(FILL, "w", encoding="utf-8"))
                json.dump(sorted(miss), open(MISS, "w", encoding="utf-8"))
    json.dump(fill, open(FILL, "w", encoding="utf-8"))
    json.dump(sorted(miss), open(MISS, "w", encoding="utf-8"))
    print(f"done: {found}/{n} resolved in {time.time() - t0:.0f}s; total DOIs on file {len(fill)}")


if __name__ == "__main__":
    main()
