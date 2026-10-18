# Radar de Investimentos — Telegram

Sistema Python 3.12 para coletar dados de mercado, calcular indicadores, pesquisar notícias com a Responses API da OpenAI, comparar teses, gerar PDF A5 legível no celular e entregar resumo/ranking/documentos pelo bot existente. **Não executa ordens financeiras.**

## Windows: iniciar automaticamente ao ligar o notebook

Extraia o pacote e dê dois cliques em **INSTALAR_WINDOWS.cmd**. Pelo CMD, dentro da pasta extraída, o comando é:

```bat
INSTALAR_WINDOWS.cmd
```

O instalador usa Python 3.12+ (instala 3.12 pelo winget se necessário), cria um ambiente próprio, instala dependências com hashes e registra uma tarefa para o usuário atual. Não depende do GitHub Actions. Se a conta não permitir criar a tarefa, usa um atalho na pasta Inicializar. Não requer senha do Windows nem solicitar elevação de administrador para a configuração do radar.

O programa é copiado para `%LOCALAPPDATA%\RadarInvestimentos`, portanto a pasta extraída em Downloads pode ser apagada após a instalação. **Um pacote privado configurado contém `.env`; não envie esse pacote a terceiros nem o publique no GitHub.** O código público tem apenas `.env.example`; quem usa esse código precisa preencher as três credenciais. A reinstalação preserva `.env` e banco já existentes no notebook.

- Inicia ao **entrar na conta do Windows**, sem manter janela de CMD aberta. Ligar o aparelho sem entrar na conta não inicia a tarefa interativa.
- Verifica o horário de **Brasília**, independentemente do fuso do Windows; pesquisa às 19h30 e envia às 20h30.
- Se estiver desligado, suspenso ou sem sessão no horário, retoma quando puder executar. Ao ligar **depois das 20h30 no mesmo dia**, pesquisa/envia a edição daquele dia. Depois da meia-noite, segue a programação do novo dia; não inventa retrospectiva do dia perdido.
- Reentrar no Windows ou verificar a cada minuto não repete uma edição já entregue. Envio com resultado incerto fica bloqueado para conferência manual.
- Requer internet para dados/APIs e notebook ligado/acordado. Não há mecanismo para executar enquanto o computador está desligado.
- Arquivos e logs ficam em `%LOCALAPPDATA%\RadarInvestimentos\data\logs\radar.log`; relatórios em `%LOCALAPPDATA%\RadarInvestimentos\reports`.

Para enviar manualmente, use **EXECUTAR_AGORA.cmd**. Para remover a inicialização automática, use **DESINSTALAR_WINDOWS.cmd**; configuração e histórico são preservados. Se já usa um agendador em outro computador ou na nuvem, desative-o ao migrar para evitar dois ambientes enviando separadamente.

Validação do instalador: a suíte inclui retomada após o horário, preparação única, edição já concluída, envio incerto e lock entre processos usando `portalocker` (Windows/Linux). O workflow de testes inclui Windows e parser PowerShell; instalar no notebook continua sendo a etapa executada pelo usuário, pois este workspace não tem acesso ao aparelho.

## Início rápido

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
# Preencha os três secrets em .env, sem colocá-los no Git.
radar test-telegram
radar demo                         # offline, sintético, sem enviar
radar run --no-ai                  # coleta real; relatório de dados, sem pesquisa
radar run --refresh                # pesquisa real, gera relatório sem enviar
radar preview                     # renderiza o resultado salvo do dia
radar run --send                   # envia resultado salvo ou coleta/pesquisa se ausente
radar status                      # custo estimado e estado das entregas
pytest -q
```

`requirements.lock` fixa versões e hashes. Para reproduzir o ambiente do workflow, instale `pip install --require-hashes -r requirements.lock` seguido de `pip install --no-deps -e .`.

Se você rodou `--no-ai`, use `--refresh` para refazer o relatório com pesquisa antes do envio. Sem `--refresh`, o resultado salvo do dia é reutilizado. Refazer a pesquisa consome orçamento adicional; não reenvia partes já entregues. Nunca rodar `--refresh` para resolver um timeout de envio sem antes verificar se a mensagem chegou.

## Configuração e watchlist

`config/watchlist.yaml` inclui os **34 ativos obrigatórios**: 10 ETFs EUA, 7 ETFs B3, 8 ações e 9 criptomoedas. EME é EMCOR, não EEM. Edite as listas para adicionar/remover ativos e os pesos para ajustar os modelos. A soma de pesos de cada grupo deve ser 1. Os valores de cripto no YAML são os IDs CoinGecko; preços históricos usam o ticker `SÍMBOLO-USD` do Yahoo.

Variáveis obrigatórias: `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. O destino deve ter iniciado o bot com `/start`. Não é preciso criar outro bot. O token é utilizado apenas na Telegram Bot API oficial. Não há integração de email/Resend.

