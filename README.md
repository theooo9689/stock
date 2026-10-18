# Radar de Investimentos — Premium local

Pesquisa diária com coleta verificável, cálculos determinísticos, investigação e revisão por **Ollama local**, PDF e Telegram. O pipeline premium não chama a OpenAI e não exige créditos. Não executa ordens.

## Windows: instalar e iniciar ao ligar o notebook

1. Extraia o ZIP inteiro e execute **INSTALAR_WINDOWS.cmd**.
2. O instalador cria `%LOCALAPPDATA%\RadarInvestimentos`, instala Python/dependências e tenta instalar Ollama pelo winget e baixar o modelo configurado. O download inicial exige vários GB e pode demorar.
3. Configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env` local, se ainda não preenchidos. O destinatário precisa iniciar o bot com `/start`.
4. A tarefa inicia ao entrar no Windows: prepara às **19h30** e entrega às **20h30 de Brasília**. Ao entrar depois das 20h30, tenta entregar a edição do dia. O notebook precisa estar ligado e conectado; suspensão/desligamento impedem processamento naquele momento. Se a pesquisa ainda estiver rodando, a entrega aguarda.

O instalador mantém a configuração existente, tenta reutilizar o Ollama e baixa somente o modelo ausente. `OLLAMA_MODEL` permite preservar outro modelo local compatível. Reexecutar atualiza os arquivos sem apagar histórico. `EXECUTAR_AGORA.cmd` gera/envia manualmente; `DESINSTALAR_WINDOWS.cmd` remove a inicialização automática e preserva dados. Logs: `data\logs\radar.log`. O instalador funciona sem administrador, usando Agendador de Tarefas ou pasta Inicializar como alternativa.

Este workspace não acessa diretamente o notebook: a execução do instalador ocorre nele. O workflow diário na nuvem continua somente manual; não ative dois agendadores com bancos independentes.

## Ollama e diagnóstico

Padrão: `qwen3:8b`, contexto 32768, até 600 segundos por chamada, temperatura zero e seed 42. O diagnóstico exige modelo ≥7B e capacidade/contexto ≥16k; recusa modelos pequenos e saída incompleta. Isso não garante qualidade: toda tese ainda exige validação e revisão.

```cmd
ollama pull qwen3:8b
.venv\Scripts\python.exe -m radar.cli doctor
```

O comando mostra RAM e capacidade do modelo. Com 16 GB, tente 8B quantizado; 32 GB ou mais permite considerar `qwen3:14b`. Memória livre, GPU e tamanho do contexto afetam desempenho: 32k pode exceder o que cabe no notebook. Ajuste o modelo/contexto no `.env` e rode o diagnóstico. Se o modelo faltar, a pesquisa falhar ou o contexto exceder o limite, a edição será **factual e parcial**, com lacunas explícitas, sem substituir a análise por texto genérico ou chamar API paga.

## Uso direto e desenvolvimento

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.lock
pip install --no-deps -e .
cp .env.example .env
# Preencha somente os dois campos Telegram para entrega.
radar doctor
radar test-telegram
radar run --refresh             # coleta + investigação local + PDF, sem enviar
radar run --refresh --no-ai     # coleta real, edição factual
radar run --send                # envia a edição salva ou prepara uma nova
radar preview                  # gera arquivos do resultado salvo, sem rede
radar replay reports/radar-2026-10-18.json # migra histórico sem confiar nas teses antigas
radar demo --deep              # tese fictícia para inspecionar layout, nunca envia
radar versions                 # IDs imutáveis do dia
radar render-version ID        # reproduz resposta congelada, sem rede/inferência
radar tick                     # verifica horário e retoma entrega diária
pytest -q
```

`--refresh` refaz dados/pesquisa, mas não apaga a deduplicação de envio. `--edition nome` identifica uma edição de teste independente. Um timeout Telegram pode significar que a mensagem chegou: o registro fica `sending` e exige conferir o destino antes de reenviar; não há retry cego de envios ambíguos.

## Funil e decisões

`config/watchlist.yaml` distingue **25 prioridades**, universo configurável e limites máximos: 5 ações, 3 ETFs, 3 criptos e 5 observações. Não há cotas. Os screeners ampliam a triagem de ações/ETFs; o restante do universo fica em JSON, sem dezenas de cards de AGUARDAR.

Etapas: coleta → cálculos → qualidade/liquidez → investigação individual → evidências favoráveis e contrárias → verificação literal/numérica → revisão crítica → publicação. Busca externa usa documentos recuperados por HTTP e resultados RSS do Bing; Ollama recebe os textos, sem fingir ter ferramentas de navegação. Documentos podem conter conteúdo hostil e são tratados como dados, sem execução de instruções.

As três dimensões ficam separadas:

