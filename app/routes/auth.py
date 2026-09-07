import hmac
import re
import secrets
from fastapi import APIRouter,Request,Form
from fastapi.responses import RedirectResponse,HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from app.db import ROOT
from app.security import config,COOKIE,LOGIN_COOKIE,login_attempt,verify_password,create_session,revoke
router=APIRouter()
templates=Jinja2Templates(directory=ROOT/'app/templates')

def login_page(request: Request,message: str='',status: int=200) -> HTMLResponse:
    existing=request.cookies.get(LOGIN_COOKIE,'')
    token=existing if re.fullmatch(r'[A-Za-z0-9_-]{43}',existing) else secrets.token_urlsafe(32)
    response=templates.TemplateResponse(request=request,name='login.html',context={'csrf':token,'message':message},status_code=status)
    response.set_cookie(LOGIN_COOKIE,token,secure=config().hosted,httponly=True,samesite='strict',max_age=1800)
    return response

@router.get('/login')
def login_get(request: Request) -> HTMLResponse:
    return login_page(request)

@router.post('/login')
async def login_post(request: Request,password: str=Form(...,max_length=1024),csrf: str=Form(...,max_length=200)) -> HTMLResponse:
    cfg=config()
    if not hmac.compare_digest(csrf,request.cookies.get(LOGIN_COOKIE,'')) or not csrf:
        return login_page(request,'This sign-in page no longer matches your browser session. Enter your password again. If this repeats, open the HTTPS site directly in Safari or your browser and allow cookies.',403)
    ip=request.client.host if request.client else 'unknown'
    if not await run_in_threadpool(login_attempt,cfg,ip):
        response=login_page(request,'Too many sign-in attempts. Try again in ten minutes.',429)
        response.headers['Retry-After']='600'
        return response
    if not await run_in_threadpool(verify_password,password,cfg.password_hash):
        return login_page(request,'Incorrect password.',401)
    token=await run_in_threadpool(create_session,cfg)
    response=RedirectResponse('/',status_code=303)
    response.set_cookie(COOKIE,token,max_age=7*86400,secure=cfg.hosted,httponly=True,samesite='strict',path='/')
    response.delete_cookie(LOGIN_COOKIE,secure=cfg.hosted,httponly=True,samesite='strict')
    return response

@router.post('/logout')
def logout(request: Request) -> RedirectResponse:
    revoke(config(),request.cookies.get(COOKIE,''))
    response=RedirectResponse('/login',status_code=303)
    response.delete_cookie(COOKIE,secure=config().hosted,httponly=True,samesite='strict')
    return response
