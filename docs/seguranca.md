# Segurança — Pastéis Miyata

Versão dos controles: `seguranca-v1`.

## Escopo

O sistema é um agente local utilizado pelo proprietário, com:

- consultas ao MySQL;
- recuperação de documentos do corpus;
- memória semântica e episódica em SQLite;
- registro de planos após aprovação humana.

Os ataques descritos neste documento foram executados somente em testes
locais, com SQLite temporário ou em memória, modelo simulado e conexão
MySQL bloqueada por mock.

Não foram atacados sistemas de terceiros nem utilizado o banco operacional
para esses testes.

Os controles não equivalem a uma garantia de ausência de vulnerabilidades
ou de conformidade legal.

As referências ao código utilizam os nomes das funções, pois a formatação
dos arquivos pode alterar os números das linhas.

## 1. Canais de conteúdo não confiável

| Canal | Conteúdo recebido | Fronteira de segurança |
|---|---|---|
| Entrada do proprietário | Texto livre, inclusive instruções hostis | Contrato de entrada, identificação técnica e bloqueio de formatos reconhecidos de credenciais |
| Corpus | Regras, exemplos e possíveis instruções inseridas em documentos | Documento é evidência, não autorização de ação |
| MySQL | Dados estruturados e textos do cadastro | Consultas fixas e parametrizadas |
| Modelo | Texto, JSON, nomes de ferramentas e argumentos | Catálogo fechado, validação estrita e uma ferramenta por decisão |
| Memória semântica | Preferências atuais e versões anteriores | Chaves e valores permitidos e autorização no pedido atual |
| Memória episódica | Resumos novos e dados legados | Somente metadados estruturados de planos calculados |
| Checkpoint | Mensagens, plano e aprovação pendente | Conferência do dono técnico e bloqueio de novo turno durante a pausa |

Não existem ferramentas para:

- executar shell;
- executar Python arbitrário;
- ler `.env`;
- ler variáveis de ambiente;
- enviar dinheiro;
- escrever diretamente no MySQL.

Uma instrução encontrada num documento não substitui a autorização do
proprietário.

## 2. Riscos do case

Impacto adotado:

- **3:** possibilidade de escrita persistente ou ação indevida relevante;
- **2:** resposta ou operação degradada;
- **1:** exposição limitada pelas capacidades atuais.

Essa classificação representa impacto no case, não probabilidade.

| Risco | Componente | Cenário | Impacto | Tratamento |
|---|---|---|---:|---|
| ASI02 — uso indevido de ferramenta | `src/graph.py`, `_executar`; `src/seguranca.py`, `validar_argumentos` | Modelo tenta executar SQL, chamar ferramenta desconhecida ou acrescentar argumentos não permitidos | 3 | Controle C1 |
| ASI06 — envenenamento de memória | `src/memory.py`; `src/graph.py`, `memorizar_episodio` | Documento ou resposta tenta persistir instruções para execuções futuras | 3 | Controle C2 |
| ASI09 — exploração da confiança humano-agente | `src/graph.py`, `aprovar_plano`; `src/agent.py`, `_validar_acesso_thread` | Modelo afirma ter aprovação ou tenta substituir o plano durante a pausa | 3 | Controle C3 |
| ASI01 — sequestro de objetivo | `src/graph.py`, `chamar_modelo`; `src/rag.py` | Texto recuperado induz resposta alheia ao pedido | 2 | Ações limitadas pelos controles; risco residual declarado |
| ASI03 — abuso de identidade e privilégio | `src/agent.py`; `src/database.py`, `conectar` | Chamador informa outro usuário ou alguém acessa os arquivos locais | 2 | Identificação e dono da thread conferidos; autenticação de rede não implementada |
| ASI10 — agente desgovernado | `src/graph.py`, `_verificar_orcamento` | Repetição de chamadas ou tentativa de exceder limites | 2 | Orçamentos, detector de laço e limite no nó de aprovação |
| ASI04 — cadeia de suprimentos | `requirements.txt`, corpus e prompts | Dependência ou arquivo alterado muda o comportamento | 1 | Versões diretas fixadas e revisão pelo responsável; auditoria transitiva pendente |

