from __future__ import annotations

import fcntl
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import Watchlist
from .calendar import official_events
from .crypto import Crypto
from .http import HTTP
from .market import Market, compare_etfs
from .news import collect_news
from .report import generate, summaries
from .research import Research, ResearchUnavailable, compact_asset
from .scoring import score_asset
from .storage import Store, BudgetExceeded
from .telegram import Telegram

log = logging.getLogger("radar")


@contextmanager
def run_lock(path):
    with open(path, "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Já existe uma execução em andamento") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def compare(assets, previous):
    if not previous:
        return [], "Primeiro relatório: não há histórico anterior para comparar."
    lookup = {a["symbol"]: a for a in previous["assets"]}
    changes = []
    for a in assets:
        old = lookup.get(a["symbol"])
        if not old:
            continue
        before, after = old["ranking"]["decision"], a["ranking"]["decision"]
        p0, p1 = old.get("quote", {}).get("price"), a.get("quote", {}).get("price")
        old_facts = {f["fact"] for f in old.get("thesis", {}).get("facts", [])}
        new = [f["fact"] for f in a.get("thesis", {}).get("facts", []) if f["fact"] not in old_facts]
        changes.append({"symbol": a["symbol"], "before": before, "after": after,
                        "previous_price": p0, "current_price": p1, "price_change": p1/p0-1 if p0 and p1 else None,
                        "score_change": a["ranking"]["score"]-old["ranking"]["score"], "new_facts": new})
    return changes, f"Comparação com {previous['day']}; mudanças de pontuação podem refletir cobertura e pesquisa, além de mercado."