Variáveis de modelo, tarifas, limites de tokens/ferramentas, orçamento diário, diretórios e fuso constam em `.env.example`. Credenciais são `SecretStr`, URLs de erros de SDK não são impressas e `.env`, banco e relatórios são ignorados pelo Git. Não use logs DEBUG de bibliotecas HTTP. O chat privado não é incluído em relatórios ou exemplos.

## Coleta e cobertura real

- **Yahoo Finance:** candles diários de dois anos, cotação com timestamp/moeda, fundamentos, demonstrativos anuais e composição de ETFs quando disponíveis. Usa endpoints públicos e `yfinance`; não há SLA. Splits/dividendos usam ajuste do provedor. Informação de fundamentos coletada hoje não significa balanço publicado hoje: o período fiscal é registrado quando disponível.
- **Triagem diária:** até 100 resultados de cada um de cinco screeners de ações/ETFs; filtra capitalização e volume financeiro e investiga 15 novos candidatos, distribuídos entre setores/screeners. O relatório registra retornados, total por screener, elegíveis e investigados. Não cobre todas as ações do mercado.
- **CoinGecko:** market cap, FDV, oferta, volume e variações 24h/7d/30d das nove criptos, com horário. Também investiga até três criptos novas da amostra top100 por capitalização, excluindo stablecoins/wrapped conhecidos. Binance USD-M fornece amostra de funding/OI quando permitido na região. Não são estatísticas agregadas de todo o mercado. Bloqueios regionais e indisponibilidade aparecem como lacunas. `market_symbols` no YAML permite mapear tickers especiais, como HYPE → HYPE32196-USD.
- **Notícias:** feeds Fed, SEC, BBC e CoinDesk; deduplicação de URL/manchete e janela máxima de três dias, seguida por pesquisa web com fontes. Manchete coletada não implica análise de impacto concluída. A pesquisa distingue fatos, interpretações e cenário alternativo. A agenda inclui coleta direta do calendário iCalendar oficial do BLS; datas e fuso são calculados, sem inferência da IA. Eventos macro sugeridos pela IA exigem fonte oficial e janela dos próximos sete dias.
- **OpenAI:** pesquisa web obrigatória em cada lote, fontes e fatos estruturados, tese de cada ativo, riscos, catalisadores, condições de espera e agenda. URLs não citadas pela ferramenta nem fornecidas na coleta são removidas das evidências. A presença de uma URL não comprova toda a interpretação; revisão humana continua necessária.
- **Verificação antes de publicar notícias:** recupera o texto do documento e faz uma checagem separada de fato/título, data e coerência econômica. Exige trecho literal existente na página e publicação recente; notícias sem suporte ou cuja fonte não pode ser recuperada ficam fora do resumo. O panorama macro usa números coletados, sem reaproveitar afirmações não verificadas da IA. Isso reduz erros, mas não garante toda interpretação nem substitui revisão humana das teses individuais.
- **FMP opcional:** somente fallback de cotação/capitalização quando Yahoo falha. Não cobre automaticamente histórico de múltiplos, consenso, agenda, vencimentos ou token unlocks. Outros dados exigem provedor licenciado ou fontes verificadas na pesquisa.

**Limitações que não são escondidas:** o acesso gratuito pode não disponibilizar taxas/composição de ETFs brasileiros, múltiplos históricos, peers normalizados, cronograma detalhado da dívida, revisões de estimativas, fluxos institucionais, liquidações, concentração/token unlocks ou TVL/receita atribuível ao token. A pesquisa procura fontes oficiais e declara o que não confirmou. Não há promessa de obter todos esses dados diariamente sem contratação de provedores específicos. Se faltarem dados para uma tese ou valuation, não se inventa valor justo ou preço de entrada. O relatório pode ser PARCIAL mesmo com preços e PDF funcionando.

