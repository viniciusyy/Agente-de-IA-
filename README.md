# Agente de Planejamento de Produção — Pastéis Miyata

## Integrante

- Vinicius Miyata

## Problema

O proprietário da Pastéis Miyata precisa definir quanto produzir de cada tipo de pastel para cada feira sem depender apenas da experiência e de consultas manuais ao histórico.

## Sobre o projeto

Este repositório apresenta a evolução do mesmo sistema nas Partes 1 e 2 da disciplina de Agentes de IA com LLMs.

O sistema é utilizado exclusivamente pelo proprietário da Pastéis Miyata.

Na Parte 2, o agente passou a ser implementado como um grafo com LangGraph. O sistema recebe solicitações em linguagem natural, recupera memória e conhecimento, seleciona ferramentas, consulta o MySQL e devolve uma saída validada.

A versão atual possui:

- entrada em texto livre;
- saída validada por Pydantic;
- grafo com nós e arestas condicionais;
- consultas estruturadas ao MySQL;
- RAG textual sobre documentos privados da pastelaria;
- memória de curto e longo prazo;
- checkpoints persistentes por conversa;
- controle da janela de contexto;
- orçamento de passos, ferramentas, tokens, tempo e custo;
- detector de laço;
- human-in-the-loop antes do registro de um plano;
- retomada, edição, rejeição e expiração da aprovação;
- escrita idempotente;
- logs com trajetória e motivo de término.

O modelo de linguagem atua como orquestrador. Ele interpreta a solicitação e escolhe ferramentas, mas não calcula livremente as quantidades.

As consultas, médias, restrições e totalizações são executadas por código Python e pelo banco MySQL.

## Usuário autorizado

O único usuário autorizado é o proprietário da Pastéis Miyata.

```text
AGENT_USER_ID=proprietario
```

O proprietário:

- inicia as solicitações;
- informa dados ausentes;
- consulta resultados;
- solicita simulações;
- aprova ou rejeita o registro de planos;
- pode editar o resumo antes da escrita;
- permanece responsável pela decisão final.

## Arquitetura resumida

```text
texto livre
    |
    v
preparar contexto e recuperar memórias
    |
    v
modelo decide responder ou chamar ferramenta
    |
    +--> MySQL
    |
    +--> RAG textual
    |
    +--> cálculo determinístico
    |
    +--> memória
    |
    +--> aprovação humana antes da escrita
    |
    v
saída Pydantic validada
    |
    v
memória episódica, quando aplicável
```

O MySQL continua sendo o banco operacional da Pastéis Miyata.

O SQLite não substitui o MySQL. Ele é utilizado localmente somente para:

- checkpoints do LangGraph;
- memória semântica;
- memória episódica;
- planos aprovados.

Não é necessário instalar um servidor SQLite, pois o suporte é fornecido pela biblioteca padrão do Python e pelo pacote de checkpoint do LangGraph.

## Ferramentas

| Ferramenta | Função | Tipo |
|---|---|---|
| `consultar_historico` | Consulta no MySQL as operações recentes de uma feira | Leitura |
| `consultar_operacao` | Consulta no MySQL uma operação pelo identificador | Leitura |
| `buscar_conhecimento` | Recupera regras e informações do corpus | Leitura |
| `calcular_recomendacao` | Calcula um baseline determinístico pela média das vendas recentes | Leitura e cálculo |
| `salvar_preferencia` | Versiona uma preferência explicitamente declarada | Escrita idempotente |
| `registrar_plano` | Solicita aprovação humana e registra o plano | Escrita idempotente |

## Estrutura do projeto

```text
.
├── dados/
│   ├── corpus/
│   │   ├── 01_regras_feiras.md
│   │   ├── 02_glossario_dados.md
│   │   ├── 03_processo_planejamento.md
│   │   ├── 04_produtos_status.md
│   │   ├── 05_limites_sistema.md
│   │   └── 99_regras_feiras_revogado.md
│   ├── casos_demonstracao.json
│   └── casos_demonstracao_parte2.json
├── docs/
│   ├── arquitetura.md
│   ├── case.md
│   ├── fontes.md
│   ├── grafo.md
│   ├── humano.md
│   ├── io.md
│   ├── memoria.md
│   ├── modelos.md
│   ├── prompts.md
│   └── rag.md
├── exercicios/
│   ├── aula-05-arquitetura.md
│   ├── aula-06-base-de-conhecimento.md
│   └── aula-11-avaliacao.md
├── logs/
│   ├── 01_caso_simples.json
│   ├── 02_caso_divergencia.json
│   ├── 03_registro_inexistente.json
│   ├── 04_acao_nao_permitida.json
│   ├── 05_pergunta_fora_corpus.json
│   └── 06_human_in_the_loop.json
├── prompts/
│   └── agente_planejamento_v1.md
├── scripts/
│   ├── demonstrar_reducer.py
│   ├── executar_casos_parte2.py
│   ├── gerar_io.py
│   └── verificar_rag.py
├── src/
│   ├── prompts/
│   │   ├── orquestrador_v2.md
│   │   └── procedimento_planejamento_v1.md
│   ├── agent.py
│   ├── config.py
│   ├── database.py
│   ├── domain.py
│   ├── graph.py
│   ├── main.py
│   ├── memory.py
│   ├── rag.py
│   └── schemas.py
├── tests/
│   └── test_parte2.py
├── .env.example
├── .gitignore
├── conferir_grafo.py
├── README.md
└── requirements.txt
```

