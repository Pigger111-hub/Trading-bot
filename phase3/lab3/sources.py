"""Bounded, credential-free source discovery. Crossref metadata is not paper evidence."""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from urllib.parse import urlsplit, urlencode

FAMILIES = ('trend_following', 'momentum', 'mean_reversion', 'volatility')
PENDING = 'VERIFIED_METADATA_PENDING_HUMAN_APPROVAL'


def now():
    return datetime.now(timezone.utc).isoformat()


class NetworkBudget:
    def __init__(self):
        self.requests = 0

    def consume(self):
        if self.requests >= 12:
            raise ValueError('cycle HTTP request budget exhausted')
        self.requests += 1


def validate_url(url, allowed):
    if not isinstance(url, str) or len(url) > 2048 or url not in allowed:
        raise ValueError('URL not an exact approved target')
    p = urlsplit(url)
    if (p.scheme != 'https' or not p.hostname or p.username or p.password
            or p.port is not None or p.fragment or '\\' in url
            or any(ord(c) <= 32 for c in url)):
        raise ValueError('unsafe HTTPS URL')
    try:
        address = ipaddress.ip_address(p.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('nonpublic address')
    return url


def resolve_public(host, timeout=10):
    """Bound resolver latency without granting a timed-out worker network access."""
    import queue
    import socket
    import threading
    if not 0 < timeout <= 10:
        raise ValueError('DNS timeout outside bounded budget')
    result = queue.Queue(maxsize=1)
    def resolve():
        try:
            result.put(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
        except Exception as exc:
            result.put(exc)
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError('DNS resolution deadline exhausted') from exc
    if isinstance(addresses, Exception):
        raise addresses
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('nonpublic DNS address')
    return addresses


class SafeFetcher:
    """No proxy/netrc; pin public DNS address through TLS to prevent rebinding."""
    def __init__(self):
        self.budget = NetworkBudget()

    def get(self, url, allowed):
        import socket
        import ssl
        import http.client
        import time
        import threading
        from urllib.parse import urljoin
        original = url
        for redirect in range(4):
            deadline = time.monotonic() + 35
            validate_url(url, allowed)
            host = urlsplit(url).hostname
            addresses = resolve_public(host)
            ip = addresses[0][4][0]
            self.budget.consume()
            conn = http.client.HTTPSConnection(host, timeout=15, context=ssl.create_default_context())
            watchdog = None
            try:
                sock = socket.create_connection((ip, 443), timeout=10)
                try:
                    conn.sock = conn._context.wrap_socket(sock, server_hostname=host)
                except BaseException:
                    sock.close()
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('HTTP connection wall-clock budget exhausted')
                tls_socket = conn.sock
                def abort(socket_to_close=tls_socket):
                    try:
                        socket_to_close.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    socket_to_close.close()
                watchdog = threading.Timer(remaining, abort)
                watchdog.daemon = True
                watchdog.start()
                p = urlsplit(url)
                conn.request('GET', p.path + ('?' + p.query if p.query else ''),
                             headers={'User-Agent': 'Phase3Research/1.0', 'Accept-Encoding': 'identity'})
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    if redirect == 3:
                        raise ValueError('redirect budget exhausted')
                    url = validate_url(urljoin(url, response.getheader('Location', '')), allowed)
                    continue
                if response.status != 200:
                    raise ValueError(f'HTTP {response.status} from approved source')
                if response.getheader('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('compressed responses unsupported')
                data = bytearray()
                read = getattr(response, 'read1', response.read)
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError('HTTP response wall-clock budget exhausted')
                    chunk = read(min(8192, 1_000_001 - len(data)))
                    if time.monotonic() > deadline:
                        raise TimeoutError('HTTP response wall-clock budget exhausted')
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > 1_000_000:
                        raise ValueError('response exceeds 1MB')
                raw = bytes(data)
                return {'raw': raw, 'requested_url': original, 'final_url': url,
                        'content_type': response.getheader('Content-Type', ''), 'retrieved_at': now()}
            finally:
                if watchdog is not None:
                    watchdog.cancel()
                conn.close()
        raise ValueError('redirect budget exhausted')


def reviewed_seeds(root):
    """Parse literal catalog only after verifying original file, never import it."""
    import ast
    from pathlib import Path
    path = Path(root) / 'src/trading_lab/sources.py'
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError('reviewed source catalog missing') from exc
    if hashlib.sha256(raw).hexdigest() != 'ba03196616cac2f06425cc90454b59fbbccec28c140d95cf998ef2b4fcab8cd0':
        raise ValueError('reviewed source catalog changed')
    tree = ast.parse(raw)
    catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'CATALOG' for t in n.targets))
    return [url for entry in catalog for url in entry['urls']]


def fetch_seed(url, approved_urls, get):
    from html.parser import HTMLParser
    validate_url(url, set(approved_urls))
    result = get(url, set(approved_urls))
    validate_url(result['final_url'], set(approved_urls))
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts, self.skip = [], 0
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self.skip += 1
        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self.skip = max(0, self.skip - 1)
        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)
    raw = result['raw']
    parser = Text()
    parser.feed(raw.decode('utf-8', errors='replace'))
    text = ' '.join(' '.join(parser.parts).split())
    if len(text) < 200:
        raise ValueError('empty or blocked reviewed document')
    return {'id': 'seed-' + hashlib.sha256(url.encode()).hexdigest(),
            'status': 'APPROVED_REVIEWED_SEED', 'approved': True,
            'evidence_scope': 'RETRIEVED_DOCUMENT_TEXT', 'requested_url': url,
            'final_url': result['final_url'], 'retrieved_at': result.get('retrieved_at', now()),
            'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_snapshot': raw.decode('utf-8', errors='replace'),
            'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text}


def approve_source(store, source_id, *, actor, reviewer, reason, scope='metadata-only'):
    try:
        return _approve_source(store, source_id, actor=actor, reviewer=reviewer, reason=reason, scope=scope)
    except Exception as exc:
        store.append('source_approval_rejected', {'source_id': source_id, 'actor': actor, 'reviewer': reviewer,
                     'reason': reason, 'scope': scope, 'error': str(exc)[:2000], 'at': now()})
        raise


def _approve_source(store, source_id, *, actor, reviewer, reason, scope):
    if actor != 'human' or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError('human reviewer and nonblank rationale required')
    items = [s for s in store.snapshot()['sources'] if s['id'] == source_id]
    if scope == 'full-document':
        from .store import digest
        if len(items) != 1 or items[0].get('status') != 'QUARANTINED_DOCUMENT_TEXT':
            raise ValueError('verified quarantined document required')
        item = dict(items[0])
        validate_document_snapshot(item)
        receipts = [e['payload'] for e in store.events('source_document_verified')
                    if e['payload'].get('source_id') == source_id
                    and e['payload'].get('source_version') == item['version']
                    and e['payload'].get('source_item_hash') == digest(item)]
        if len(receipts) != 1:
            raise ValueError('exact verified quarantine revision required')
        review = {'actor': actor, 'reviewer': reviewer, 'reason': reason, 'at': now()}
        item.update(status='APPROVED_REVIEWED_DOCUMENT', approved=True,
                    evidence_scope='RETRIEVED_DOCUMENT_TEXT', support_scope='MECHANICS_VALIDATION_ONLY')
        item['approval'] = {**review, 'scope': scope, 'source_version': item['version'] + 1,
                            'quarantine_version': items[0]['version'], 'quarantine_item_hash': digest(items[0]),
                            'raw_sha256': item['raw_sha256'], 'text_sha256': item['text_sha256']}
        item['review_history'] = [*item.get('review_history', []), review]
        saved = store.put('sources', item)
        store.append('source_document_approved', {'source_id': source_id, 'source_version': saved['version'],
                     'source_item_hash': digest(saved), 'approval': saved['approval']})
        return saved
    if scope != 'metadata-only':
        raise ValueError('unknown source approval scope')
    if len(items) != 1 or items[0].get('status') != PENDING:
        raise ValueError('exact pending metadata source ID required')
    item = dict(items[0])
    item.update(status='APPROVED_METADATA_ONLY', approved=True, evidence_scope='METADATA_REVIEW_ONLY')
    item['review_history'] = [*item.get('review_history', []),
                              {'actor': actor, 'reviewer': reviewer, 'reason': reason, 'at': now()}]
    store.put('sources', item)
    return next(s for s in store.snapshot()['sources'] if s['id'] == source_id)


def validate_document_snapshot(item):
    import base64
    raw = base64.b64decode(item['raw_snapshot_base64'], validate=True)
    if (not raw or len(raw) > 1_000_000 or hashlib.sha256(raw).hexdigest() != item['raw_sha256']
            or hashlib.sha256(item['text'].encode()).hexdigest() != item['text_sha256']):
        raise ValueError('document snapshot hashes mismatch')
    if item.get('association', {}).get('heuristic_not_scientific_proof') is not True:
        raise ValueError('document association verification required')
    return item


def verify_source(store, source_id, *, url, actor, reviewer, reason, redirect_urls=(), fetcher=None):
    """Explicit human fetch only; every refreshed document returns to quarantine."""
    import base64
    try:
        if actor != 'human' or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reason, str) or not reason.strip():
            raise ValueError('human reviewer and nonblank rationale required')
        items = [s for s in store.snapshot()['sources'] if s['id'] == source_id]
        if len(items) != 1 or not items[0].get('doi') or not items[0].get('title'):
            raise ValueError('registered DOI/title candidate required')
        if not isinstance(redirect_urls, (list, tuple)) or len(redirect_urls) > 3:
            raise ValueError('at most three explicit redirect URLs')
        allowed = {url, *redirect_urls}
        for target in allowed:
            validate_url(target, allowed)
        result = (fetcher if fetcher is not None else SafeFetcher()).get(url, allowed)
        validate_url(result['final_url'], allowed)
        raw = result['raw']
        if not isinstance(raw, bytes) or len(raw) > 1_000_000:
            raise ValueError('invalid or oversized document')
        store.append('source_document_received', {'source_id': source_id, 'requested_url': url,
                     'final_url': result['final_url'], 'retrieved_at': result.get('retrieved_at', now()),
                     'raw_snapshot_base64': base64.b64encode(raw).decode('ascii'),
                     'raw_sha256': hashlib.sha256(raw).hexdigest(), 'content_type': result.get('content_type', '')})
        if not raw:
            raise ValueError('empty document')
        content_type = result.get('content_type', '').split(';', 1)[0].strip().lower()
        if raw.lstrip().startswith(b'%PDF') or content_type == 'application/pdf':
            raise ValueError('unsupported PDF document')
        if content_type not in ('text/html', 'text/plain', 'application/xhtml+xml'):
            raise ValueError('unsupported document content type')
        # Reuse the bounded HTML text extractor; this does not grant seed approval.
        parsed = fetch_seed(url, allowed, lambda *_: result)
        text = parsed['text']
        lower = text.casefold()
        if any(marker in lower for marker in ('verify you are human', 'captcha', 'access denied',
                                               'checking your browser', 'just a moment', 'enable javascript and cookies')):
            raise ValueError('blocked or bot challenge document')
        doi_match = items[0]['doi'].casefold() in lower
        title_match = ' '.join(items[0]['title'].casefold().split()) in lower
        if not doi_match and not title_match:
            raise ValueError('document DOI/title association mismatch')
        item = dict(items[0])
        item.pop('approval', None)
        item.update({k: parsed[k] for k in ('requested_url', 'final_url', 'retrieved_at', 'raw_sha256', 'text_sha256', 'text')})
        item.update(status='QUARANTINED_DOCUMENT_TEXT', approved=False, evidence_scope='QUARANTINED_DOCUMENT_TEXT',
                    raw_snapshot_base64=base64.b64encode(raw).decode('ascii'),
                    association={'doi_match': doi_match, 'registered_title_match': title_match,
                                 'heuristic_not_scientific_proof': True},
                    verification_review={'actor': actor, 'reviewer': reviewer, 'reason': reason, 'at': now()},
                    allowed_document_urls=sorted(allowed))
        from .store import digest
        saved = store.put('sources', item)
        store.append('source_document_verified', {'source_id': source_id, 'source_version': saved['version'],
                     'source_item_hash': digest(saved), 'raw_sha256': saved['raw_sha256'],
                     'text_sha256': saved['text_sha256'], 'heuristic_not_scientific_proof': True})
        return saved
    except Exception as exc:
        store.append('source_verification_rejected', {'source_id': source_id, 'url': url, 'actor': actor,
                     'reviewer': reviewer, 'reason': reason, 'error': str(exc)[:2000], 'at': now()})
        raise


