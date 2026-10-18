import copy
import json
from pathlib import Path
from html.parser import HTMLParser

import httpx
import pytest
from pydantic import BaseModel
from pypdf import PdfReader

from radar.config import Settings, Watchlist
from radar.deep_research import validate_thesis
from radar.evidence import factbook, verify_evidence
from radar.local_ai import Ollama, LocalAIError
from radar.premium import upgrade_report, enrich
from radar.presentation import messages
from radar.report import generate
from radar.scoring import score_asset, INCONCLUSIVE
from radar.selection import publication
from radar.storage import Store
from radar.telegram import html_chunks

WL=Watchlist.load('config/watchlist.yaml')


def stock():
    return {'symbol':'TEST','category':'stocks','quote':{'price':50,'currency':'USD','as_of':'2026-10-18T12:00:00Z','source':'https://finance.yahoo.com/quote/TEST'},
            'market':{'stale':False},'average_dollar_volume':100_000_000,
            'technical':{'sma50':50,'sma200':40,'rsi14':45,'macd':1,'macd_histogram':1,'atr14':2},
            'fundamentals_source':{'url':'https://example.org/financials','period':'2025-12-31'},
            'fundamentals':{'pe':10,'ev_ebitda':8,'fcf_yield':.1,'revenue_growth':.2,'earnings_growth':.2,'operating_margin':.3,'roe':.3,'roic':.2,'net_debt_ebitda':0,'ebitda':100,'fcf':20},
            'valuation':{'available':True,'scenarios':[{'fair_value':100},{'fair_value':150},{'fair_value':200}],'entry_max':112}}


def test_low_coverage_is_not_poor_investment():
    a={'symbol':'IVVB11','category':'br_etfs','fundamentals':{},'technical':{},'quote':{}}
    r=score_asset(a,WL.weights)
    assert r['score'] is None and r['decision']==INCONCLUSIVE
    assert not r['attractiveness']['missing_is_zero']


def test_crypto_missing_security_and_adoption_never_full_coverage():
    a=stock();a['category']='crypto';a['crypto']={'market_cap':100,'fully_diluted_valuation':100,'total_volume':20,'circulating_supply':100}
    r=score_asset(a,WL.weights,{'assessments':[{'criterion':'safety','score':100}]})
    assert r['coverage']<1 and r['score'] is None and r['decision']==INCONCLUSIVE
    assert 'security_verified' in r['data_quality']['critical_missing']


def test_high_quantitative_score_does_not_create_thesis():
    a=stock();r=score_asset(a,WL.weights)
    assert r['score']>=75 and r['decision']==INCONCLUSIVE
    assert r['confidence']['level']=='baixa'
    for n in (0,100):
        assert score_asset(a,WL.weights,{'assessments':[{'criterion':'macro','score':n}]})==r


def test_snapshots_stable_on_rerender_and_timestamps():
    a=stock();base={'day':'2026-10-18','assets':[a],'status':'parcial','research':{}}
    first=upgrade_report(base,WL);second=upgrade_report(first,WL)
    assert first['snapshot_id']==second['snapshot_id']
    assert first['assets'][0]['score_input_hash']==second['assets'][0]['score_input_hash']
    base['assets'][0]['retrieved_at']='different fetch time'
    assert upgrade_report(base,WL)['snapshot_id']==first['snapshot_id']
    base['assets'][0]['quote']['price']=75
    assert upgrade_report(base,WL)['snapshot_id']!=first['snapshot_id']


def test_selective_limits_and_no_quotas():
    assets=[]
    for kind,maximum in [('stocks',5),('us_etfs',3),('crypto',3)]:
        for i in range(12):
            a=stock();a.update(symbol=kind+str(i),category=kind,thesis={'premium':{'validated':True}},ranking={'decision':'COMPRAR PARCIALMENTE','score':90});assets.append(a)
    p=publication(assets,[],WL.publication)
    assert len(p['selected'])==11
    assert publication([],[],WL.publication)['selected']==[]
    assets[0].pop('thesis');assert assets[0]['symbol'] not in publication(assets,[],WL.publication)['selected']


