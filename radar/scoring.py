from __future__ import annotations

from datetime import datetime

from .fundamentals import number
from .http import safe_url

METHODOLOGY = "premium-2.0"
INCONCLUSIVE = "ANÁLISE INCONCLUSIVA — DADOS INSUFICIENTES"


def recent_period(period, as_of, max_days=550):
    try:
        age=(datetime.fromisoformat(as_of.replace("Z","+00:00")).date()-datetime.fromisoformat(period).date()).days
        return 0 <= age <= max_days
    except (TypeError,ValueError,AttributeError):return False


def data_quality(a):
    m, t, q = (a.get(k, {}) for k in ("fundamentals", "technical", "quote"))
    source = a.get("fundamentals_source", {})
    checks = {
        "cotação com fonte, moeda e horário": bool(q.get("price") and q.get("as_of") and q.get("currency") and safe_url(q.get("source", ""))),
        "cotação atual para a sessão": bool(q) and not a.get("market", {}).get("stale", True),
        "histórico técnico suficiente": all(t.get(k) is not None for k in ("rsi14", "macd", "sma50", "sma200", "atr14")),
        "liquidez mensurada": (a.get("average_dollar_volume") or 0) >= 10_000_000,
    }
    critical = []
    if a["category"] == "stocks":
        for key in ("pe", "ev_ebitda", "fcf_yield", "revenue_growth", "operating_margin", "net_debt_ebitda"):
            checks[key] = m.get(key) is not None
        checks["fonte dos demonstrativos"] = safe_url(source.get("url", "")) and recent_period(source.get("period"),q.get("as_of"))
        critical = ["fonte dos demonstrativos", "fcf_yield", "net_debt_ebitda"]
    elif a["category"] in ("us_etfs", "br_etfs"):
        checks.update({"custos": m.get("expense_ratio") is not None,
                       "composição datada": bool(a.get("holdings", {}).get("top")) and bool(a.get("holdings", {}).get("period")),
                       "estratégia documentada": bool(a.get("etf_profile", {}).get("source")),
                       "patrimônio": m.get("fund_assets") is not None})
        critical = ["custos", "composição datada", "estratégia documentada"]
    else:
        c = a.get("crypto", {})
        for key in ("market_cap", "fully_diluted_valuation", "circulating_supply", "total_volume"):
            checks[key] = c.get(key) is not None
        # FDV and a language-model score do not verify unlocks, security or adoption.
        for key in ("tokenomics_verified", "adoption_verified", "security_verified"):
            proof = c.get(key, {})
            checks[key] = isinstance(proof, dict) and proof.get("checked") is True and safe_url(proof.get("source", "")) and bool(proof.get("as_of")) and bool(proof.get("quote"))
        critical = ["tokenomics_verified", "adoption_verified", "security_verified"]
    critical = ["cotação com fonte, moeda e horário", "cotação atual para a sessão"] + critical
    missing = [k for k, ok in checks.items() if not ok]
    return {"coverage": sum(bool(v) for v in checks.values()) / len(checks), "checks": checks, "missing": missing,
            "critical_missing": [k for k in critical if not checks[k]], "method": "Completude de requisitos do tipo de ativo; não mede atratividade."}


def clamp(x):
    return max(0, min(100, x))


