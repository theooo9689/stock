# Viabilidade verificada — Radar com ChatGPT Plus

Consulta de documentação oficial em **18/10/2026 UTC**. A tabela foi apresentada antes das mudanças de implementação. Disponibilidade e limites mudam; revise a documentação e a interface da sua conta antes de depender do agendamento.

| Funcionalidade | Suporte oficial comprovado? | API paga de IA? | Computador ligado? | Automatizável? | Limitações |
|---|---|---|---|---|---|
| Tarefa ChatGPT diária às 20h30 America/Sao_Paulo | Sim, conta elegível | Não | Não, se executada na nuvem | Sim, após criação na UI | Plus: até 5 tarefas ativas na documentação consultada. Horário solicitado não garante término de uma pesquisa longa no mesmo minuto. |
| Busca de notícias atuais em conversa/pesquisa | Sim | Não dentro da franquia | Não na nuvem | Ferramentas da tarefa precisam ser verificadas | Não basta escrever “pesquise” para comprovar acesso à web na execução. |
| Deep Research disparado todo dia por Tasks, sem intervenção | Não há confirmação explícita nos documentos consultados | Não dentro da franquia disponível | Não na nuvem | Não comprovado | Recurso separado; pode exigir revisão do plano e tem franquia própria. |
| Relatório longo com citações e exportação PDF/Word/Markdown por Deep Research | Sim, exportação pela interface | Não dentro da franquia | Não | Exportação manual comprovada | Não comprova exportação automática em Tasks. |
| Task usar diretamente o bot deste repositório | Não da forma atual | Não se aplica | Não se aplica | Não comprovado | Token BotFather não registra app/MCP no ChatGPT. Código e .env locais não ficam acessíveis à tarefa na nuvem. |
| Apps em Tasks | Sim, apps suportados e autorizados | Depende do serviço; assinatura não é API | Não na nuvem | Condicionado à conta/permissões | Ações de escrita podem pausar pedindo aprovação; não promete Telegram. |
| Codex CLI autenticado por ChatGPT | Sim | Não usa cobrança da API por chave | Sim para execução local | Sim, `codex exec` é documentado para scripts/agendamento | Consome a franquia ChatGPT/Codex. Não é o produto Deep Research. |
| Codex pesquisar fontes, raciocinar e usar cálculos externos | Busca nativa e execução de scripts são suportadas | Não com login ChatGPT | Sim na arquitetura local | Sim, condicionado a ferramentas/rede | Nenhuma garantia de dados completos, qualidade financeira ou franquia diária suficiente. |
| Resultado Codex entregue a componente local | Sim: `--output-schema` e `--output-last-message` | Não com login ChatGPT | Sim | Sim | Usa saída oficial do processo, não intercepta conversas, cookies ou tokens. |
| Local enviar resumo/PDF ao Telegram | Sim: Bot API | Não | Sim durante envio | Sim | Bot iniciado pelo destinatário, token e destino configurados, rede disponível. Timeout pode ser incerto; não repetir cegamente. |
| Consultar resultados de Tasks pessoais Plus por API pública | Não foi localizada API pública documentada | Não se aplica | Não se aplica | Não implementado | Tasks/snapshots não constam do export pessoal conforme documentação consultada. Compliance API empresarial não equivale a API da conta Plus. |
| Histórico comparável | Local: snapshots/versões já implementados. Tasks no mesmo chat podem usar contexto disponível | Não | Sim no modo local | Sim local; contexto nativo condicionado | Não garantir acesso a chats apagados, arquivos do projeto ou execuções indisponíveis. |

## Arquitetura entregue

**Plano A, nuvem e notificações ChatGPT:** pedido autocontido em `docs/tarefa-chatgpt.md`, para criação na UI oficial. Não foi criado ou ativado por esta sessão porque não há ferramenta de Tasks exposta. Sem promessa de Deep Research agendável ou Telegram direto. `INSTALAR_CHATGPT_MANUAL.cmd` instala somente o encaminhador local e desativa a automação local anterior; `ENCAMINHAR_PDF.cmd` envia o PDF que o usuário baixar oficialmente. A instalação do encaminhador não cria a tarefa ChatGPT.

**Plano B, automação local com assinatura:** fontes/cálculos Python → seleção → Codex CLI com login ChatGPT e busca oficial para descobrir fontes → documentos recuperados e verificação literal → tese/revisão → PDF/Telegram/histórico. `INSTALAR_WINDOWS.cmd` configura esse modo no notebook. Ele não inicia nem baixa Ollama. O aplicativo ChatGPT não precisa ficar aberto para o CLI, mas o notebook e a sessão Windows precisam estar ativos/conectados. O instalador só ativa a nova tarefa após o diagnóstico/login; a autenticação com o serviço ainda pode falhar posteriormente.

