"""Selective mobile research report, with real tables, TOC and clickable citations."""
from __future__ import annotations

import hashlib
import html
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents

from .http import safe_url
from .presentation import value, stamp, metric_label
from .scoring import INCONCLUSIVE


def fonts():
    candidates=[(Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
                (Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arial.ttf',Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/arialbd.ttf')]
    for normal,bold in candidates:
        if normal.exists() and bold.exists():
            if 'Premium' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Premium',str(normal)));pdfmetrics.registerFont(TTFont('PremiumBold',str(bold)))
            return 'Premium','PremiumBold'
    return 'Helvetica','Helvetica-Bold'


def link(label,url):
    label=html.escape(str(label))
    return '<a href="'+html.escape(url,quote=True)+'" color="#245779">'+label+'</a>' if safe_url(url or '') else label


class ResearchDoc(SimpleDocTemplate):
    def beforeDocument(self):self.heading_count=0
    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='PremiumHeading':
            self.heading_count+=1
            key='heading-'+str(self.heading_count)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(),key,0)
            self.notify('TOCEntry',(0,flowable.getPlainText(),self.page,key))


def render(report,path):
    normal,bold=fonts();width=A5[0]-24*mm
    styles={
        'body':ParagraphStyle('PremiumBody',fontName=normal,fontSize=9,leading=13,spaceAfter=7,splitLongWords=True),
        'heading':ParagraphStyle('PremiumHeading',fontName=bold,fontSize=14,leading=18,spaceBefore=15,spaceAfter=10,keepWithNext=True),
        'sub':ParagraphStyle('PremiumSub',fontName=bold,fontSize=10,leading=14,spaceBefore=9,spaceAfter=5,keepWithNext=True),
        'small':ParagraphStyle('PremiumSmall',fontName=normal,fontSize=7.5,leading=10.5,spaceAfter=5),
        'cell':ParagraphStyle('PremiumCell',fontName=normal,fontSize=7.5,leading=10),
        'right':ParagraphStyle('PremiumRight',fontName=normal,fontSize=7.5,leading=10,alignment=2),
        'title':ParagraphStyle('PremiumTitle',fontName=bold,fontSize=21,leading=26,spaceAfter=12),
    }
    story=[]
    def p(text,style='body',markup=False):
        story.append(Paragraph(text if markup else html.escape(str(text)).replace('\n','<br/>'),styles[style]))
    def heading(text):p(text,'heading')
    def table(headers,rows,ratios,numeric=()):
        body=[[Paragraph(html.escape(str(x)),styles['cell']) for x in headers]]
        for row in rows:
            body.append([Paragraph(str(x),styles['right' if i in numeric else 'cell']) for i,x in enumerate(row)])
        t=Table(body,colWidths=[width*r/sum(ratios) for r in ratios],repeatRows=1,splitInRow=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eef2')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fa')]),
                               ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#a3b4c0')),
                               ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        story.extend([t,Spacer(1,8)])
    lookup={a['symbol']:a for a in report['assets']};pub=report['publication'];selected=[lookup[s] for s in pub['selected']]
    p('RADAR\nDE INVESTIMENTOS','title')
    p(('DEMONSTRAÇÃO • DADOS SINTÉTICOS • ' if report.get('demo') else '')+report['day']+' • '+stamp(report['generated_at']),'small')
    p('1. Resumo executivo','heading')
    p(f"{len(selected)} oportunidades aprovadas • {len(pub['watchlist'])} ativos prioritários • edição {report['status']}")
    if selected:
        for a in selected[:3]:p(a['symbol']+' — '+a['thesis']['premium']['why_now'][:200])
    else:p('Nenhuma compra passou simultaneamente por qualidade de dados, tese individual e revisão crítica. Uma cotação atrativa isolada não comprova margem de segurança.')
    macro=[m for m in report.get('macro',[]) if m.get('price') is not None][:3]
    if macro:table(['Mercado','Último dado','Variação'],[[html.escape(m['name']),html.escape(value(m['price'])+' '+(m.get('unit') or m.get('currency',''))),value(m.get('change_last_session'),True)] for m in macro],[2,2,1],(1,2))
    p('Risco que merece atenção','sub');p((report['research'].get('risks') or ['Cobertura incompleta de evidências.'])[0])
    if not report.get('ai',{}).get('ready'):p(report.get('ai',{}).get('reason','IA local indisponível; edição factual, sem teses inventadas.'),'small')
    p('Último pregão e cripto 24/7 têm horários próprios. Fontes e lacunas aparecem nas seções seguintes. Sem execução de ordens.','small')
    story.append(PageBreak());p('Sumário','title')
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('PremiumTOC',fontName=normal,fontSize=9,leading=16,leftIndent=0,firstLineIndent=0)]
    story.append(toc);story.append(PageBreak())
    heading('2. Acontecimentos e impactos')
    news=[n for n in report['research'].get('news',[]) if n.get('verification',{}).get('review',{}).get('approved')]
    if not news:
        p('Não foi possível concluir a validação de contexto das notícias nesta edição. Isso não significa ausência de acontecimentos. Os boletins abaixo foram coletados diretamente; não receberam interpretação de impacto aprovada.')
        useful=[n for n in report.get('headlines',[]) if any(k in n['title'].lower() for k in ('fed','oil','china','budget','tax','inflation','earnings','hormuz','bitcoin'))][:5]
        for n in useful:p(link(n['title'],n['url'])+'<br/>'+html.escape(stamp(n.get('published_at'))),'small',True)
    for n in news:
        p(n['title'],'sub');p(n['evidence']['fact'])
        p(link('Fonte',n['evidence']['source_url'])+' • '+html.escape(str(n['evidence']['published_at'])),'small',True)
        for field,label in [('prior_context','Contexto'),('surprise','O que surpreendeu'),('mechanism','Mecanismo econômico'),('observed_effect','Observado'),('positive_scenario','Hipótese favorável'),('negative_scenario','Hipótese adversa'),('watchlist_effect','Consequência nas teses'),('monitor','O que monitorar')]:
            if n.get(field):p(label+': '+n[field])
        p('Trecho conferido: '+n['verification']['supporting_quote'],'small')
    heading('3. Panorama macro e mercado')
    for m in report.get('macro',[]):
        if m.get('price') is None:continue
        p('<b>'+html.escape(m['name'])+'</b> — '+html.escape(value(m['price'])+' '+(m.get('unit') or m.get('currency','')))+'<br/>'+html.escape(stamp(m.get('as_of')))+' • '+link('Fonte',m.get('source')),'body',True)
    heading('4. Oportunidades selecionadas')
    if not selected:p('Sem ranking de compra nesta edição. Dados ausentes não foram convertidos em notas baixas; nenhuma posição foi preenchida para cumprir uma cota.')
    else:table(['Ativo','Atratividade','Decisão'],[[link(a['symbol'],a['quote'].get('source')),str(a['ranking']['score'])+'/100',html.escape(a['ranking']['decision'])] for a in selected],[1,1,3],(1,))
    heading('5. Teses aprofundadas')
    if not selected:p('As teses que não passaram pela validação permaneceram no histórico de investigação, sem ocupar páginas com texto genérico.')
    for a in selected:
        t=a['thesis']['premium'];q=a['quote']
        p(a['symbol']+' — '+a.get('name',a['symbol']),'sub')
        p(value(q['price'])+' '+q['currency']+' • '+stamp(q['as_of']))
        for field,label in [('business','O negócio'),('why_now','Por que agora')]:p(label,'sub');p(t[field])
        p('Fundamentos interpretados','sub')
        rows=[]
        for row in t['interpretations']:
            f=t['metrics'].get(row['metric_id'])
            if f:rows.append([html.escape(metric_label(row['metric_id'])),value(f['value'],f['unit']=='fração'),html.escape(row['interpretation'])+'<br/>'+link('Fonte • '+str(f.get('as_of')),f['source'])])
        table(['Indicador','Valor','O que significa'],rows,[1.2,.8,3],(1,))
        v=a.get('valuation',{});p('Valuation e margem de segurança','sub')
        if v.get('available'):
            table(['Cenário','Valor','Upside / perda'],[[html.escape(x['scenario']),value(x['fair_value']),value(x['fair_value']/q['price']-1,True)] for x in v['scenarios']],[2,1,1],(1,2))
            p(v['method'],'small');p('Premissas por cenário: '+'; '.join(x['scenario']+' → crescimento '+value(x['growth'],True)+', desconto '+value(x['discount'],True) for x in v['scenarios']),'small');p('Crescimento terminal: '+value(v['terminal_growth'],True)+'; preço máximo com margem de segurança: '+value(v['entry_max'])+' '+q['currency'])
            p('Sensibilidade: '+ '; '.join('g='+value(x['growth'],True)+', r='+value(x['discount'],True)+' → '+value(x['value']) for x in v['sensitivity']),'small')
        else:p('Não há estimativa de valor justo sustentada para este tipo de ativo/insumos; não se fabricou preço-alvo.')
        if a.get('financial_history'):
            p('Histórico anual dos demonstrativos','sub')
            table(['Exercício','Receita','Lucro por ação'],[[html.escape(x['period']),value(x.get('revenue')),value(x.get('eps'))] for x in a['financial_history']],[1,2,1],(1,2))
            p('Moeda dos demonstrativos: '+str(a.get('fundamentals_source',{}).get('currency','N/D'))+' • '+link('Demonstrativos',a.get('fundamentals_source',{}).get('url')),'small',True)
        if t.get('missing'):p('Não confirmado: '+'; '.join(t['missing']),'small')
        tech=a.get('technical',{})
        table(['RSI 14','MACD / sinal','MM50 / MM200','EMA20 / ATR14'],[[value(tech.get('rsi14')),value(tech.get('macd'))+' / '+value(tech.get('macd_signal')),value(tech.get('sma50'))+' / '+value(tech.get('sma200')),value(tech.get('ema20'))+' / '+value(tech.get('atr14'))]],[1,1.5,1.5,1.5],(0,1,2,3))
        p(t['technical_context']);p('Volume relativo: '+value(tech.get('relative_volume'))+'; volatilidade anualizada: '+value(tech.get('annualized_volatility'),True)+'; suporte / resistência: '+value(tech.get('support'))+' / '+value(tech.get('resistance')),'small')
        for field,label in [('counter_thesis','Argumento mais forte contra'),('buy_now','Por que comprar agora'),('do_not_buy','Por que não comprar agora'),('entry_condition','Condição de entrada'),('invalidation','O que invalida a tese'),('horizon','Horizonte')]:p(label,'sub');p(t[field])
        p('Catalisadores: '+'; '.join(t['catalysts']))
        for e in t['evidence']:p(link(e['source'],e['source'])+'<br/>'+html.escape(str(e.get('published_at'))+' • '+e['stance']+' • '+e['quote']),'small',True)
    heading('6. ETFs prioritários e comparação')
    rows=[]
    comparison=report.get('etf_comparison',{});rets=comparison.get('total_returns',{})
    for symbol in ('AVUV','AVDV','JEPI','JEPQ','SCHD','IVVB11'):
        a=lookup.get(symbol)
        if not a:continue
        m=a.get('fundamentals',{});profile=a.get('etf_profile',{})
        rows.append([link(symbol,profile.get('source')),value(m.get('expense_ratio'),True),value(rets.get(symbol),True),html.escape(profile.get('strategy','Estratégia ainda não documentada'))])
    table(['ETF','Taxa a.a.','Retorno total','Estratégia / risco'],rows,[.8,.8,1,3],(1,2))
    if comparison.get('available'):p('Período comum: '+comparison['start']+' a '+comparison['end']+' • USD. '+comparison['method'],'small')
    else:p('Comparação de retorno total indisponível em período/moeda comuns; sem presumir superioridade.','small')
    from .etf_research import exposure
    for symbol in ('AVUV','AVDV','JEPI','JEPQ','SCHD','IVVB11'):
        a=lookup.get(symbol)
        if not a:continue
        x=exposure(a);risk=comparison.get('risk',{}).get(symbol,{})
        p(symbol+' • composição e risco','sub')
        p('Taxa informada pelo provedor: '+value(a.get('fundamentals',{}).get('expense_ratio'),True)+' • '+link('Fonte dos fundamentos',a.get('fundamentals_source',{}).get('url')),'small',True)
        p('Volatilidade / drawdown no período comum: '+value(risk.get('volatility'),True)+' / '+value(risk.get('max_drawdown'),True)+'. Concentração nas maiores posições reportadas: '+value(x['top10_weight'],True)+'.','small')
        if x['top']:p('Maiores posições: '+'; '.join(h['symbol']+' '+value(h.get('weight'),True) for h in x['top']),'small')
        if x['sectors']:p('Setores reportados: '+'; '.join(k+' '+value(v,True) for k,v in sorted(x['sectors'].items(),key=lambda row:-(row[1] or 0))[:3]),'small')
        p('Período efetivo: '+str(x['effective_period'] or 'não confirmado')+' • coleta '+stamp(x['retrieved_at'])+' • '+link('Composição',x['source']),'small',True)
    p('Lacunas dos ETFs nesta edição: valuation agregado, distribuição por geografia e crescimento histórico dos dividendos. Sem confirmação, não se presume adequação a renda/crescimento.','small')
    for row in comparison.get('overlaps',[])[:6]:p(row['left']+' / '+row['right']+': sobreposição mínima da amostra '+value(row['common_weight_lower_bound'],True)+'; '+row['method'],'small')
    p('Distribuição de renda não é retorno total. ELNs trazem risco de contraparte; opções podem limitar a alta. Small-cap value pode passar anos atrás do S&P 500. A sobreposição depende de composição atual, não apenas do nome do ETF.')
    heading('7. Criptomoedas')
    rows=[]
    for symbol in ('BTC','ETH','SOL','BNB','XRP','LINK'):
        a=lookup.get(symbol)
        if not a:continue
        c=a.get('crypto',{});q=a.get('quote',{})
        rows.append([link(symbol,q.get('source')),value(q.get('price')),value((c.get('price_change_percentage_24h') or 0)/100,True) if c.get('price_change_percentage_24h') is not None else 'N/D',value(c.get('market_cap')),value(c.get('fully_diluted_valuation'))])
    table(['Ativo','USD','24h','Market cap','FDV'],rows,[.7,1, .7,1.5,1.5],(1,2,3,4))
    p('Não se aplica P/L de ações a tokens. Market cap/FDV não comprova desbloqueios, adoção nem segurança. Sem evidência suficiente de tokenomics, atividade e risco de protocolo, a análise permanece inconclusiva. Fontes e horários individuais estão no JSON.','small')
    heading('8. Acompanhamento e gatilhos')
    for row in pub['observe']:p(row['symbol']+' — '+row['condition'])
    if not pub['observe']:p('Nenhum gatilho de investimento foi publicado sem tese validada. A lista abaixo é acompanhamento, não ranking de compra/venda.')
    rows=[]
    for symbol in pub['watchlist']:
        a=lookup[symbol];q=a.get('quote',{});rank=a['ranking'];label='Inconclusiva' if rank['decision']==INCONCLUSIVE else rank['decision'].capitalize()
        change=next((x for x in report.get('changes',[]) if x['symbol']==symbol),{})
        novelty='; '.join(change.get('new_facts',[])[:1]) or ('Sem comparação anterior' if not change else 'Sem mudança de tese confirmada')
        if change.get('fundamental_changes'):novelty='; '.join(str(x) for x in change['fundamental_changes'][:2])
        related=[n['title'] for n in news if symbol in n.get('affected',[])]
        if related:novelty+=' • '+related[0]
        rows.append([link(symbol,q.get('source')),value(q.get('price'))+' '+html.escape(q.get('currency',''))+'<br/>'+html.escape(stamp(q.get('as_of'))),value(a.get('change_last_session'),True),html.escape(label)+'<br/>'+html.escape(novelty)])
    table(['Watchlist','Preço / horário','Variação','Leitura / novidade'],rows,[.8,1.7,.7,2.5],(2,))
    p('Inconclusiva significa evidências insuficientes, e não investimento ruim. Variações de bolsa referem-se aos candles completos; cripto tem mercado 24/7. Ausência de mudança confirmada não prova ausência de notícia.','small')
    heading('9. Agenda e catalisadores futuros')
    for e in report['research'].get('events',[]):p(html.escape(str(e['published_at'])+' — '+e['fact'])+'<br/>'+link('Fonte oficial',e['source_url']),'body',True)
    if not report['research'].get('events'):p('Agenda não confirmada nesta edição; nenhuma data foi inferida pelo modelo.')
    heading('10. Mudanças desde a edição anterior')
    p(report.get('comparison_note','Sem snapshot anterior comparável.'))
    changes=[c for c in report.get('changes',[]) if c.get('before')!=c.get('after') or c.get('new_facts') or c.get('fundamental_changes')]
    for c in changes[:8]:p(c['symbol']+' — '+c['before']+' → '+c['after']+'; '+c.get('score_change_reason','Metodologia/dados devem ser comparáveis antes de interpretar a variação.'))
    heading('11. Metodologia, lacunas e fontes')
    p('Versão '+report['methodology_version']+' • snapshot '+report['snapshot_id'][:16])
    p('A qualidade dos dados mede completude, atualidade e fonte. A atratividade usa somente critérios determinísticos disponíveis, com avaliação indisponível abaixo do limiar de cobertura ou com lacunas críticas. Confiança exige tese individual, citações literais e revisão crítica; não equivale a probabilidade de retorno.')
    p('Funil: '+str(pub['funnel'])+'. Limites são máximos, não cotas. O universo completo permanece em JSON/snapshots, sem tabelas irrelevantes no PDF.','small')
    p('RSI/ATR Wilder 14; MACD EMA 12/26/9; SMA50/200 e EMA20; volatilidade de 60 retornos anualizada em 252/365; suporte e resistência pelo mínimo/máximo dos últimos 20 candles completos. Comparações de retorno usam dividendos ajustados conforme provedor e mesma moeda/período.','small')
    issues=sorted({f['stage'] for f in report.get('failures',[])})
    if issues:p('Etapas com limitações: '+', '.join(issues)+'. Detalhes e ativos afetados no JSON; isso impediu conclusões que não poderiam ser sustentadas.')
    for item in dict.fromkeys(report.get('limitations',[])):p(item,'small')
    p('Fontes numéricas: cada linha de acompanhamento é clicável; as teses mostram origem e período por indicador. Documentos, hashes, parâmetros, identidade/digest do modelo e versões ficam no snapshot. Sem API paga no pipeline local.','small')
    p('A IA pode falhar mesmo com revisão. Citações comprovam trechos, não garantem cada inferência econômica. Nenhuma ordem é executada. Dados ausentes e comparativos não confirmados não são preenchidos com estimativas do modelo.','small')
    def footer(canvas,doc):
        canvas.setFont(normal,7);canvas.setFillColor(colors.HexColor('#647786'))
        canvas.drawString(12*mm,8*mm,('DEMONSTRAÇÃO • ' if report.get('demo') else 'RADAR PREMIUM • ')+report['day']);canvas.drawRightString(A5[0]-12*mm,8*mm,str(doc.page))
    doc=ResearchDoc(str(path),pagesize=A5,leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=16*mm,title='Radar de Investimentos • Premium',author='Radar de Investimentos')
    doc.multiBuild(story,onFirstPage=footer,onLaterPages=footer)