def score_asset(asset, weights, thesis=None):
    kind = "etfs" if asset["category"] in ("us_etfs", "br_etfs") else "crypto" if asset["category"] == "crypto" else "stocks"
    m, t, q, v = (asset.get(k, {}) for k in ("fundamentals", "technical", "quote", "valuation"))
    parts = {}

    def put(key, score, reason):
        if score is not None:
            parts[key] = {"score": round(clamp(score), 2), "reason": reason, "type": "cálculo reproduzível"}

    if t.get("sma200") and t.get("rsi14") is not None:
        tech = 50 + (15 if q.get("price", 0) > t["sma200"] else -15) + (10 if t.get("macd_histogram", 0) > 0 else -10)
        tech -= 15 if t["rsi14"] > 75 else 0
        put("technical", tech, "50 ±15 preço vs MM200 ±10 MACD histograma; −15 RSI>75")
    if kind == "stocks":
        if v.get("available") and q.get("price"):
            fair = v["scenarios"][1]["fair_value"]
            put("valuation", 50 + (fair / q["price"] - 1) * 100, "50 + upside DCF base ×100; cenário, não certeza")
        quality = [clamp(m[k] / target * 70) for k, target in (("roe", 0.15), ("operating_margin", 0.15), ("roic", 0.12)) if m.get(k) is not None]
        if len(quality) >= 2:
            put("quality", sum(quality) / len(quality), "Média ROE/15%, margem operacional/15%, ROIC/12%, ×70; limites 0–100")
        if m.get("revenue_growth") is not None and m.get("earnings_growth") is not None:
            put("growth", 50 + 100 * (m["revenue_growth"] + m["earnings_growth"]) / 2, "50 + média crescimento receita e lucro ×100")
        if m.get("net_debt_ebitda") is not None and (m.get("ebitda") or 0) > 0:
            put("safety", 100 - 20 * max(0, m["net_debt_ebitda"]), "100 −20 × dívida líquida/EBITDA, caixa líquido limitado a 100")
    elif kind == "etfs":
        if m.get("expense_ratio") is not None:
            put("cost", 100 - m["expense_ratio"] * 10000, "100 − taxa anual em pontos-base; corte em zero")
        holdings = asset.get("holdings", {}).get("top", [])
        vals = [h["weight"] for h in holdings if h.get("weight") is not None]
        if len(vals) >= 5:
            put("diversification", 100 - sum(vals) * 100, "100 − concentração percentual nas dez maiores posições; não mede correlação")
        aum = m.get("fund_assets")
        if aum and aum > 0:
            put("liquidity", min(100, aum / 1e9 * 20), "Proxy por patrimônio: 20 pontos por US$/R$ bilhão; não substitui spread/volume")
    else:
        c = asset.get("crypto", {})
        cap, volume, fdv = (number(c.get(k)) for k in ("market_cap", "total_volume", "fully_diluted_valuation"))
        if cap and cap > 0 and volume is not None:
            put("liquidity", min(100, volume / cap * 1000), "Volume 24h/market cap ×1000; volume reportado pode conter distorções")
        if cap and fdv and fdv > 0:
            put("tokenomics", cap / fdv * 100, "Market cap/FDV ×100; não substitui auditoria de desbloqueios e concentração")
    w = weights[kind]
    quality = data_quality(asset)
    component_coverage = sum(w[k] for k in parts if k in w)
    minimum_weight=.5 if kind=="crypto" else .6
    sufficient = quality["coverage"] >= .8 and not quality["critical_missing"] and component_coverage >= minimum_weight
    score = 5 * round(sum(parts[k]["score"] * w[k] for k in parts if k in w) / component_coverage / 5) if sufficient else None
    premium = (thesis or {}).get("premium", {})
    evidence_ok = bool(premium.get("validated") and premium.get("review", {}).get("approved"))
    blockers = list(quality["critical_missing"])
    if not sufficient:
        blockers.append("Avaliação indisponível: cobertura objetiva insuficiente")
    if not evidence_ok:
        blockers.append("Tese aprofundada e revisão com evidências ainda não aprovadas")
    decision = INCONCLUSIVE
    if sufficient and evidence_ok:
        decision = "AGUARDAR"
        if score < 35:
            decision = "EVITAR"
        if score >= 75 and (kind != "stocks" or (v.get("available") and q["price"] <= v.get("entry_max", 0))) and not asset.get("value_traps"):
            decision = "COMPRAR PARCIALMENTE"
    for key, part in parts.items():
        part["inputs_source"] = asset.get("quote", {}).get("source") if key == "technical" else source_for(asset, kind)
    return {"decision": decision, "score": score, "coverage": round(quality["coverage"], 3), "data_quality": quality,
            "attractiveness": {"score": score, "available_weight": component_coverage, "missing_is_zero": False},
            "confidence": {"level": "média" if evidence_ok and sufficient else "baixa", "reason": "Evidências e revisão aprovadas" if evidence_ok else "Conclusão não sustentada por investigação aprovada"},
            "components": parts, "weights": w, "blockers": blockers, "methodology_version": METHODOLOGY,
            "method": "Qualidade dos dados separada de atratividade e confiança. Score indisponível se cobertura insuficiente; sem notas da IA. Soma normalizada dos critérios observados, arredondada a 5 pontos, sem falsa precisão."}


def source_for(asset, kind):
    if kind == "crypto":
        return asset.get("crypto", {}).get("source")
    return asset.get("fundamentals_source", {}).get("url")
