from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
import portalocker

from .config import Watchlist
from .calendar import official_events
from .crypto import Crypto
from .http import HTTP
from .market import Market, compare_etfs
from .news import collect_news
from .report import generate, summaries
from .storage import Store
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
        changed_fields=[k for k,v in a.get('fundamentals',{}).items() if old.get('fundamentals',{}).get(k)!=v]
        if old['ranking'].get('methodology_version') != a['ranking'].get('methodology_version'):
            score_reason='Mudança de metodologia; notas antigas não são diretamente comparáveis.'
        elif a.get('score_input_hash') and a.get('score_input_hash')==old.get('score_input_hash'):
            if a['ranking']['score']!=old['ranking']['score']:raise RuntimeError('Score divergente com entradas e metodologia idênticas')
            score_reason='Mesmas entradas e metodologia; atratividade preservada.'
        else:score_reason='Entradas alteradas: '+(', '.join(changed_fields) or 'preço, técnico, qualidade ou fontes; conferir snapshots')
        changes.append({"symbol": a["symbol"], "before": before, "after": after,
                        "previous_price": p0, "current_price": p1, "price_change": p1/p0-1 if p0 and p1 else None,
                        "score_change": (a["ranking"]["score"]-old["ranking"]["score"]) if a["ranking"].get("score") is not None and old["ranking"].get("score") is not None else None,
                        "score_change_reason":score_reason,"fundamental_changes":changed_fields,"new_facts": new})
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
    from .premium import enrich
    wl = Watchlist.load(settings.config_path)
    http = HTTP(store)
    market = Market(http, settings, wl)
    day = settings.now().date().isoformat()
    candidates, discovery = market.discover()
    crypto_candidates, crypto_discovery = Crypto(http).discover(set(wl.assets['crypto']), wl.discovery.get('crypto_candidates', 0))
    discovery['crypto'] = crypto_discovery
    assets = market.collect_many(wl.instruments() + candidates + crypto_candidates)
    Crypto(http).enrich(assets, wl.assets['crypto'])
    macro = market.macro()
    headlines, errors = collect_news(http, wl.news_feeds)
    events, calendar_errors = official_events(http)
    failures = [{'stage':'news_feed','source':e['feed'],'failure':e['error']} for e in errors]
    for a in assets:
        for error in a.get('errors',[]):
            failures.append({'stage':'market_data','asset':a['symbol'],'failure':error})
    try:
        fx, _, _ = market.history('BRL=X')
        rows = [{'date':str(i.date()),'adjusted_close':float(row.adjclose)} for i,row in fx.iterrows()]
        comparison = compare_etfs(assets, rows)
    except Exception:
        comparison = {'available':False,'reason':'FX não recuperado; sem comparação entre moedas diferentes'}
    report = {'day':day,'generated_at':settings.now().isoformat(),'demo':False,'status':'parcial',
              'assets':assets,'macro':macro,'headlines':headlines,'research':{'events':events},
              'etf_comparison':comparison,'discovery':discovery,'limitations':calendar_errors,
              'failures':failures,'changes':[],'comparison_note':'Primeiro relatório com metodologia premium.'}
    result = enrich(settings, store, wl, report, http, ai_enabled=ai)
    result['changes'],result['comparison_note'] = compare(result['assets'], store.previous(day))
    return result


def deliver(report, paths, telegram, edition="manual"):
    if report.get("demo"):raise ValueError("Demonstração sintética não pode ser enviada")
    day = report["day"]
    complete = f"{edition}-concluido"
    if telegram.store.delivery_states(day).get(complete) == "sent":
        return
    if report["status"] != "concluído":
        telegram.alert(day, f"Relatório {day} PARCIAL. Há dados ou pesquisa indisponíveis. Consulte as limitações no PDF; conclusões insuficientes ficaram inconclusivas, sem nota de investimento.")
    summary, ranking = summaries(report)
    telegram.text(day, f"{edition}-resumo", summary, parse_mode='HTML')
    telegram.text(day, f"{edition}-ranking", ranking, parse_mode='HTML')
    telegram.send_once(day, f"{edition}-relatorio-completo", path=paths["pdf"], caption=f"Radar de Investimentos — {day} — relatório completo ({report['status']})")
    telegram.send_once(day, f"{edition}-dados-estruturados", path=paths["json"], caption=f"Dados estruturados — {day}")
    from .telegram import html_chunks
    expected = {f"{edition}-resumo-{i+1}" for i in range(len(html_chunks(summary)))}
    expected.update(f"{edition}-ranking-{i+1}" for i in range(len(html_chunks(ranking))))
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
        if report and report.get("methodology_version") != "premium-2.0":
            from .premium import upgrade_report
            report = upgrade_report(report, Watchlist.load(settings.config_path))
            store.save_report(day, report)
        if report is None:
            report = collect(settings, store, ai=ai)
            store.save_report(day, report)
        paths = generate(report, settings.reports_dir)
        if send:
            deliver(report, paths, Telegram(settings, store), edition=edition)
        log.info("Relatório %s: %s; %s ativos; USD estimados %.4f", day, report["status"], len(report["assets"]), report.get("cost", {}).get("estimated_usd", 0))
        return report, paths
