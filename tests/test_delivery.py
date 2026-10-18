import json
from pathlib import Path

import httpx
import pytest
from pypdf import PdfReader

from radar.config import Settings, Watchlist
from radar.demo import demo_report
from radar.http import HTTP, APIError
from radar.report import generate, render_pdf
from radar.storage import Store
from radar.telegram import Telegram, TelegramError, chunks


def test_unicode_chunks_no_loss():
    text = ('🚀 Ação e câmbio\n'*1000)
    parts = chunks(text)
    assert ''.join(parts) == text
    assert all(len(p.encode('utf-16-le'))//2 <= 3800 for p in parts)


def test_send_documents_and_idempotency(tmp_path):
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':len(calls)}})
    s = Settings(telegram_token='test',telegram_chat='private')
    db = Store(tmp_path/'state.db')
    t = Telegram(s,db,httpx.Client(transport=httpx.MockTransport(handle)))
    assert t.text('day','summary','Olá') == 1
    assert t.text('day','summary','Olá') == 0
    f = tmp_path/'report.pdf'; f.write_bytes(b'%PDF test')
    assert t.send_once('day','pdf',path=f)
    assert not t.send_once('day','pdf',path=f)
    assert b'%PDF test' in calls[-1].content
    assert db.delivery_states('day') == {'summary-1':'sent','pdf':'sent'}


def test_telegram_429_and_ambiguous_timeout(tmp_path,monkeypatch):
    monkeypatch.setattr('radar.telegram.time.sleep',lambda _:None)
    n = 0
    def handle(req):
        nonlocal n
        n+=1
        if n==1: return httpx.Response(429,json={'ok':False,'parameters':{'retry_after':1}})
        return httpx.Response(200,json={'ok':True,'result':{'message_id':1}})
    db = Store(tmp_path/'state.db')
    s = Settings(telegram_token='test',telegram_chat='private')
    Telegram(s,db,httpx.Client(transport=httpx.MockTransport(handle))).text('day','s','text')
    assert n == 2
    def timeout(req): raise httpx.ReadTimeout('private URL',request=req)
    t=Telegram(s,db,httpx.Client(transport=httpx.MockTransport(timeout)))
    with pytest.raises(TelegramError) as e: t.text('day','uncertain','text')
    assert e.value.ambiguous
    assert t.text('day','uncertain','text') == 0
    assert db.delivery_states('day')['uncertain-1'] == 'sending'


def test_definitive_failure_releases_delivery(tmp_path):
    db=Store(tmp_path/'state.db')
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(400,json={'ok':False})))
    t=Telegram(Settings(telegram_token='test',telegram_chat='private'),db,client)
    with pytest.raises(TelegramError):t.text('day','summary','x')
    assert db.delivery_states('day') == {}


def test_manual_report_does_not_block_scheduled_delivery(tmp_path):
    from radar.pipeline import deliver
    calls=[]
    def handle(req):
        calls.append(req)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':len(calls)}})
    settings=Settings(telegram_token='test',telegram_chat='private')
    telegram=Telegram(settings,Store(tmp_path/'state.db'),httpx.Client(transport=httpx.MockTransport(handle)))
    report=demo_report(settings)
    pdf=tmp_path/'demo.pdf';pdf.write_bytes(b'%PDF synthetic')
    data=tmp_path/'demo.json';data.write_text('{}')
    paths={'pdf':pdf,'json':data}
    deliver(report,paths,telegram,edition='manual')
    first=len(calls)
    deliver(report,paths,telegram,edition='manual')
    assert len(calls)==first
    deliver(report,paths,telegram,edition='scheduled')
    assert len(calls)>first
    assert sum(r.url.path.endswith('/sendDocument') for r in calls)==4
    second=len(calls)
    deliver(report,paths,telegram,edition='scheduled')
    assert len(calls)==second


def test_api_retry_cache_and_errors(tmp_path,monkeypatch):
    monkeypatch.setattr('radar.http.time.sleep',lambda _:None)
    n=0
    def handle(req):
        nonlocal n
        n+=1
        return httpx.Response(429 if n==1 else 200,json={'data':123})
    http=HTTP(Store(tmp_path/'state.db'),httpx.Client(transport=httpx.MockTransport(handle)))
    assert http.get('https://example.com/data') == {'data':123}
    assert http.get('https://example.com/data') == {'data':123}
    assert n==2
    with pytest.raises(APIError):http.get('http://localhost')


def test_pdf_full_content_and_demo_all_watchlist(tmp_path):
    s=Settings(reports_dir=tmp_path)
    report=demo_report(s)
    assert len(report['assets']) == 34
    assert {a['symbol'] for a in report['assets']} == {a['symbol'] for a in Watchlist.load('config/watchlist.yaml').instruments()}
    paths=generate(report,tmp_path)
    pdf=PdfReader(paths['pdf'])
    text=''.join(p.extract_text() for p in pdf.pages)
    assert len(pdf.pages)>5
    assert 'DEMONSTRAÇÃO' in text
    assert 'EME' in text and 'HYPE' in text and 'AVDV' in text
    assert 'Métrica' in text
    assert 'As credenciais' in text
    assert 'private' not in text


def test_pdf_long_sources_and_injection_text_no_truncation(tmp_path):
    path=tmp_path/'long.pdf'
    text='# Relatório\n\n'+'\n\n'.join(['<script>texto externo</script> & '+'https://example.com/'+('a'*200)]*100)+'\n\nMARCADOR_FINAL'
    render_pdf(text,path)
    content=''.join(p.extract_text() for p in PdfReader(path).pages)
    assert 'MARCADOR_FINAL' in content
    assert 'texto externo' in content