def test_numeric_facts_need_source_and_period():
    a=stock();assert factbook(a)['fundamentals.pe']['as_of']=='2025-12-31'
    a['fundamentals_source'].pop('period');assert 'fundamentals.pe' not in factbook(a)
    a['quote']['source']='https://127.0.0.1/';assert 'quote.price' not in factbook(a)


def test_invented_citations_rejected():
    docs=[{'id':'D1','url':'https://example.org','primary':True,'text':'Real evidence '*20}]
    assert verify_evidence([{'document_id':'D1','quote':'Fabricated evidence '*10}],docs)==[]


def test_numeric_claims_in_catalysts_and_interpretations_checked():
    a=stock();t={k:'Descrição fundamentada e específica do mecanismo econômico. '*4 for k in ('business','why_now','counter_thesis','technical_context','buy_now','do_not_buy','entry_condition','invalidation','horizon')}
    t.update(evidence=[],missing=[],interpretations=[{'metric_id':'fundamentals.pe','interpretation':'Texto interpretativo sem comparativos fabricados. '*3}]*4,catalysts=['Lucro sobe 999999%'])
    assert any('999999' in issue for issue in validate_thesis(t,a,[])['validation_issues'])


class Answer(BaseModel):
    answer:str


def local_client(handler):return httpx.Client(transport=httpx.MockTransport(handler),base_url='http://127.0.0.1:11434')


def test_local_model_capacity_and_no_remote_fallback(tmp_path):
    calls=[]
    def handler(req):
        calls.append(req.url.host)
        return httpx.Response(200,json={'models':[{'name':'qwen3:8b','digest':'immutable'}]} if req.url.path.endswith('tags') else {'model_info':{'general.parameter_count':3e9,'qwen.context_length':40960}})
    ai=Ollama(Settings(data_dir=tmp_path),Store(tmp_path/'state.db'),local_client(handler))
    with pytest.raises(LocalAIError,match='insuficiente'):ai.doctor()
    assert set(calls)=={'127.0.0.1'}
    with pytest.raises(LocalAIError):Ollama(Settings(ollama_url='https://external.example.org'),None)


def test_local_requests_cached_with_model_identity_and_seed(tmp_path):
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        if req.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'qwen3:8b','digest':'abc'}]})
        if req.url.path=='/api/show':return httpx.Response(200,json={'model_info':{'general.parameter_count':8e9,'qwen.context_length':40960}})
        body=json.loads(req.content);assert body['options']['seed']==42 and body['options']['temperature']==0
        return httpx.Response(200,json={'done':True,'done_reason':'stop','message':{'content':'{"answer":"local"}'}})
    ai=Ollama(Settings(data_dir=tmp_path),Store(tmp_path/'db'),local_client(handler));ai.doctor()
    for _ in range(2):assert ai.complete('test',Answer,{'fact':1},'Use evidence').answer=='local'
    assert calls.count('/api/chat')==1
    audit=list((tmp_path/'local-research').glob('*.json'));assert len(audit)==1
    assert json.loads(audit[0].read_text(encoding='utf-8'))['model']['digest']=='abc'


