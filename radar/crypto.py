from __future__ import annotations

from datetime import datetime, timezone


class Crypto:
    def __init__(self, http):
        self.http = http

    def discover(self, known, count=3):
        if count <= 0:
            return [], {"disabled": True, "investigated": 0}
        try:
            rows = self.http.get("https://api.coingecko.com/api/v3/coins/markets",
                                 {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100, "page": 1}, ttl=21600)
            excluded = {"tether", "usd-coin", "dai", "usds", "ethena-usde", "usdd", "paypal-usd", "first-digital-usd", "true-usd", "pax-dollar", "usd1", "usual-usd", "falcon-usd", "ripple-usd", "ethena-staked-usde"}
            out = []
            for r in rows:
                symbol = r["symbol"].upper()
                if not symbol.isalnum():
                    continue
                if symbol in known or r["id"] in excluded or any(x in r["name"].lower() for x in ("wrapped", "staked", "bridged", "usd", "bitcoin", "ethereum")):
                    continue
                if (r.get("market_cap") or 0) < 1e9 or (r.get("total_volume") or 0) < 1e7:
                    continue
                out.append({"symbol": symbol, "category": "crypto", "watchlist": False, "coin_id": r["id"], "screen": "CoinGecko: top 100 market cap, volume>USD10M; exclui stablecoins/wrapped conhecidos"})
                if len(out) >= count:
                    break
            return out, {"returned": len(rows), "investigated": len(out), "scope": "Amostra top100 CoinGecko; exclusões heurísticas de stablecoins e ativos duplicados. Não é mercado completo."}
        except Exception as exc:
            return [], {"error": type(exc).__name__, "investigated": 0}

    def enrich(self, assets, ids):
        crypto = [a for a in assets if a["category"] == "crypto"]
        ids = {**ids, **{a["symbol"]: a["coin_id"] for a in crypto if a.get("coin_id")}}
        try:
            rows = self.http.get("https://api.coingecko.com/api/v3/coins/markets",
                                 {"vs_currency": "usd", "ids": ",".join(ids.values()), "price_change_percentage": "7d,30d"}, ttl=900)
            by_id = {r["id"]: r for r in rows}
        except Exception:
            by_id = {}
        for a in crypto:
            row = by_id.get(ids.get(a["symbol"]), {})
            a["crypto"] = {k: row.get(k) for k in (
                "market_cap", "fully_diluted_valuation", "circulating_supply", "total_supply", "max_supply",
                "total_volume", "price_change_percentage_24h", "price_change_percentage_7d_in_currency",
                "price_change_percentage_30d_in_currency", "last_updated")}
            a["crypto"]["source"] = "https://www.coingecko.com/en/coins/" + ids.get(a["symbol"], "")
            a["crypto"]["retrieved_at"] = datetime.now(timezone.utc).isoformat()
            if row.get("last_updated"):
                a["crypto"]["coingecko_quote"] = {"price": row.get("current_price"), "currency": "USD", "as_of": row["last_updated"]}
                if not a.get("quote") and row.get("current_price") is not None:
                    from .market import market_status
                    a["quote"] = {"price": row["current_price"], "currency": "USD", "as_of": row["last_updated"], "source": a["crypto"]["source"], "unit": "USD por token"}
                    a["market"] = market_status("crypto", row["last_updated"].replace("Z", "+00:00"))
            if not row:
                a["errors"].append("CoinGecko indisponível: market cap, FDV e oferta não verificados")
            # Derivatives: public Binance futures are a venue sample, not the whole market.
            try:
                funding = self.http.get("https://fapi.binance.com/fapi/v1/premiumIndex", {"symbol": a["symbol"] + "USDT"}, ttl=900)
                oi = self.http.get("https://fapi.binance.com/fapi/v1/openInterest", {"symbol": a["symbol"] + "USDT"}, ttl=900)
                a["crypto"]["derivatives"] = {"funding_rate": float(funding["lastFundingRate"]), "open_interest_contracts": float(oi["openInterest"]),
                                                "as_of_ms": oi.get("time"), "venue": "Binance USD-M, amostra de uma única bolsa", "source": "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest"}
            except Exception:
                a["crypto"]["derivatives"] = {"missing": True}
            a["crypto"]["unverified"] = ["concentração de detentores", "emissão e desbloqueios futuros", "liquidações agregadas", "fluxos de ETF spot", "TVL/receita atribuível ao token"]
        return assets
