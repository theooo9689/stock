from __future__ import annotations

from .config import Watchlist
from .fundamentals import derive, value_range
from .scoring import score_asset


def demo_report(settings):
    wl = Watchlist.load(settings.config_path)
    assets = []
    for a in wl.instruments():
        a.update({"name": "EXEMPLO SINTÉTICO — " + a["symbol"], "retrieved_at": "DEMONSTRAÇÃO", "errors": ["DADOS FICTÍCIOS"],
                  "quote": {"price": 100.0, "currency": "USD", "as_of": "DEMONSTRAÇÃO", "source": "https://example.org/dados-ficticios"},
                  "technical": {"rsi14": 50.0, "sma200": 98.0, "macd_histogram": 0.2},
                  "market": {"stale": True, "session": "DEMONSTRAÇÃO"}, "fundamentals": {}, "history": []})
        a["ranking"] = score_asset(a, wl.weights)
        assets.append(a)
    return {"day": settings.now().date().isoformat(), "generated_at": settings.now().isoformat(), "status": "DEMONSTRAÇÃO", "demo": True,
            "assets": assets, "macro": [], "headlines": [], "research": {"summary": "DEMONSTRAÇÃO COM DADOS FICTÍCIOS. Este exemplo ilustra o formato e não apresenta oportunidades reais.", "summaries": [], "news": [], "risks": ["Dados sintéticos, sem valor analítico"], "events": [], "limitations": ["Não houve pesquisa real"], "sources": []},
            "limitations": ["TODOS OS DADOS SÃO SINTÉTICOS"], "etf_comparison": {"available": False}, "discovery": {"scope": "simulação"},
            "changes": [], "comparison_note": "Exemplo sem histórico", "cost": {"estimated_usd": 0}}