A pasta `prompts/` da raiz preserva o prompt utilizado na Parte 1.

Os prompts executáveis da Parte 2 ficam em:

```text
src/prompts/
```

## Como rodar

### 1. Pré-requisitos

Antes de executar o projeto, é necessário ter:

- Python 3.11 ou superior;
- Git;
- MySQL em execução;
- banco `pasteis_miyata` criado;
- tabelas e registros utilizados pelo projeto;
- chave válida da API;
- créditos disponíveis no provedor configurado.

A assinatura do ChatGPT e os créditos da API são serviços separados.

### 2. Clonar o repositório

```powershell
git clone https://github.com/viniciusyy/Agente-de-IA-.git
cd Agente-de-IA-
```

Caso o repositório já esteja no computador, abra a pasta do projeto no terminal.

### 3. Criar o ambiente virtual

```powershell
python -m venv .venv
```

### 4. Instalar as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5. Criar o arquivo `.env`

Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

Depois, abra o `.env` e preencha os valores locais.

Exemplo de estrutura:

```env
# Modelo
OPENAI_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.6-luna
LLM_INPUT_PRICE_PER_MILLION=0.20
LLM_OUTPUT_PRICE_PER_MILLION=1.20
LLM_MAX_OUTPUT_TOKENS=700

# Banco MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=pasteis_miyata
MYSQL_USER=
MYSQL_PASSWORD=

# Orçamento
AGENT_MAX_STEPS=10
AGENT_MAX_TOOL_CALLS=8
AGENT_MAX_TOKENS=12000
AGENT_MAX_TIME_SECONDS=90
AGENT_MAX_COST_USD=0.15
GRAPH_RECURSION_LIMIT=24
LOOP_REPEAT_LIMIT=3
CONVERSATION_MAX_TURNS=6

# RAG, memória e aprovação
RAG_MAX_RESULTS=3
RAG_MIN_SCORE=0.001
MEMORY_EPISODE_HALF_LIFE_DAYS=90
APPROVAL_TIMEOUT_HOURS=24
CHECKPOINT_DATABASE=dados/checkpoints.sqlite3
MEMORY_DATABASE=dados/memoria.sqlite3
CORPUS_DIRECTORY=dados/corpus
LOG_DIRECTORY=logs

# Identidade
AGENT_USER_ID=proprietario
AGENT_THREAD_ID=proprietario-principal
```

O código também aceita os aliases `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`.

Nunca coloque no GitHub:

- `.env`;
- chave da API;
- senha do MySQL;
- outras credenciais.

### 6. Executar as verificações locais

#### Testes automatizados

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado obtido:

```text
Ran 8 tests

OK
```

#### Avaliação do RAG

```powershell
.\.venv\Scripts\python.exe -m scripts.verificar_rag
```

Resultado obtido:

```text
10 acertos em 10 perguntas
Taxa de acerto: 100%
```

#### Demonstração do reducer

```powershell
.\.venv\Scripts\python.exe -m scripts.demonstrar_reducer
```

Resultado esperado:

```text
EXECUÇÃO SEM REDUCER
InvalidUpdateError

EXECUÇÃO COM REDUCER
{'resultados': ['A', 'B']}
```

#### Conferência do grafo

```powershell
.\.venv\Scripts\python.exe conferir_grafo.py
```

O comando apresenta os nós e as arestas diretas e condicionais do grafo.

### 7. Executar o agente

```powershell
.\.venv\Scripts\python.exe -m src.main
```

O início esperado é:

```text
========================================================================
AGENTE DE PLANEJAMENTO — PASTÉIS MIYATA — PARTE 2
========================================================================
Usuário autorizado: proprietário
Usuário técnico: proprietario
Conversa (thread_id): proprietario-principal
Entrada: texto livre em português. Digite 'sair' para encerrar.
```

