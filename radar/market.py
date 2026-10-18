from __future__ import annotations

import concurrent.futures
import logging
from datetime import datetime, timedelta, timezone

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf

from .fundamentals import derive, number, value_range, value_traps
from .http import APIError
from .technical import indicators, returns

MACRO = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Russell 2000": "^RUT", "VIX": "^VIX",
         "Treasury 10 anos (%)": "^TNX", "USD/BRL": "BRL=X", "Dólar DXY": "DX-Y.NYB", "Ouro futuro (USD)": "GC=F", "Petróleo WTI futuro (USD)": "CL=F"}
MACRO_UNITS = {"^GSPC": "pontos", "^IXIC": "pontos", "^RUT": "pontos", "^VIX": "pontos",
               "^TNX": "% ao ano", "BRL=X": "BRL por USD", "DX-Y.NYB": "pontos",
               "GC=F": "USD por onça troy", "CL=F": "USD por barril"}


def market_status(category, quote_time, now=None):
    now = now or datetime.now(timezone.utc)
    if category == "crypto":
        age = (now - datetime.fromisoformat(quote_time)).total_seconds() / 3600 if quote_time else 999
        return {"session": "24/7", "stale": age > 3, "quote_age_hours": round(age, 2)}
    name = "BVMF" if category == "br_etfs" else "XNYS"
    try:
        cal = xcals.get_calendar(name)
        day = pd.Timestamp(now.date())
        opened = bool(cal.is_open_on_minute(pd.Timestamp(now).floor("min")))
        last_session = cal.date_to_session(day, direction="previous")
        if cal.session_close(last_session).to_pydatetime() > now:
            last_session = cal.previous_session(last_session)
        expected_close = cal.session_close(last_session).to_pydatetime()
        quote = datetime.fromisoformat(quote_time) if quote_time else datetime.min.replace(tzinfo=timezone.utc)
        return {"session": "aberta" if opened else "fechada", "calendar": name,
                "expected_last_close": expected_close.isoformat(), "stale": quote < expected_close - timedelta(hours=8)}
    except Exception:
        return {"session": "calendário indisponível", "stale": True}


