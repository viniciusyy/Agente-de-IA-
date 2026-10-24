# Exercício 14 — Os Dez Riscos de Segurança no Agente da Pastéis Miyata

## 1. Os dez riscos no case

### Contexto do sistema analisado

O agente da Pastéis Miyata é utilizado exclusivamente pelo proprietário para consultar dados históricos, obter recomendações de produção, recuperar regras do negócio e registrar planos aprovados.

A versão atual utiliza Python, LangGraph, MySQL, RAG textual e memória persistente em SQLite. O LLM interpreta solicitações e escolhe ferramentas, enquanto os cálculos são realizados por código determinístico. O registro de um plano depende de uma interrupção para aprovação humana.

Os principais canais de entrada de conteúdo não confiável são as mensagens do usuário, os campos textuais retornados pelo MySQL, os documentos Markdown do RAG e as memórias recuperadas. Um atacante precisaria conseguir controlar algum desses canais, por exemplo por acesso indevido ao terminal, comprometimento de documentos ou alteração de registros operacionais.

Os cenários descritos são hipóteses de ameaça, não ataques comprovadamente executados. As mitigações distinguem controles já existentes de melhorias propostas.

### ASI01 — Sequestro de objetivo do agente

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/graph.py:460-553` (montagem do contexto e chamada ao LLM), `src/graph.py:948-956` (retorno das ferramentas) e `src/rag.py:457-484` (documentos recuperados). |
| **Cenário de ataque** | Uma pessoa com acesso indevido à edição das observações do MySQL insere um texto dizendo que o agente deve abandonar a consulta solicitada e informar uma regra diferente. Quando o proprietário consulta a operação, o texto chega como resultado da ferramenta e pode ser interpretado pelo LLM como instrução. |
| **Impacto** | **1 —** Uma resposta incorreta pode prejudicar o planejamento daquela execução, mas o cenário considerado não envolve escrita nem exposição de dados pessoais. |
| **Mitigação** | **Minimização de contexto e separação entre dados e instruções.** Proposta: reduzir os campos textuais enviados ao modelo e tratar observações recuperadas exclusivamente como dados. Os cálculos e regras obrigatórias devem permanecer no código, em `src/graph.py` e `src/domain.py`. |

### ASI02 — Uso indevido e exploração de ferramenta

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/graph.py:744-802` (despacho de ferramentas), `src/graph.py:973-1140` (registro com aprovação) e `src/memory.py:405-475` (persistência de planos). |
| **Cenário de ataque** | Após alterar um documento recuperado, um atacante insere instruções para o agente utilizar um plano antigo e solicitar seu registro como se fosse o planejamento atual. O proprietário recebe a solicitação de aprovação e pode confirmar o plano inadequado. |
| **Impacto** | **3 —** Um registro formal de plano aprovado pode permanecer no sistema e influenciar uma decisão real de produção. |
| **Mitigação** | **Menor privilégio por ferramenta, validação dos argumentos e confirmação humana inescapável por prompt.** O código já limita as ferramentas disponíveis e exige aprovação. Como melhoria, o registro deverá conferir `usuario_id`, `thread_id`, identificador do plano e vínculo com a solicitação autorizada antes de persistir a decisão. |

