# Radar de Investimentos — ChatGPT Plus + Codex oficial

A viabilidade foi verificada antes da implementação: [tabela, fontes e limites](docs/viabilidade-chatgpt-plus.md). **Plus não inclui API paga.** O modo padrão agora usa o **Codex CLI oficial com login ChatGPT**, dentro da franquia da conta; não inicia Ollama nem usa chave OpenAI. A pesquisa do Codex não é o produto Deep Research.

Há duas formas suportadas de usar esta entrega:

## Plano A: tarefa dentro do ChatGPT e encaminhamento manual

Use o [pedido completo e instruções](docs/tarefa-chatgpt.md) para criar uma tarefa na interface oficial, diariamente às **20h30 America/Sao_Paulo**, com notificações ChatGPT. Este projeto e esta sessão não criaram essa tarefa: é preciso verificar o cartão de confirmação e a lista Scheduled na conta. Não há API pública documentada para este programa ler os resultados pessoais de Tasks.

Acesso a busca, anexos e modelos depende das ferramentas disponíveis na tarefa. Não há confirmação explícita, nos documentos consultados, de que Tasks pode acionar automaticamente o produto Deep Research; não prometemos esse encadeamento, PDF automático ou Telegram direto. Para pesquisa pelo Deep Research interativo, use sua exportação oficial de PDF/Word/Markdown.

Para encaminhar o PDF que você baixou oficialmente, execute **INSTALAR_CHATGPT_MANUAL.cmd** e depois **ENCAMINHAR_PDF.cmd**. Esse modo instala o componente local sem Codex/Ollama, desativa o agendador local anterior e não cria uma tarefa ChatGPT. O encaminhamento é manual e deduplicado por conteúdo/dia. O notebook só precisa estar ligado durante o encaminhamento; a tarefa ChatGPT na nuvem é independente dele.

## Plano B: pesquisa e Telegram automáticos no notebook

Extraia o ZIP inteiro e execute **INSTALAR_WINDOWS.cmd**. O instalador atualiza `%LOCALAPPDATA%\RadarInvestimentos`, configura Python/dependências, tenta instalar o CLI oficial `@openai/codex` via npm e solicita o **login oficial na sua conta ChatGPT** quando necessário. Node.js LTS pode exigir autorização de instalação do Windows. Login por API key é recusado; a tarefa só é ativada depois do diagnóstico local. Isso não garante que a sessão/limite esteja válido no serviço: confira a primeira execução real.

Ele preserva Telegram e histórico e altera somente `RESEARCH_PROVIDER` para `codex`. O login não vai no `.env` e não deve ser compartilhado; o cliente oficial administra a autenticação. O app ChatGPT não precisa ficar aberto para a automação via CLI. O **notebook deve estar ligado, conectado e com sessão Windows ativa**. Não é possível ativar a tarefa no seu notebook a partir deste workspace.

O trabalhador inicia no login, prepara às **19h30** e entrega às **20h30 de Brasília**. A tarefa entra na fila se a pesquisa demorar. Ao entrar depois do horário, tenta entregar a edição do dia. Suspensão/desligamento impedem processamento naquele momento. `EXECUTAR_AGORA.cmd` gera/envia manualmente; `DESINSTALAR_WINDOWS.cmd` remove a automação e preserva dados.

```cmd
codex login
.venv\Scripts\python.exe -m radar.cli doctor
```

O diagnóstico informa modo de login e opções locais do CLI; não testa o saldo/franquia nem valida uma inferência no serviço. **Neste workspace, a inferência real foi recusada com 401 e pediu novo login.** Não houve relatório financeiro Codex concluído aqui. O código, as validações e a integração foram testados com mocks; a autenticação e a primeira pesquisa precisam ser verificadas no notebook.

## Franquia e falhas

Modelo padrão `gpt-6.1-sol`, raciocínio alto, até 900 segundos por chamada. A disponibilidade deve ser confirmada na conta; `CODEX_MODEL` permite selecionar outro modelo disponível. A descoberta usa busca oficial; documentos recuperados por HTTP e métricas calculadas são fornecidos à análise. Notícias são analisadas/revisadas em lotes, e a investigação se limita a até três ações, dois ETFs e uma cripto entre candidatos elegíveis, sem cotas de compra.

Há limite **local** persistente de 20 chamadas/dia (`CODEX_MAX_DAILY_CALLS`), cache e auditoria. Isso não é um limite monetário da conta nem garantia de que a franquia Plus comporte pesquisa diária extensa. Contexto, busca e raciocínio consomem franquia. O programa não compra créditos, não faz fallback para chave API e não escolhe automaticamente outro provedor. Confira no produto os limites reais e quaisquer configurações de compra automática/créditos adicionais.

