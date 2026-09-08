from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from collections.abc import AsyncIterator, Callable
from starlette.responses import Response
from sqlalchemy.exc import IntegrityError
from app.db import ROOT,SessionLocal
from app.services.migrate import initialize
from app.services.backup import backup_database
from app.routes.api import router as api_router
from app import security
from starlette.concurrency import run_in_threadpool
import hmac

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    security.validate_configuration(security.config())
    initialize()
    from datetime import datetime,timezone
    import os
    from pathlib import Path
    # Hosted backups always use the explicit volume path, regardless of imported settings.
    if security.config().hosted:
        backup_dir=Path(os.environ['COMMANDER_BACKUPS'])
        today=datetime.now(timezone.utc).strftime('%Y%m%d')
        if not any(backup_dir.glob('commander-'+today+'-*.sqlite3')):
            with SessionLocal() as db: backup_database(db)
    else:
        with SessionLocal() as db: backup_database(db)
    import asyncio
    from app.services.maintenance import loop
    maintenance=asyncio.create_task(loop(SessionLocal))
    try: yield
    finally:
        maintenance.cancel()
        try: await maintenance
        except asyncio.CancelledError: pass

app=FastAPI(title='Commander Ledger',lifespan=lifespan,docs_url=None,redoc_url=None)
@app.middleware('http')
async def security_boundary(request: Request,call_next: Callable) -> Response:
    cfg=security.config()
    request.state.auth_enabled=cfg.enabled
    request.state.csrf=''
    request.state.role='owner'
    request.state.player_id=None
    request.state.username='owner'
    try: security.validate_configuration(cfg)
    except RuntimeError:
        return JSONResponse({'detail':'Server configuration is incomplete; access is disabled.'},status_code=503)
    origin=request.headers.get('origin')
    expected=cfg.origin or str(request.base_url).rstrip('/')
    if cfg.hosted and request.headers.get('host')!=urlsplit(cfg.origin).netloc and request.url.path!='/healthz':
        return JSONResponse({'detail':'Unrecognized host.'},status_code=400)
    writing=request.method not in ('GET','HEAD','OPTIONS')
    if writing and ((origin and origin!=expected) or request.headers.get('sec-fetch-site')=='cross-site'):
        return JSONResponse({'detail':'Cross-site writes are blocked'},status_code=403)
    public=request.url.path in ('/login','/healthz','/join') or request.url.path.startswith('/static/')
    if cfg.enabled and not public:
        active=await run_in_threadpool(security.session,request,cfg)
        if not active:
            if request.url.path.startswith('/api/'):
                return JSONResponse({'detail':'Please sign in again. Your session has expired.'},status_code=401)
            from fastapi.responses import RedirectResponse
            return RedirectResponse('/login',status_code=303)
        request.state.csrf=active['csrf']
        request.state.role=active.get('role','owner')
        request.state.player_id=active.get('player_id')
        request.state.username=active.get('username','owner')
        if request.state.role=='member' and not (request.url.path=='/member' or request.url.path.startswith('/api/member/') or request.url.path.startswith('/api/scryfall/') or request.url.path=='/logout'):
            return JSONResponse({'detail':'This page is for the administrator. Open /member for your player portal.'},status_code=403)
        if writing and not hmac.compare_digest(request.headers.get('x-csrf-token',''),active['csrf']):
            return JSONResponse({'detail':'Session verification failed. Reload the page and retry.'},status_code=403)
    from app.services.audit import actor
    context_token=actor.set(request.state.username)
    try: response=await call_next(request)
    finally: actor.reset(context_token)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    if not request.url.path.startswith('/static/'):
        response.headers['Cache-Control']='no-store'
    if cfg.hosted: response.headers['Strict-Transport-Security']='max-age=31536000'
    return response

@app.get('/healthz')
def health() -> dict:
    return {'status':'ok'}

@app.exception_handler(IntegrityError)
async def integrity_error(request: Request,exc: IntegrityError) -> JSONResponse:
    return JSONResponse({'detail':'This change conflicts with an existing record. Refresh and retry.'},status_code=409)
@app.exception_handler(ValidationError)
async def input_error(request: Request,exc: ValidationError) -> JSONResponse:
    return JSONResponse({'detail':'; '.join(error['msg'] for error in exc.errors())},status_code=422)

app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
app.include_router(api_router)
from app.routes.pages import router as pages_router
app.include_router(pages_router)

from app.routes.auth import router as auth_router
app.include_router(auth_router)

from app.routes.scryfall import router as scryfall_router
app.include_router(scryfall_router)

from app.routes.features import router as features_router
app.include_router(features_router)

from app.routes.playgroup import router as playgroup_router
app.include_router(playgroup_router)