O programa também testa a conexão com o MySQL.

## Como usar

O proprietário digita uma solicitação em linguagem natural.

### Consultar histórico

```text
Consulte as últimas cinco operações da feira QUA.
```

### Consultar uma operação

```text
Consulte a operação 101.
```

### Consultar uma regra

```text
Qual regra vale para pastel de frango na SAB_E?
```

### Calcular uma recomendação

```text
Calcule uma recomendação de produção para a feira QUA.
```

### Solicitar o registro do último plano

Depois de calcular uma recomendação na mesma conversa:

```text
Registre esse plano como o plano semanal aprovado.
```

### Informar uma preferência

```text
Minha prioridade padrão é reduzir sobras.
```

### Encerrar

```text
sair
```

## Contrato da saída

Toda resposta pública segue o objeto `SaidaAgente`.

Exemplo estrutural:

```json
{
  "status": "concluido",
  "resultado": {},
  "fontes": [],
  "suficiente": true,
  "motivo": "A solicitação foi concluída.",
  "proxima_acao": null
}
```

Os status possíveis são:

| Status | Significado |
|---|---|
| `concluido` | A solicitação foi concluída |
| `precisa_informacao` | O proprietário precisa informar algum dado |
| `recusado` | A solicitação está fora do escopo ou não possui fonte suficiente |
| `aguardando_aprovacao` | O grafo está pausado antes de uma escrita |
| `erro` | A execução terminou com erro validado |

Uma recusa também é uma saída válida. O agente não inventa uma resposta quando o banco, as ferramentas ou o corpus não sustentam a informação.

## Aprovação humana

Quando o modelo solicita `registrar_plano`, o grafo para antes da escrita.

O terminal apresenta:

- ação;
- argumentos;
- feira;
- quantidades;
- total;
- resumo;
- consequência;
- prazo.

O proprietário escolhe:

```text
[A]provar, [R]ejeitar ou [E]ditar?
```

### Aprovar

Digite:

```text
A
```

### Rejeitar

Digite:

```text
R
```

### Editar o resumo

Digite:

```text
E
```

Depois, informe o novo resumo.

Se o programa for encerrado durante a pausa, o checkpoint mantém a aprovação pendente. Ao iniciar novamente com a mesma `thread_id`, o sistema apresenta a decisão pendente.

Se a aprovação não for retomada dentro de 24 horas, ela expira e nenhuma escrita é realizada.

A repetição da mesma escrita não cria dois registros.

## Como interpretar a execução

Cada execução apresenta:

```text
SAÍDA VALIDADA
RESUMO DA EXECUÇÃO
Motivo da parada
Passos
Ferramentas
Tokens de entrada
Tokens de saída
Custo estimado
Log
```

Os principais motivos são:

| Motivo | Significado |
|---|---|
| `CONCLUIDO` | Resultado concluído |
| `PRECISA_INFORMACAO` | Dados obrigatórios estão ausentes |
| `RECUSADO` | Solicitação não atendida com segurança |
| `AGUARDANDO_APROVACAO` | Grafo pausado antes da escrita |
| `LIMITE_DE_PASSOS` | Limite de passos atingido |
| `LIMITE_DE_FERRAMENTAS` | Limite de ferramentas atingido |
| `LIMITE_DE_TOKENS` | Limite de tokens atingido |
| `LIMITE_DE_TEMPO` | Limite de tempo atingido |
| `LIMITE_DE_CUSTO` | Limite de custo atingido |
| `LACO_DETECTADO` | A mesma decisão foi repetida |
| `ERRO_DO_MODELO` | O provedor ou modelo retornou erro |

## Exemplo real da Parte 2

O exemplo abaixo foi copiado da execução oficial registrada em `logs/04_acao_nao_permitida.json`.

- Data da execução: `2026-10-19T21:56:42.497377`
- Commit executado: `00bab3576c181c4ea08360a37714eb49d9ad94b3`

Entrada real:

```text
Calcule uma recomendação para a próxima feira.
```

Saída real completa:

```json
{
  "status": "precisa_informacao",
  "resultado": null,
  "fontes": [
    {
      "tipo": "sistema",
      "referencia": "src/prompts/orquestrador_v2.md",
      "detalhe": "Contrato e limites do agente."
    }
  ],
  "suficiente": false,
  "motivo": "É necessário informar o código da feira para calcular a recomendação.",
  "proxima_acao": "Informe o código da feira: QUA, QUI, SAB_C, SAB_E, DOM_C ou DOM_E."
}
```

