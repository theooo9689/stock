from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from radar.config import Settings, Watchlist
from radar.fundamentals import dcf_equity, derive, ratio, value_range, value_traps
from radar.http import safe_url
from radar.market import market_status, compare_etfs
from radar.news import dedupe
from radar.pipeline import compare
from radar.scoring import score_asset
from radar.storage import Store
from radar.technical import indicators, wilder


def candles(close):
    x = np.array(close, dtype=float)
    return pd.DataFrame({'close': x, 'high': x+1, 'low': x-1, 'volume': np.repeat(100., len(x))}, index=pd.date_range('2025-01-01', periods=len(x), tz='UTC'))


def test_wilder_has_sma_seed_and_recursive_update():
    r = wilder(pd.Series([1.,2.,3.,7.]), 3)
    assert pd.isna(r.iloc[1])
    assert r.iloc[2] == 2
    assert r.iloc[3] == pytest.approx(11/3)


@pytest.mark.parametrize('values,rsi', [(np.arange(1,301),100), (np.arange(301,1,-1),0), (np.repeat(100.,300),50)])
def test_rsi_extremes_and_neutral(values,rsi):
    assert indicators(candles(values))['rsi14'] == pytest.approx(rsi)


def test_macd_and_atr_against_independent_reference():
    f = candles(np.repeat(100.,300))
    t = indicators(f)
    assert t['macd'] == 0
    assert t['macd_signal'] == 0
    assert t['atr14'] == 2
    assert t['relative_volume'] == 1
    assert t['drawdown'] == 0
    assert t['annualized_volatility'] == 0
    assert t['sma200'] == 100
    assert t['high52w'] == 101
    assert t['support'] == 99


def test_macd_on_trend_converges_and_crypto_annualization():
    f = candles(np.arange(1.,401))
    t = indicators(f)
    assert t['macd'] == pytest.approx(7, abs=1e-8)
    assert t['macd_signal'] == pytest.approx(7, abs=1e-8)
    assert t['trend'] == 'alta'
    assert indicators(f,crypto=True)['annualized_volatility'] / t['annualized_volatility'] == pytest.approx(np.sqrt(365/252))


def test_missing_indicators_do_not_invent_values():
    assert 'error' in indicators(candles([1,2,3]))
    assert indicators(candles(np.arange(1.,81)))['sma200'] is None


def test_macro_units_do_not_treat_yield_or_index_as_dollars():
    from radar.market import MACRO_UNITS
    assert MACRO_UNITS['^TNX'] == '% ao ano'
    assert MACRO_UNITS['^GSPC'] == 'pontos'
    assert MACRO_UNITS['BRL=X'] == 'BRL por USD'


def test_perpetuity_dcf_closed_form_and_invalid_inputs():
    # Zero growth and zero terminal growth: finite horizon + perpetuity = FCF/r.
    assert dcf_equity(100,10,0,.1,0) == pytest.approx(100)
    assert dcf_equity(-100,10,.1,.1) is None
    assert dcf_equity(100,10,.1,.02,.025) is None
    assert ratio(10,0) is None
    assert ratio(None,10) is None


def test_fundamentals_and_value_traps():
    m = derive({'marketCap':1000,'freeCashflow':50,'totalDebt':400,'totalCash':100,'ebitda':50,'revenueGrowth':-.2,'earningsGrowth':-.1})
    assert m['fcf_yield'] == .05
    assert m['price_fcf'] == 20
    assert m['net_debt_ebitda'] == 6
    assert len(value_traps(m)) == 3
    assert derive({})['fcf_yield'] is None


def test_fair_value_requires_history_and_discloses_assumptions():
    cfg = Watchlist.load('config/watchlist.yaml').valuation
    assert not value_range({'fcf':100,'shares':10},cfg)['available']
    v = value_range({'fcf':100,'shares':10,'positive_fcf_years':3,'median_annual_fcf':90,'eps':2},cfg)
    assert v['available']
    assert len(v['sensitivity']) == 9
    assert v['entry_max'] == pytest.approx(v['scenarios'][1]['fair_value']*.75)