- **Qualidade dos dados:** fonte, horário, atualidade, liquidez e requisitos por classe. ETF exige custos/composição com período efetivo; data da coleta não comprova data da carteira. Cripto exige prova adicional de tokenomics, adoção e segurança; market cap/FDV sozinho nunca significa cobertura total.
- **Atratividade:** critérios calculados com os dados disponíveis, normalizados pelos pesos observados e arredondados a cinco pontos. Não usa notas inventadas pelo modelo. Exige qualidade ≥80%, ausência de lacunas críticas e peso disponível ≥60%; do contrário, nota `null`.
- **Confiança:** evidências verificadas e revisão aprovada; não é probabilidade de retorno.

Dados insuficientes geram **ANÁLISE INCONCLUSIVA — DADOS INSUFICIENTES**, nunca uma nota zero de investimento. Compra parcial exige nota ≥75, tese validada, revisão e ausência de alertas de deterioração; ações ainda exigem preço abaixo do limite com margem de segurança do DCF. Sem tese aprovada, indicador favorável não gera compra. As regras são heurísticas auditáveis, não validação estatística de uma estratégia.

A tese exige duas fontes e uma primária, trecho contrário literal, indicadores rastreáveis interpretados, negócio, oportunidade específica, técnico contextualizado, catalisadores, argumento contrário, razões para comprar/não comprar, condição de entrada, invalidação e horizonte. Números não rastreáveis e citações fabricadas são rejeitados antes da revisão. A revisão usa o mesmo modelo em chamada separada; não substitui análise humana.

## Fontes e limites reais

Yahoo Finance/yfinance fornecem preços, candles, demonstrativos anuais e composição quando disponíveis; CoinGecko fornece capitalização, FDV, oferta e volume; Binance fornece amostras de funding/OI quando acessível. Os endpoints públicos podem falhar ou limitar acesso. Feeds Fed, SEC, BBC, Yahoo e CoinDesk fornecem notícias; BLS fornece calendário oficial. Se uma fonte falha, outras continuam. Manchete coletada não implica impacto econômico verificado. Notícias publicadas exigem trecho literal, data recente e revisão de contexto/causalidade; busca resultados não garante acesso ao corpo das páginas.

Múltiplos históricos, peers normalizados, revisões de guidance, recompras, unlocks, TVL/taxas de redes e fluxos institucionais podem faltar. A integração atual não certifica automaticamente toda a diligência de cripto: ausência dessas provas bloqueia publicação, mesmo com cotação funcionando. Sem período efetivo da composição, ETFs também podem ficar inconclusivos. Nenhum campo ausente é preenchido pelo modelo.

RSI/ATR usam Wilder14; MACD EMA12/26/9; SMA50/200, EMA20, volume relativo, volatilidade, suporte e resistência usam candles completos. Calendários distinguem feriados XNYS/BVMF e cripto 24/7. Cotação pontual e último candle podem ter horários diferentes, preservados no JSON. Valores contábeis respeitam moeda dos demonstrativos.

DCF exige três anos positivos de FCF, normaliza pelo menor entre FCF recente e mediana e apresenta cenários/sensibilidade. É aproximação de caixa ao acionista, com hipóteses configuráveis, sem promessa de preço-alvo. Não aplica DCF genérico a bancos/seguradoras/REITs nem compara moedas incompatíveis. Retornos de ETFs usam preço ajustado em moeda/período comuns; impostos e situação fiscal pessoal não são modelados. Distribuições de JEPI/JEPQ não equivalem a retorno total.

## Saída e auditoria

`reports/radar-premium-DATA-HASH.{pdf,html,json,md}` contém relatório seletivo com 11 seções, sumário clicável, tabelas, páginas e fontes. O HTML é prévia visual local das mensagens Telegram; texto é escapado e repartido preservando tags e caracteres UTF-16. PDFs completos são anexados. `demo` é explicitamente sintético e nunca enviado.

`data/radar.sqlite3` guarda estado/deduplicação, snapshots e versões imutáveis de relatórios. `data/local-research/` registra entradas, respostas, identidade/digest do modelo, contexto, seed e uso local. Mesmas entradas/metodologia produzem a mesma atratividade; cache inclui prompt/esquema/modelo. Inferência local pode variar entre hardware/backend, portanto a resposta congelada e a versão do relatório permitem auditoria. Compare snapshots antes de interpretar mudanças. Faça backup de `data` e `reports`.

`.env`, dados privados e relatórios são ignorados no Git. Não imprima credenciais nem ative logs HTTP de debug. `scripts/build_windows_package.py arquivo.zip` gera fonte pública; `--configured` inclui configuração e backup SQLite e produz um ZIP **privado**, que não deve ser publicado ou compartilhado. A aplicação mantém os módulos antigos de pesquisa OpenAI apenas para compatibilidade/testes; o pipeline premium não os instancia.

## Validação

Testes Linux e Windows verificam cálculos financeiros/técnicos, feriados, calendário, entrega/deduplicação, retomada e locks, parser PowerShell, limites/escaping HTML, snapshots e revisão. A fixture `tests/fixtures/problem-2026-10-18.json` preserva entradas objetivas do relatório problemático para impedir regressões de notas, cobertura, compras sem tese e PDF excessivo. Testes locais usam mocks; execução com dados reais e Ollama é uma verificação adicional dependente de rede/modelo/hardware.
