# Segurança — Pastéis Miyata

**Versão dos controles:** `seguranca-v1`

## Escopo

O agente consulta o MySQL, recupera documentos locais, usa memória SQLite e registra planos após aprovação humana. Os testes de segurança são locais, com modelo simulado e armazenamento temporário; não exercitam sistemas de terceiros.

Os pontos de código foram conferidos no commit `d76c6cc`. Os controles reduzem efeitos indevidos, mas não garantem correção de todo texto produzido nem conformidade legal.

## 1. Canais de conteúdo não confiável

| Canal | Conteúdo recebido | Fronteira de segurança |
|---|---|---|
| Entrada do proprietário | Texto livre, inclusive formatos reconhecidos de credenciais | Contrato de entrada e filtro de credenciais |
| Corpus | Regras, exemplos e possíveis instruções | Documento é evidência, não autorização |
| MySQL | Valores estruturados e campos livres do cadastro | Consultas parametrizadas, definidas no código |
| Modelo | Texto, JSON, nomes de ferramentas e argumentos | Catálogo fechado e validação estrita |
| Memória semântica | Preferência atual e versões anteriores | Chave e valores previstos; autorização no pedido atual |
| Memória episódica | Metadados de planos e registros legados | Validação na escrita e na leitura |
| Checkpoint | Mensagens, proposta e aprovação pendente | Conferência da identidade técnica e bloqueio de troca da proposta |

Não há ferramentas para executar shell ou Python arbitrário, ler `.env`, consultar variáveis de ambiente, enviar dinheiro ou modificar diretamente o histórico operacional do MySQL.

## 2. Riscos do case

Escala de impacto: **3** para escrita persistente ou ação indevida relevante; **2** para resposta ou operação degradada; **1** para exposição limitada pelas capacidades atuais. Os números classificam impacto no case, não probabilidade.