ASI07 não se aplica porque o sistema não possui comunicação entre agentes.

ASI05 não corresponde a uma ferramenta exposta: o modelo não pode pedir
execução arbitrária de código.

Falhas em cascata, associadas ao ASI08, continuam sujeitas aos contratos e
orçamentos existentes. Não se afirma que todos os modos de falha foram
eliminados.

## 3. Controles fora do prompt

### C1 — catálogo e argumentos fechados

Pontos de aplicação:

- `src/seguranca.py`: `validar_argumentos`;
- `src/seguranca.py`: `validar_lote_chamadas`;
- `src/graph.py`: `chamar_modelo`;
- `src/graph.py`: `_executar`;
- `src/graph.py`: `executar_ferramentas`.

O contrato enviado ao modelo deriva do mesmo esquema utilizado pela
validação no código.

São bloqueados:

- ferramenta fora do catálogo;
- JSON que não representa um objeto;
- chaves duplicadas;
- constantes `NaN` e `Infinity`;
- argumentos acima de 8.192 bytes;
- campos extras;
- booleanos usados como inteiros;
- identificadores textuais;
- limite de histórico fora de 1–10;
- múltiplas ferramentas na mesma decisão.

O executor não transforma automaticamente `"101"` no inteiro `101`.

Erros de validação não reproduzem o valor rejeitado. Erros do provedor
registram a classe da exceção, sem copiar seu corpo livre para o log.

Testes principais:

- `test_argumento_sql_nao_chega_a_ferramenta`;
- `test_ferramenta_nao_declarada_nao_executa_codigo`;
- `test_duas_ferramentas_na_mesma_decisao_nao_tem_efeito_parcial`;
- `test_erro_do_provedor_nao_reproduz_credencial_no_log`.

**Custo funcional:** perde flexibilidade para aceitar argumentos novos,
coerções e chamadas em lote. Novas ferramentas exigem alteração revisada do
catálogo e dos modelos de validação.

**Comportamento na falha:** fail-closed. A ferramenta não é executada.

### C2 — memória mínima e preferência autorizada

Pontos de aplicação:

- `src/seguranca.py`: `validar_preferencia`;
- `src/seguranca.py`: `autorizar_preferencia`;
- `src/seguranca.py`: `validar_resumo_episodio`;
- `src/memory.py`: `salvar_fato_semantico`;
- `src/memory.py`: `ler_fatos_semanticos`;
- `src/memory.py`: `salvar_episodio`;
- `src/memory.py`: `buscar_episodios`;
- `src/graph.py`: `memorizar_episodio`.

A única preferência persistível nesta versão é:

```text
chave: prioridade
valores: reduzir sobra | evitar falta
```

O pedido atual precisa autorizar exatamente o valor solicitado pela
ferramenta.

Exemplo aceito:

```text
Guarde como preferência permanente a chave prioridade com o valor reduzir sobra.
```

Também é aceita a forma:

```text
Guarde como preferência permanente para meus planejamentos a chave prioridade com o valor reduzir sobra.
```

Uma instrução encontrada num documento não autoriza essa gravação.

Episódios novos contêm somente:

- tipo;
- feira;
- total recomendado;
- quantidade de operações consideradas, quando disponível.

Não são copiados para episódios:

- pedido original;
- resposta livre do modelo;
- nomes de produtos;
- instruções recuperadas;
- tags livres.

Somente um plano calculado e conclusivo do turno atual pode gerar um
episódio. Consultas e confirmações sem novo cálculo não geram episódio.

Registros legados incompatíveis são ignorados na recuperação, sem serem
apagados.

A leitura semântica utiliza a versão válida mais recente. O hash verifica
consistência e idempotência; não autentica criptograficamente o conteúdo.

Testes principais:

- `test_instrucao_no_documento_nao_autoriza_preferencia`;
- `test_valor_diferente_do_pedido_nao_e_salvo`;
- `test_preferencia_arbitraria_nao_chega_ao_sqlite`;
- `test_episodio_nao_copia_pedido_nem_texto_do_modelo`;
- `test_episodio_legado_livre_nao_reentra_no_contexto`.