### ASI03 — Abuso de identidade e privilégio

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/agent.py:321-341` (identificação de usuário e conversa), `src/agent.py:397-445` (retomada da aprovação) e `src/config.py` (configuração de identidade e credenciais). |
| **Cenário de ataque** | Uma pessoa não autorizada consegue acesso ao computador onde o agente está instalado e utiliza a identidade configurada do proprietário. Como a versão de terminal não possui autenticação independente do sistema operacional, essa pessoa pode consultar informações internas e tentar interagir com uma aprovação pendente. |
| **Impacto** | **2 —** Existe possibilidade de exposição de informações internas da pastelaria a uma pessoa não autorizada. |
| **Mitigação** | **Credencial delegada, menor privilégio e autorização fora do LLM.** Na versão local, restringir acesso ao computador, arquivos e bancos. Antes de disponibilizar uma API ou interface remota, implementar autenticação real e verificar a autorização do usuário antes de executar ou retomar operações. Um identificador informado pelo cliente não deve ser considerado prova de identidade. |

### ASI04 — Cadeia de suprimentos agêntica

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `requirements.txt:1-7`, que define as dependências Python, e `src/graph.py:490-553`, que utiliza o cliente do provedor de LLM. A versão atual ainda não possui um servidor MCP próprio. |
| **Cenário de ataque** | Um invasor compromete uma versão de uma biblioteca utilizada pelo projeto ou sua distribuição. Quando o ambiente é instalado ou atualizado, a dependência maliciosa é executada com as permissões do processo e pode acessar informações internas ou alterar arquivos persistentes. |
| **Impacto** | **3 —** Uma dependência comprometida poderia modificar dados persistidos ou executar operações fora das restrições do agente, afetando o funcionamento completo da instalação. |
| **Mitigação** | **Versões fixadas, verificação de integridade e menor privilégio do processo.** O `requirements.txt` já fixa versões. Como melhorias, verificar vulnerabilidades, conferir a procedência das dependências, utilizar hashes de pacotes e executar o agente com apenas as permissões necessárias. Futuras ferramentas MCP deverão ter sua origem e permissões verificadas. |

### ASI05 — Execução inesperada de código

| Campo | Resposta |
|---|---|
| **Existe no case?** | Não aplicável. |
| **Onde** | |
| **Cenário de ataque** | |
| **Impacto** | |
| **Mitigação** | |

A versão analisada não oferece ao LLM uma ferramenta de execução arbitrária de Python, shell ou comandos produzidos dinamicamente. As operações disponíveis correspondem a funções Python previamente definidas.

### ASI06 — Envenenamento de memória e de contexto

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/memory.py:138-246` (memória semântica), `src/memory.py:248-301` (memória episódica), `src/graph.py:335-356` (recuperação) e `src/graph.py:503-523` (inclusão da memória no contexto do LLM). |
| **Cenário de ataque** | Uma pessoa com acesso indevido à interface consegue induzir o agente a salvar uma preferência operacional falsa, como a alteração permanente da prioridade de produção. A informação é gravada no SQLite e recuperada em conversas futuras, podendo influenciar explicações e decisões apresentadas ao proprietário. |
| **Impacto** | **3 —** Uma preferência contaminada pode persistir entre execuções e contribuir para a aprovação e o registro de um planejamento inadequado. |
| **Mitigação** | **Menor privilégio de escrita, validação da origem e minimização de contexto.** A memória já diferencia fatos semânticos e episódios, mas é necessário impedir que conteúdo proveniente de documentos ou ferramentas seja promovido automaticamente a uma preferência autorizada. Alterações estáveis devem exigir confirmação explícita do proprietário e possuir histórico de versões, origem e mecanismo de revogação. |

### ASI07 — Comunicação insegura entre agentes

| Campo | Resposta |
|---|---|
| **Existe no case?** | Não aplicável. |
| **Onde** | |
| **Cenário de ataque** | |
| **Impacto** | |
| **Mitigação** | |

Atualmente, existe um único agente orquestrador utilizando nós do LangGraph e ferramentas Python. Esses nós não representam agentes autônomos que trocam mensagens ou realizam handoffs entre si.

Caso a arquitetura passe a utilizar subagentes ou comunicação por protocolos entre agentes, esse risco deverá ser reavaliado.