## Cálculos e decisões auditáveis

RSI e ATR usam Wilder 14, com média inicial simples. MACD usa EMA 12/26/9; MM20/50/200, volume relativo a 20 candles anteriores, volatilidade de 60 retornos anualizada por 252/365, máxima/mínima 52 semanas, drawdown e níveis mínimo/máximo de 20 candles. Candles provisórios de hoje são retirados se a sessão ainda estiver em andamento. O preço pontual pode ser mais recente que o último candle completo; ambos os horários são exibidos. Calendários XNYS/BVMF tratam feriados e bolsas fechadas; cripto é 24/7. Dados ausentes ou muito antigos bloqueiam compra.

Fundamentos calculam FCF yield, P/FCF, dívida líquida/EBITDA, EV/EBIT, cobertura de juros e ROIC aproximado quando existem insumos. Crescimento, margens e múltiplos recebidos preservam a unidade. Alerta de dívida/EBITDA >3×, juros <2×, FCF/margens negativos e contração de resultados impede confundir queda com pechincha. FIS recebe atenção explícita na pesquisa.

DCF requer FCF positivo e ao menos três anos positivos de histórico. Usa o menor entre FCF atual e mediana anual, cenários de crescimento/desconto, crescimento terminal e sensibilidade 3×3. É aproximação do caixa ao acionista, **não um modelo institucional completo de FCFE**. Os múltiplos configuráveis são cenários ilustrativos, não médias históricas ou de pares. Moedas incompatíveis invalidam o cálculo até conversão auditada. A entrada máxima aplica margem de segurança de 25% ao cenário base. Se os insumos não sustentam a avaliação, o campo fica indisponível.

Há modelos separados para ações/ETFs/cripto. Fórmulas, pesos, notas, fontes, julgamentos qualitativos e cobertura constam do JSON/PDF. Critérios ausentes não são reescalados. COMPRA PARCIAL exige nota ≥72, cobertura ≥85%, cotação válida e pesquisa com fontes; ações exigem também valor justo/margem de segurança. EVITAR exige <35 com cobertura ≥85%. Demais ficam em AGUARDAR. Os cortes são heurísticas transparentes, não probabilidades calibradas. RSI baixo ou MACD positivo isolado não gera compra.

Comparação de ETFs usa datas comuns, fechamento ajustado e USD; B3 é convertido com USD/BRL nas mesmas datas. Taxas internas já afetam cotas; impostos, spreads, corretagem e situação fiscal individual não são modelados. Não se presume que AVUV/AVDV sejam melhores que IVVB11. ELNs/opções de JEPI/JEPQ, concentração e sobreposição são investigados na pesquisa.

## Relatórios, histórico e envio

`reports/radar-AAAA-MM-DD.{pdf,json,md}` guarda o conteúdo completo. O PDF inclui as 16 partes solicitadas e análise de cada ativo; blocos longos fluem entre páginas. Não há cortes para caber no Telegram. O resumo e o ranking são divididos por limite UTF-16 e os documentos integrais seguem anexos. O comando `demo` gera arquivos `demonstracao-*`, com todos os valores claramente sintéticos; exemplos não são enviados.

`data/radar.sqlite3` guarda relatórios, comparação com o último dia anterior, cache, custos e entregas. `data/research/` preserva saídas e IDs OpenAI para auditoria. Faça backup regular destes diretórios. Execuções concorrentes locais são bloqueadas; o workflow tem fila única. A deduplicação é por dia/edição/parte, com registro antes do POST. O envio manual é independente da edição agendada, para que um teste ou relatório manual à tarde não bloqueie a entrega das 20h30. Repetições da mesma edição não são enviadas novamente.

**Timeout de envio é resultado incerto.** Telegram não fornece chave de idempotência: se a resposta se perde, o sistema conserva o estado `sending` para não duplicar automaticamente. Confira o Telegram antes de excluir esse registro de `deliveries` no SQLite para reenvio manual. HTTP 429 recebe retry limitado; 5xx de envio não é repetido cegamente. Alertas de falhas também são deduplicados. Falha total de rede/Telegram pode impedir o próprio alerta; o workflow registra a falha.

## Automação às 20h30 de Brasília

### GitHub Actions

