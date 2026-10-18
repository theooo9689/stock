from __future__ import annotations

import math


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def ratio(a, b):
    a, b = number(a), number(b)
    return a / b if a is not None and b not in (None, 0) else None


def derive(info, statements=None):
    s = statements or {}
    keys = {
        "pe": "trailingPE", "forward_pe": "forwardPE", "ev_ebitda": "enterpriseToEbitda",
        "price_book": "priceToBook", "roe": "returnOnEquity", "roa": "returnOnAssets",
        "gross_margin": "grossMargins", "operating_margin": "operatingMargins", "net_margin": "profitMargins",
        "revenue_growth": "revenueGrowth", "earnings_growth": "earningsGrowth",
        "market_cap": "marketCap", "enterprise_value": "enterpriseValue", "cash": "totalCash",
        "debt": "totalDebt", "revenue": "totalRevenue", "ebitda": "ebitda",
        "eps": "trailingEps", "forward_eps": "forwardEps", "shares": "sharesOutstanding",
        "payout_ratio": "payoutRatio", "current_ratio": "currentRatio", "fcf": "freeCashflow",
        "target_mean_price": "targetMeanPrice", "analyst_count": "numberOfAnalystOpinions",
        "expense_ratio": "annualReportExpenseRatio", "fund_assets": "totalAssets",
    }
    out = {k: number(info.get(v)) for k, v in keys.items()}
    # Yahoo's dividendYield is percent; trailingAnnualDividendYield is a fraction.
    out["dividend_yield"] = number(info.get("trailingAnnualDividendYield"))
    if out["dividend_yield"] is None and number(info.get("dividendYield")) is not None:
        out["dividend_yield"] = float(info["dividendYield"]) / 100
    out.update({k: number(v) for k, v in s.items()})
    out["price_fcf"] = ratio(out["market_cap"], out["fcf"])
    out["fcf_yield"] = ratio(out["fcf"], out["market_cap"])
    out["net_debt_ebitda"] = ratio(out["debt"] - out["cash"], out["ebitda"]) if out["debt"] is not None and out["cash"] is not None else None
    out["ev_ebit"] = ratio(out["enterprise_value"], out.get("ebit"))
    out["interest_coverage"] = ratio(out.get("ebit"), abs(out["interest_expense"])) if out.get("interest_expense") is not None else None
    # Approximation: NOPAT / end-of-period invested capital; explicitly labelled.
    if all(out.get(k) is not None for k in ("ebit", "equity", "debt", "cash")):
        tax = out.get("effective_tax_rate")
        out["roic"] = ratio(out["ebit"] * (1 - (tax if tax is not None else 0.25)), out["equity"] + out["debt"] - out["cash"])
        out["roic_method"] = "NOPAT/capital investido de fim de período; alíquota efetiva, ou hipótese de 25%; não é ROIC médio"
    else:
        out["roic"] = None
    return out


def dcf_equity(fcf, shares, growth, discount, terminal=0.025, years=5):
    """Equity cash-flow scenario; FCF levered. Do not subtract net debt twice."""
    if fcf is None or shares is None or fcf <= 0 or shares <= 0 or discount <= terminal:
        return None
    pv = sum(fcf * (1 + growth) ** year / (1 + discount) ** year for year in range(1, years + 1))
    future = fcf * (1 + growth) ** years * (1 + terminal) / (discount - terminal)
    return (pv + future / (1 + discount) ** years) / shares


def value_range(metrics, cfg):
    fcf, shares = metrics.get("fcf"), metrics.get("shares")
    # A single FCF observation is not sufficient to claim normalized fair value.
    positive_years = metrics.get("positive_fcf_years", 0) or 0
    if positive_years < 3 or not fcf or fcf <= 0 or not shares:
        return {"available": False, "reason": "DCF exige FCF positivo e ao menos três anos positivos; não há dados suficientes ou negócio tem FCF negativo."}
    normalized_fcf = min(fcf, metrics.get("median_annual_fcf") or fcf)
    scenarios = []
    for name, growth, discount in zip(("pessimista", "base", "otimista"), cfg["growth_rates"], cfg["discount_rates"]):
        value = dcf_equity(normalized_fcf, shares, growth, discount, cfg["terminal_growth"])
        if value is None:
            return {"available": False, "reason": "Premissas de DCF inválidas"}
        scenarios.append({"scenario": name, "growth": growth, "discount": discount, "fair_value": value})
    sensitivity = [{"growth": g, "discount": d, "value": dcf_equity(normalized_fcf, shares, g, d, cfg["terminal_growth"])}
                   for g in cfg["growth_rates"] for d in cfg["discount_rates"]]
    eps = metrics.get("eps")
    multiples = [{"pe_assumed": pe, "value": eps * pe} for pe in cfg["normalized_pe"]] if eps and eps > 0 else []
    return {"available": True, "scenarios": scenarios, "sensitivity": sensitivity,
            "normalized_multiple_scenarios": multiples,
            "entry_max": scenarios[1]["fair_value"] * (1 - cfg["margin_of_safety"]),
            "fcf_used": normalized_fcf, "terminal_growth": cfg["terminal_growth"],
            "method": "DCF de FCF ao acionista: menor entre FCF recente e mediana anual. Hipóteses configuráveis, não estimativas de consenso. Múltiplos 12/18/24 são cenários ilustrativos, não média de pares. FCF de Yahoo pode divergir de FCFE econômico."}


def value_traps(m):
    risks = []
    for key, threshold, message in [
        ("revenue_growth", 0, "Receita em contração"), ("earnings_growth", 0, "Lucro em contração"),
        ("fcf", 0, "Fluxo de caixa livre negativo"), ("operating_margin", 0, "Margem operacional negativa"),
    ]:
        if m.get(key) is not None and m[key] < threshold:
            risks.append(message)
    if m.get("net_debt_ebitda") is not None and m["net_debt_ebitda"] > 3:
        risks.append("Dívida líquida/EBITDA superior a 3×")
    if m.get("interest_coverage") is not None and m["interest_coverage"] < 2:
        risks.append("Cobertura de juros inferior a 2×")
    if m.get("payout_ratio") is not None and m["payout_ratio"] > 1:
        risks.append("Payout superior ao lucro; investigar sustentabilidade")
    return risks
