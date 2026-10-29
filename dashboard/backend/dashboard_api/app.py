"""Loopback-only read-only web API. No research engine or credential imports."""
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

LOOPBACK = frozenset({'127.0.0.1', 'localhost', '::1'})
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; object-src 'none'; form-action 'none'")


def _allowed_origin(origin):
    if origin is None:
        return True
    try:
        parsed = urlsplit(origin)
        return (parsed.scheme == 'http' and parsed.hostname in LOOPBACK and not parsed.username
                and not parsed.password and parsed.path in ('', '/') and not parsed.query
                and not parsed.fragment and parsed.port in (None, 8765, 5173))
    except ValueError:
        return False


def create_app(root: Path | None = None, store: Any = None, dist: Path | None = None):
    root = Path(root or Path(__file__).resolve().parents[3]).resolve()
    dist = Path(dist or root / 'dashboard/frontend/dist').resolve()
    app = FastAPI(title='Batch 001 Read-only Evidence Explorer', docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.state.root = root

    @app.middleware('http')
    async def read_only_boundary(request: Request, call_next):
        if request.method not in ('GET', 'HEAD'):
            response = JSONResponse({'detail': 'READ_ONLY: only GET and HEAD are supported'}, status_code=405,
                                    headers={'Allow': 'GET, HEAD'})
        elif request.url.hostname not in LOOPBACK:
            response = JSONResponse({'detail': 'Loopback host required'}, status_code=400)
        else:
            if not _allowed_origin(request.headers.get('origin')):
                response = JSONResponse({'detail': 'Foreign origin rejected'}, status_code=403)
            else:
                response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = CSP
        return response

    def read(method, *args):
        try:
            selected = store
            if selected is None:
                from .evidence import EvidenceStore
                selected = EvidenceStore(root)
            return getattr(selected, method)(*args)
        except (KeyError, LookupError) as error:
            raise HTTPException(404, detail={'code': 'NOT_FOUND',
                'message_th': 'ไม่พบ strategy, fold หรือหลักฐานที่เลือก'}) from error
        except (ValueError, OSError) as error:
            # EvidenceStore IntegrityError subclasses ValueError. Never expose private paths.
            raise HTTPException(503, detail={'code': 'INTEGRITY_ERROR',
                'message_th': 'ตรวจสอบ hash หรือ provenance ไม่ผ่าน หยุดแสดงผลและไม่ใช้ข้อมูลเก่าทดแทน'}) from error

    @app.get('/api/overview')
    def overview():
        return read('overview')

    @app.get('/api/view')
    def view(strategy: str = '10-50', scope: str = 'oos_1'):
        return read('view', strategy, scope)

    @app.get('/api/trades/{trade_id}')
    def trade(trade_id: str, strategy: str = '10-50', scope: str = 'oos_1'):
        return read('trade', strategy, scope, trade_id)

    @app.get('/api/phase3')
    def phase3():
        # Original evidence is always verified first, including on missing new state.
        original = read('overview')
        try:
            if original.get('integrity', {}).get('verified') is not True:
                raise ValueError('Original evidence unverified')
            from lab3.store import Store
            return Store.read_snapshot(root)
        except (ValueError, OSError) as error:
            raise HTTPException(503, detail={'code': 'INTEGRITY_ERROR',
                'message_th': 'Phase3 ตรวจสอบไม่ผ่าน ล้างข้อมูลวิจัยใหม่และไม่ใช้ข้อมูลเก่าทดแทน'}) from error

    @app.get('/api/research')
    def research():
        return read('research')

    @app.get('/api/sources/{source_id}')
    def source(source_id: str):
        return read('source', source_id)

    @app.get('/api/raw')
    def raw(strategy: str, scope: str, trade: str, role: str):
        return read('raw', strategy, scope, trade, role)

    @app.get('/')
    def index():
        target = dist / 'index.html'
        if not target.is_file():
            raise HTTPException(503, detail='Frontend not built. See dashboard/README.md build commands.')
        return FileResponse(target)

    @app.get('/favicon.svg')
    def favicon():
        target = dist / 'favicon.svg'
        if not target.is_file():
            raise HTTPException(404)
        return FileResponse(target, media_type='image/svg+xml')

    if (dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=dist / 'assets', follow_symlink=False), name='assets')
    for route in app.routes:
        if getattr(route, 'methods', None) and 'GET' in route.methods:
            route.methods.add('HEAD')
    return app


app = create_app()
