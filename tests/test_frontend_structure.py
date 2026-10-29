"""Prevent regressions where DOM rendering destroys the explorer controls."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'script' and 'src' in attrs:
            self.scripts.append(attrs['src'])

def test_unique_ids_and_planner_script_order():
    page = Elements()
    page.feed((Path(__file__).resolve().parents[1] / 'static/index.html').read_text())
    assert not [key for key, count in Counter(page.ids).items() if count > 1]
    assert {'markets', 'marketCards', 'stockSearch', 'plan', 'business'} <= set(page.ids)
    assert page.scripts.index('/static/finance.js') < page.scripts.index('/static/planner.js')


def test_new_pages_have_unique_element_ids():
    for name in ('landing.html', 'launch.html', 'workbook.html', 'operator.html'):
        page = Elements()
        page.feed((Path(__file__).resolve().parents[1] / 'static' / name).read_text())
        assert len(page.ids) == len(set(page.ids)), name
