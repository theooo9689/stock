"""Quality funnel, frozen inputs, local research and selective publication."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pydantic import BaseModel

from .deep_research import investigate, CriticalReview
from .evidence import document, asset_documents, normalized
from .local_ai import Ollama, LocalAIError
from .scoring import score_asset, METHODOLOGY
from .selection import research_candidates, publication

PRIORITY = ['AVUV','AVDV','JEPI','JEPQ','SCHD','IVVB11','VOO','IVV','SPY','QQQ','WRLD11','EME','FIS','ORCL','CRWV','AAOI','AMKR','NBIS','VRT','BTC','ETH','SOL','BNB','XRP','LINK']
ETF_PROFILES = {
 'AVUV':('Small caps americanas, value e lucratividade; exposição a fatores e risco de porte.', 'https://www.avantisinvestors.com/avantis-investments/avantis-us-small-cap-value-etf/'),
 'AVDV':('Small caps internacionais desenvolvidas, value e lucratividade; risco cambial e regional.', 'https://www.avantisinvestors.com/avantis-investments/avantis-international-small-cap-value-etf/'),
 'JEPI':('Renda com ações e exposição a opções via ELNs; distribuições não equivalem a retorno total, upside pode ser limitado.', 'https://am.jpmorgan.com/us/en/asset-management/adv/products/jpmorgan-equity-premium-income-etf-etf-shares-46641q332'),
 'JEPQ':('Ações ligadas ao Nasdaq e renda com opções/ELNs; concentração tecnológica, risco de contraparte e upside limitado.', 'https://am.jpmorgan.com/us/en/asset-management/adv/products/jpmorgan-nasdaq-equity-premium-income-etf-etf-shares-46654q203'),
 'SCHD':('Dividendos, qualidade e sustentabilidade; examinar crescimento das distribuições e concentração setorial.', 'https://www.schwabassetmanagement.com/products/schd'),
 'IVVB11':('Exposição ao S&P 500 em veículo brasileiro; risco de concentração das maiores empresas, custos e dólar/real.', 'https://www.blackrock.com/br/products/251969/ishares-sp-500-fundo-de-investimento-em-cotas-de-fundo-de-ndice-fundo-brl'),
}


def stable(value):
    if isinstance(value,dict):return {k:stable(v) for k,v in sorted(value.items()) if k not in ('retrieved_at','generated_at','thesis','ranking','history','score_input_hash')}
    if isinstance(value,list):return [stable(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(stable(value),ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()


class NewsAnalysis(BaseModel):
    model_config={'extra':'forbid'}
    title: str
    document_id: str
    quote: str
    fact: str
    prior_context: str
    surprise: str
    mechanism: str
    observed_effect: str
    positive_scenario: str
    negative_scenario: str
    affected: list[str]
    watchlist_effect: str
    monitor: str


def collect_documents(http, headlines):
    important=('fed','inflation','inflation','tariff','treasury','jobs','earnings','guidance','rates','oil','hormuz','china','budget','tax','bitcoin','ethereum','regulation','econom','trade')
    ordered=sorted(headlines,key=lambda n:(-sum(k in n['title'].lower() for k in important),n['url']))
    docs=[];failures=[]
    for n in ordered[:12]:
        try:docs.append(document(http,n['url'],n.get('published_at')))
        except Exception as exc:failures.append({'stage':'news','source':n['url'],'failure':type(exc).__name__})
    return docs,failures


def news_research(ai, docs, day):
    result=[];failures=[]
    for d in docs:
        try:
            when=datetime.fromisoformat((d.get('published_at') or '').replace('Z','+00:00'))
            if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
            now=datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1)
            if not now-timedelta(days=4)<=when<=now:continue
            item=ai.complete('news-context-v2',NewsAnalysis,{'document':d,'watchlist':PRIORITY},
                'Analise somente uma notícia financeira material. Copie um trecho literal que sustente o fato. Separe contexto anterior, surpresa confirmada (se desconhecida, diga), efeito observado de hipótese, mecanismo econômico, cenários positivo e negativo, ativos afetados, efeito nas teses e o que monitorar. Não atribua decisão de governo ao Fed nem invente reação de preço. Se a notícia não for material, use affected vazio. Não use título sensacionalista.')
            if item.document_id!=d['id'] or len(item.quote)<60 or normalized(item.quote) not in normalized(d['text']) or not item.affected:continue
            review=ai.complete('news-review-v2',CriticalReview,{'article':d,'analysis':item.model_dump()},
                'Revise com ceticismo a notícia contra o documento. Reprove título incorreto, órgão errado, citação que não sustenta a afirmação, causalidade indevida, data inventada, número não presente e erro econômico como dizer que dólar mais caro sempre prejudica exportadores. Não confirme reação de mercado sem dado observado.')
            if not (review.approved and review.numeric_consistency and review.citations_support_claims) or review.unsupported_claims:continue
            result.append({**item.model_dump(),'evidence':{'fact':item.fact,'source_url':d['url'],'published_at':d['published_at']},'interpretation':item.mechanism,
                           'verification':{'supporting_quote':item.quote,'document_sha':d['sha256'],'review':review.model_dump()}})
        except (ValueError,TypeError):
            continue
        except LocalAIError as exc:
            failures.append({'stage':'news_review','failure':str(exc)})
            break
        if len(result)>=10:break
    return result,failures


def upgrade_report(original, watchlist=None):
    """Regenerate the problematic report safely without trusting its old scores/AI claims."""
    r=copy.deepcopy(original)
    if r.get('methodology_version') != METHODOLOGY:
        # Unreviewed claims/decisions from the old report cannot survive migration.
        r.setdefault('research',{})['news']=[]
        r['research']['summary']='Relatório histórico reavaliado; conclusões antigas não verificadas foram descartadas.'
        r['research'].setdefault('risks',['Dados insuficientes não sustentam uma conclusão de investimento.'])
        for a in r['assets']:a.pop('thesis',None)
    priority=(watchlist.priority if watchlist else None) or PRIORITY
    caps=(watchlist.publication if watchlist else None) or {'stocks':5,'etfs':3,'crypto':3,'observe':5}
    weights=watchlist.weights if watchlist else __import__('radar.config',fromlist=['Watchlist']).Watchlist.load('config/watchlist.yaml').weights
    for a in r['assets']:
        if a['symbol'] in ETF_PROFILES:
            strategy,url=ETF_PROFILES[a['symbol']];a['etf_profile']={'strategy':strategy,'source':url,'status':'Referência da estratégia; composição e custos exigem dados datados'}
        a['ranking']=score_asset(a,weights,a.get('thesis'))
        a['score_input_hash']=digest({'method':METHODOLOGY,'asset':a,'weights':weights})
    r['publication']=publication(r['assets'],priority,caps)
    r['methodology_version']=METHODOLOGY
    r['snapshot_id']=digest({'day':r['day'],'assets':r['assets'],'method':METHODOLOGY,'weights':weights})
    r.setdefault('ai',{'provider':'none','ready':False,'reason':'Pesquisa local não executada nesta reconstituição; sem compra inferida do relatório antigo.'})
    r.setdefault('failures',[])
    r['status']='parcial' if not r['ai'].get('ready') else r['status']
    return r


def enrich(settings, store, wl, report, http, ai_enabled=True):
    r=upgrade_report(report,wl)
    r['failures']=report.get('failures',[])
    r['research']={'summary':'','summaries':[],'news':[],'events':report.get('research',{}).get('events',[]),'risks':[], 'limitations':[], 'sources':[]}
    ai=None
    try:
        if settings.research_provider!='ollama':raise LocalAIError('Pesquisa local desabilitada pela configuração')
        if not ai_enabled:raise LocalAIError('IA desativada; edição factual de dados')
        ai=Ollama(settings,store)
        r['ai']=ai.doctor()
    except LocalAIError as exc:
        r['ai']={'provider':'ollama','model':settings.ollama_model,'ready':False,'reason':str(exc),'cloud_cost_usd':0}
        r['failures'].append({'stage':'local_model','failure':str(exc)})
    docs=[]
    if r['ai']['ready']:
        docs,errors=collect_documents(http,r.get('headlines',[]));r['failures'].extend(errors)
        r['research']['news'],errors=news_research(ai,docs,r['day']);r['failures'].extend(errors)
        candidates=research_candidates(r['assets'],wl.publication)
        for asset in candidates:
            try:
                sources=asset_documents(http,asset,docs)
                if len(sources)<2:
                    r['failures'].append({'stage':'evidence','asset':asset['symbol'],'failure':'Menos de duas fontes recuperadas; não publicar tese'});continue
                known={d['id'] for d in docs}
                docs.extend(d for d in sources if d['id'] not in known)
                thesis=investigate(ai,asset,sources)
                asset['thesis']={'premium':thesis}
                if not thesis['validated']:r['failures'].append({'stage':'critical_review','asset':asset['symbol'],'failure':thesis.get('review',{}).get('reason','Tese insuficiente')})
            except LocalAIError as exc:
                r['failures'].append({'stage':'deep_research','asset':asset['symbol'],'failure':str(exc)})
                break
        r['ai']['investigated']=[a['symbol'] for a in candidates]
    for a in r['assets']:a['ranking']=score_asset(a,wl.weights,a.get('thesis'))
    r['publication']=publication(r['assets'],wl.priority or PRIORITY,wl.publication)
    if ai and r['ai']['ready'] and (r['publication']['selected'] or r['research']['news']):
        try:
            items=[{'type':'news','content':n} for n in r['research']['news']]
            items.extend({'type':'opportunity','symbol':a['symbol'],'ranking':a['ranking'],'thesis':a.get('thesis')} for a in r['assets'] if a['symbol'] in r['publication']['selected'])
            batches=[];batch=[];size=0
            budget=max(4000,settings.ollama_context*2-24000)
            for item in items:
                item_size=len(json.dumps(item,ensure_ascii=False).encode())
                if batch and size+item_size>budget:batches.append(batch);batch=[];size=0
                batch.append(item);size+=item_size
            if batch:batches.append(batch)
            reviews=[]
            for batch in batches:
                reviews.append(ai.complete('publication-review-v2',CriticalReview,{'items':batch},
                    'Revisão final da publicação: verifique coerência entre notícias, indicadores, riscos e decisões. Reprove compra que não decorra da tese, justificativas repetitivas/genéricas, contradição econômica, narrativa ou números sem suporte nas evidências já verificadas. Não trate ausência de oportunidades como falha. Não invente informação externa.'))
            approved=all(all((v.approved,v.numeric_consistency,v.citations_support_claims,v.strongest_objection_addressed)) and not v.unsupported_claims for v in reviews)
            r['final_review']={'approved':approved,'batches':[v.model_dump() for v in reviews]}
            if not approved:
                for a in r['assets']:
                    if a.get('thesis',{}).get('premium'):a['thesis']['premium']['validated']=False
                    a['ranking']=score_asset(a,wl.weights,a.get('thesis'))
                r['research']['news']=[]
                r['publication']=publication(r['assets'],wl.priority or PRIORITY,wl.publication)
                r['failures'].append({'stage':'final_review','failure':'; '.join(v.reason for v in reviews if not v.approved or v.unsupported_claims)})
        except LocalAIError as exc:
            # Previously reviewed items remain in the audit, but no unreviewed final edition is published.
            r['publication']['selected']=[];r['publication']['observe']=[];r['research']['news']=[]
            r['failures'].append({'stage':'final_review','failure':str(exc)})
    r['research']['sources']=sorted({d['url'] for d in docs})
    r['research']['risks']=['Lacunas de evidência podem impedir uma conclusão mesmo com indicadores favoráveis.',
                            'Valuation depende de premissas; cenário base não é garantia de retorno.',
                            'ETFs sobrepostos e cripto podem concentrar riscos distintos apesar de tickers diferentes.']
    r['research']['summary']=f"{len(r['publication']['selected'])} oportunidades passaram pelo funil; {len(r['publication']['watchlist'])} ativos prioritários acompanhados."
    r['status']='parcial' if r['failures'] or not r['ai']['ready'] or not r['research']['news'] else 'concluído'
    r['limitations']=list(dict.fromkeys(report.get('limitations',[])))
    if not r['ai']['ready']:r['limitations'].append(r['ai']['reason'])
    r['audit']={'methodology':METHODOLOGY,'model':r['ai'],'parameters':{'weights':wl.weights,'publication':wl.publication,'priority':wl.priority},
                'data_snapshot_hash':r['snapshot_id'],'documents':[{'id':d['id'],'sha256':d['sha256'],'url':d['url'],'published_at':d['published_at']} for d in docs]}
    snapshot={'inputs':stable(report),'documents':docs,'model':r['ai'],'parameters':r['audit']['parameters'],'methodology':METHODOLOGY}
    r['snapshot_id']=digest(snapshot)
    store.save_snapshot(r['snapshot_id'],r['day'],snapshot)
    r['cost']={'provider':'ollama','cloud_api_usd':0,'note':'Execução local; tempo/energia e dados/licenças externos não são custo de API OpenAI.'}
    return r