O workflow `.github/workflows/daily.yml` ficou **somente manual** (`prepare`/`deliver`) após a migração solicitada para o notebook. A automação Windows funciona sem secrets do GitHub. Para voltar a usar execução diária na nuvem, configure os secrets e um agendador antes de desativar o notebook; não ative duas instalações diárias independentes.

No repositório, cadastre em **Settings → Secrets and variables → Actions**:

1. `TELEGRAM_BOT_TOKEN`
2. `TELEGRAM_CHAT_ID`
3. `OPENAI_API_KEY`

O script local já pode usar o `.env` privado; não copie valores para código, issues, commits ou logs. O ID de destino pode ser obtido de sua configuração local. Há helper que envia os três valores ao GitHub sem imprimi-los: `python scripts/configure_github_secrets.py OWNER/REPO`. Ele requer `gh` autenticado com permissão de administrar Actions secrets. Se retornar 403, um administrador precisa cadastrar os secrets pelo site ou fornecer uma credencial com essa permissão.

O estado e relatórios são restaurados do último artifact `radar-state` e regravados por 90 dias; cada nova execução carrega o histórico anterior. Se não houver execução por mais de 90 dias, restaure backup antes de retomar. Artifacts de repositório público podem ser acessíveis a usuários autenticados no GitHub: use repositório privado se quiser restringir seus relatórios/watchlist. Eles não incluem `.env` nem destino privado. Não rode simultaneamente o agendador local e Actions com bancos diferentes: a deduplicação depende do mesmo estado. Para migrar o primeiro envio local, comece Actions no dia seguinte ou restaure o mesmo banco antes de um envio no mesmo dia.

**Apenas incluir o YAML não ativa a automação.** São necessários push na branch padrão, Actions habilitado, secrets presentes e ao menos uma execução verificada. No ambiente desta entrega, a API de Actions secrets recusou acesso com HTTP 403; isso é impedimento para ativação automática pela credencial disponível, não falha do token Telegram. A primeira tentativa da API OpenAI foi recusada com `credit_balance_exhausted` / `insufficient_quota`; uma tentativa posterior passou a responder e produziu pesquisa real. Se o erro voltar, adicione créditos à conta da API; assinatura do ChatGPT não fornece esse saldo.

### Servidor sempre ligado

```bash
radar schedule
```

O scheduler pesquisa uma hora antes e entrega no horário configurado, com `ZoneInfo('America/Sao_Paulo')`, coalescência e um executor único que serializa os dois jobs. Instale o exemplo `docs/radar.service` em um servidor Linux, ajuste `/opt/radar` e o usuário, mantenha volume persistente/backup e habilite o serviço no systemd. O processo precisa permanecer ativo; uma sessão temporária de desenvolvimento não garante execução amanhã. Se a pesquisa se estender além do horário, a entrega fica na fila; não há promessa de pontualidade com APIs lentas.

## Orçamento e segurança da pesquisa

O padrão é USD 3/dia. Cada pesquisa faz reserva atômica conservadora de custo antes da API. Uso retornado ajusta a estimativa. Falha com cobrança incerta conserva a reserva. Sem orçamento, o lote aparece incompleto e o Telegram recebe alerta. A estimativa não é fatura; tarifas, impostos e política da conta podem variar. Atualize os preços ao trocar de modelo. Veja [documentação consultada](docs/openai-api.md).

Notícias e páginas são dados não confiáveis; as instruções fixas impedem que sejam tratadas como comandos. A IA só recebe ferramenta de pesquisa, dados de mercado e fontes — não recebe os secrets, shell ou funções de envio. Fontes HTTPS são validadas e dados externos são escapados no PDF. Esses controles reduzem risco, mas não garantem veracidade de toda afirmação da IA.

## Testes

`pytest -q` verifica RSI/Wilder, MACD, ATR, médias, volume, volatilidade cripto, dados faltantes, DCF por identidade de perpetuidade, margens/ratios, feriados e fins de semana, fuso Brasília, deduplicação de notícias, igualdade de retornos após FX, histórico, orçamento/cache, esquema de pesquisa, citações, respostas incompletas, PDF completo, Unicode Telegram, documento multipart, retries, erro definitivo e timeout ambíguo. Testes usam fixtures/mocks sem gastar API; a execução real é uma validação adicional separada.
