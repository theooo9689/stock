from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .http import safe_url
from .news import canonical


def normalized(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip().casefold()


def document(http, url, published_at=None, primary_hosts=()):
    html = http.get(url, ttl=21600, json_response=False)
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else urlparse(url).hostname
    meta = soup.select_one('meta[property="article:published_time"],meta[itemprop="datePublished"],meta[name="date"]')
    date = meta.get('content') if meta else published_at
    if not date:
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                values = json.loads(script.string or '')
                for v in values if isinstance(values,list) else [values]:
                    if isinstance(v,dict) and v.get('datePublished'):
                        date=v['datePublished'];break
            except (ValueError,TypeError):pass
    for t in soup(['script','style','nav','footer','header','aside','form']):t.decompose()
    body = (soup.find('article') or soup.find('main') or soup.body or soup).get_text(' ',strip=True)
    if len(body) < 200:
        raise ValueError('Documento sem corpo verificável')
    host = urlparse(url).hostname or ''
    primary = host.endswith(('.gov','.gov.br')) or any(host.removeprefix('www.') == h.removeprefix('www.') or host.endswith('.'+h.removeprefix('www.')) for h in primary_hosts if h)
    return {'id':'D'+hashlib.sha256(canonical(url).encode()).hexdigest()[:12], 'url':url, 'title':title,
            'published_at':date, 'retrieved_at':datetime.now(timezone.utc).isoformat(), 'primary':primary,
            'text':body[:24000], 'excerpt_limited':len(body)>24000, 'sha256':hashlib.sha256(body.encode()).hexdigest()}


def search(http, query):
    """Actual external retrieval; the local model never pretends to search."""
    try:raw = http.get('https://www.bing.com/search', {'q':query,'format':'rss'}, ttl=21600, json_response=False)
    except Exception:return []
    if not isinstance(raw,str):return []
    try:
        root=ET.fromstring(raw)
        return [{'url':n.findtext('link'),'title':n.findtext('title')} for n in root.findall('.//item') if safe_url(n.findtext('link') or '')][:6]
    except ET.ParseError:return []


def asset_documents(http, asset, news_docs):
    symbol=asset['symbol']; name=asset.get('name',symbol)
    host=urlparse(asset.get('business',{}).get('website') or '').hostname
    profiles=asset.get('etf_profile',{})
    primary_hosts=[host] if host else []
    if profiles.get('source'):primary_hosts.append(urlparse(profiles['source']).hostname)
    docs=[d for d in news_docs if symbol.lower() in d['title'].lower() or name.lower() in d['title'].lower()]
    urls=[profiles['source']] if profiles.get('source') else []
    urls += [r['url'] for r in search(http, f'{name} {symbol} investor relations latest earnings results cash flow risks')]
    seen={d['url'] for d in docs}
    for url in urls:
        if url in seen:continue
        seen.add(url)
        try:docs.append(document(http,url,primary_hosts=primary_hosts))
        except Exception:continue
        if len(docs)>=4:break
    return docs


def factbook(a):
    facts={}
    sources={'quote':a.get('quote',{}).get('source'), 'technical':a.get('quote',{}).get('source'),
             'fundamentals':a.get('fundamentals_source',{}).get('url'), 'crypto':a.get('crypto',{}).get('source')}
    for group in sources:
        period=(a.get('technical_as_of') or a.get('quote',{}).get('as_of')) if group in ('quote','technical') else a.get('fundamentals_source',{}).get('period') if group=='fundamentals' else a.get('crypto',{}).get('last_updated')
        if not safe_url(sources[group] or '') or not period:continue
        for k,v in a.get(group,{}).items():
            if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v):
                facts[group+'.'+k]={'value':v,'source':sources[group], 'as_of':period,
                                   'unit':'fração' if any(x in k for x in ('yield','growth','margin','volatility','drawdown','roe','roic','roa')) else 'vezes / unidade indicada pelo campo'}
    return facts


def verify_evidence(items, docs):
    lookup={d['id']:d for d in docs}; accepted=[]
    for item in items:
        d=lookup.get(item['document_id'])
        if d and len(item['quote'])>=60 and normalized(item['quote']) in normalized(d['text']):
            accepted.append({**item,'source':d['url'],'primary':d['primary'],'published_at':d.get('published_at')})
    return accepted
