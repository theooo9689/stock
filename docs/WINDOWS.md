# Instalação no notebook Windows

1. Extraia o ZIP em uma pasta local.
2. Execute **INSTALAR_WINDOWS.cmd** com dois cliques, ou digite esse nome no CMD aberto nessa pasta.
3. Espere a mensagem **PRONTO**. A instalação testa o bot no Telegram.

O pacote privado fornecido nesta conversa já traz a configuração e uma cópia consistente do histórico. O arquivo `.env` não é publicado no GitHub. Não compartilhe o pacote configurado. Se usar o código público, preencha o `.env` quando solicitado.

O instalador prepara Python 3.12+, instala as dependências, copia o programa para `%LOCALAPPDATA%\RadarInvestimentos` e configura a inicialização para seu usuário, sem senha de administrador. Se o Agendador de Tarefas estiver bloqueado, cria um atalho na pasta Inicializar. Não mova/apague a pasta instalada; a pasta baixada pode ser removida.

O radar usa o horário de Brasília e funciona sem uma janela de CMD aberta. Ele pesquisa às 19h30 e envia às 20h30. A tarefa verifica o horário a cada minuto e não faz novas pesquisas quando o trabalho do dia já está pronto. A retomada pelo atalho alternativo verifica a cada 30 segundos.

O notebook precisa estar ligado, acordado, conectado à internet e com sua conta iniciada. Se entrar no Windows depois das 20h30, ele tenta enviar a edição **daquele dia**. Se só ligar na manhã seguinte, segue a programação do novo dia; não reconstrói retrospectivamente um relatório com dados que não coletou.

Uma edição já entregue não é repetida ao reiniciar. Se um envio tiver resultado incerto, o sistema preserva o bloqueio para conferência manual. Logs rotativos: `%LOCALAPPDATA%\RadarInvestimentos\data\logs\radar.log`. Relatórios: subpasta `reports` no mesmo local.

Para uma execução manual, abra `EXECUTAR_AGORA.cmd`. Ela faz pesquisa atualizada e consome o orçamento de API configurado. Para remover a inicialização, abra `DESINSTALAR_WINDOWS.cmd`; os dados e credenciais locais são preservados.

Se a instalação falhar porque não existe winget, instale Python 3.12 no site oficial `https://www.python.org/downloads/windows/` e rode o instalador novamente. Se faltar configuração, edite `%LOCALAPPDATA%\RadarInvestimentos\.env` e repita a instalação.

## Validação realizada

49 testes Python passaram no ambiente Linux, incluindo os novos cenários de retomada e o lock entre processos. O parser PowerShell foi executado para verificar sintaxe. O workflow de testes também inclui Windows/PowerShell 5.1, sem depender de secrets ou gastar APIs. O instalador não foi executado no notebook do usuário: esta sessão tem acesso apenas ao workspace Linux.