def test_closed_exchange_holiday_and_crypto_current():
    sunday = datetime(2026,10,18,20,tzinfo=timezone.utc)
    friday = '2026-10-16T20:00:00+00:00'
    s = market_status('stocks',friday,sunday)
    assert s['session'] == 'fechada'
    assert not s['stale']
    holiday = market_status('stocks','2026-07-02T20:00:00+00:00',datetime(2026,7,3,22,tzinfo=timezone.utc))
    assert not holiday['stale']
    c = market_status('crypto','2026-10-18T19:30:00+00:00',sunday)
    assert c['session'] == '24/7'
    assert not c['stale']
    assert market_status('crypto',friday,sunday)['stale']


def test_brasilia_time_validation():
    s = Settings()
    assert s.now().utcoffset().total_seconds() == -10800
    assert s.delivery_time == '20:30'
    with pytest.raises(ValueError):
        Settings(delivery_time='25:30')


def test_official_calendar_timezone_window():
    from radar.calendar import parse_calendar
    text='BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=US-Eastern:20261020T083000\nSUMMARY:Employment report\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20261220T120000Z\nSUMMARY:Outside window\nEND:VEVENT\nEND:VCALENDAR'
    rows=parse_calendar(text,datetime(2026,10,18,tzinfo=timezone.utc))
    assert len(rows)==1
    assert rows[0]['published_at']=='2026-10-20T12:30:00+00:00'


def test_news_dedup_urls_and_titles():
    rows = [{'title':'Taxas de juros caem!','url':'https://example.com/news?utm_source=x'},
            {'title':'Outra manchete','url':'https://example.com/news'},
            {'title':'Taxas de juros caem','url':'https://example.com/different'},
            {'title':'Injeção','url':'http://127.0.0.1/secrets'}]
    assert len(dedupe(rows)) == 1


@pytest.mark.parametrize('url', ['http://example.com','https://127.0.0.1/x','https://localhost/x','https://user:pass@example.com','https://example.com:123','https://[::1]/x'])
def test_invalid_source_urls(url):
    assert not safe_url(url)


def test_no_buy_without_fundamentals_and_research():
    wl = Watchlist.load('config/watchlist.yaml')
    r = score_asset({'category':'stocks','technical':{'sma200':100,'rsi14':20,'macd_histogram':1},'quote':{'price':101},'market':{'stale':False}},wl.weights)
    assert r['decision'] == 'AGUARDAR'
    assert r['coverage'] == .1
    assert r['score'] < 10
    assert len(r['blockers']) >= 3


def test_report_history_and_comparison(tmp_path):
    db = Store(tmp_path/'state.db')
    a = {'symbol':'EME','ranking':{'decision':'AGUARDAR','score':50},'quote':{'price':100}}
    old = {'day':'2026-10-17','status':'parcial','assets':[a]}
    db.save_report(old['day'],old)
    assert db.previous('2026-10-18') == old
    new = {**a,'quote':{'price':110},'ranking':{'decision':'COMPRAR PARCIALMENTE','score':80}}
    changes,_ = compare([new],old)
    assert changes[0]['price_change'] == pytest.approx(.1)
    assert changes[0]['score_change'] == 30


def test_budget_reservation_and_cache(tmp_path):
    db = Store(tmp_path/'state.db')
    db.reserve('day','r1',.8,1)
    with pytest.raises(RuntimeError): db.reserve('day','r2',.3,1)
    db.settle('r1',.1,{})
    db.reserve('day','r2',.3,1)
    assert db.cost('day') == pytest.approx((.1,.3))
    db.cache('x',{'value':1},-1)
    assert db.cached('x') is None
    db.cache('x',{'value':2},60)
    assert db.cached('x')['value'] == 2


def test_comparison_common_dates_and_fx():
    rows = [{'date':f'2026-01-{i:02}','adjusted_close':100+i} for i in range(1,29)]
    fx = [{'date':r['date'],'adjusted_close':5} for r in rows]
    assets = [{'symbol':'VOO','category':'us_etfs','history':rows,'quote':{'currency':'USD'}},
              {'symbol':'IVVB11','category':'br_etfs','history':[dict(r,adjusted_close=r['adjusted_close']*5) for r in rows],'quote':{'currency':'BRL'}}]
    c = compare_etfs(assets,fx)
    assert c['total_returns']['VOO'] == pytest.approx(c['total_returns']['IVVB11'])
    assert c['currency'] == 'USD'