| Risco | Ponto de código | Cenário | Impacto | Tratamento |
|---|---|---|---:|---|
| ASI02 — uso indevido de ferramenta | [`src/graph.py:542`](../src/graph.py#L542); [`src/seguranca.py:231`](../src/seguranca.py#L231) | O modelo escolhe ferramenta não declarada ou passa argumentos não permitidos | 3 | C1: catálogo e argumentos fechados |
| ASI06 — envenenamento de memória | [`src/memory.py:140`](../src/memory.py#L140), [`:266`](../src/memory.py#L266); [`src/graph.py:1019`](../src/graph.py#L1019) | Instruções de um documento ou de uma resposta tentam persistir para outros turnos | 3 | C2: memória mínima e autorização explícita |
| ASI09 — exploração da confiança humano-agente | [`src/graph.py:690`](../src/graph.py#L690); [`src/agent.py:40`](../src/agent.py#L40) | O modelo afirma ter aprovação ou tenta substituir o plano durante a pausa | 3 | C3: aprovação vinculada à conversa |
| ASI01 — sequestro de objetivo | [`src/graph.py:399`](../src/graph.py#L399); [`src/rag.py:533`](../src/rag.py#L533) | Instrução em documento recuperado desvia a resposta | 2 | Efeito limitado pelos controles; risco residual aceito |
| ASI03 — abuso de identidade e privilégio | [`src/agent.py:40`](../src/agent.py#L40); [`src/database.py:60`](../src/database.py#L60) | Uma chamada tenta retomar thread alheia; quem tem acesso ao host pode tentar operar fora do fluxo | 2 | Verificação de identidade e thread; sem autenticação de rede |
| ASI08 — propagação de falha | [`src/graph.py:542`](../src/graph.py#L542), [`:612`](../src/graph.py#L612) | Falha de consulta pode ser interpretada como confirmação em etapa posterior | 2 | Desfechos estruturados, validação e orçamento |
| ASI10 — agente desgovernado | [`src/graph.py:351`](../src/graph.py#L351) | Repetição de chamadas esgota recursos | 2 | Orçamentos e detector de laço |
| ASI04 — cadeia de suprimentos | [`requirements.txt:1`](../requirements.txt#L1); [`src/graph.py:399`](../src/graph.py#L399) | Alteração em dependência, prompt ou documento modifica o comportamento | 1 | Versões diretas fixadas; auditoria transitiva pendente |

ASI07 não se aplica ao grafo de um único agente sem comunicação entre agentes. ASI05 não corresponde a uma ferramenta exposta: o modelo não tem ação de execução arbitrária de código. Os três riscos de impacto 3 têm controles fora do prompt e testes próprios.

## 3. Controles fora do prompt

### C1 — catálogo e argumentos fechados

[`validar_argumentos`](../src/seguranca.py#L231) e [`validar_lote_chamadas`](../src/seguranca.py#L283) são aplicadas antes do executor. A validação bloqueia ferramenta desconhecida, JSON que não é objeto, chaves duplicadas, `NaN` e `Infinity`, argumentos acima de 8.192 bytes, campos extras, tipos incompatíveis, limite de histórico fora de 1–10 e múltiplas ferramentas na mesma decisão. O executor não converte `"101"` em inteiro. Mensagens de erro não repetem argumentos rejeitados; os erros de provedor registram a classe da exceção, não seu corpo livre.

**Teste:** `test_argumento_sql_nao_chega_a_ferramenta`, `test_ferramenta_nao_declarada_nao_executa_codigo`, `test_duas_ferramentas_na_mesma_decisao_nao_tem_efeito_parcial` e `test_erro_do_provedor_nao_reproduz_credencial_no_log`.

**Custo funcional:** perde coerções automáticas e chamadas em lote. Novas ferramentas exigem atualização do catálogo e de seu contrato. **Falha:** fail-closed; a ferramenta não é executada.

### C2 — memória mínima e preferência autorizada

A validação permite somente `prioridade=reduzir sobra` ou `prioridade=evitar falta`, com [autorização explícita no turno](../src/seguranca.py#L342). Um trecho de RAG ou uma afirmação do modelo não concede essa permissão.

A memória episódica aceita somente tipo, feira, total e contagem de operações quando houver plano verificável e saída conclusiva do turno. Pedido original, resposta livre, nomes de produtos, instruções externas e tags livres não são copiados. A [escrita semântica](../src/memory.py#L140) e a [escrita episódica](../src/memory.py#L266) validam os dados; a leitura ignora registros legados incompatíveis sem apagá-los. O hash serve à consistência e à idempotência, não à autenticação.

**Teste:** `test_instrucao_no_documento_nao_autoriza_preferencia`, `test_valor_diferente_do_pedido_nao_e_salvo`, `test_preferencia_arbitraria_nao_chega_ao_sqlite`, `test_episodio_nao_copia_pedido_nem_texto_do_modelo` e `test_episodio_legado_livre_nao_reentra_no_contexto`.

**Custo funcional:** perde preferências arbitrárias e resumos narrativos ricos. **Falha:** fail-closed; entrada incompatível não é escrita nem recuperada para o contexto. Isso não remove dados de checkpoints, logs ou registros antigos.

### C3 — aprovação vinculada à conversa

A [fachada](../src/agent.py#L40) confere identidade, conversa e checkpoint. Outro turno não pode substituir a proposta pendente. O [nó de aprovação](../src/graph.py#L690) valida o plano e exige uma decisão humana válida depois da pausa. Um campo `aprovado` produzido pelo modelo não autoriza a gravação e o executor comum não pode registrar planos.

A edição humana modifica apenas o resumo. Validade do plano, correspondência da aprovação, prazo e chave de idempotência são conferidos antes da escrita. Identidade inválida, checkpoint indisponível, decisão inválida, rejeição ou vencimento não autorizam gravar.

**Teste:** `test_aprovacao_falsa_em_argumento_nao_grava_nem_abre_pausa`, `test_executor_comum_nao_substitui_o_no_humano`, `test_turno_novo_nao_troca_plano_durante_a_pausa`, `test_edicao_humana_nao_pode_incluir_quantidades` e `test_prazo_vencido_nao_grava_o_plano`.

**Custo funcional:** exige intervenção humana, impede trocar quantidades pela edição do resumo e suspende novos turnos na conversa enquanto a decisão está pendente. **Falha:** fail-closed; não escreve sem a cadeia de validação.

## 4. Dados e credenciais

[`validar_texto_sem_credenciais`](../src/seguranca.py#L159) bloqueia formatos reconhecidos de senha, chave de API, Bearer token e chave privada. O filtro é aplicado antes do checkpoint da [entrada](../src/agent.py#L188) e na [edição do resumo](../src/agent.py#L256). Não é um detector universal de dados pessoais, credenciais ou texto ofuscado.

### Fluxos e retenção

| Lugar | Dado e finalidade | Destino e acesso | Guarda |
|---|---|---|---|
| Entrada e prompt | Solicitação, identidade técnica e contexto necessário | Checkpoint local; parte segue ao provedor na chamada do modelo | Prazo local e condições no provedor a confirmar |
| MySQL e corpus | Produção, vendas, regras e textos livres usados na recuperação | Banco e arquivos administrados pelo proprietário; trechos selecionados podem entrar no prompt | Política a confirmar; revisar campos livres antes do uso |
| Memórias semântica e episódica | Preferência permitida e metadados de planos | SQLite local, sob permissões do sistema operacional | Sem eliminação automática; decaimento não apaga registros |
| Planos aprovados | Produtos, quantidades, resumo aprovado e IDs técnicos | SQLite local; escrita condicionada à decisão humana | Prazo e tratamento do resumo a definir |
| Checkpoint e log de execução | Mensagens, ferramentas e estado para retomar e diagnosticar | Arquivos locais com acesso pelas permissões do sistema | Formalizar retenção e revisar campos persistidos |
| Trace OpenTelemetry | Campos estruturados e referências de auditoria | JSONL local; somente extrato sanitizado versionado | Até 30 dias como proposta, sem eliminação automática |
| Provedor externo | Mensagens e retornos selecionados para interpretar o pedido e compor a resposta | Conta e provedor configurados | Confirmar as condições e o prazo efetivos da conta |

O fluxo não precisa de um cadastro de clientes, mas o texto livre pode conter dados pessoais. Quando houver tratamento de dados pessoais, o responsável precisa validar a base aplicável e o prazo de guarda. Não se declara conformidade legal nem ausência absoluta de dados pessoais no projeto.

## 5. Riscos residuais aceitos

No uso local e supervisionado, admite-se que conteúdo recuperado possa influenciar indevidamente uma resposta textual (ASI01). C1, C2 e C3 bloqueiam ações fora dos contratos, mas não provam que toda resposta esteja correta. O proprietário revisa o resultado antes da produção.

Também permanece a dependência das permissões do host. Quem pode alterar arquivos, SQLite ou código não está isolado por `AGENT_USER_ID`, que é uma identidade técnica, não autenticação de rede. Reavaliar antes de expor HTTP/MCP, permitir múltiplos usuários, usar corpus de terceiros sem curadoria ou habilitar escrita externa automática.

## 6. Evidências executadas

Os testes foram executados em cópia limpa de `d76c6cc`, com Python 3.12 no Linux e dependências de `requirements.txt`. Os testes de segurança usam modelo simulado e SQLite temporário ou em memória.

```powershell
python.exe -m unittest discover -s tests -p "test_seguranca*.py" -v
python.exe -m unittest discover -s tests -v
```

| Conjunto | Resultado |
|---|---:|
| Testes de controles e integração | 39 aprovados |
| Suíte completa, incluindo os 39 acima | 105 aprovados |

Os testes dos controles estão em [`tests/test_seguranca_grafo.py`](../tests/test_seguranca_grafo.py) e [`tests/test_seguranca.py`](../tests/test_seguranca.py).

A [comparação regressão × segurança](../evals/resultados/comparacao-regressao-seguranca-v1.json) manteve **20/20** nos dois lados, com o mesmo dataset, modelo e snapshot. Isso demonstra que não houve regressão observada nos 20 casos; não prova ausência de vulnerabilidades.

## 7. Auditoria do histórico publicado

A auditoria foi feita em clone completo das referências publicadas, com `origin/main` em `d76c6cc` e a branch publicada da Parte 2. Foram inspecionadas 16 árvores de commits alcançáveis.

```powershell
git log --all -- .env
git log --all -S "OPENAI_API_KEY=" --oneline
git ls-files -- .env dados/checkpoints.sqlite3 dados/memoria.sqlite3
```

O primeiro e o terceiro comandos não retornaram linhas. A busca pela atribuição da variável retornou:

```text
d76c6cc feat: implementar avaliacao, seguranca e observabilidade da parte 3
eb1a5e7 add docker e como executar
b393c2e add: Trabalho 01 - Proposta de Agente
```

As ocorrências são o comando de auditoria, exemplos de configuração, campos vazios e valores fictícios de teste. A busca complementar por formato longo de chave encontrou somente um valor de teste em `tests/test_seguranca.py`. Não foi identificada chave real nessas verificações. A auditoria não cobre cópias e branches locais não publicadas, nem garante a detecção de todo tipo de segredo.

Se uma credencial real for descoberta, revogue-a ou rotacione-a no provedor. Alterar o histórico Git não invalida uma credencial.

## 8. Limites remanescentes

- A conta de leitura da avaliação não comprova os privilégios da conta operacional. Verifique-os no ambiente responsável, sem publicar a credencial.
- A base aplicável aos dados, os prazos de guarda e o procedimento de exclusão precisam ser formalizados.
- Traces não substituem os logs operacionais. Veja o [plano de observabilidade](observabilidade.md) e a [reconstrução da aprovação no model card](model-card.md#11-registro-e-retenção).