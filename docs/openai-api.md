# Pesquisa e custo — documentação consultada em 18/10/2026

A implementação usa o SDK oficial `openai`, a **Responses API** e a ferramenta hospedada `web_search`. O modelo padrão é `gpt-4.1-mini`, validado com chamadas reais de pesquisa nesta conta. A documentação mantém esse modelo compatível com pesquisa web. Não se presume acesso ao Deep Research do ChatGPT.

- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://developers.openai.com/api/docs/pricing
- https://developers.openai.com/api/docs/guides/background

Modelo, preços, limite de ferramentas, limite de saída e execução em segundo plano são configuráveis. O padrão usa execução síncrona; `RESEARCH_BACKGROUND=true` habilita criação e acompanhamento por ID, até conclusão ou cancelamento após 40 minutos. A configuração de retenção da conta precisa permitir background.

As tarifas iniciais são USD 0,40/1M tokens de entrada, USD 1,60/1M tokens de saída e USD 0,01 por pesquisa. Em gpt-4.1-mini, o conteúdo de pesquisa não-preview tem bloco de 8.000 tokens por busca, faturado como entrada. Lotes de cinco ativos e cardinalidade no schema evitam omissões silenciosas. O consumo retornado em `usage` é usado na estimativa; confira o faturamento no provedor. A reserva anterior à chamada usa um teto conservador de 128k tokens por passo e máximo configurado de ferramentas/saída. Ao mudar de modelo, atualize as tarifas; orçamento local não substitui limites da conta OpenAI.

Também foram consultadas as informações de `gpt-5.4-mini`, compatível com web_search e saída estruturada. A API de modelos o reconheceu, mas a tentativa de pesquisa nessa conta retornou falta de cota; ele não foi escolhido como padrão funcional. Para usá-lo, configure preços USD 0,75/1M entrada e USD 4,50/1M saída. `OPENAI_REASONING_EFFORT=medium` é aplicado apenas a modelos GPT-5; não é enviado ao GPT-4.1.

Chamadas com resultado de cobrança incerto preservam a reserva. Respostas incompletas nunca são rotuladas como concluídas. Resultados e IDs são salvos em `data/research/`; páginas externas são entradas não confiáveis e não recebem credenciais nem ferramentas de execução.