def select_frozen_documents(store):
    """Select at most two already-reviewed snapshots, without network access."""
    from .store import digest
    selected = []
    for item in store.snapshot()['sources']:
        if item.get('status') != 'APPROVED_REVIEWED_DOCUMENT':
            continue
        validate_document_snapshot(item)
        approval = item.get('approval', {})
        if (item.get('approved') is not True or item.get('evidence_scope') != 'RETRIEVED_DOCUMENT_TEXT'
                or approval.get('actor') != 'human' or not approval.get('reviewer', '').strip()
                or not approval.get('reason', '').strip() or approval.get('scope') != 'full-document'
                or approval.get('source_version') != item['version']
                or approval.get('raw_sha256') != item['raw_sha256'] or approval.get('text_sha256') != item['text_sha256']):
            raise ValueError('document approval binding mismatch')
        quarantines = [e['payload']['item'] for e in store.events('item_saved')
                       if e['payload']['collection'] == 'sources' and e['payload']['item']['id'] == item['id']
                       and e['payload']['item']['version'] == approval.get('quarantine_version')]
        if (len(quarantines) != 1 or digest(quarantines[0]) != approval.get('quarantine_item_hash')
                or quarantines[0].get('status') != 'QUARANTINED_DOCUMENT_TEXT'
                or quarantines[0].get('raw_sha256') != item['raw_sha256']
                or quarantines[0].get('text_sha256') != item['text_sha256']):
            raise ValueError('quarantine approval binding mismatch')
        receipts = [e['payload'] for e in store.events('source_document_approved')
                    if e['payload'].get('source_id') == item['id']
                    and e['payload'].get('source_version') == item['version']
                    and e['payload'].get('source_item_hash') == digest(item)
                    and e['payload'].get('approval') == approval]
        if len(receipts) != 1:
            raise ValueError('exact human document approval receipt required')
        selected.append(item)
    return selected[:2]


