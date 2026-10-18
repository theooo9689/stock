from __future__ import annotations

from .fundamentals import number


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
    if thesis:
        for a in thesis.get("assessments", []):
            if a["criterion"] in weights[kind] and a["criterion"] not in parts and a.get("sources"):
                parts[a["criterion"]] = {"score": a["score"], "reason": a["reason"], "sources": a["sources"], "type": "julgamento qualitativo da pesquisa"}
    w = weights[kind]
    coverage = sum(w[k] for k in parts if k in w)
    score = sum(parts[k]["score"] * w[k] for k in parts if k in w)  # missing is zero, never renormalized
    blockers = []
    if coverage < 0.85:
        blockers.append(f"Cobertura de critérios de apenas {coverage:.0%}")
    if not q or asset.get("market", {}).get("stale", True):
        blockers.append("Cotação ausente/desatualizada ou calendário não validado")
    if not thesis or not thesis.get("facts"):
        blockers.append("Pesquisa com fontes ainda insuficiente")
    if kind == "stocks" and not v.get("available"):
        blockers.append("Valor justo não sustentado pelos dados")
    if kind == "crypto" and (not thesis or thesis.get("missing")):
        blockers.append("Lacunas na investigação de cripto")
    traps = asset.get("value_traps", [])
    if len(traps) >= 2:
        blockers.append("Possível armadilha de valor: " + "; ".join(traps))
    decision = "AGUARDAR"
    if coverage >= 0.85 and score < 35 and q and thesis:
        decision = "EVITAR"
    if score >= 72 and not blockers and (kind != "stocks" or q["price"] <= v.get("entry_max", 0)):
        decision = "COMPRAR PARCIALMENTE"
    return {"decision": decision, "score": round(score, 2), "coverage": round(coverage, 3), "components": parts,
            "weights": w, "blockers": blockers, "method": "Soma ponderada sem reescalar dados ausentes. Compra exige >=72, cobertura >=85%, cotação válida e fontes; ações também margem de segurança. Evitar <35 com cobertura >=85%. Não são probabilidades de retorno."}
