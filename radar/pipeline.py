from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
import portalocker

from .config import Watchlist
from .calendar import official_events
from .crypto import Crypto
from .http import HTTP
from .grounding import verify_news
from .market import Market, compare_etfs
from .news import collect_news
from .report import generate, summaries
from .research import Research, ResearchUnavailable, compact_asset
from .scoring import score_asset
from .storage import Store, BudgetExceeded
from .telegram import Telegram

log = logging.getLogger("radar")


class RunInProgress(RuntimeError):
    pass


@contextmanager
def run_lock(path):
    lock = portalocker.Lock(str(path), mode="a", timeout=0)
    try:
        lock.acquire()
    except portalocker.exceptions.LockException:
        raise RunInProgress("Já existe uma execução em andamento") from None
    try:
        yield
    finally:
        lock.release()


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


def grounded_overview(research, macro, assets):
    """Publish macro numbers from collection, without recycling unchecked AI headlines."""
    snapshot = []
    for m in macro:
        if m.get("price") is not None:
            change = m.get("change_last_session")
            delta = f"; variação no último candle {change:+.2%}" if change is not None else ""
            snapshot.append(f"{m['name']}: {m['price']} {m.get('unit') or m.get('currency', '')}{delta}; cotação de {m.get('as_of', 'horário indisponível')}")
    research["summaries"] = ["\n".join(snapshot)]
    research["summary"] = (f"Foram coletados {len(assets)} ativos e confirmadas {len(research['news'])} notícias na verificação de fonte/data. "
                           "Os horários das bolsas e de cripto são exibidos separadamente. Lacunas de fundamentos e pesquisa impedem recomendações sem cobertura suficiente.\n" + "\n".join(snapshot[:3]))
    lookup = {m.get("ticker"): m for m in macro}
    risks = ["Dados incompletos de valuation, composição de ETFs ou tokenomics podem alterar as teses; conferir a cobertura de cada ativo."]
    if lookup.get("^VIX", {}).get("price") is not None:
        risks.append(f"Volatilidade: VIX em {lookup['^VIX']['price']} pontos no último dado; choques podem ampliar oscilações e spreads.")
    if lookup.get("^TNX", {}).get("price") is not None:
        risks.append(f"Juros: Treasury de dez anos em {lookup['^TNX']['price']}% ao ano; juros maiores podem reduzir valuations de ativos de longa duração.")
    research["risks"] = risks


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
    event_keys = set()
    research["events"] = [e for e in research["events"] if not ((e["published_at"], e["source_url"]) in event_keys or event_keys.add((e["published_at"], e["source_url"])))]
    if calendar_events:
        research["sources"] = sorted(set(research["sources"] + ["https://www.bls.gov/schedule/news_release/bls.ics"]))
    research["risks"] = list(dict.fromkeys(research["risks"]))
    seen = set()
    research["news"] = [n for n in research["news"] if not (n["evidence"]["source_url"] in seen or seen.add(n["evidence"]["source_url"]))]
    research["news"], grounding_limits = verify_news(settings, store, http, research["news"], day)
    limitations.extend(grounding_limits)
    grounded_overview(research, macro, assets)
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


def deliver(report, paths, telegram, edition="manual"):
    day = report["day"]
    complete = f"{edition}-concluido"
    if telegram.store.delivery_states(day).get(complete) == "sent":
        return
    if report["status"] != "concluído":
        telegram.alert(day, f"Relatório {day} PARCIAL. Há dados ou pesquisa indisponíveis. Consulte as limitações no PDF; decisões sem cobertura suficiente ficaram em AGUARDAR.")
    summary, ranking = summaries(report)
    telegram.text(day, f"{edition}-resumo", summary)
    telegram.text(day, f"{edition}-ranking", ranking)
    telegram.send_once(day, f"{edition}-relatorio-completo", path=paths["pdf"], caption=f"Radar de Investimentos — {day} — relatório completo ({report['status']})")
    telegram.send_once(day, f"{edition}-dados-estruturados", path=paths["json"], caption=f"Dados estruturados — {day}")
    from .telegram import chunks
    expected = {f"{edition}-resumo-{i+1}" for i in range(len(chunks(summary)))}
    expected.update(f"{edition}-ranking-{i+1}" for i in range(len(chunks(ranking))))
    expected.update((f"{edition}-relatorio-completo", f"{edition}-dados-estruturados"))
    states = telegram.store.delivery_states(day)
    if all(states.get(part) == "sent" for part in expected):
        telegram.store.claim_delivery(day, complete)
        telegram.store.sent(day, complete, 0)


def run(settings, *, send=False, ai=True, refresh=False, edition="manual"):
    store = Store(settings.data_dir / "radar.sqlite3")
    day = settings.now().date().isoformat()
    with run_lock(settings.data_dir / "run.lock"):
        report = store.report(day) if not refresh else None
        if report is None:
            report = collect(settings, store, ai=ai)
            store.save_report(day, report)
        paths = generate(report, settings.reports_dir)
        if send:
            deliver(report, paths, Telegram(settings, store), edition=edition)
        log.info("Relatório %s: %s; %s ativos; USD estimados %.4f", day, report["status"], len(report["assets"]), report["cost"]["estimated_usd"])
        return report, paths