def collect(settings, store, *, ai=True):
    wl = Watchlist.load(settings.config_path)
    http = HTTP(store)
    market = Market(http, settings, wl)
    day = settings.now().date().isoformat()
    candidates, discovery = market.discover()
    crypto_candidates, crypto_discovery = Crypto(http).discover(set(wl.assets["crypto"]), wl.discovery.get("crypto_candidates", 3))
    discovery["crypto"] = crypto_discovery
    log.info("Coletando %s ativos da watchlist e %s candidatos", len(wl.instruments()), len(candidates))
    assets = market.collect_many(wl.instruments() + candidates + crypto_candidates)
    Crypto(http).enrich(assets, wl.assets["crypto"])
    macro = market.macro()
    news, news_errors = collect_news(http, wl.news_feeds)
    calendar_events, calendar_errors = official_events(http)
    limitations = [f"Feed indisponível: {e['feed']} ({e['error']})" for e in news_errors]
    limitations.extend(calendar_errors)
    research = {"summary": "", "summaries": [], "news": [], "events": [], "risks": [], "limitations": [], "sources": []}
    theses = {}
    if ai and settings.openai_key.get_secret_value():
        researcher = Research(settings, store)
        batches = [(None, {"macro": macro, "headlines": news, "official_events": calendar_events}, [], "Panorama macro do dia, até cinco notícias financeiras PRIORITÁRIAS com impactos materiais; excluir matérias gerais de saúde animal/esportes sem impacto demonstrado. Não preencher cinco notícias se não houver material relevante. Agenda confirmada dos próximos sete dias, preferencialmente fontes oficiais. Não produzir teses de ativos nesta etapa.")]
        for i in range(0, len(assets), 5):
            batch = assets[i:i+5]
            batches.append((i, {"assets": [compact_asset(a) for a in batch], "macro": macro, "headlines": news[:30]},
                            [a["symbol"] for a in batch], "Investigue cada símbolo obrigatório, fontes primárias e notícias específicas recentes. Compare ETFs e investigue armadilhas de valor. Produza todas as teses, com lacunas explícitas e assessments auditáveis."))
        for i, data, symbols, task in batches:
            try:
                log.info("Pesquisa com fontes: %s", "macro" if i is None else ", ".join(symbols))
                answer = researcher.run(day, data, symbols, task)
                result = answer["result"]
                research["summaries"].append(result["summary"])
                for key in ("news", "events", "risks", "limitations"):
                    research[key].extend(result[key])
                research["sources"].extend(answer["sources"])
                theses.update({t["symbol"]: t for t in result["theses"] if t["symbol"] in symbols})
            except (ResearchUnavailable, BudgetExceeded) as exc:
                limitations.append(str(exc))
                log.warning("Pesquisa indisponível: %s", str(exc))
                break
            except Exception as exc:
                limitations.append(f"Pesquisa {'macro' if i is None else ','.join(symbols)} não concluída ({type(exc).__name__}); reserva de custo preservada se resultado incerto")
                log.warning("Lote de pesquisa incompleto (%s)", type(exc).__name__)
    else:
        limitations.append("Pesquisa OpenAI não executada; relatório de dados, sem validação de teses")
    research["summary"] = research["summaries"][0] if research["summaries"] else "Pesquisa aprofundada não concluída; não utilizar métricas isoladas como recomendação."
    research["sources"] = sorted(set(research["sources"]))
    research["events"] = calendar_events + [e for e in research["events"] if e not in calendar_events]
    if calendar_events:
        research["sources"] = sorted(set(research["sources"] + ["https://www.bls.gov/schedule/news_release/bls.ics"]))
    research["risks"] = list(dict.fromkeys(research["risks"]))
    seen = set()
    research["news"] = [n for n in research["news"] if not (n["evidence"]["source_url"] in seen or seen.add(n["evidence"]["source_url"]))]
    for a in assets:
        if a["symbol"] in theses:
            a["thesis"] = theses[a["symbol"]]
        a["ranking"] = score_asset(a, wl.weights, a.get("thesis"))
        if a.get("errors"):
            limitations.append(a["symbol"] + ": " + "; ".join(a["errors"]))
        if not a.get("thesis"):
            limitations.append(a["symbol"] + ": tese pesquisada indisponível")
    if discovery.get("investigated", 0) < 10:
        limitations.append("Triagem não atingiu dez novos candidatos")
    if not research["events"]:
        limitations.append("Agenda dos próximos sete dias não verificada")
    try:
        fx, _, _ = market.history("BRL=X")
        fx_rows = [{"date": str(i.date()), "adjusted_close": float(r.adjclose)} for i, r in fx.iterrows()]
        etf_comparison = compare_etfs(assets, fx_rows)
    except Exception:
        etf_comparison = {"available": False, "reason": "FX indisponível para comparação consistente"}
    changes, comparison_note = compare(assets, store.previous(day))
    spent, reserved = store.cost(day)
    # Track known provider/research gaps openly, even if no endpoint threw an error.
    missing = {a["symbol"]: a.get("thesis", {}).get("missing", []) for a in assets if a.get("thesis", {}).get("missing")}
    if missing:
        limitations.append("Lacunas de pesquisa por ativo: " + ", ".join(missing))
    return {"day": day, "generated_at": settings.now().isoformat(), "status": "parcial" if limitations else "concluído",
            "demo": False, "assets": assets, "macro": macro, "headlines": news, "research": research,
            "discovery": discovery, "etf_comparison": etf_comparison, "changes": changes,
            "comparison_note": comparison_note, "limitations": limitations,
            "cost": {"estimated_usd": round(spent, 5), "reserved_usd": round(reserved, 5), "daily_budget_usd": settings.budget,
                     "model": settings.model, "prices_per_million": {"input": settings.input_price, "output": settings.output_price}, "web_call_usd": settings.search_price}}


def deliver(report, paths, telegram):
    day = report["day"]
    if report["status"] != "concluído":
        telegram.alert(day, f"Relatório {day} PARCIAL. Há dados ou pesquisa indisponíveis. Consulte as limitações no PDF; decisões sem cobertura suficiente ficaram em AGUARDAR.")
    summary, ranking = summaries(report)
    telegram.text(day, "resumo", summary)
    telegram.text(day, "ranking", ranking)
    telegram.send_once(day, "relatorio-completo", path=paths["pdf"])
    telegram.send_once(day, "dados-estruturados", path=paths["json"])


def run(settings, *, send=False, ai=True, refresh=False):
    store = Store(settings.data_dir / "radar.sqlite3")
    day = settings.now().date().isoformat()
    with run_lock(settings.data_dir / "run.lock"):
        report = store.report(day) if not refresh else None
        if report is None:
            report = collect(settings, store, ai=ai)
            store.save_report(day, report)
        paths = generate(report, settings.reports_dir)
        if send:
            deliver(report, paths, Telegram(settings, store))
        log.info("Relatório %s: %s; %s ativos; USD estimados %.4f", day, report["status"], len(report["assets"]), report["cost"]["estimated_usd"])
        return report, paths