Falha de login, quota, fonte ou revisão gera uma edição parcial/factual; compras sem evidência não são publicadas. Tentativas interrompidas ficam registradas sem repetição cega. Alterar apenas o horário de coleta não repete inferência com os mesmos dados. Logs: `data/logs/radar.log`; entradas/respostas/eventos oficiais: `data/codex-research/`; consumo de chamadas: `radar status`. Não ative dois agendadores com bancos separados.

## Uso direto

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.lock
pip install --no-deps -e .
cp .env.example .env
# Configure Telegram. Não é necessário preencher OPENAI_API_KEY.
# Instale o CLI oficial conforme developers.openai.com/codex/cli, então:
codex login
radar doctor
radar run --refresh               # pesquisa Codex + PDF, sem enviar
radar run --send                  # envia a edição salva ou prepara se ausente
radar run --refresh --no-ai       # somente dados reais, sem Codex/Ollama
radar forward exportado.pdf       # exportação oficial baixada manualmente
radar forward exportado.pdf --summary resumo.txt
radar preview                    # renderiza a edição salva, sem rede
radar versions                   # versões imutáveis do dia
radar render-version ID          # resposta congelada, sem inferência
radar demo --deep                # exemplo fictício, nunca enviado
pytest -q
```

`--refresh` refaz a pesquisa sem apagar deduplicação. `--edition nome` identifica uma edição independente. Timeout Telegram pode significar que o envio chegou; o estado fica `sending`, exigindo conferir o destino antes de reenviar. Campos e módulos Ollama/API antigos permanecem apenas para compatibilidade/opção explícita, sem uso no caminho Codex.

## Funil e decisões

`config/watchlist.yaml` distingue **25 prioridades**, universo configurável e limites máximos: 5 ações, 3 ETFs, 3 criptos e 5 observações. Não há cotas. Os screeners ampliam a triagem de ações/ETFs; o restante do universo fica em JSON, sem dezenas de cards de AGUARDAR.

Etapas: coleta → cálculos → qualidade/liquidez → investigação individual → evidências favoráveis e contrárias → verificação literal/numérica → revisão crítica → publicação. Busca externa usa documentos recuperados por HTTP e resultados RSS do Bing; Ollama recebe os textos, sem fingir ter ferramentas de navegação. Documentos podem conter conteúdo hostil e são tratados como dados, sem execução de instruções.

As três dimensões ficam separadas:

- **Qualidade dos dados:** fonte, horário, atualidade, liquidez e requisitos por classe. ETF exige custos/composição com período efetivo; data da coleta não comprova data da carteira. Cripto exige prova adicional de tokenomics, adoção e segurança; market cap/FDV sozinho nunca significa cobertura total.
- **Atratividade:** critérios calculados com os dados disponíveis, normalizados pelos pesos observados e arredondados a cinco pontos. Não usa notas inventadas pelo modelo. Exige qualidade ≥80%, ausência de lacunas críticas e peso disponível ≥60% (50% para o núcleo quantitativo de cripto, além das provas obrigatórias); do contrário, nota `null`.
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

`data/radar.sqlite3` guarda estado/deduplicação, snapshots e versões imutáveis de relatórios. `data/codex-research/` registra entradas, saídas oficiais, eventos e versão/modelo do CLI. O modo Ollama legado mantém sua auditoria separada. Mesmas entradas/metodologia produzem a mesma atratividade; cache inclui prompt/esquema/modelo/versão do CLI. Inferência pode variar entre versões/backend, portanto a resposta congelada e a versão do relatório permitem auditoria. Compare snapshots antes de interpretar mudanças. Faça backup de `data` e `reports`.

`.env`, dados privados e relatórios são ignorados no Git. Não imprima credenciais nem ative logs HTTP de debug. `scripts/build_windows_package.py arquivo.zip` gera fonte pública; `--configured` inclui configuração e backup SQLite e produz um ZIP **privado**, que não deve ser publicado ou compartilhado. A aplicação mantém os módulos antigos de pesquisa OpenAI apenas para compatibilidade/testes; o modo Codex não os instancia. O workflow diário GitHub fica manual e factual, sem login de assinatura em CI público.

## Validação

Testes Linux e Windows verificam cálculos financeiros/técnicos, feriados, calendário, entrega/deduplicação, retomada e locks, parser PowerShell, limites/escaping HTML, snapshots e revisão. A fixture `tests/fixtures/problem-2026-10-18.json` preserva entradas objetivas do relatório problemático para impedir regressões de notas, cobertura, compras sem tese e PDF excessivo. Testes locais usam mocks; execução real com Codex é uma verificação adicional dependente de login, franquia e rede. O teste neste workspace chegou ao serviço e recebeu 401, sem inferência concluída.
