from __future__ import annotations

from .config import Watchlist
from .fundamentals import derive, value_range
from .scoring import score_asset


def demo_report(settings):
    wl = Watchlist.load(settings.config_path)
    assets = []
    for a in wl.instruments():
        a.update({"name": "EXEMPLO SINTÉTICO — " + a["symbol"], "retrieved_at": "DEMONSTRAÇÃO", "errors": ["DADOS FICTÍCIOS"],
                  "quote": {"price": 100.0, "currency": "USD", "as_of": "DEMONSTRAÇÃO", "source": "https://example.org/dados-ficticios"},
                  "technical": {"rsi14": 50.0, "sma200": 98.0, "macd_histogram": 0.2},
                  "market": {"stale": True, "session": "DEMONSTRAÇÃO"}, "fundamentals": {}, "history": []})
        a["ranking"] = score_asset(a, wl.weights)
        assets.append(a)
    return {"day": settings.now().date().isoformat(), "generated_at": settings.now().isoformat(), "status": "DEMONSTRAÇÃO", "demo": True,
            "assets": assets, "macro": [], "headlines": [], "research": {"summary": "DEMONSTRAÇÃO COM DADOS FICTÍCIOS. Este exemplo ilustra o formato e não apresenta oportunidades reais.", "summaries": [], "news": [], "risks": ["Dados sintéticos, sem valor analítico"], "events": [], "limitations": ["Não houve pesquisa real"], "sources": []},
            "limitations": ["TODOS OS DADOS SÃO SINTÉTICOS"], "etf_comparison": {"available": False}, "discovery": {"scope": "simulação"},
            "changes": [], "comparison_note": "Exemplo sem histórico", "cost": {"estimated_usd": 0}}


