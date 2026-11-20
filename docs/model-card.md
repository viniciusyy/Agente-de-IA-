# Model card — Agente de Planejamento da Pastéis Miyata

## 1. Identificação

Agente de planejamento de produção da Pastéis Miyata, desenvolvido em Python com LangGraph e usado por terminal. O identificador `obs-v1-9393b1db60fb` contém o prefixo da impressão digital do código executado na coleta; não é um hash de commit Git.

## 2. Finalidade

Apoiar o proprietário na consulta ao histórico, na interpretação de regras das feiras e na preparação de recomendações. O modelo interpreta o pedido e seleciona ferramentas; a consulta e o cálculo das quantidades ocorrem fora do modelo.

A recomendação usa a média das vendas das cinco operações recentes da feira. Não executa o modelo definitivo de previsão nem a otimização por Simplex do TCC. A decisão de produção é do proprietário.

## 3. Autoridade

O agente pode consultar dados e regras, calcular recomendações, persistir a preferência operacional permitida e solicitar o registro local de planos. Não pode comprar insumos, contatar fornecedores, realizar pagamentos nem iniciar a produção.

| Limite | Aplicação | Evidência |
|---|---|---|
| Aceitar apenas ferramentas e argumentos previstos | Contrato em [`src/seguranca.py`](../src/seguranca.py#L231) e validação antes do executor | `test_ferramenta_nao_declarada_nao_executa_codigo` e `test_duas_ferramentas_na_mesma_decisao_nao_tem_efeito_parcial` |
| Consultar MySQL sem executar SQL gerado pelo modelo | Consultas definidas em [`src/database.py`](../src/database.py); `evals/referencias_mysql.py` verifica a conta da suíte | `test_argumento_sql_nao_chega_a_ferramenta`. A conta da suíte não comprova os privilégios da conta operacional |
| Salvar somente preferência explicitamente autorizada | [`autorizar_preferencia`](../src/seguranca.py#L342) e contrato da chave `prioridade` | `test_instrucao_no_documento_nao_autoriza_preferencia` e `test_valor_diferente_do_pedido_nao_e_salvo` |
| Exigir aprovação para todo registro de plano | [`aprovar_plano`](../src/graph.py#L690) valida o plano e pausa; o executor comum não grava | [Trace do GD06](trace-aprovacao.json) e `test_executor_comum_nao_substitui_o_no_humano` |
| Impedir troca do plano durante a pausa e retomada por outra identidade | A fachada verifica usuário, conversa e checkpoint | `test_turno_novo_nao_troca_plano_durante_a_pausa`, `test_outro_usuario_nao_retoma_uma_aprovacao` e `test_falha_na_leitura_do_checkpoint_e_fail_closed` |
| Limitar esforço de uma execução | `src/config.py` e [`_verificar_orcamento`](../src/graph.py#L351). Padrões: 10 passos, 8 ferramentas, 12.000 tokens, 90 s e US$ 0,15 estimados | `test_limite_de_ferramentas_tambem_bloqueia_o_no_de_aprovacao`. O custo estimado não é teto de cobrança do provedor |
| Impedir compras, pagamentos e produção física | Não há ferramentas para essas ações | Catálogo do grafo e [limites do agente](../dados/corpus/05_limites_sistema.md) |

Os testes de bloqueio estão em [`tests/test_seguranca_grafo.py`](../tests/test_seguranca_grafo.py). O proprietário pode encerrar a sessão. Encerrar não apaga o checkpoint; uma aprovação pendente pode reaparecer quando retomada pela mesma identidade e conversa. `AGENT_USER_ID` é uma identidade técnica local, não autenticação de rede nem prova de identidade civil.

## 4. Ferramentas e integrações

| Ferramenta | Integração e efeito |
|---|---|
| `consultar_historico` | Lê operações recentes de uma feira no MySQL |
| `consultar_operacao` | Lê a operação identificada e consolida os totais |
| `buscar_conhecimento` | Recupera regras e definições do corpus local |
| `calcular_recomendacao` | Calcula o baseline e aplica as restrições do domínio |
| `salvar_preferencia` | Persiste a preferência permitida no SQLite após autorização |
| `registrar_plano` | Persiste no SQLite após decisão válida, com idempotência |

O grafo usa checkpoint SQLite para retomar conversas. A suíte cria memória e checkpoint temporários por caso. Uma escrita da suíte não é uma escrita no ambiente operacional.

## 5. Modelo e provedor

A versão avaliada usou `gpt-5.6-luna`. No GD06, os spans registraram `openai` como provedor e o mesmo modelo como solicitado e retornado. Os hashes de `orquestrador_v2` e `procedimento_planejamento_v1` aparecem no [extrato do trace](trace-aprovacao.json).

O modelo não executa diretamente consultas, não calcula as quantidades do plano e não autoriza sua própria escrita.

## 6. Avaliação

As duas rodadas de `obs-v1-9393b1db60fb` usaram o dataset `1.0.0` e o snapshot `c7f695afd8f7`.

| Evidência | Resultado |
|---|---:|
| [Rodada 1](../evals/resultados/obs-v1-9393b1db60fb-20261119T005315581767Z/resultado.json) | 20/20 casos aprovados |
| [Rodada 2](../evals/resultados/obs-v1-9393b1db60fb-20261119T005640561234Z/resultado.json) | 20/20 casos aprovados |
| [Resumo de observabilidade](../evals/resultados/obs-v1-9393b1db60fb-resumo.json) | 52 raízes; p95 de 5,899 s; SLI de 46/46 elegíveis |

Foram 40 avaliações dos mesmos 20 casos, não 40 cenários distintos. O verificador mede o comportamento esperado nesses casos; o SLI mede a qualidade do término, incluindo recusas e esclarecimentos adequados. Os números não demonstram desempenho contínuo em produção. Veja [critérios e comparações](evals.md).

**LACUNA:** essas rodadas não são evidência de adoção do juiz LLM. A matriz de concordância, o limiar e a análise dos desacordos são evidências separadas da suíte automática.

## 7. Dados

O MySQL contém histórico de feiras, produtos, operações, produção, vendas e sobras. O snapshot avaliado tinha 138 operações e 3.634 registros. O corpus contém regras e definições locais.

A memória semântica guarda a preferência permitida. A episódica guarda metadados de planos verificáveis. Checkpoints e logs são armazenamentos distintos e podem conter mais contexto que os traces sanitizados. Quando há chamada ao modelo, as mensagens e o contexto necessários são enviados ao provedor.

**LACUNA:** o fluxo não exige cadastro de clientes, mas texto livre pode conter dados pessoais. A classificação, a base aplicável ao tratamento e a retenção no provedor precisam de validação pelo responsável. Consulte [Segurança](seguranca.md). Este cartão não declara conformidade legal.

## 8. Limites conhecidos

- O baseline usa vendas observadas, não mede perdas por falta e não é um plano ótimo.
- A produção de uma resposta no formato correto não garante que toda afirmação em texto livre esteja correta.
- As medidas de latência, custo e qualidade vêm de duas rodadas em uma janela curta.
- A edição humana permite alterar o resumo, não substituir as quantidades validadas.

## 9. Riscos aceitos

No uso local e supervisionado, admite-se o risco residual de conteúdo recuperado influenciar uma resposta textual (ASI01). O catálogo fechado, os contratos, a memória restrita e a aprovação humana limitam os efeitos, mas não eliminam respostas incorretas. Também permanece a dependência das permissões do computador.

As evidências estão nos [riscos residuais aceitos](seguranca.md#5-riscos-residuais-aceitos) e nos [testes de bloqueio](../tests/test_seguranca_grafo.py). Reavaliar antes de expor o agente em rede, incluir outros usuários ou permitir escrita externa automática.

## 10. Supervisão humana

O proprietário pode aprovar, rejeitar ou registrar com edição do resumo. A pausa apresenta a proposta antes de qualquer gravação. Rejeição, decisão inválida ou expiração não autorizam a escrita. O prazo padrão é de 24 horas a partir do início do turno que solicita o registro.

Na suíte, a decisão roteirizada percorre o mesmo mecanismo. Isso testa o fluxo e o efeito da decisão, não o comportamento ou o tempo de uma pessoa ao vivo.

## 11. Registro e retenção

### Reconstrução do GD06 a partir do trace

O [extrato sanitizado](trace-aprovacao.json) foi gerado por `scripts/extrair_evidencia_aprovacao.py` a partir dos spans da rodada 1 da coorte `avaliacao`. O identificador da aprovação tem prefixo `abc5098a97ce`. As horas abaixo são de **18/11/2026, no fuso de São Paulo**; os carimbos no JSON estão em UTC.

| Horário | Evidência | Interpretação |
|---|---|---|
| `21:51:37.647124` | `calcular_recomendacao` para `QUA`, trace `0x61ff95d251c6c9b84b5a4e73a09cca01` | O baseline de cinco operações retornou 518 unidades. |
| `21:51:42.150235` | `aprovacao.solicitada`, trace `0x4f70e51bea9b0afdd002e7e3ab8601bd` | A proposta com os mesmos 27 itens ficou pendente. O turno terminou em `AGUARDANDO_APROVACAO`, sem tentativa de escrita. |
| `21:51:42.167696` | `aprovacao.decidida`, ação `editar`, identidade técnica de prefixo `064850df4c7b` | A decisão roteirizada chegou antes do vencimento e apontou para a mesma aprovação. |
| `21:51:42.167774` | Início do span `registrar_plano` | A escrita só foi tentada depois da decisão. Preservou `QUA` e o total 518. |
| `21:51:42.171440` | `aprovacao.escrita`, trace `0xaf290634378e816c3996281e4888b967` | `ok`, `registro_id=1`, `ja_existia=false`; a retomada terminou em `CONCLUIDO` sem normalização. |

A evidência da gravação é o evento junto ao resultado da ferramenta, não a mensagem do modelo. O registro pertence ao SQLite temporário do caso. O extrato confirma a igualdade dos itens entre cálculo e proposta e da feira e do total na escrita; não expõe a lista de produtos, o resumo editado nem o pedido literal. Os três traces têm a mesma versão, o mesmo modelo e os mesmos hashes de prompts. Não houve documento RAG nem dado de memória recuperado nas etapas selecionadas.

### Acesso e guarda

Os traces brutos permanecem em `logs/traces/` e têm acesso condicionado às permissões do sistema operacional. Não são versionados. O repositório contém apenas o [extrato sanitizado](trace-aprovacao.json) para esta auditoria. Veja [Uso dos traces](uso_traces.md).

**LACUNA:** a guarda operacional de até 30 dias é proposta, sem exclusão automática. Checkpoints, memória e logs de execução têm ciclos de vida próprios.

## 12. Histórico de mudanças

A Parte 2 implementou grafo, RAG, memória, checkpoint e aprovação humana. A Parte 3 acrescentou os controles de segurança, a suíte e a instrumentação de observabilidade no commit [`d76c6cc`](https://github.com/viniciusyy/Agente-de-IA-/commit/d76c6cc1fb4d8e8eb4402b46045bdf44a9f4f653). Os commits e as correções verificadas estão no [histórico de mudanças](mudancas.md).

## Lacunas e encaminhamentos

| Lacuna | Encaminhamento |
|---|---|
| Privilégios da conta operacional não comprovados pela suíte | Verificar e documentar somente os privilégios, sem publicar a credencial |
| Adoção do juiz não comprovada pelas rodadas | Manter a evidência da suíte separada de uma eventual validação do juiz |
| Classificação, tratamento e retenção de dados não formalizados | Revisar os fluxos e a conta do provedor com o responsável |
| Retenção dos traces sem exclusão automática | Definir e verificar procedimento de revisão e remoção periódica |