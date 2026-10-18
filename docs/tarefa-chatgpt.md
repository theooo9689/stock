# Plano A — tarefa nativa do ChatGPT

Este é um texto para criar a tarefa pela interface oficial, não uma tarefa já ativada. Nesta sessão não há ferramenta de criação/edição de Tasks. Não existe neste projeto uma API para cadastrar tarefas na conta Plus.

1. Abra o ChatGPT com sua conta Plus e procure **Scheduled / Tarefas** ou **Configurações → Notificações → Gerenciar tarefas**. A disponibilidade depende da conta e versão do app.
2. Use o pedido abaixo em uma conversa que permita criar tarefas. Confirme a criação no cartão oficial e confira o fuso **America/Sao_Paulo**, diariamente às **20h30**. Esse é o início solicitado da execução, não uma garantia de que um relatório longo estará pronto exatamente nesse minuto.
3. Ative as notificações push/email nas configurações. Só considere a tarefa ativa depois que ela aparecer em Scheduled com o horário correto. A assinatura Plus tem, na documentação consultada em 18/10/2026, até cinco tarefas ativas; confira o limite exibido na sua conta.
4. Faça uma execução de teste e verifique se a tarefa realmente dispõe de busca atual. Não assuma que o recurso **Deep Research** está disponível em execução agendada. A documentação consultada não confirma explicitamente esse encadeamento; não basta escrever “pesquisa aprofundada” no prompt.
5. Para Deep Research interativo, selecione a ferramenta oficialmente, revise o plano quando solicitado e acompanhe o contador de uso. A exportação oficial permite PDF, Markdown e Word. Baixe o PDF e use `ENCAMINHAR_PDF.cmd` para envio manual ao Telegram, ou anexe-o diretamente no Telegram.

Nenhuma chave, cookie, login ou token deve ser colado no pedido. O bot Telegram existente não é um app conectado do ChatGPT. Este plano não promete geração automática de PDF, envio Telegram, cálculo de indicadores sem séries ou acesso programático ao resultado da tarefa.

## Pedido completo para copiar

Crie uma tarefa diária nesta conversa, às 20h30 no fuso America/Sao_Paulo, chamada “Radar de Investimentos — análise diária”. Use o histórico desta conversa quando ele estiver disponível; não presuma acesso a anexos de projetos, arquivos do notebook ou resultados anteriores que você não consiga consultar.

Em cada execução, produza em português uma análise financeira criteriosa usando busca e ferramentas que estejam efetivamente disponíveis para a tarefa. Antes de analisar, informe a data/hora de corte em Brasília, se os mercados estão abertos ou fechados, quais ferramentas foram usadas e se houve limitação de acesso às fontes. Não afirme que executou Deep Research se essa ferramenta não estiver disponível na tarefa. Se não puder consultar fontes atuais, informe a limitação; não substitua notícias atuais por memória do modelo.

Pesquise amplamente e publique somente as melhores oportunidades, sem cotas de compra. Prefiro até três teses de ações bem fundamentadas a dezenas de justificativas genéricas. Priorize ETFs AVUV, AVDV, JEPI, JEPQ, SCHD e IVVB11; acompanhe também VOO, IVV, SPY, QQQ e WRLD11. Ações prioritárias: EME é EMCOR Group, FIS, ORCL, CRWV, AAOI, AMKR, NBIS e VRT. Cripto: priorize BTC, ETH e SOL; BNB, XRP e LINK só merecem destaque quando houver tese específica.

O relatório precisa responder: o que aconteceu hoje; por que bolsas e outros mercados se moveram quando houver evidência; como notícias afetam juros, dólar, lucros, liquidez e cripto; quais ativos podem estar baratos; por que comprar parcialmente, esperar ou evitar; quais fatos e condições fariam mudar essas conclusões. Distinguir impacto observado de hipótese econômica. Não atribuir uma decisão de governo ao banco central nem deduzir causalidade apenas porque notícia e preço ocorreram no mesmo dia.

