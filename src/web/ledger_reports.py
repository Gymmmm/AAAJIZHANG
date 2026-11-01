"""Dedicated read-only Yam ledger view, separate from the unrelated Mini App API."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import text
from ..models import AsyncSessionLocal
from ..services.billing_service import BillingService
from ..services.reports import read_report_token, html_text, xlsx_bytes

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
HEADERS={'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
         'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"}

@app.get('/health')
async def health():
    async with AsyncSessionLocal() as db:
        await db.execute(text('SELECT 1'))
    return {'status':'ok'}

@app.get('/bill/{token}')
async def bill(token: str):
    try:
        gid=read_report_token(token)
    except ValueError as error:
        raise HTTPException(403,str(error))
    async with AsyncSessionLocal() as db:
        rows=await BillingService.get_transactions(db,gid,include_deleted=True)
        return HTMLResponse(html_text(rows),headers=HEADERS)

@app.get('/export/{token}')
async def export(token: str):
    try:
        gid=read_report_token(token)
    except ValueError as error:
        raise HTTPException(403,str(error))
    async with AsyncSessionLocal() as db:
        rows=await BillingService.get_transactions(db,gid,include_deleted=True)
        return Response(xlsx_bytes(rows),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={**HEADERS,'Content-Disposition':'attachment; filename="yam-ledger.xlsx"'})
