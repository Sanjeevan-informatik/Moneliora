"""Ensure the hosted demo contains no customer intake or backend-dependent scripts."""
from html.parser import HTMLParser
from pathlib import Path
import importlib.util
import json

spec = importlib.util.spec_from_file_location('demo_export', Path(__file__).resolve().parents[1] / 'scripts/build_demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        self.links.extend(attrs[key] for key in ('src', 'href') if key in attrs)


def test_demo_export_is_static_and_complete(tmp_path):
    output = tmp_path / 'demo'
    demo.build(output)
    for file in output.rglob('*.html'):
        page = Page()
        page.feed(file.read_text())
        assert len(page.ids) == len(set(page.ids)), file
        assert not (set(page.ids) & demo.REMOVE_IDS), file
        for link in page.links:
            if not link.startswith('/'):
                continue
            target = output / link.split('#')[0].split('?')[0].lstrip('/')
            assert target.exists(), (file, link)
    for file in output.rglob('*.js'):
        assert '/api/' not in file.read_text(), file
        assert 'fetch(' not in file.read_text(), file
    assert not (output / 'static/account.js').exists()
    assert not (output / 'static/paypal.js').exists()
    assert 'const nav=' in (output / 'static/app.js').read_text()
    assert 'renderMarkets();' in (output / 'static/app.js').read_text()
    assert json.loads((output / 'demo-info.json').read_text())['payments'] is False
    assert 'demo-operator.js' in (output / 'operator/index.html').read_text()