class Visible(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.text=''
    def handle_starttag(self,tag,attrs):self.stack.append(tag)
    def handle_endtag(self,tag):assert self.stack.pop()==tag
    def handle_data(self,data):self.text+=data


def test_html_splitting_preserves_every_character_and_balances_tags():
    original='<>&😀 çã '*2500
    import html
    markup='<b>Título <i>'+html.escape(original)+'</i></b><a href="https://example.org/?a=1&amp;b=2">fim</a>'
    output=''
    for part in html_chunks(markup):
        parsed=Visible();parsed.feed(part);assert parsed.stack==[]
        assert len(parsed.text.encode('utf-16-le'))//2<=3800;output+=parsed.text
    assert output=='Título '+original+'fim'


def test_real_problem_report_regression(tmp_path):
    report=json.loads(Path('tests/fixtures/problem-2026-10-18.json').read_text(encoding='utf-8'))
    fixed=upgrade_report(report,WL)
    assert len(fixed['assets'])==52
    for a in fixed['assets']:
        assert a['ranking']['decision']==INCONCLUSIVE
        if a['symbol'] in ('IVVB11','WRLD11'):assert a['ranking']['score'] is None
        if a['category']=='crypto':assert a['ranking']['coverage']<1
    assert not fixed['research']['news'] and fixed['publication']['selected']==[]
    assert len(fixed['publication']['watchlist'])==25
    text='\n'.join(messages(fixed));assert text.count('AGUARDAR')<3 and len(text)<4000
    paths=generate(fixed,tmp_path);pdf=PdfReader(paths['pdf']);content=''.join(p.extract_text() for p in pdf.pages)
    assert len(pdf.pages)<=18 and len(pdf.outline)>=11
    for symbol in ('AVUV','AVDV','JEPI','JEPQ','SCHD','IVVB11','LINK'):assert symbol in content
    assert 'Metodologia, lacunas e fontes' in content
    assert any(page.get('/Annots') for page in pdf.pages)


def test_local_failure_yields_factual_report_without_cloud(tmp_path,monkeypatch):
    def unavailable(self):raise LocalAIError('Ollama indisponível')
    monkeypatch.setattr(Ollama,'doctor',unavailable)
    s=Settings(data_dir=tmp_path)
    raw={'day':'2026-10-18','generated_at':'2026-10-18T12:00:00Z','status':'parcial','assets':[stock()],'macro':[],'headlines':[],'research':{}}
    report=enrich(s,Store(tmp_path/'db'),WL,raw,None)
    assert not report['ai']['ready'] and report['cost']['cloud_api_usd']==0
    assert report['publication']['selected']==[] and report['assets'][0]['quote']['price']==50


def test_deep_pdf_flows_entire_thesis_and_demo_never_sends(tmp_path):
    from radar.demo import premium_sample_report
    from radar.pipeline import deliver
    report=premium_sample_report(Settings(data_dir=tmp_path,reports_dir=tmp_path))
    report['assets'][next(i for i,a in enumerate(report['assets']) if a['symbol']=='EME')]['thesis']['premium']['invalidation']+=' MARCADOR FINAL DA TESE SEM CORTE.'
    paths=generate(report,tmp_path)
    pdf=PdfReader(paths['pdf']);text=''.join(p.extract_text() for p in pdf.pages)
    assert 'MARCADOR FINAL DA TESE SEM CORTE' in ' '.join(text.split()) and 'Premissas por cenário' in text
    assert 'Argumento mais forte contra' in text and 'FCF yield' in text
    assert all('DEMONSTRAÇÃO' in p.extract_text() for p in pdf.pages)
    with pytest.raises(ValueError,match='sintética'):deliver(report,paths,None)


def test_versions_preserve_distinct_outputs_for_same_snapshot(tmp_path):
    db=Store(tmp_path/'state.db')
    a={'day':'2026-10-18','status':'parcial','snapshot_id':'same-input','result':'first'}
    db.save_report(a['day'],a)
    db.save_report(a['day'],{**a,'result':'second'})
    versions=db.versions(a['day']);assert len(versions)==2
    assert {db.report_version(v)['result'] for v in versions}=={'first','second'}


def test_undated_news_is_skipped_and_redirects_remain_public(tmp_path):
    from radar.premium import news_research
    from radar.http import HTTP, APIError
    assert news_research(None,[{'published_at':None}], '2026-10-18')==([],[])
    urls=[]
    def handler(req):
        urls.append(str(req.url))
        return httpx.Response(302,headers={'Location':'https://127.0.0.1/private'})
    h=HTTP(Store(tmp_path/'state.db'),httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(APIError):h.get('https://example.org/news')
    assert len(urls)==1


def test_crypto_has_a_scoring_route_only_after_required_diligence():
    a=stock();a['category']='crypto';a['crypto']={'market_cap':100,'fully_diluted_valuation':100,'circulating_supply':100,'total_volume':20}
    for field in ('tokenomics_verified','adoption_verified','security_verified'):
        a['crypto'][field]={'checked':True,'source':'https://example.org/verified-diligence','as_of':'2026-10-18','quote':'SYNTHETIC fixture representing separately verified due diligence.'}
    thesis={'premium':{'validated':True,'review':{'approved':True}}}
    rank=score_asset(a,WL.weights,thesis)
    assert rank['score'] is not None
    a['crypto'].pop('adoption_verified')
    assert score_asset(a,WL.weights,thesis)['score'] is None
