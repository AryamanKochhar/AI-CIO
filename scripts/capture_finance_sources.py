"""Capture six curated public pages with bounded requests and honest receipts.

Raw HTML is ignored local evidence, never prompt instructions or committed text.
This utility does not refresh the manifest's manual verification dates.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
IDS = {'sebi_bond_risks', 'sec_fee_drag', 'cfa_wealth_risks', 'cfa_covariance', 'sec_allocation', 'sebi_investment_constraints'}
HOSTS = {'investor.sebi.gov.in', 'www.investor.gov', 'www.cfainstitute.org'}
MAX_BYTES = 2_000_000


def capture(row):
    receipt = {'source_id': row['id'], 'url': row['url'], 'attempted_at_utc': datetime.now(timezone.utc).isoformat()}
    try:
        parsed = urlsplit(row['url'])
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
            raise ValueError('Source URL outside reviewed hosts')
        request = Request(row['url'], headers={'User-Agent': 'AI-cio-source-review/1.0', 'Accept': 'text/html'})
        with urlopen(request, timeout=30) as response:
            if urlsplit(response.url).hostname not in HOSTS:
                raise ValueError('Redirect outside reviewed hosts')
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES or len(body) < 200:
                raise ValueError('Unexpected public page size')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected source content type')
            if response.status != 200:
                raise ValueError('Unsuccessful source retrieval')
            target = ROOT / '.dev/finance-source-captures' / (row['id'] + '.html')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            receipt.update(status='retrieved', http_status=response.status, final_url=response.url,
                           bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
                           content_review='retrieval receipt only; financial summaries reviewed separately')
    except Exception as error:
        receipt.update(status='unavailable', error_type=type(error).__name__)
    return receipt


def main():
    manifest = json.loads((ROOT / 'knowledge/finance_sources.json').read_text(encoding='utf-8-sig'))
    rows = [row for row in manifest['sources'] if row['id'] in IDS]
    if {row['id'] for row in rows} != IDS:
        raise ValueError('Curated source metadata incomplete')
    with ThreadPoolExecutor(max_workers=3) as pool:
        receipts = list(pool.map(capture, rows))
    target = ROOT / 'docs/validation/finance-source-captures.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Bounded HTTPS GET; no authentication, bypass or full source publication',
        'raw_content': 'Ignored .dev storage; never treated as instructions', 'sources': receipts}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({row['source_id']: row['status'] for row in receipts}))


if __name__ == '__main__':
    main()
