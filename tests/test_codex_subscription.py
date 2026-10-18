import json
import os
from pathlib import Path
import subprocess

import pytest
from pydantic import BaseModel

from radar.codex_research import CodexResearch, command_path
from radar.config import Settings
from radar.local_ai import LocalAIError
from radar.storage import Store


class Answer(BaseModel):
    model_config={'extra':'forbid'}
    answer: str


def engine(tmp_path, monkeypatch, *, login='Logged in using ChatGPT', fail=False, bad_json=False, search=True, timeout=False):
    calls=[]
    executable=tmp_path/'codex.exe';executable.write_bytes(b'fixture')
    monkeypatch.setattr('radar.codex_research.command_path',lambda _:str(executable))
    def runner(args,**kwargs):
        calls.append((args,kwargs))
        if args[1:]==['--version']:return subprocess.CompletedProcess(args,0,'codex-cli fixture','')
        if args[1:]==['login','status']:return subprocess.CompletedProcess(args,0,login,'')
        if args[1:]==['exec','--help']:return subprocess.CompletedProcess(args,0,'--output-schema --ignore-user-config --json','')
        if timeout:raise subprocess.TimeoutExpired(args,10)
        output=Path(args[args.index('--output-last-message')+1])
        output.write_text('invalid' if bad_json else '{"answer":"Resposta com fonte"}',encoding='utf-8')
        events=[]
        if search:events.append({'type':'item.completed','item':{'type':'web_search','query':'official'}})
        events.append({'type':'turn.failed'} if fail else {'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':50}})
        return subprocess.CompletedProcess(args,1 if fail else 0,'\n'.join(json.dumps(e) for e in events),'private details excluded')
    settings=Settings(data_dir=tmp_path/'data',reports_dir=tmp_path/'reports')
    provider=CodexResearch(settings,Store(tmp_path/'state.db'),runner)
    return provider,calls


@pytest.mark.parametrize('login',['Logged in using an API key','Not authenticated','ChatGPT API key'])
def test_api_login_refused_before_inference(tmp_path,monkeypatch,login):
    ai,calls=engine(tmp_path,monkeypatch,login=login)
    with pytest.raises(LocalAIError,match='login ChatGPT'):ai.doctor()
    assert not any('--output-last-message' in args for args,_ in calls)


def test_codex_login_and_official_output_cache(tmp_path,monkeypatch):
    ai,calls=engine(tmp_path,monkeypatch);ai.doctor()
    for _ in range(2):assert ai.complete('test',Answer,{'source':'verified'},'Use the source').answer=='Resposta com fonte'
    inference=[(args,kwargs) for args,kwargs in calls if '--output-last-message' in args]
    assert len(inference)==1
    args,kwargs=inference[0]
    assert 'forced_login_method="chatgpt"' in args and 'model_provider="openai"' in args
    assert '--ignore-user-config' in args and 'read-only' in args and kwargs['shell'] is False
    assert ai.store.subscription_usage(ai.settings.now().date().isoformat())==[{'state':'completed','calls':1}]
    audit=list((ai.settings.data_dir/'codex-research').glob('*/request.json'));assert len(audit)==1
    saved=json.loads(audit[0].read_text(encoding='utf-8'));assert saved['engine']['auth']=='chatgpt'


def test_env_keys_and_telegram_destination_not_passed_to_agent(tmp_path,monkeypatch):
    for key in ('OPENAI_API_KEY','CODEX_API_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','FMP_API_KEY','OPENAI_BASE_URL'):
        monkeypatch.setenv(key,'PRIVATE_TEST_VALUE')
    ai,calls=engine(tmp_path,monkeypatch);ai.doctor();ai.complete('test',Answer,{'fact':1},'Use the fact')
    _,kwargs=next((a,k) for a,k in calls if '--output-last-message' in a)
    assert 'PRIVATE_TEST_VALUE' not in json.dumps(kwargs['env'])
    assert 'PRIVATE_TEST_VALUE' not in kwargs['input']
    assert all('PRIVATE_TEST_VALUE' not in json.dumps(k.get('env',{})) for _,k in calls)
    assert os.environ['OPENAI_API_KEY']=='PRIVATE_TEST_VALUE'


