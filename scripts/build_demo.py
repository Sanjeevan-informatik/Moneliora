"""Export the browser-only demo without customer APIs or provider credentials.

Usage: python scripts/build_demo.py /absolute/output/directory
Only listed static assets are copied. The FastAPI app is not deployed by this export.
"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import argparse
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
REMOVE_IDS = {'account', 'consult', 'live-market', 'market-linked', 'pilotForm',
              'operatorLogin', 'operatorLock', 'privacyLink', 'termsLink', 'legalLink'}
REMOVE_SCRIPTS = {'account.js', 'paypal.js', 'market.js', 'live_portfolio.js', 'landing.js', 'operator.js'}

class DemoHTML(HTMLParser):
    """Drop backend-dependent subtrees rather than only hiding them with CSS."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if self.skip:
            if tag not in VOID:
                self.skip += 1
            return
        remove = (values.get('id') in REMOVE_IDS
                  or values.get('data-nav') in {'account', 'consult', 'live-market', 'market-linked'}
                  or (tag == 'script' and values.get('src', '').split('/')[-1] in REMOVE_SCRIPTS))
        if remove:
            self.skip = 0 if tag in VOID else 1
            return
        if values.get('id') == 'operatorWorkspace':
            attrs = [(key, value) for key, value in attrs if key != 'hidden']
        self.parts.append('<' + tag + ''.join(' ' + key + ('' if value is None else '="' + escape(value, quote=True) + '"') for key, value in attrs) + '>')

    def handle_endtag(self, tag):
        if self.skip:
            if tag not in VOID:
                self.skip -= 1
        else:
            self.parts.append('</' + tag + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, text):
        if not self.skip:
            self.parts.append(text)

    def handle_entityref(self, name):
        if not self.skip:
            self.parts.append('&' + name + ';')

    def handle_charref(self, name):
        if not self.skip:
            self.parts.append('&#' + name + ';')

    def handle_decl(self, text):
        if not self.skip:
            self.parts.append('<!' + text + '>')


def transform(text, page):
    parser = DemoHTML()
    parser.feed(text)
    result = ''.join(parser.parts)
    for route in ('studio', 'launch', 'operator'):
        for suffix in ('"', '#', '?'):
            result = result.replace('href="/' + route + suffix, 'href="/' + route + '/' + suffix)
    banner = ('<div class="demo-banner" role="note"><strong>INTERACTIVE DEMO</strong>'
              '<span>Fictional data · No real trades, bookings or payments</span>'
              '<a href="/">Overview</a><a href="/studio/#plan">Try the studio</a>'
              '<a href="/operator/">Sample dashboard</a></div>')
    result = result.replace('<body>', '<body>' + banner, 1)
    additions = '<link rel="stylesheet" href="/static/demo.css">'
    if page == 'landing':
        additions += '<script src="/static/demo-shell.js" defer></script>'
        result = result.replace('Requests not open', 'Demo only — no booking')
        result = result.replace('Checking pilot availability. You can use the free studio now.',
                                'Demo mode. Explore the free tools; session requests and payments are disabled.')
        result = result.replace('Can I buy a session today?', 'Can I buy a session in this demo?')
    if page == 'operator':
        additions += '<script src="/static/demo-operator.js" defer></script>'
        result = result.replace('Review inquiries and track follow-up. Stages are operator records, not verified payments, bookings or revenue. Public preview blocks access.',
                                'Explore two fictional inquiries. Stage changes and deletion affect this tab only. No credentials, real customers, messages or payments are involved.')
        result = result.replace('Workspace locked.', 'Loading fictional sample inquiries…')
        result = result.replace('Requests load in pages of up to 100. Use Load older requests for more. Counts cover all retained requests. Data expires 30 days after creation. No messages are sent by this workspace.',
                                'Sample data only. Reload or select Reset samples to restore the examples. Nothing is sent or saved.')
        result = result.replace('id="operatorRefresh">Refresh', 'id="operatorRefresh">Reset samples')
    return result.replace('</head>', additions + '</head>')


