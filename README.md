# Econ Faculty

**https://econ-faculty.github.io/** — an open, community-maintained directory of tenure-line faculty doing research in economics and business at leading universities worldwide.

## Structure

```
data/universities.json          institutions covered (name, country, region)
data/faculty/<institution>.json one JSON array of faculty records per institution (hand-editable)
scripts/build.py                builds site/data.js (search index) + site/people/<institution>.json
site/                           static front end (HTML/CSS/JS)
.github/workflows/deploy.yml    builds and deploys to GitHub Pages on every push
```

## Contributing

- **Fix a record**: edit `data/faculty/<institution>.json` on GitHub and open a pull request (or use "Suggest a correction" on a profile page).
- **Request removal**: open an issue with the profile link.
- **Add an institution**: add it to `data/universities.json` and add `data/faculty/<id>.json` following the existing record format.

Record fields: `name, rank_std (Assistant/Associate Professor, Professor), title, unit, unit_type, area, other_units, fields_raw, fields_std, phd_institution, phd_year, phd_field, ma_*, ba_*, homepage_url, profile_url, cv_url, google_scholar_url, orcid, year_joined, source_url, notes`. We do not store emails, phone numbers or photos.

## Local build

```
python scripts/build.py --check
python -m http.server 8000 -d site
```