class Market:
    def __init__(self, http, settings, watchlist):
        self.http, self.settings, self.watchlist = http, settings, watchlist
        yf.set_tz_cache_location(str(settings.data_dir / "yahoo-cache"))
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    def history(self, ticker):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        raw = self.http.get(url, {"range": "2y", "interval": "1d", "events": "div,splits"}, ttl=1800)
        results = raw.get("chart", {}).get("result")
        if not results:
            raise APIError("Histórico ausente")
        data = results[0]
        q = data["indicators"]["quote"][0]
        frame = pd.DataFrame(q, index=pd.to_datetime(data["timestamp"], unit="s", utc=True))
        adj = data["indicators"].get("adjclose", [{}])[0].get("adjclose")
        frame["adjclose"] = adj if adj else frame["close"]
        frame = frame.dropna(subset=["close", "high", "low"])
        # Remove today's provisional daily candle while its session is in progress.
        meta = data.get("meta", {})
        end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end")
        if end and datetime.now(timezone.utc).timestamp() < end and len(frame):
            if frame.index[-1].date() == datetime.now(timezone.utc).date():
                frame = frame.iloc[:-1]
        if frame.empty:
            raise APIError("Nenhum candle completo")
        return frame, meta, url

    def statements(self, ticker):
        cached = self.http.store.cached("fundamentals:v2:" + ticker)
        if cached is not None:
            return cached
        t = yf.Ticker(ticker)
        try:
            info = t.info or {}
        except Exception:
            info = {}
        out = {}
        if ticker.endswith(".SA") or info.get("quoteType") == "ETF":
            result = {"info": info, "statements": out}
            self.http.store.cache("fundamentals:v2:" + ticker, result, 21600)
            return result
        try:
            income, balance, cash = t.income_stmt, t.balance_sheet, t.cashflow
            annual = []
            for period in list(income.columns)[:5]:
                annual.append({"period": str(period.date()), "revenue": number(income.loc["Total Revenue", period]) if "Total Revenue" in income.index else None,
                               "eps": number(income.loc["Diluted EPS", period]) if "Diluted EPS" in income.index else None})
            out["annual_history"] = annual
            for metric in ("revenue", "eps"):
                valid = [r for r in annual if r[metric] is not None]
                if len(valid) >= 3 and valid[-1][metric] > 0 and valid[0][metric] > 0:
                    years = (pd.Timestamp(valid[0]["period"]) - pd.Timestamp(valid[-1]["period"])).days / 365.25
                    if years > 0:
                        out[metric + "_cagr"] = (valid[0][metric] / valid[-1][metric]) ** (1 / years) - 1

            def latest(frame, keys):
                for k in keys:
                    if k in frame.index:
                        return number(frame.loc[k].iloc[0])
                return None

            for key, frame, names in [
                ("ebit", income, ["EBIT", "Operating Income"]), ("interest_expense", income, ["Interest Expense"]),
                ("equity", balance, ["Stockholders Equity", "Total Equity Gross Minority Interest"]),
                ("short_term_debt", balance, ["Current Debt And Capital Lease Obligation", "Current Debt"]),
            ]:
                out[key] = latest(frame, names)
            tax, pretax = latest(income, ["Tax Provision"]), latest(income, ["Pretax Income"])
            out["effective_tax_rate"] = max(0, min(0.5, tax / pretax)) if tax is not None and pretax and pretax > 0 else None
            if "Free Cash Flow" in cash.index:
                vals = cash.loc["Free Cash Flow"].dropna()
                out["positive_fcf_years"] = int((vals > 0).sum())
                out["median_annual_fcf"] = number(vals.median())
                if len(vals) >= 2 and vals.iloc[1] > 0:
                    out["fcf_growth"] = number(vals.iloc[0] / vals.iloc[1] - 1)
            for key, frame, row in [("dilution", balance, "Ordinary Shares Number"), ("revenue_annual_growth", income, "Total Revenue")]:
                if row in frame.index:
                    vals = frame.loc[row].dropna()
                    if len(vals) >= 2 and vals.iloc[1] > 0:
                        out[key] = number(vals.iloc[0] / vals.iloc[1] - 1)
            if len(income.columns):
                out["financial_period"] = str(income.columns[0].date())
        except Exception:
            out["statements_missing"] = True
        # Optional licensed fallback, with a cache key that excludes credentials.
        if not info.get("marketCap") and self.settings.fmp_key.get_secret_value():
            try:
                quotes = self.http.get("https://financialmodelingprep.com/stable/quote",
                                       {"symbol": ticker, "apikey": self.settings.fmp_key.get_secret_value()},
                                       cache_key="fmp:quote:" + ticker)
                if quotes:
                    info.update({"marketCap": quotes[0].get("marketCap"), "currentPrice": quotes[0].get("price")})
            except APIError:
                pass
        result = {"info": info, "statements": out}
        # Yahoo occasionally returns non-JSON native values. Normalize before persistence.
        import json
        result = json.loads(json.dumps(result, default=str))
        self.http.store.cache("fundamentals:v2:" + ticker, result, 21600 if info else 300)
        return result

    def collect(self, asset):
        result = dict(asset)
        symbol, kind = asset["symbol"], asset["category"]
        ticker = symbol + ".SA" if kind == "br_etfs" else symbol + "-USD" if kind == "crypto" else symbol
        ticker = self.watchlist.market_symbols.get(symbol, ticker)
        result.update({"ticker": ticker, "retrieved_at": datetime.now(timezone.utc).isoformat(), "errors": []})
        try:
            frame, meta, url = self.history(ticker)
            timestamp = meta.get("regularMarketTime")
            result["quote"] = {
                "price": number(meta.get("regularMarketPrice")) or float(frame.close.iloc[-1]),
                "currency": meta.get("currency", "USD"),
                "as_of": datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else str(frame.index[-1]),
                "source": url, "unit": "moeda por unidade do ativo",
            }
            result["market"] = market_status(kind, result["quote"]["as_of"])
            result["technical"] = indicators(frame, crypto=kind == "crypto")
            result["technical_as_of"] = frame.index[-1].isoformat()
            result["returns"] = returns(frame)
            result["change_last_session"] = number(frame.close.iloc[-1] / frame.close.iloc[-2] - 1) if len(frame) > 1 else None
            result["average_dollar_volume"] = number((frame.close * frame.volume).tail(20).mean())
            result["history"] = [{"date": str(i.date()), "adjusted_close": number(r.adjclose)} for i, r in frame.iterrows()]
            result["name"] = meta.get("longName", meta.get("shortName", symbol))
        except Exception as exc:
            result["errors"].append(f"Histórico/preço indisponível ({type(exc).__name__})")
        if kind != "crypto":
            try:
                data = self.statements(ticker)
                info = data["info"]
                result["fundamentals"] = derive(info, data["statements"])
                result["financial_history"] = data["statements"].get("annual_history", [])
                result["fundamentals_source"] = {"url": f"https://finance.yahoo.com/quote/{ticker}/financials/",
                                                   "retrieved_at": result["retrieved_at"], "period": data["statements"].get("financial_period"),
                                                   "currency": info.get("financialCurrency", info.get("currency")),
                                                   "units": "Ratios em fração/vezes; valores monetários na moeda dos demonstrativos; totalDebt inclui arrendamentos conforme provedor."}
                result["sector"] = info.get("sector")
                result["industry"] = info.get("industry")
                result["business"] = {"description": info.get("longBusinessSummary"), "website": info.get("website"), "sector": info.get("sector"), "industry": info.get("industry")}
                if kind == "stocks":
                    result["valuation"] = value_range(result["fundamentals"], self.watchlist.valuation)
                    if info.get("sector") in ("Financial Services", "Real Estate"):
                        result["valuation"] = {"available": False, "reason": "DCF genérico de FCF inadequado para bancos, seguradoras e imóveis/REITs; exige modelo setorial (dividendos, capital regulatório ou NAV/AFFO)."}
                    # Avoid comparing monetary values from different currencies.
                    if info.get("financialCurrency") and info.get("financialCurrency") != result.get("quote", {}).get("currency"):
                        result["valuation"] = {"available": False, "reason": "Moedas dos demonstrativos e da cotação diferentes; conversão precisa ser auditada"}
                    result["value_traps"] = value_traps(result["fundamentals"])
                else:
                    result["holdings"] = self.etf_holdings(ticker)
            except Exception as exc:
                result["errors"].append(f"Fundamentos indisponíveis ({type(exc).__name__})")
        return result

    def etf_holdings(self, ticker):
        key = "holdings:" + ticker
        cached = self.http.store.cached(key)
        if cached is not None:
            return cached
        try:
            funds = yf.Ticker(ticker).funds_data
            h = funds.top_holdings
            holdings = [{"symbol": str(i), "weight": number(r.get("Holding Percent"))} for i, r in h.iterrows()]
            result = {"top": holdings, "sectors": funds.sector_weightings, "source": f"https://finance.yahoo.com/quote/{ticker}/holdings/", "as_of": datetime.now(timezone.utc).isoformat(), "period": None, "date_note": "Data de coleta; data efetiva da composição não fornecida pelo endpoint."}
        except Exception:
            result = {"top": [], "sectors": {}, "missing": True}
        self.http.store.cache(key, result, 86400)
        return result

    def collect_many(self, assets):
        # Keep concurrency low to respect public provider limits.
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            return list(pool.map(self.collect, assets))

    def discover(self):
        cfg, known, selected, coverage = self.watchlist.discovery, {a["symbol"] for a in self.watchlist.instruments()}, {}, []
        if not cfg.get("enabled"):
            return [], {"disabled": True}
        for screen in cfg["screeners"]:
            try:
                d = self.http.get("https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved", {"scrIds": screen, "count": 100}, ttl=21600)
                r = d.get("finance", {}).get("result") or []
                quotes = r[0].get("quotes", []) if r else []
                coverage.append({"screen": screen, "returned": len(quotes), "total_in_screen": r[0].get("total") if r else None})
                for q in quotes:
                    symbol = q.get("symbol", "")
                    if not symbol or symbol in known or any(ch in symbol for ch in ("^", "=", "/")) or "." in symbol:
                        continue
                    if (q.get("regularMarketPrice") or 0) * (q.get("averageDailyVolume3Month") or 0) < cfg["min_dollar_volume"]:
                        continue
                    category = "us_etfs" if q.get("quoteType") == "ETF" else "stocks"
                    if category == "stocks" and (q.get("marketCap") or 0) < cfg["min_market_cap"]:
                        continue
                    selected[symbol] = {"symbol": symbol, "category": category, "watchlist": False, "screen": screen, "sector": q.get("sector")}
            except Exception as exc:
                coverage.append({"screen": screen, "error": type(exc).__name__})
        # Round-robin across sectors/screens rather than taking one sector's first 15.
        groups = {}
        for a in selected.values():
            groups.setdefault(a.get("sector") or a["screen"], []).append(a)
        candidates = []
        while groups and len(candidates) < cfg["max_candidates"]:
            for key in list(groups):
                candidates.append(groups[key].pop(0))
                if not groups[key]:
                    del groups[key]
                if len(candidates) >= cfg["max_candidates"]:
                    break
        return candidates, {"screens": coverage, "eligible_unique": len(selected), "investigated": len(candidates),
                            "scope": "Até 100 resultados por screener público Yahoo; amostra de ações e ETFs líquidos, sem cobertura integral do mercado."}

    def macro(self):
        rows = []
        for name, ticker in MACRO.items():
            try:
                frame, meta, url = self.history(ticker)
                rows.append({"name": name, "ticker": ticker, "price": meta.get("regularMarketPrice"), "currency": meta.get("currency"), "unit": MACRO_UNITS.get(ticker),
                             "as_of": datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).isoformat(),
                             "change_last_session": number(frame.close.iloc[-1] / frame.close.iloc[-2] - 1), "source": url})
            except Exception as exc:
                rows.append({"name": name, "error": type(exc).__name__})
        return rows