def premium_sample_report(settings):
    """Fictional layout sample only; never feed this object to delivery."""
    from .premium import upgrade_report
    from .evidence import factbook
    r=upgrade_report(demo_report(settings))
    a=next(a for a in r['assets'] if a['symbol']=='EME')
    a.update(name='EMPRESA FICTÍCIA — layout; não representa EMCOR',market={'stale':False,'session':'SIMULAÇÃO'},average_dollar_volume=50_000_000)
    a['quote'].update(price=70,as_of=settings.now().isoformat())
    a['technical'].update(sma50=66,sma200=60,ema20=68,macd=1.2,macd_signal=1,atr14=2,relative_volume=1.1,annualized_volatility=.25,support=64,resistance=73,trend='alta')
    a['fundamentals_source']={'url':'https://example.org/dados-sinteticos','period':'2025-12-31','currency':'USD'}
    a['fundamentals']={'pe':12,'forward_pe':11,'ev_ebitda':8,'price_fcf':7/.9,'fcf_yield':.9/7,'revenue_growth':.12,'earnings_growth':.15,'operating_margin':.2,'net_margin':.12,'roe':.25,'roic':.18,'net_debt_ebitda':1,'ebitda':1e9,'fcf':.9e9,'cash':.5e9,'shares':100e6,'positive_fcf_years':4,'median_annual_fcf':.9e9,'eps':70/12}
    wl=Watchlist.load(settings.config_path);a['valuation']=value_range(a['fundamentals'],wl.valuation)
    meanings={
        'pe':'O múltiplo representa a relação entre preço e lucro passado. No exemplo, só constitui desconto se os resultados recorrentes sobreviverem ao ciclo; não há média setorial verificada para afirmar que está barato frente aos pares.',
        'ev_ebitda':'A métrica inclui dívida e caixa na avaliação do negócio, mas não capta sozinha a necessidade de investimento nem o custo financeiro. O desconto precisa ser confirmado pela conversão em caixa.',
        'fcf_yield':'O caixa livre em relação à capitalização dá suporte ao cenário de valuation, desde que seja recorrente. Adiantamento de clientes pode elevar o indicador temporariamente e exige conferir capital de giro.',
        'revenue_growth':'Crescimento de vendas amplia a base de resultados apenas se vier de demanda recorrente e preservar margem. É necessário separar volume, reajustes e aquisições antes de extrapolar a taxa.',
        'operating_margin':'A margem indica quanto da receita permanece após custos operacionais. Sua sustentação depende de disciplina em contratos, produtividade e repasse de custos; contratos mal precificados podem inverter a leitura.',
        'net_debt_ebitda':'A alavancagem oferece espaço para absorver oscilações, mas não revela calendário de vencimentos ou covenants. A tese depende de preservar liquidez e evitar aquisições que consumam caixa.'}
    t={'business':'EXEMPLO FICTÍCIO. Empresa de serviços industriais que recebe por execução e manutenção de projetos. Receita depende de carteira contratada e capacidade de entregar sem estouro de custos. Concorrência por preço e escassez de mão de obra limitam o poder de repasse; este exemplo não descreve a companhia real do ticker.',
       'why_now':'EXEMPLO FICTÍCIO. O desconto frente ao cenário base só seria interessante se a carteira contratada convertesse em receita e caixa sem deterioração das margens. A oportunidade ilustrada é a diferença entre preço e caixa normalizado, sujeita à confirmação em resultados e contratos.',
       'interpretations':[{'metric_id':'fundamentals.'+key,'interpretation':text} for key,text in meanings.items()],
       'technical_context':'EXEMPLO FICTÍCIO. Preço e médias apontam tendência favorável, enquanto o volume não comprova aceleração de demanda. O técnico ajuda a administrar execução, mas não confirma a qualidade da carteira de contratos nem substitui a análise de caixa.',
       'catalysts':['EXEMPLO: publicação de resultados que confirme conversão da carteira em caixa. Não é uma data real confirmada.'],
       'counter_thesis':'EXEMPLO FICTÍCIO. O argumento mais forte contra a compra é que o caixa recente resulte de adiantamentos e não de rentabilidade sustentável. Se novos contratos exigirem capital de giro e enfrentarem pressão de custos, o DCF superestima o valor econômico e o aparente desconto desaparece.',
       'buy_now':'Na simulação, uma entrada gradual dependeria de confirmar o caixa normalizado, mantendo exposição compatível com a incerteza dos contratos.',
       'do_not_buy':'Não comprar com base neste exemplo. Para um ativo real, faltam documentos, histórico de múltiplos, carteira de contratos e revisão independente.',
       'entry_condition':'Somente na simulação: preço abaixo do limite do cenário base com margem de segurança e confirmação documental da geração recorrente de caixa.',
       'invalidation':'A tese simulada seria invalidada por deterioração persistente de margem, consumo de capital de giro que comprometa o caixa normalizado ou alavancagem incompatível com a execução dos contratos.',
       'horizon':'Exemplo de horizonte plurianual, sujeito à revisão após cada balanço, sem previsão de retorno.',
       'evidence':[{'source':'https://example.org/relatorio-ficticio','published_at':'2025-12-31','stance':'contrária — sintética','quote':'EXEMPLO FICTÍCIO: o caixa pode ter sido antecipado por clientes; esta não é uma citação de documento real.'}],
       'missing':['Todos os dados são fictícios; nenhuma pesquisa real ocorreu nesta demonstração.'],
       'metrics':factbook(a),'validated':False,'review':{'approved':False,'reason':'Demonstração de layout, não evidência real.'}}
    a['thesis']={'premium':t};a['ranking']=score_asset(a,wl.weights)
    a['ranking']['decision']='EXEMPLO DE DECISÃO — NÃO É RECOMENDAÇÃO'
    r['publication']['selected']=['EME'];r['publication']['funnel']['published']=0
    r['status']='DEMONSTRAÇÃO';r['research']['summary']='Demonstração de layout com uma tese fictícia; nenhuma recomendação real.'
    return r