@pytest.mark.parametrize('options',[{'fail':True},{'bad_json':True},{'timeout':True}])
def test_failed_or_ambiguous_session_not_retried(tmp_path,monkeypatch,options):
    ai,calls=engine(tmp_path,monkeypatch,**options);ai.doctor()
    with pytest.raises(LocalAIError):ai.complete('test',Answer,{},'Test')
    with pytest.raises(LocalAIError):ai.complete('test',Answer,{},'Test')
    fresh=CodexResearch(ai.settings,ai.store,ai.runner);fresh.doctor()
    with pytest.raises(LocalAIError,match='já registrada'):fresh.complete('test',Answer,{},'Test')
    assert sum('--output-last-message' in a for a,_ in calls)==1
    assert ai.store.subscription_usage(ai.settings.now().date().isoformat())==[{'state':'incomplete','calls':1}]


def test_daily_limit_survives_new_provider_instance(tmp_path,monkeypatch):
    ai,calls=engine(tmp_path,monkeypatch);ai.settings.codex_max_calls=1;ai.doctor();ai.complete('first',Answer,{},'Test')
    other=CodexResearch(ai.settings,ai.store,ai.runner);other.doctor()
    with pytest.raises(LocalAIError,match='Limite diário'):other.complete('second',Answer,{},'Test')
    assert sum('--output-last-message' in a for a,_ in calls)==1


def test_discovery_requires_real_web_search_event(tmp_path,monkeypatch):
    ai,calls=engine(tmp_path,monkeypatch,search=False);ai.doctor()
    with pytest.raises(LocalAIError,match='não comprovou uso da busca'):ai.complete('discover-sources-test',Answer,{},'Search')
    args=next(a for a,_ in calls if '--output-last-message' in a);assert '--search' in args


def test_oversized_payload_does_not_start_cli_or_charge_slot(tmp_path,monkeypatch):
    ai,calls=engine(tmp_path,monkeypatch);ai.doctor()
    with pytest.raises(LocalAIError,match='contexto Codex'):ai.complete('test',Answer,{'large':'a'*200000},'Test')
    assert not any('--output-last-message' in a for a,_ in calls)
    assert ai.store.subscription_usage(ai.settings.now().date().isoformat())==[]


def test_windows_npm_shim_resolves_to_native_binary(tmp_path,monkeypatch):
    shim=tmp_path/'codex.cmd';shim.write_text('fixture')
    native=tmp_path/'node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/codex/codex.exe'
    native.parent.mkdir(parents=True);native.write_bytes(b'fixture')
    monkeypatch.setattr('radar.codex_research.shutil.which',lambda _:str(shim))
    assert command_path()==str(native.resolve())
    native.unlink()
    with pytest.raises(LocalAIError,match='Binário nativo'):command_path()


def test_provider_failure_does_not_fall_back_to_ollama(tmp_path,monkeypatch):
    from radar.premium import enrich
    from radar.config import Watchlist
    def unavailable(self):raise LocalAIError('ChatGPT sign-in needed')
    monkeypatch.setattr(CodexResearch,'doctor',unavailable)
    def forbidden(*args,**kwargs):raise AssertionError('Ollama fallback forbidden')
    monkeypatch.setattr('radar.premium.Ollama',forbidden)
    report={'day':'2026-10-18','status':'parcial','assets':[],'research':{},'headlines':[]}
    settings=Settings(data_dir=tmp_path)
    result=enrich(settings,Store(tmp_path/'state.db'),Watchlist.load('config/watchlist.yaml'),report,None)
    assert result['cost']['cloud_api_usd']==0 and not result['ai']['ready']
    assert result['ai']['provider']=='codex' and result['publication']['selected']==[]


