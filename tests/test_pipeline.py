from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from radar.config import Settings
from radar.research import Research, ResearchUnavailable
from radar.storage import Store


def test_empty_api_credit_stops_research_and_releases_reservation(tmp_path):
    def reject(**kwargs):
        response=httpx.Response(429,request=httpx.Request('POST','https://api.openai.com/v1/responses'))
        raise RateLimitError('quota',response=response,body={'code':'credit_balance_exhausted','type':'insufficient_quota'})
    store=Store(tmp_path/'state.db')
    researcher=Research(Settings(data_dir=tmp_path),store,SimpleNamespace(responses=SimpleNamespace(create=reject)))
    with pytest.raises(ResearchUnavailable,match='sem saldo'):
        researcher.run('2026-10-18',{},[],'macro')
    assert store.cost('2026-10-18') == (0,0)


def test_watchlist_hype_uses_verified_market_symbol():
    from radar.config import Watchlist
    wl=Watchlist.load('config/watchlist.yaml')
    assert wl.market_symbols['HYPE']=='HYPE32196-USD'


def test_technical_good_signal_does_not_override_missing_valuation():
    from radar.scoring import score_asset
    from radar.config import Watchlist
    wl=Watchlist.load('config/watchlist.yaml')
    asset={'category':'stocks','quote':{'price':50},'market':{'stale':False},'technical':{'sma200':40,'rsi14':40,'macd_histogram':1},
           'fundamentals':{'roe':.4,'roic':.4,'operating_margin':.5,'revenue_growth':.5,'earnings_growth':.5,'ebitda':100,'net_debt_ebitda':0},
           'valuation':{'available':False}}
    thesis={'facts':[{'fact':'verified'}],'assessments':[{'criterion':'macro','score':100,'reason':'context','sources':['https://example.com']}], 'missing':[]}
    ranking=score_asset(asset,wl.weights,thesis)
    assert ranking['decision']=='AGUARDAR'
    assert 'Valor justo não sustentado pelos dados' in ranking['blockers']
