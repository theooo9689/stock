from __future__ import annotations

from .scoring import data_quality, INCONCLUSIVE


def kind(asset):
    return 'etfs' if asset['category'] in ('us_etfs','br_etfs') else 'crypto' if asset['category']=='crypto' else 'stocks'


def research_candidates(assets, caps):
    groups={'stocks':[],'etfs':[],'crypto':[]}
    for a in assets:
        quality=data_quality(a)
        if quality['coverage']<.8 or quality['critical_missing']:continue
        m=a.get('fundamentals',{})
        if kind(a)=='stocks' and ((m.get('fcf') or 0)<=0 or (m.get('operating_margin') or 0)<=0 or (m.get('net_debt_ebitda') or 0)>3):continue
        # Screening priority is internal, never presented as an investment recommendation.
        priority=(m.get('fcf_yield') or 0)*100 + (m.get('revenue_growth') or 0)*10
        groups[kind(a)].append((priority,a['symbol'],a))
    return [a for group in groups for _,_,a in sorted(groups[group],key=lambda row:(-row[0],row[1]))[:caps.get(group,0)]]


def trigger(asset):
    m,t,v= (asset.get(k,{}) for k in ('fundamentals','technical','valuation'))
    if v.get('available') and v.get('entry_max'):
        return f"Reavaliar preço ≤ {v['entry_max']:.2f} {asset.get('quote',{}).get('currency','')}, limite do cenário base com margem de segurança; exigir tese e balanço confirmados."
    if m.get('net_debt_ebitda') is not None and m['net_debt_ebitda']>3:
        return f"Reavaliar após divulgação de dívida líquida/EBITDA abaixo de 3× (atual {m['net_debt_ebitda']:.2f}×), sem piora do FCF."
    if t.get('sma200') and t.get('resistance'):
        return f"Monitorar fechamento acima de {t['resistance']:.2f} com volume relativo ≥ 1,5; MM200 em {t['sma200']:.2f}. É gatilho de investigação, sem autorização de compra."
    return None


def publication(assets, priority, caps):
    selected=[]
    for category in ('stocks','etfs','crypto'):
        eligible=[a for a in assets if kind(a)==category and a.get('thesis',{}).get('premium',{}).get('validated')
                  and a['ranking']['decision']=='COMPRAR PARCIALMENTE']
        selected.extend(sorted(eligible,key=lambda a:(-(a['ranking']['score'] or 0),a['symbol']))[:caps.get(category,0)])
    chosen={a['symbol'] for a in selected}
    observe=[]
    for a in sorted(assets,key=lambda a:(a['symbol'] not in priority,a['symbol'])):
        if a['symbol'] in chosen or a['ranking']['decision']==INCONCLUSIVE:continue
        condition=trigger(a)
        if condition:observe.append({'symbol':a['symbol'],'condition':condition,'reason':a.get('thesis',{}).get('premium',{}).get('do_not_buy','')})
        if len(observe)>=caps.get('observe',5):break
    return {'selected':[a['symbol'] for a in selected], 'observe':observe,
            'watchlist':[a['symbol'] for a in assets if a['symbol'] in priority],
            'funnel':{'screened':len(assets),'data_eligible':sum(data_quality(a)['coverage']>=.8 and not data_quality(a)['critical_missing'] for a in assets),
                      'theses_approved':sum(a.get('thesis',{}).get('premium',{}).get('validated',False) for a in assets),'published':len(selected)}}