def compare_etfs(assets, fx_history):
    """Same dates/currency/distribution treatment; comparison only, not a selection rule."""
    series = {}
    fx = pd.Series({r["date"]: r["adjusted_close"] for r in fx_history})
    for a in assets:
        if a["category"] not in ("us_etfs", "br_etfs") or not a.get("history"):
            continue
        s = pd.Series({r["date"]: r["adjusted_close"] for r in a["history"]})
        if a.get("quote", {}).get("currency") == "BRL":
            s = s / fx.reindex(s.index).ffill(limit=5)
        elif a.get("quote", {}).get("currency") != "USD":
            continue
        series[a["symbol"]] = s
    if not series:
        return {"available": False}
    common = pd.DataFrame(series).dropna()
    if len(common) < 20:
        return {"available": False, "reason": "Período comum insuficiente"}
    from .etf_research import compare_series, overlaps
    result = (common.iloc[-1] / common.iloc[0] - 1).to_dict()
    return {"available": True, "currency": "USD", "start": str(common.index[0]), "end": str(common.index[-1]),
            "observations": len(common), "total_returns": result, "risk":compare_series(common),
            "overlaps": overlaps([a for a in assets if a["symbol"] in series]),
            "method": "Fechamentos ajustados Yahoo, mesmas datas, dividendos reinvestidos conforme ajustes do provedor; B3 convertido por USD/BRL nas mesmas datas. Taxas internas já refletidas nas cotas; impostos, corretagem e spread excluídos. Checar ajustes em eventos corporativos."}
