"""Read-only, allowlisted primary-source retrieval with bounded immutable snapshots."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from .registry import canonical, digest

ALLOWED_HOSTS = frozenset({'kernc.github.io', 'www.freqtrade.io', 'docs.freqtrade.io',
                           'developers.binance.com', 'github.com', 'raw.githubusercontent.com',
                           'scholarworks.wmich.edu', 'hermes-agent.nousresearch.com'})
CATALOG = [
    {'topic': 'fees commission spread slippage transaction costs execution ค่าธรรมเนียม',
     'urls': ['https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html',
              'https://www.freqtrade.io/en/stable/backtesting/']},
    {'topic': 'lookahead bias data leakage overfitting validation walk forward อคติ',
     'urls': ['https://www.freqtrade.io/en/stable/lookahead-analysis/',
              'https://scholarworks.wmich.edu/math_pubs/40/']},
    {'topic': 'moving average crossover SMA trend momentum strategy กลยุทธ์',
     'urls': ['https://kernc.github.io/backtesting.py/',
              'https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html']},
    {'topic': 'Binance public market data candles klines timestamp spot ข้อมูล',
     'urls': ['https://developers.binance.com/en/docs/binance-spot-api-docs/rest-api/market-data-endpoints',
              'https://raw.githubusercontent.com/binance/binance-public-data/master/README.md']},
]


def validate_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('invalid source URL')
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname not in ALLOWED_HOSTS
            or parts.username or parts.password or parts.port not in (None, 443)
            or '\\' in url or any(ord(c) < 32 for c in url)):
        raise ValueError('only allowlisted HTTPS primary-source URLs without credentials accepted')
    return url


def select_sources(topic):
    tokens = set(topic.casefold().replace('-', ' ').split())
    scored = sorted(enumerate(CATALOG), key=lambda pair: (
        -len(tokens.intersection(pair[1]['topic'].casefold().split())), pair[0]))
    if not tokens.intersection(scored[0][1]['topic'].casefold().split()):
        raise ValueError('knowledge gap needs a reviewed source-catalog extension')
    return scored[0][1]['urls']


def fetch_source(root, url):
    validate_url(url)
    original = url
    with requests.Session() as session:
        session.trust_env = False  # no .netrc credentials or inherited proxy auth
        session.headers['User-Agent'] = 'TradingResearchLab/0.1 (local educational research)'
        for _ in range(4):
            with session.get(url, timeout=(10, 35), allow_redirects=False, stream=True) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = validate_url(urljoin(url, response.headers['Location']))
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_content(8192):
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise ValueError('source exceeds 2MB retrieval budget')
                raw = bytes(data)
                encoding = response.encoding or 'utf-8'
                break
        else:
            raise ValueError('source redirect budget exhausted')
    soup = BeautifulSoup(raw.decode(encoding, errors='replace'), 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else urlsplit(url).path
    for item in soup(['script', 'style', 'nav', 'footer', 'header']):
        item.decompose()
    body = soup.find('main') or soup.find('article') or soup
    text = ' '.join(body.get_text(' ', strip=True).split())
    if len(text) < 200:
        raise ValueError('source empty/blocked; no knowledge fabricated')
    retrieved_at = datetime.now(timezone.utc).isoformat()
    record = {'url': url, 'requested_url': original, 'title': title, 'retrieved_at': retrieved_at,
              'raw_sha256': hashlib.sha256(raw).hexdigest(), 'text': text,
              'text_sha256': hashlib.sha256(text.encode()).hexdigest()}
    record['source_id'] = digest(record)
    target = Path(root) / 'knowledge/sources' / (record['source_id'] + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as handle:
        handle.write(canonical(record))
    return record
