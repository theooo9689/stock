"""Bounded Telegram HTML and a local visual preview of the exact message bodies."""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .scoring import INCONCLUSIVE


def esc(value):return html.escape(str(value),quote=True)


def value(v, percent=False):
    if v is None:return 'N/D'
    return (f'{v*100:.1f}%' if percent else f'{v:,.2f}').replace(',','_').replace('.',',').replace('_','.')


METRIC_LABELS = {'pe':'P/L trailing','forward_pe':'P/L forward','ev_ebitda':'EV/EBITDA','price_fcf':'P/FCF','fcf_yield':'FCF yield','revenue_growth':'Crescimento receita','earnings_growth':'Crescimento lucro','revenue_cagr':'CAGR receita','eps_cagr':'CAGR lucro por ação','operating_margin':'Margem operacional','net_margin':'Margem líquida','roe':'ROE','roic':'ROIC aprox.','net_debt_ebitda':'Dívida líquida/EBITDA','cash':'Caixa','fcf':'Fluxo de caixa livre','dividend_yield':'Dividend yield','price':'Preço','rsi14':'RSI 14','macd':'MACD','expense_ratio':'Taxa anual','market_cap':'Market cap','fully_diluted_valuation':'FDV'}


def metric_label(key):
    field=key.split('.')[-1]
    return METRIC_LABELS.get(field,field.replace('_',' ').capitalize())


def stamp(iso):
    try:return datetime.fromisoformat(iso.replace('Z','+00:00')).astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m %Hh%M BRT')
    except (ValueError,TypeError,AttributeError):return 'horário indisponível'


def short(text, budget=240):
    """Executive excerpts only. Complete analysis remains in PDF/JSON."""
    if len(text)<=budget:return text
    return text[:budget].rsplit(' ',1)[0]+'…'


def messages(report):
    lookup={a['symbol']:a for a in report['assets']}; pub=report['publication']
    selected=[lookup[s] for s in pub['selected']]
    marker=' • DEMONSTRAÇÃO' if report.get('demo') else ''
    parts=[f'<b>📊 RADAR DE INVESTIMENTOS{marker}</b>\n{esc(report["day"])} • {esc(stamp(report["generated_at"]))}', '<b>🌎 MERCADO EM 1 MINUTO</b>']
    for m in [m for m in report.get('macro',[]) if m.get('price') is not None][:3]:
        change=m.get('change_last_session')
        parts.append(f'• {esc(m["name"])}: {esc(value(m["price"]))} {esc(m.get("unit") or m.get("currency", ""))}'+(f' ({esc(value(change,True))})' if change is not None else '')+f'\n  {esc(stamp(m.get("as_of")))}')
    parts.append('<b>📰 NOTÍCIAS QUE IMPORTAM</b>')
    news=[n for n in report['research'].get('news',[]) if n.get('verification',{}).get('review',{}).get('approved')]
    for n in news[:3]:parts.append(f'• <a href="{esc(n["evidence"]["source_url"])}">{esc(short(n["title"],110))}</a> — {esc(short(n["interpretation"],170))}')
    if not news:parts.append('A verificação de contexto não foi concluída. O boletim factual e as fontes coletadas estão no PDF; não inferimos ausência de acontecimentos.')
    parts.append('<b>🎯 MELHORES OPORTUNIDADES</b>')
    for a in selected[:5]:parts.append(f'<b>{esc(a["symbol"])}</b> — {esc(short(a["thesis"]["premium"]["why_now"],160))}')
    if not selected:parts.append('Nenhuma compra sustentada por dados, tese e revisão suficientes nesta edição. Preço baixo isoladamente não muda essa conclusão.')
    if pub['observe']:
        parts.append('<b>⏳ O QUE MONITORAR</b>')
        for a in pub['observe'][:3]:parts.append(f'<b>{esc(a["symbol"])}</b> — {esc(short(a["condition"],190))}')
    parts.append('<b>⚠️ RISCO PRINCIPAL</b>\n'+esc(short((report['research'].get('risks') or ['Cobertura incompleta de fundamentos e evidências.'])[0],230)))
    parts.append('📎 Relatório completo anexado.\n<i>Leitura informativa; sem execução de ordens. Dados insuficientes não viram nota baixa.</i>')
    first='\n\n'.join(parts)
    cards=['<b>🔎 TESES SELECIONADAS</b>']
    for a in selected:
        t=a['thesis']['premium'];m=a.get('fundamentals',{});technical=a.get('technical',{});q=a['quote']
        lines=[f'<b>{esc(a["symbol"])} — {esc(a.get("name",a["symbol"]))}</b>',f'{esc(value(q["price"]))} {esc(q["currency"])} • {esc(stamp(q["as_of"]))}']
        if a['category']=='stocks':lines.append(f'<b>Fundamentos</b>\nP/L {value(m.get("pe"))}× | EV/EBITDA {value(m.get("ev_ebitda"))}×\nFCF yield {value(m.get("fcf_yield"),True)} | Receita {value(m.get("revenue_growth"),True)}')
        lines += [f'<b>Técnico</b>\nRSI {value(technical.get("rsi14"))} | MACD {value(technical.get("macd"))} | {esc(technical.get("trend","N/D"))}',
                  '<b>Tese</b>\n'+esc(short(t['why_now'],330)),'<b>Argumento contrário</b>\n'+esc(short(t['counter_thesis'],240)),
                  '<b>Decisão</b>\n'+esc(a['ranking']['decision']),'<b>Condição de entrada</b>\n'+esc(short(t['entry_condition'],220))]
        cards.append('\n\n'.join(lines))
    if not selected:cards.append('Sem cards de compra nesta edição. A watchlist prioritária está resumida no PDF; os demais candidatos ficam apenas no histórico de triagem.')
    return first,'\n\n'.join(cards)


def preview(report, path):
    bodies=messages(report)
    content='<!doctype html><html lang="pt-br"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar • prévia Telegram</title><style>body{margin:0;background:#101820;color:#e5edf4;font:15px/1.55 system-ui,sans-serif}.phone{max-width:440px;margin:28px auto;padding:20px;background:#182532;border-radius:20px}.top{font-weight:700;color:#8cb9d9;padding:0 0 18px}.msg{background:#223647;border-radius:12px;padding:18px;margin-bottom:16px;overflow-wrap:anywhere}a{color:#80c9ff}b{color:#fff}i{color:#b5c4cf}</style><div class="phone"><div class="top">Radar de Investimentos • prévia local</div>'
    content+=''.join('<div class="msg">'+m.replace('\n','<br>')+'</div>' for m in bodies)
    content+='<div class="msg">📎 Relatório completo.pdf<br>Dados estruturados.json</div></div></html>'
    Path(path).write_text(content,encoding='utf-8')