def discover(queries, get):
    if not isinstance(queries, dict) or set(queries) != set(FAMILIES):
        raise ValueError('exactly four family queries required')
    found = {}
    for family in FAMILIES:
        query = queries[family]
        if not isinstance(query, str) or not query.strip() or len(query) > 240:
            raise ValueError('invalid bounded query')
        url = 'https://api.crossref.org/works?' + urlencode({'query': query, 'rows': 3})
        response = get(url, {url})
        data = json.loads(response['raw'], parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        items = data['message']['items']
        if not isinstance(items, list) or len(items) > 3:
            raise ValueError('Crossref result budget/schema')
        for item in items:
            import re
            doi = item.get('DOI', '')
            titles = item.get('title', [])
            if (not isinstance(doi, str) or not re.fullmatch(r'10\.\d{4,9}/[^\s<>"\x00-\x1f]+', doi)
                    or not isinstance(titles, list) or not titles or not isinstance(titles[0], str)
                    or not titles[0].strip() or not isinstance(item.get('publisher'), str)
                    or not item['publisher'].strip() or item.get('type') not in
                    ('journal-article', 'proceedings-article', 'book-chapter', 'posted-content', 'monograph', 'book')):
                continue
            key = doi.lower()
            if key in found:
                found[key]['families'].append(family)
                continue
            found[key] = {'id': 'crossref-' + hashlib.sha256(key.encode()).hexdigest(),
                          'doi': doi, 'title': titles[0], 'publisher': item['publisher'],
                          'families': [family], 'status': PENDING, 'approved': False,
                          'evidence_scope': 'CROSSREF_METADATA_ONLY', 'metadata': item,
                          'verification': {'authority': 'Crossref REST DOI registration metadata',
                                           'requested_url': url, 'final_url': response['final_url'],
                                           'retrieved_at': now(),
                                           'raw_sha256': hashlib.sha256(response['raw']).hexdigest(),
                                           'raw_snapshot': response['raw'].decode('utf-8')},
                          'limitations': 'DOI metadata verified, not scientific credibility, full text, or approval.'}
    return list(found.values())
