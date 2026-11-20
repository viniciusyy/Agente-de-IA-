# Histórico de mudanças

## Versões registradas no Git

| Entrega | Commit | Mudança |
|---|---|---|
| Parte 2 | [`00bab35`](https://github.com/viniciusyy/Agente-de-IA-/commit/00bab3576c181c4ea08360a37714eb49d9ad94b3) | Agente LangGraph com RAG, memória, estado, aprovação humana e ferramentas determinísticas. |
| Evidências da Parte 2 | [`9bef2ed`](https://github.com/viniciusyy/Agente-de-IA-/commit/9bef2edf66f055582eae88a00b124a54f25ba683) | Publicação dos seis casos oficiais, contratos, prompts e exemplos reais. |
| Demonstração | [`eb1a5e7`](https://github.com/viniciusyy/Agente-de-IA-/commit/eb1a5e7a9c6fd698fa0bbb1ea403c7f87b2c5881) | Docker Compose para executar o agente com banco de demonstração separado do operacional. |
| Parte 3 | [`d76c6cc`](https://github.com/viniciusyy/Agente-de-IA-/commit/d76c6cc1fb4d8e8eb4402b46045bdf44a9f4f653) | Correções funcionais, suíte, controles de segurança, instrumentação GenAI e publicação dos resultados. |

## Correções verificadas

As rodadas da Parte 3 detectaram os problemas abaixo. As correções foram reunidas em `d76c6cc`. Os hashes de código das rodadas identificam os snapshots intermediários testados.

| Caso | Problema observado | Correção | Evidência |
|---|---|---|---|
| GD02 e GD10 | A regra de feira nem sempre era recuperada antes de responder sobre restrições ou calendário. | Rota com busca no corpus, identificação do documento vigente e recusa se o trecho não sustentar a decisão. | [`src/regras_feira.py`](../src/regras_feira.py) e [testes do grafo](../tests/test_aprovacao_grafo.py). |
| GD14 | Capacidade total zero podia disparar um cálculo indevido. | Validação determinística antes de chamar o modelo ou calcular. | [`src/capacidade.py`](../src/capacidade.py) e [testes de capacidade](../tests/test_capacidade.py). |
| GD06 e GD19 | A redação podia omitir os dados do plano; o encerramento da rejeição dependia de outra decisão do modelo. | Preservação dos dados calculados no turno e resposta determinística após rejeição, sem gravação. | [`src/graph.py`](../src/graph.py) e [testes de aprovação](../tests/test_aprovacao_grafo.py). |
| GD08 | O texto final podia não preservar os totais solicitados de uma operação. | Consolidação dos totais com os dados estruturados da consulta. | [`src/domain.py`](../src/domain.py) e [teste dos totais](../tests/test_aprovacao_grafo.py#L213). |
| GD11 | A interpretação de sobra zero podia ser recusada sem consultar o glossário. | Rota apoiada em trecho vigente: sobra zero não prova falta nem perda de venda. | [`src/glossario.py`](../src/glossario.py) e [testes do glossário](../tests/test_glossario.py). |

No [comparativo das rodadas completas](../evals/resultados/comparacao-baseline-final.json), GD02, GD10, GD14 e GD19 passaram de falha a aprovação. O total foi de 16/20 para 20/20. As outras correções também foram verificadas em rodadas focadas; elas não são contadas como ganhos extras sobre o baseline.

## Controles e observabilidade

- **Segurança:** contrato fechado de ferramenta, memória restrita e aprovação vinculada à conversa. O [comparativo após os controles](../evals/resultados/comparacao-regressao-seguranca-v1.json) mostra 20/20 antes e depois nos casos da suíte.
- **Observabilidade:** spans GenAI, exportação local, versão e motivo de término. O [plano e os resultados](observabilidade.md) documentam 52 raízes da mesma versão. O [extrato do GD06](trace-aprovacao.json) sustenta a reconstrução da decisão no [model card](model-card.md).

A revisão documental não altera as ferramentas, o método de produção, os prompts, as bases operacionais nem os resultados registrados.