Selecione de cinco a dez acontecimentos materiais se houver fontes suficientes, sem preencher uma cota com notícias irrelevantes. Para cada um: fato e fonte/data, contexto anterior, surpresa comprovada ou não confirmada, mecanismo econômico, ativos afetados, cenário favorável/adverso e o que monitorar. Use o último pregão de bolsa e notícias do fim de semana quando aplicável; cripto tem mercado 24/7. Tente fontes alternativas quando uma falhar.

Para cada oportunidade real, explique negócio, segmentos, clientes, concorrentes e vantagem competitiva, por que merece atenção agora, evidências favoráveis e argumento mais forte contra. Inclua quando aplicáveis, verificáveis e datados: preço/moeda, P/L trailing e forward, EV/EBITDA, P/FCF e FCF yield, ROIC/ROE, crescimento de receita/lucro, margens, dívida e caixa, guidance, dividendos/recompras e comparações históricas/relativas. Interprete os números, sem apenas listá-los. Não invente pares, médias setoriais, múltiplos históricos ou revisões de consenso.

Se os dados permitirem, apresente cenários pessimista/base/otimista de valor justo, premissas, faixa de risco/retorno e margem de segurança. Se não permitirem, declare valuation indisponível. Não use um DCF genérico inadequado para bancos/REITs nem misture moedas. Calcule RSI14, MACD12/26/9, SMA50/200, EMA20, ATR14 e volume relativo somente com séries verificáveis e ferramenta de cálculo disponível, identificando fonte, janela e último candle completo. Sem esses insumos, marque N/D; não estime indicadores por linguagem natural.

Para AVUV/AVDV, analise small-cap value, lucratividade, concentração e diversificação. Para JEPI/JEPQ, explique opções/ELNs, contraparte, limitação de upside e diferença entre distribuição de renda e retorno total. Para SCHD, examine qualidade e crescimento dos dividendos. Para IVVB11, avalie S&P 500, concentração, custos e câmbio. Compare retornos só na mesma moeda/período e com tratamento coerente dos dividendos. Lacuna de dados brasileiros não é nota baixa de investimento.

Para cripto, não use P/L de ações. Examine liquidez, market cap/FDV, emissão e desbloqueios, adoção/atividade/taxas de rede, riscos de protocolo/segurança/concentração, fluxos e derivativos quando disponíveis e regulação. Não declare diligência completa só porque preço, capitalização e FDV estão disponíveis. Não destacar memecoins só por terem caído.

Separe qualidade dos dados, atratividade e confiança. Informação ausente não é zero. Se faltarem elementos essenciais, use “ANÁLISE INCONCLUSIVA — DADOS INSUFICIENTES”. Não produza compra/venda ou score aparentemente preciso sem suporte. A decisão vem após a tese. Responda por que comprar agora, por que não comprar, preço/condição de entrada, invalidação e horizonte. Mesmo para esperar/evitar, dê motivo e gatilho concretos quando sustentáveis; não repita frases genéricas.

Organize em: resumo executivo, acontecimentos e impactos, macro/mercado, oportunidades selecionadas, teses, ETFs prioritários, cripto, esperar/evitar, agenda confirmada, mudanças desde o relatório anterior e metodologia/lacunas/fontes. Use links reais e datas. Compare com a execução anterior somente se puder acessá-la, informando mudanças de dados/metodologia; senão, registre “sem comparação anterior disponível”. Não envie Telegram nem prometa anexos se não houver ferramenta oficialmente conectada e autorizada. Notifique-me dentro do ChatGPT usando os recursos oficiais da tarefa.

## Referências

- [Tasks — criação, notificações, limites e aprovações](https://help.openai.com/en/articles/10291617)
- [Deep Research — fontes, limites e exportação oficial](https://help.openai.com/en/articles/10500283)
- [Plus — API separada e limites](https://help.openai.com/en/articles/6950777)