**Custo funcional:** perde preferências arbitrárias e resumos narrativos
ricos. Algumas declarações naturais precisam ser repetidas na forma
explícita documentada.

**Comportamento na falha:** fail-closed. Não grava nem recupera conteúdo
incompatível para o contexto.

Essa política não apaga checkpoints, logs ou registros antigos.

### C3 — aprovação vinculada à conversa

Pontos de aplicação:

- `src/agent.py`: `_validar_acesso_thread`;
- `src/agent.py`: `executar`;
- `src/agent.py`: `retomar`;
- `src/graph.py`: `aprovar_plano`;
- `src/seguranca.py`: `validar_plano_para_registro`;
- `src/schemas.py`: `DecisaoHumana`.

O executor comum não registra planos. A escrita ocorre somente depois do
`interrupt` e de uma decisão humana válida.

O campo `aprovado` enviado pelo modelo é argumento extra e não autoriza
escrita.

Antes da aprovação são conferidos:

- código da feira;
- inteiros não negativos;
- produtos distintos;
- soma das quantidades;
- exclusão dos produtos 5 e 15 nas feiras E.

A fachada verifica:

- identificação técnica autorizada;
- dono da thread;
- existência de aprovação pendente;
- disponibilidade do checkpoint.

Durante a pausa não é permitido iniciar outro turno na mesma thread.
Isso impede que um novo pedido substitua o plano apresentado.

A edição humana modifica somente o resumo, limitado a 600 caracteres.
Quantidades exigem um novo cálculo.

Rejeição explícita encerra a tentativa sem pedir que o modelo
reinterprete a decisão. Aprovação inválida ou vencida não grava.

A idempotência do registro permanece aplicada na tabela de planos.

Testes principais:

- `test_aprovacao_falsa_em_argumento_nao_grava_nem_abre_pausa`;
- `test_executor_comum_nao_substitui_o_no_humano`;
- `test_turno_novo_nao_troca_plano_durante_a_pausa`;
- `test_edicao_humana_nao_pode_incluir_quantidades`;
- `test_prazo_vencido_nao_grava_o_plano`;
- testes originais de rejeição e idempotência.

**Custo funcional:** não registra sem intervenção humana, não aceita
mudança de quantidades pelo resumo e não continua outra tarefa na mesma
thread enquanto houver pausa.

**Comportamento na falha:** fail-closed. Sem validação e decisão humana
válida, não registra o plano.

`AGENT_USER_ID` é identificação técnica local, não autenticação de rede.
Quem já pode executar Python no computador pode informar essa identidade
ou chamar métodos internos. HTTP/MCP exigirão autenticação própria.

## 4. Dados e credenciais

`validar_texto_sem_credenciais` bloqueia formatos reconhecidos de:

- senha;
- chave de API;
- token Bearer;
- chave privada.

A verificação acontece antes do checkpoint para a entrada nova e também
na edição humana do resumo.

É defesa adicional, não detector universal de dados pessoais ou segredos
ofuscados.

Credenciais de configuração não são ferramentas do modelo. Não existe
operação exposta para ler `.env` ou variáveis de ambiente.

Esta atualização não altera:

- `.env`;
- credenciais MySQL;
- banco operacional;
- bases SQLite existentes;
- corpus;
- prompts;
- Docker.

### Fluxos e retenção

| Lugar | Dados e finalidade | Guarda | Situação |
|---|---|---|---|
| Entrada/prompt | Solicitação, identificação técnica e contexto da tarefa | Conversa local e provedor quando há chamada | LACUNA: classificação e base formal pelo responsável |
| MySQL/corpus | Produção, vendas e regras | Ambiente administrado pelo proprietário | LACUNA: revisar textos livres, especialmente observações |
| Memória semântica | Prioridade operacional e identificação técnica | SQLite local | LACUNA: prazo formal e base aplicável; não há expiração automática |
| Memória episódica | Metadados de planos calculados | SQLite local | LACUNA: prazo formal; decaimento não apaga registros |
| Plano aprovado | Produtos, quantidades, resumo aprovado e IDs técnicos | SQLite local | LACUNA: retenção e tratamento do resumo livre |
| Checkpoint/log | Mensagens, ferramentas, saída e estado | Arquivos locais | LACUNA: minimização completa, remoção e acesso pelo SO |
| Provedor | Mensagens e retornos selecionados | Conforme conta e configuração utilizadas | LACUNA: verificar condições efetivas sem presumir prazo |