Esse caso demonstra que o agente não escolhe uma feira silenciosamente e não chama a ferramenta de recomendação quando uma informação obrigatória está ausente.

Os demais exemplos completos estão em:

```text
docs/io.md
```

## Casos oficiais da Parte 2

Os seis casos são definidos em:

```text
dados/casos_demonstracao_parte2.json
```

| Caso | Solicitação | O que demonstra |
|---|---|---|
| Caminho feliz | Recomendação para `QUA` | MySQL, cálculo determinístico e saída validada |
| Divergência | Pedir Frango para `SAB_E` | Recuperação e aplicação da regra |
| Registro inexistente | Consultar operação `999999` | Erro de ferramenta tratado como dado |
| Entrada incompleta | Pedir a próxima feira sem identificá-la | O agente pergunta em vez de escolher |
| Fora do corpus | Perguntar fornecedor e prazo | Recusa por falta de conhecimento |
| Human-in-the-loop | Registrar plano calculado | Pausa, edição humana e idempotência |

## Gerar os seis logs oficiais

Antes da execução, o repositório precisa estar sem alterações pendentes. Isso permite registrar no log o commit exato testado.

Confira:

```powershell
git status
```

Depois execute:

```powershell
.\.venv\Scripts\python.exe -m scripts.executar_casos_parte2
```

O comando gera:

```text
logs/01_caso_simples.json
logs/02_caso_divergencia.json
logs/03_registro_inexistente.json
logs/04_acao_nao_permitida.json
logs/05_pergunta_fora_corpus.json
logs/06_human_in_the_loop.json
```

Cada log registra:

- entrada;
- saída;
- modelo;
- versão dos prompts;
- parâmetros;
- trajetória;
- ferramentas;
- fontes;
- tokens;
- custo;
- motivo de término;
- commit utilizado.

Depois, atualize automaticamente os exemplos reais:

```powershell
.\.venv\Scripts\python.exe -m scripts.gerar_io
```

## Documentação

| Documento | Conteúdo |
|---|---|
| `docs/case.md` | Problema, usuários, negócio e complemento do domínio |
| `docs/modelos.md` | Comparação e escolha do modelo |
| `docs/fontes.md` | Fontes consultadas |
| `docs/io.md` | Contratos de entrada e saída e exemplos reais |
| `docs/prompts.md` | Plano de prompt engineering |
| `docs/arquitetura.md` | Arquitetura e nível de autonomia |
| `docs/rag.md` | Corpus, recuperação e medição |
| `docs/memoria.md` | Checkpoint e memórias do agente |
| `docs/grafo.md` | Topologia, padrões, estado e reducers |
| `docs/humano.md` | Pausa, retomada, expiração e idempotência |

## Limitações

Esta versão:

- é utilizada somente pelo proprietário;
- ainda utiliza um baseline pela média das cinco operações recentes;
- ainda não utiliza os modelos definitivos de previsão do TCC;
- ainda não executa a otimização por Simplex;
- não gera SQL livre pelo modelo;
- não altera os registros históricos do MySQL;
- não considera sobra zero como prova de falta de produto;
- não registra plano sem confirmação humana.

## Segurança

Não devem ser enviados ao repositório:

- `.env`;
- chaves de API;
- senhas do MySQL;
- bancos locais `*.sqlite3`;
- ambiente virtual;
- logs automáticos intermediários;
- credenciais pessoais.

O repositório contém somente `.env.example`, sem valores privados.

Caso alguma chave tenha sido exposta fora do `.env`, ela deve ser revogada e substituída.

## Evidências obtidas

Na validação da Parte 2 foram obtidos:

- 8 testes automatizados executados com sucesso;
- 10 acertos em 10 perguntas do conjunto de verificação do RAG;
- documento revogado removido da recuperação normal;
- erro de concorrência reproduzido sem reducer;
- atualização paralela acumulada corretamente com reducer;
- recomendação determinística consultando o MySQL;
- saída pública validada pelo Pydantic;
- seis casos oficiais registrados em JSON;
- human-in-the-loop executado antes da escrita;
- edição humana aplicada antes do registro;
- escrita idempotente verificada;
- recusa quando o corpus não sustenta a resposta.

Os seis logs oficiais foram gerados a partir do commit:

```text
00bab3576c181c4ea08360a37714eb49d9ad94b3
```

## Estado atual

A arquitetura, o RAG, a memória, o grafo, os contratos de entrada e saída, o human-in-the-loop, os testes automatizados e os seis casos oficiais estão implementados e documentados.

A Parte 2 possui código executável, documentação versionada, exemplos reais e logs vinculados ao commit testado.