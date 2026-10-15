"""Verify the reviewed HBS deltas against the original source records.

Run after fetching the review's baseline commit:
    python scripts/check_hbs_publication_review.py

This checks data/provenance consistency and preservation, not the scientific
validity of the papers or whether every working paper has a later version.
"""
import collections
import copy
import json
from pathlib import Path
import re
import subprocess
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'diagnostics/hbs/2026-10-15/publication-review.json'
PAPERS = 'data/papers/harvard-university.json'


def title_key(text):
    text = text.replace('’', "'").replace('‘', "'")
    return ' '.join(re.findall('[a-z0-9]+', unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()))


def check():
    review = json.loads(REVIEW.read_text())
    baseline = json.loads(subprocess.check_output(
        ['git', 'show', review['baseline_commit'] + ':' + PAPERS], cwd=ROOT, text=True))
    expected = copy.deepcopy(baseline)
    actual = json.loads((ROOT / PAPERS).read_text())
    faculty = json.loads((ROOT / 'data/faculty/harvard-university.json').read_text())
    hbs_names = {p['name'] for p in faculty if p.get('unit') == 'Harvard Business School'}
    keys = {p['name']: k for k, p in baseline.items()}
    for p in faculty:
        if p['name'] not in keys:
            # Existing build normalization is the source-data key convention.
            import build
            keys[p['name']] = build.norm(p['name'])
    counts = collections.Counter()
    priority = {'working_paper': 0, 'revise_resubmit': 1, 'forthcoming': 2, 'published': 3}
    allowed = {'title', 'authors', 'year', 'venue', 'status', 'link', 'doi'}
    for change in review['changes']:
        if change['decision'] != 'accept':
            continue
        assert change['name'] in hbs_names
        row = change['after']
        assert set(row) <= allowed
        assert row['title'] and row['authors'] and row.get('link')
        assert row['venue'] not in {'Harvard Business Review', 'MIT Sloan Management Review', 'California Management Review'}
        assert change['source_url'].startswith('https://www.hbs.edu/faculty/Pages/item.aspx?num=')
        captured = change.get('bibliographic_verification', {}).get('hbs_extracted_record', row)
        assert title_key(captured['title']) in title_key(change['source_citation'])
        k = keys[change['name']]
        person = expected.setdefault(k, dict(name=change['name'], papers=[]))
        if change['action'] == 'add':
            assert change['before'] is None
            assert not any(title_key(q['title']) == title_key(row['title']) for q in person['papers'])
            person['papers'].append(row)
            counts['source_additions'] += 1
        else:
            before = change['before']
            assert row['title'] == before['title'] and row['authors'] == before['authors']
            assert priority[row['status']] > priority[before['status']]
            index = person['papers'].index(before)
            person['papers'][index] = row
            counts['status_upgrades'] += 1
    assert actual == expected, 'Source data differs from the reviewed additions/upgrades; an existing record or unrelated person may have changed.'
    result = dict(counts, existing_source_records_retained=True, unrelated_people_unchanged=True,
                  accepted_titles_trace_to_official_citations=True)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    check()