Não há necessidade funcional de cadastrar dados de clientes, mas textos
livres podem introduzi-los.

Não se declara conformidade LGPD nem ausência absoluta de dado pessoal
somente por existir um usuário. A base legal não foi escolhida
automaticamente.

## 5. Riscos residuais aceitos

Aceita-se que uma injeção em texto recuperado ainda possa prejudicar uma
resposta em linguagem natural.

Os controles limitam ações e memória, mas não provam que toda resposta
esteja correta.

O uso continua local e assistido. O proprietário decide a produção.

Reavaliar esse risco antes de:

- permitir escrita externa automática;
- expor HTTP/MCP;
- adicionar usuários;
- receber documentos de terceiros sem curadoria;
- tomar decisões sem revisão do proprietário.

Também permanece a dependência da segurança da conta do sistema
operacional. Quem pode alterar Python, `.env` ou SQLite pode contornar
controles locais.

Não há autenticação multiusuário nem proteção criptográfica dos arquivos.

## 6. Evidências executadas

Verificação em cópia do código enviado pelo proprietário:

- ambiente Linux;
- Python 3.12;
- versões exatas do `requirements.txt` enviado;
- modelo simulado;
- SQLite temporário ou em memória;
- conexão ao MySQL proibida nos testes novos de integração.

Corpus e prompts de apoio vieram da cópia anterior do projeto e não foram
substituídos no pacote.

| Conjunto | Resultado |
|---|---:|
| Testes existentes | 53 aprovados |
| Novos testes de políticas e memória | 15 aprovados |
| Novos testes de integração | 24 aprovados |
| Total | 92 aprovados |

Comandos:

```powershell
python.exe -m unittest discover -s tests -p "test_seguranca*.py" -v
python.exe -m unittest discover -s tests -v
```

Isso não é uma nova rodada do golden set com o LLM real e não mede
latência ou custo de produção.

### Regressão após os controles de segurança

A versão `seguranca-v1-local` manteve 20/20 casos aprovados no
verificador automático, assim como `regressao-final-local`.
A comparação usou o dataset v1.0.0, o mesmo snapshot MySQL
(`c7f695afd8f7`, prefixo do hash) e o mesmo modelo (`gpt-5.6-luna`).
A diferença foi de 0 pontos percentuais, sem piora em nenhum caso.

Evidência: `evals/resultados/comparacao-regressao-seguranca-v1.json`.
O resultado não inclui a calibração do juiz LLM.

## 7. Auditoria Git pendente

O ZIP de código não contém o histórico Git original. Portanto, os
comandos abaixo ainda precisam ser executados e examinados no projeto do
proprietário:

```powershell
git log --all -- .env
git log --all -S "OPENAI_API_KEY=" --oneline
git ls-files -- .env dados/checkpoints.sqlite3 dados/memoria.sqlite3
```

Não se presumiu que as saídas estejam vazias.

A busca `-S` pode encontrar exemplos ou nomes de variável. Um resultado
não comprova sozinho que uma chave real foi exposta.

Se houver segredo real exposto, revogá-lo ou rotacioná-lo no provedor e
registrar o tratamento. Alterar o histórico não invalida uma chave já
copiada.

Também falta verificar os privilégios da credencial utilizada pelo agente
normal. A conta de leitura das avaliações não comprova que o agente
normal possua os mesmos privilégios.

Esta atualização não cria usuário ou cópia de banco.

## 8. Pendências

1. Repetir os testes no Windows após aplicar a atualização.
2. Executar a suíte real como nova versão e comparar com a anterior.
3. Registrar o commit efetivo em `docs/mudancas.md`.
4. Atualizar `docs/memoria.md` para a política de `seguranca-v1`.
5. Completar auditoria Git, privilégios e política de dados/retenção.
6. Integrar os futuros traces OpenTelemetry e atualizar o model card.

O log atual ainda não equivale à instrumentação final de observabilidade.