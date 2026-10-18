"""ETF comparisons use adjusted prices in common currency and dated holdings."""
from __future__ import annotations

import math


def exposure(a):
    holdings=a.get('holdings',{});top=holdings.get('top',[])
    weights=[row['weight'] for row in top if row.get('weight') is not None]
    return {'top10_weight':sum(weights) if weights else None,'holdings_count_reported':len(top),
            'top':top[:5], 'sectors':holdings.get('sectors',{}),'source':holdings.get('source'),
            'effective_period':holdings.get('period'),'retrieved_at':holdings.get('as_of'),
            'warning':'A amostra de maiores posições não representa toda a carteira. Data de coleta não comprova período efetivo.'}


def compare_series(common):
    changes=common.pct_change().dropna()
    return {name:{'volatility':float(changes[name].std()*math.sqrt(252)),
                  'max_drawdown':float((common[name]/common[name].cummax()-1).min())} for name in common.columns}


def overlaps(assets):
    result=[]
    for i,a in enumerate(assets):
        left={h['symbol']:h['weight'] for h in a.get('holdings',{}).get('top',[]) if h.get('weight') is not None}
        if not left or not a.get('holdings',{}).get('period'):continue
        for b in assets[i+1:]:
            if not b.get('holdings',{}).get('period') or b['holdings']['period']!=a['holdings']['period']:continue
            right={h['symbol']:h['weight'] for h in b['holdings']['top'] if h.get('weight') is not None}
            result.append({'left':a['symbol'],'right':b['symbol'],'common_weight_lower_bound':sum(min(v,right.get(k,0)) for k,v in left.items()),'period':a['holdings']['period'],
                           'method':'Soma dos menores pesos comuns na amostra divulgada; limite inferior, não sobreposição da carteira completa.'})
    return result
