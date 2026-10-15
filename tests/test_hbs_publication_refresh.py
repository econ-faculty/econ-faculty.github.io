"""Regressions from the HBS publication review, including lost links and status errors."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build


class HbsPublicationRefreshTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = json.loads((ROOT / 'diagnostics/hbs/2026-10-15/publication-review.json').read_text())
        cls.papers = json.loads((ROOT / 'data/papers/harvard-university.json').read_text())

    def test_source_link_survives_rendering_and_doi_keeps_priority(self):
        q = dict(title='Example research paper', status='working_paper',
                 link='https://www.hbs.edu/faculty/Pages/item.aspx?num=1')
        rendered = build.paper_extracted(q)
        self.assertEqual((rendered['l'], rendered['lt']), (q['link'], 'wp'))
        q['doi'] = '10.1234/example'
        self.assertEqual(build.paper_extracted(q)['l'], 'https://doi.org/10.1234/example')

    def test_every_accepted_change_is_present_in_source_data(self):
        for change in self.review['changes']:
            if change['decision'] != 'accept':
                continue
            rows = self.papers[build.norm(change['name'])]['papers']
            self.assertIn(change['after'], rows, change['after']['title'])

    def test_old_wp_footnote_does_not_downgrade_published_article(self):
        change = next(q for q in self.review['changes'] if q.get('candidate_index') == 376)
        paper = change['after']
        self.assertEqual((paper['status'], paper['venue'], paper['year']),
                         ('published', 'Journal of Finance', 1993))

    def test_quoted_subtitle_does_not_replace_complete_paper_title(self):
        change = next(q for q in self.review['changes'] if q.get('candidate_index') == 547)
        paper = change['after']
        self.assertEqual(paper['authors'], ['Puneet Manchanda', 'Asim Ansari', 'Sunil Gupta'])
        self.assertNotEqual(paper['title'], 'Shopping Basket')

    def test_old_wp_year_is_not_reused_as_unassigned_journal_year(self):
        for name, title in [
            ('Raffaella Sadun', 'The Impact of CEOs in the Public Sector: Evidence from the English NHS'),
            ('Sabrina T. Howell', 'After the Storm: How Emergency Liquidity Helps Small Businesses Following Natural Disasters'),
        ]:
            paper = next(q for q in self.papers[build.norm(name)]['papers'] if q['title'] == title)
            self.assertEqual(paper['status'], 'forthcoming')
            self.assertIsNone(paper['year'])

    def test_reviewed_comments_appendix_and_letter_are_excluded(self):
        by_index = {q['candidate_index']:q for q in self.review['changes'] if 'candidate_index' in q}
        for index in (61, 62, 138, 208, 310, 344, 554, 648, 857):
            self.assertEqual(by_index[index]['decision'], 'exclude')


if __name__ == '__main__':
    unittest.main()