### ASI08 — Falhas em cascata

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/graph.py:805-917` (tratamento dos retornos das ferramentas), `src/graph.py:1258-1386` (validação da saída) e `src/database.py:355-363` (erro na consulta MySQL). |
| **Cenário de ataque** | Um atacante com acesso ao ambiente provoca uma indisponibilidade do MySQL durante o planejamento. A ferramenta retorna erro, mas o LLM pode tentar continuar a conversa utilizando informações incompletas e apresentar uma conclusão como se a consulta tivesse sido realizada. |
| **Impacto** | **1 —** A resposta incorreta pode comprometer uma execução, exigindo nova consulta e correção do planejamento. |
| **Mitigação** | **Falha segura, validação determinística e interrupção controlada.** O sistema já transforma erros das ferramentas em resultados estruturados. Como melhoria, falhas em fontes obrigatórias devem bloquear a conclusão operacional e impedir o registro de um plano que dependa dos dados indisponíveis. |

### ASI09 — Exploração da confiança humano-agente

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/graph.py:1037-1066` (dados apresentados para aprovação), `src/main.py:65-111` (interface de decisão humana) e `src/graph.py:1133-1140` (registro após aprovação). |
| **Cenário de ataque** | Um atacante consegue influenciar o texto utilizado no resumo de um plano e faz com que ele descreva uma recomendação inadequada como segura e rotineira. O proprietário, confiando na explicação do agente sem conferir as quantidades e restrições, aprova o registro. |
| **Impacto** | **3 —** O proprietário pode aprovar um plano operacional incorreto, produzindo um registro persistente e uma possível decisão de produção prejudicial. |
| **Mitigação** | **Confirmação humana inescapável por prompt e apresentação independente dos dados críticos.** O LangGraph já exige uma aprovação antes da escrita. A melhoria proposta é gerar a tela de confirmação diretamente dos valores validados pelo código, destacando feira, quantidades, restrições e consequência do registro, sem depender da descrição livre produzida pelo LLM. |

### ASI10 — Agentes desgovernados

| Campo | Resposta |
|---|---|
| **Existe no case?** | Sim. |
| **Onde** | `src/graph.py:367-407` (orçamento de execução), `src/graph.py:460-690` (chamadas ao modelo) e `.env.example:29-40` (limites configuráveis). |
| **Cenário de ataque** | Uma pessoa que tenha acesso ao terminal envia uma solicitação extensa e repetitiva, procurando fazer o agente executar muitas consultas e chamadas ao LLM sem concluir a tarefa. Isso pode consumir tempo, recursos e créditos da API. |
| **Impacto** | **1 —** O prejuízo considerado é financeiro e operacional, reversível e limitado à execução pelos tetos existentes, sem envolver dados pessoais. |
| **Mitigação** | **Teto de gasto, limite de ferramentas, detector de laços e condição de término.** O sistema já possui limites de passos, chamadas, tokens, tempo e custo. A versão atual ainda não possui uma cota acumulada de consumo para todas as execuções de um dia. |

## 2. Um risco aceito, declarado

### Risco aceito — ASI10: consumo acumulado entre execuções

O risco aceito é a possibilidade de consumo excessivo de créditos da API por meio de várias solicitações independentes.

A decisão é **não implementar, nesta versão acadêmica, uma cota diária global de utilização**, embora já existam limites individuais para cada execução.

**Por que foi aceito:** o sistema é um protótipo local utilizado exclusivamente pelo proprietário. Uma restrição diária poderia interromper testes, demonstrações e atividades de desenvolvimento que precisam executar diversos casos consecutivamente. Implementar um serviço adicional de controle de cotas aumentaria a complexidade para um único usuário.

**O que limita o risco atualmente:** cada execução possui limites de passos, ferramentas, tokens, tempo e custo. O agente também possui detector de laços e não inicia solicitações automaticamente. O proprietário controla o acesso à instalação local e pode acompanhar os gastos da API.

**Quando o risco será reavaliado:** se o agente passar a funcionar remotamente, permitir vários usuários, executar tarefas automaticamente ou apresentar consumo acumulado acima de US$ 5 em um dia de uso normal. Nesses casos, deverão ser implementadas cotas diárias, alertas de consumo e controles por usuário.

A aceitação é restrita ao **consumo acumulado entre execuções**, não à remoção dos limites já existentes. Os riscos relacionados a autenticação, registros indevidos, dados internos e envenenamento de memória não estão sendo aceitos sem tratamento.