def build(output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents or output in ROOT.parents:
        raise ValueError('Use an output directory outside the source repository.')
    output.mkdir(parents=True, exist_ok=True)
    # Refuse to mix an old export with newly changed sources or unrelated files.
    if any(output.iterdir()):
        raise ValueError('The output directory must be empty; choose a new export directory.')
    assets = output / 'static'
    assets.mkdir()
    for name in ('styles.css', 'site.css', 'launch.css', 'finance.js', 'money.js', 'planner.js',
                 'launch-model.js', 'launch.js', 'workbook.js'):
        shutil.copyfile(ROOT / 'static' / name, assets / name)
    app = (ROOT / 'static/app.js').read_text()
    start, end = app.index('const dateInput='), app.index('const nav=')
    (assets / 'app.js').write_text(app[:start] + app[end:])
    for source, destination, page in (
        ('landing.html', 'index.html', 'landing'), ('index.html', 'studio/index.html', 'studio'),
        ('launch.html', 'launch/index.html', 'launch'), ('operator.html', 'operator/index.html', 'operator'),
        ('workbook.html', 'static/workbook.html', 'workbook')):
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(transform((ROOT / 'static' / source).read_text(), page))
    (assets / 'demo-shell.js').write_text('''"use strict";
(() => {
  const supported = new Set(['home','plan','business','markets','portfolio','watchlist','learn','tools']);
  if (supported.has(location.hash.slice(1))) location.replace('/studio/' + location.hash);
})();
''')
    (assets / 'demo-operator.js').write_text('''"use strict";
(() => {
  const stages=['new','contacted','qualified','completed','declined'];
  const examples=[{name:'Sample learner A',offer:'Guided planning',objective:'How do fees and inflation affect the example savings goal?',stage:'new'},
                  {name:'Sample founder B',offer:'Business numbers',objective:'Explore break-even for a fictional one-product business.',stage:'qualified'}];
  let records=examples.map(row=>({...row}));
  function render(){
    const root=document.getElementById('operatorRequests');root.replaceChildren();
    document.getElementById('operatorCounts').textContent=stages.map(stage=>stage+': '+records.filter(row=>row.stage===stage).length).join(' · ');
    records.forEach((row,index)=>{
      const card=document.createElement('article');card.className='launch-card';
      const title=document.createElement('h2');title.textContent=row.name;
      const detail=document.createElement('p');detail.textContent='FICTIONAL EXAMPLE · '+row.offer;
      const objective=document.createElement('p');objective.textContent=row.objective;
      const label=document.createElement('label');label.textContent='Try changing the sample stage';
      const select=document.createElement('select');for(const stage of stages){const option=document.createElement('option');option.value=stage;option.textContent=stage;select.append(option);}select.value=row.stage;
      select.addEventListener('change',()=>{row.stage=select.value;render();});label.append(select);
      const remove=document.createElement('button');remove.type='button';remove.className='button outline';remove.textContent='Remove sample';
      remove.addEventListener('click',()=>{records.splice(index,1);render();});
      card.append(title,detail,objective,label,remove);root.append(card);
    });
    document.getElementById('operatorStatus').textContent=records.length+' fictional inquiries displayed. Changes are local to this tab.';
  }
  document.getElementById('operatorRefresh').addEventListener('click',()=>{records=examples.map(row=>({...row}));render();});
  render();
})();
''')
    (assets / 'demo.css').write_text('''.demo-banner{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;padding:12px 24px;background:#e6efdf;border-bottom:1px solid #c5d8bb;color:#244939;font:12px/1.5 system-ui,sans-serif}.demo-banner strong{font-size:10px;letter-spacing:1px}.demo-banner a{color:#164c40;font-weight:700;text-underline-offset:3px}@media(max-width:600px){.demo-banner{padding:12px 18px;gap:7px 14px}.demo-banner span{flex-basis:100%}}@media print{.demo-banner{display:none}}
''')
    (output / '404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Demo page unavailable</title><link rel="stylesheet" href="/static/site.css"><main class="section-wrap section-space"><h1>This page is not part of the demo.</h1><p>Accounts, live market feeds, customer requests and payments are not connected.</p><a class="button" href="/">Return to Moneliora</a></main></html>')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (output / 'demo-info.json').write_text(json.dumps({'project':'Moneliora','source_commit':commit,'mode':'static-demo','real_trades':False,'payments':False,'customer_intake':False}, indent=2))
    print(f'Demo exported to {output}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output)