def test_parallel_cap_is_atomic(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    db=Store(tmp_path/'state.db')
    def reserve(i):
        try:db.claim_subscription_call('day',str(i),'test',3);return True
        except LocalAIError:return False
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(12)))
    assert sum(results)==3


def test_retrieval_timestamp_alone_does_not_spend_again(tmp_path,monkeypatch):
    ai,calls=engine(tmp_path,monkeypatch);ai.doctor()
    for stamp in ('2026-10-18T10:00Z','2026-10-18T11:00Z'):
        ai.complete('test',Answer,{'document':{'retrieved_at':stamp,'text':'same evidence'}},'Use evidence')
    assert sum('--output-last-message' in a for a,_ in calls)==1


def test_manual_official_pdf_dedup_and_validation(tmp_path):
    import httpx
    from radar.manual_delivery import forward_pdf
    from radar.telegram import Telegram
    settings=Settings(telegram_token='test',telegram_chat='private',data_dir=tmp_path)
    db=Store(tmp_path/'state.db');calls=[]
    def handle(req):
        calls.append(req);return httpx.Response(200,json={'ok':True,'result':{'message_id':len(calls)}})
    sender=Telegram(settings,db,httpx.Client(transport=httpx.MockTransport(handle)))
    pdf=tmp_path/'export.pdf';pdf.write_bytes(b'%PDF-1.7\nSynthetic export fixture')
    assert forward_pdf(settings,db,pdf,telegram=sender)['sent']
    renamed=tmp_path/'renamed.pdf';renamed.write_bytes(pdf.read_bytes())
    assert not forward_pdf(settings,db,renamed,telegram=sender)['sent']
    assert len(calls)==1
    bad=tmp_path/'bad.pdf';bad.write_bytes(b'not PDF')
    with pytest.raises(ValueError):forward_pdf(settings,db,bad,telegram=sender)
    assert len(calls)==1


def test_manual_summary_limit_precedes_send(tmp_path):
    from radar.manual_delivery import forward_pdf
    path=tmp_path/'valid.pdf';path.write_bytes(b'%PDF-1.7\nfixture')
    summary=tmp_path/'summary.txt';summary.write_text('A'*2001,encoding='utf-8')
    with pytest.raises(ValueError,match='2000'):forward_pdf(Settings(),Store(tmp_path/'db'),path,summary)


def test_batch_news_drops_fabrication_and_failed_review():
    from radar.premium import batch_news_research,NewsBatch,NewsReviews
    from radar.deep_research import CriticalReview
    quote='A statement that is present literally in the source document, with sufficient detail for the citation.'
    docs=[{'id':'D'+str(i),'url':'https://example.org/'+str(i),'text':quote,'published_at':'2026-10-18T12:00:00Z','sha256':'fixture','primary':True} for i in range(3)]
    class BatchAI:
        input_budget_bytes=150000
        def complete(self,purpose,schema,payload,instructions):
            if schema is NewsBatch:
                rows=[]
                for i in range(3):
                    row={key:'Explanation tied to the verified source' for key in ['title','fact','prior_context','surprise','mechanism','observed_effect','positive_scenario','negative_scenario','watchlist_effect','monitor']}
                    row.update(document_id='D'+str(i),quote=quote if i!=2 else 'Fabricated quote '*10,affected=['EME']);rows.append(row)
                return NewsBatch.model_validate({'items':rows})
            return NewsReviews.model_validate({'items':[{'document_id':'D'+str(i),'review':{'approved':i==0,'numeric_consistency':True,'citations_support_claims':True,'strongest_objection_addressed':True,'unsupported_claims':[],'reason':'fixture'}} for i in range(2)]})
    items,failures=batch_news_research(BatchAI(),docs,'2026-10-18')
    assert not failures and len(items)==1 and items[0]['document_id']=='D0'
