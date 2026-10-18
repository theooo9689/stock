# Validação da entrega — 2026-10-18

Atualização posterior: a automação migrou para o notebook por solicitação do usuário. O agendador deste workspace foi interrompido e o workflow de envio ficou manual. Foram preparados instalador Windows, tarefa ao entrar na conta, retomada por minuto e pacote privado com configuração/histórico. A suíte passou a 49 testes; a sintaxe PowerShell foi validada pelo parser. A instalação no notebook requer executar `INSTALAR_WINDOWS.cmd` ali; não foi executada remotamente por esta sessão Linux. Consulte [WINDOWS.md](WINDOWS.md).

Executada em 2026-10-18T17:48:46.780868-03:00.

## Evidências verificadas

- 41 testes automatizados passaram. Quatro avisos de depreciação vêm de exchange_calendars/NumPy; não houve falhas.
- 52 ativos coletados: 34 da watchlist, 15 candidatos de ações e 3 criptos novas.
- 52 cotações e 52 conjuntos de indicadores reais, com fontes e horários.
- 52 entradas de pesquisa estruturada; lacunas continuam descritas por ativo. Uma entrada de tese não significa que toda a investigação desejada foi completada.
- PDF A5 de 269 páginas, Markdown e JSON gerados. Primeira e última páginas e presença do conteúdo completo foram conferidas.
- Telegram confirmou envio do resumo, ranking dividido, PDF e JSON atualizados. Destino e credenciais não constam aqui.
- Decisões desta execução: {'AGUARDAR': 50, 'EVITAR': 2}. São heurísticas auditáveis, não ordens ou garantias.
- Custo estimado acumulado das pesquisas/testes: USD 0.78386; orçamento configurado USD 3.00/dia.
- Agendador local iniciado e processo verificado: pesquisa 19h30 e envio 20h30 America/Sao_Paulo. Depende de o ambiente continuar ligado.
- Código e workflow publicados na branch main do repositório theooo9689/stock.

## O que ainda impede considerar o projeto plenamente concluído

- O relatório foi marcado PARCIAL. Nenhuma notícia passou por toda a checagem desta execução: houve erros de limite da API na verificação independente, notícias antigas descartadas e fontes insuficientes. O panorama publicado usa cotações coletadas; não reproduz alegações de notícias sem confirmação.
- Valuation setorial, históricos de múltiplos/consenso, dívida detalhada, algumas informações de ETFs e tokenomics/fluxos agregados continuam ausentes quando os provedores/fontes não os disponibilizam. Não foram inventados.
- A credencial GitHub disponível recusou leitura/cadastro de Actions secrets com HTTP 403. É necessário configurar TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID e OPENAI_API_KEY e validar uma execução do workflow para ativação permanente.
- O agendador local não transforma um ambiente temporário em servidor permanente. GitHub cron pode atrasar; nenhuma pontualidade de minuto foi afirmada.

## Arquivos de configuração

- .env local preenchido, privado e ignorado pelo Git; .env.example público sem valores.
- config/watchlist.yaml editável; requirements.lock com versões e hashes.
- README.md contém comandos, limites, procedimentos de ativação, backup e conciliação de envios incertos.