O processo prepara às 19h30 e tenta entregar às 20h30 em Brasília, quando ligado; a pesquisa pode atrasar a entrega. Se entrar depois do horário, retoma a edição do dia. Sem acesso, rede, quota ou evidência, entrega factual/parcial sem inventar compras. Há limite local persistente de chamadas/dia; ele não mede ou garante a franquia real da conta. Se a pesquisa continuar sem conseguir concluir uma revisão final, as recomendações não são publicadas.

**Plano C automático lendo Tasks:** não implementado. A alternativa suportada é exportação manual do relatório na interface, ou saída oficial do Codex CLI, seguida de Bot API local. Não há scraping, Selenium, leitura de cookies/auth.json, captura de tokens de login, engenharia reversa ou API “grátis do Plus”.

## Autenticação e custos

O adaptador usa `codex login status` e recusa modo API antes da inferência. Executa `codex exec` com login ChatGPT e provedor OpenAI forçados. Não lê o cache de autenticação; login, armazenamento e renovação são responsabilidade do cliente oficial. As chaves antigas de IA e Telegram não são passadas ao subprocesso de pesquisa. Não migra sessão de navegador nem copia tokens para este projeto.

O Codex acessa o serviço oficial com a assinatura; isso não transforma Plus em crédito de API. Não faz compra de créditos ou fallback pago. A configuração de créditos adicionais/compra automática da própria conta deve ser conferida pelo usuário nos controles oficiais; o programa não consegue impor um limite monetário à conta. Fontes/dados licenciados, se contratados, podem ter custos próprios.

A documentação recomenda API keys para CI compartilhado e restringe o fluxo avançado de credenciais de assinatura em CI público. Portanto **não** configuramos login ChatGPT em GitHub Actions. O workflow diário fica manual, com IA desligada e sem chave OpenAI. Os testes CI usam mocks. Não coloque a sessão do Codex, `.env` ou banco em artifacts públicos.

## Validação e limites observados

- CLI oficial disponível neste workspace: `codex-cli 0.159.2`; opções de saída estruturada e modo de login verificadas.
- O primeiro teste foi impedido antes da inferência por diretórios de estado somente leitura deste ambiente. Um teste autorizado com o estado normal do CLI alcançou o serviço.
- **O serviço recusou a sessão com HTTP 401 e solicitou novo login.** O diagnóstico local de modo ChatGPT não prova que a sessão ainda esteja válida no serviço. Não foi concluída pesquisa financeira pelo Codex neste ambiente e nenhuma tarefa pessoal ChatGPT foi criada.
- Nenhum fallback de API ou extração de credenciais foi usado. A pesquisa completa e o primeiro agendamento continuam dependendo do login oficial e de uma execução real no notebook.
- Testes automatizados cobrem recusa de API key, argumentos oficiais, dados privados fora do subprocesso, cache, limite persistente/atômico, ausência de retry em resultado incerto, erro de sessão, saída inválida, comprovação de busca, resolução do binário Windows e encaminhamento manual com deduplicação.

## Documentação oficial consultada

1. [Tasks em ChatGPT](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt) — criação, fuso, notificações, apps, limites, aprovações, histórico e ausência em export pessoal.
2. [Deep Research](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt) — fontes atuais, revisão do plano, limites próprios, citações e exportação.
3. [Plus](https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus) — API cobrada separadamente e uso da assinatura.
4. [Codex: autenticação](https://developers.openai.com/codex/auth/) — login ChatGPT versus API key e restrição do método de login.
5. [Codex: modo não interativo](https://developers.openai.com/codex/noninteractive/) — scripts/agendamento, `codex exec`, JSON schema e saída em arquivo; autenticação de conta em automação.
6. [Codex: planos/limites](https://developers.openai.com/codex/pricing/) — Plus inclui CLI; consumo varia com contexto, raciocínio e ferramentas.
7. [Codex: automações](https://developers.openai.com/codex/app/automations/) — tarefas na UI, local versus nuvem, permissões e máquina ligada.
8. [Codex no Windows](https://developers.openai.com/codex/windows/) — CLI/app nativos e sandbox.
9. [Apps conectados](https://help.openai.com/en/articles/11487775) — disponibilidade e autorizações não presumidas.
10. [Telegram Bot API](https://core.telegram.org/bots/api#senddocument) — envio por bot. A integração preexistente usa `sendMessage` e `sendDocument` oficiais.

Os links Codex redirecionaram oficialmente para `learn.chatgpt.com/docs/` na consulta. O recibo de URLs e hashes do texto consultado está em `docs/official-docs-receipt.json`.
