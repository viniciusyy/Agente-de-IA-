# Grafo, padrões e estado

## Topologia do grafo

O agente foi implementado com LangGraph e possui os seguintes nós:

```text
START
  |
  v
preparar_contexto
  |
  v
chamar_modelo
  |
  +------------------------+
  |                        |
  v                        v
executar_ferramentas    aprovar_plano
  |                        |
  +-----------+------------+
              |
              v
       chamar_modelo
              |
              v
       validar_saida
              |
              v
    memorizar_episodio
              |
              v
             END
```

Depois de `chamar_modelo`, uma aresta condicional decide entre:

- executar uma ferramenta comum;
- entrar na aprovação humana;
- validar a resposta final.

A decisão da aresta é feita por código com base na presença e no nome da chamada de ferramenta produzida pelo modelo.

## Padrões utilizados

| Padrão | Local no grafo | Por que foi escolhido | Condição de não uso |
|---|---|---|---|
| Sequencial com portão | `validar_saida → memorizar_episodio` | O código verifica se a saída é conclusiva e suficiente antes de gravar memória | Saídas recusadas, incompletas ou com erro não geram episódio |
| Agente com laço | `chamar_modelo → executar_ferramentas → chamar_modelo` | Uma solicitação em texto livre pode exigir combinações diferentes de consulta, RAG e cálculo | Entrada incompleta ou fora do escopo pode terminar sem ferramenta |
| Human-in-the-loop | `chamar_modelo → aprovar_plano → chamar_modelo` | O registro do plano exige autorização do proprietário | Consultas e cálculos não exigem pausa |

Não foram utilizados:

- Router separado;
- paralelização no agente principal;
- orquestrador com trabalhadores;
- avaliador-otimizador;
- arquitetura multiagente.

Um único agente com ferramentas, validações e portões determinísticos resolve o escopo atual com menor autonomia e menor custo.

## Quem decide cada bifurcação

| Decisão | Responsável | Justificativa |
|---|---|---|
| Chamar ferramenta ou responder | Modelo por tool calling | Exige interpretar a solicitação em linguagem natural |
| Escolher qual ferramenta chamar | Modelo limitado pelos schemas | Depende da intenção identificada |
| Direcionar para ferramenta, aprovação ou saída | Código | A presença e o nome da chamada são verificáveis |
| Aplicar regra fixa de produto | Código | Não exige interpretação semântica |
| Remover documento revogado | Código pelo campo `status` | Vigência é uma condição objetiva |
| Validar o formato da saída | Pydantic | O contrato possui tipos e campos definidos |
| Registrar ou não o plano | Proprietário no `interrupt` | É uma ação persistente |
| Memorizar um episódio | Código | Apenas saídas conclusivas e suficientes são gravadas |

O schema de ferramentas limita o formato dos argumentos, mas não prova que o modelo escolheu a ferramenta correta. Essa decisão é verificada pelos casos demonstrados e pelos logs.

## Estado do grafo

| Campo | Tipo | Quem escreve | Quem utiliza | Origem |
|---|---|---|---|---|
| `mensagens` | Lista acumulada | Entrada, modelo e ferramentas | Modelo | Conversa |
| `entrada_texto` | Texto | Fachada | Memória e log | Proprietário |
| `usuario_id` | Texto | Fachada | Memória | Metadado |
| `thread_id` | Texto | Fachada | Checkpointer e escrita | Metadado |
| `turno_id` | Texto | Fachada | Fontes e trajetória | UUID por solicitação |
| `memoria_semantica` | Dicionário | `preparar_contexto` | Modelo | SQLite |
| `memoria_episodica` | Lista | `preparar_contexto` | Modelo | SQLite |
| `fontes` | Lista acumulada | Ferramentas e aprovação | Validador | Integrações |
| `trajetoria` | Lista acumulada | Todos os nós | Log | Execução |
| `assinaturas_passos` | Lista acumulada | Modelo | Detector de laço | Hash das decisões |
| `passos_turno` | Inteiro | Modelo | Orçamento e log | Contador |
| `chamadas_ferramenta_turno` | Inteiro | Ferramentas | Orçamento e log | Contador |
| `tokens_entrada_turno` | Inteiro | Modelo | Orçamento e log | API |
| `tokens_saida_turno` | Inteiro | Modelo | Orçamento e log | API |
| `custo_turno_usd` | Decimal | Modelo | Orçamento e log | Preços configurados |
| `inicio_turno_epoch` | Decimal | Fachada | Limite de tempo e aprovação | Relógio |
| `ultimo_plano` | Objeto opcional | Ferramenta de recomendação | Aprovação | Cálculo determinístico |
| `resposta_validada` | Objeto opcional | Validador | Fachada e memória | Pydantic |
| `erro_fatal` | Texto opcional | Modelo ou orçamento | Validador | Execução |
| `motivo_termino` | Texto | Validador ou orçamento | Fachada e log | Taxonomia própria |

## Reducers

Os campos que podem receber atualizações sucessivas utilizam reducers.

### Concatenação

Os campos abaixo utilizam concatenação com `operator.add`:

- `mensagens`;
- `trajetoria`;
- `assinaturas_passos`.

Cada nó acrescenta novos elementos sem apagar os anteriores.

### Fontes

O campo `fontes` utiliza o reducer próprio `juntar_fontes`.

Ele:

1. recebe as fontes atuais;
2. recebe as novas fontes;
3. combina as listas;
4. elimina duplicidades por tipo e referência;
5. preserva somente uma ocorrência de cada fonte.

### Substituição

Os outros campos são substituídos porque possuem apenas um valor vigente por etapa.

Exemplos:

- `ultimo_plano`;
- `resposta_validada`;
- `erro_fatal`;
- `motivo_termino`;
- contadores do turno.

## Demonstração do reducer

O comportamento foi demonstrado com:

```powershell
python.exe -m scripts.demonstrar_reducer
```

Resultado:

```text
========================================================================
EXECUÇÃO SEM REDUCER
========================================================================
InvalidUpdateError: At key 'resultados': Can receive only one value per step.
Use an Annotated key to handle multiple values.

========================================================================
EXECUÇÃO COM REDUCER
========================================================================
{'resultados': ['A', 'B']}
```

Sem reducer, o LangGraph rejeitou duas atualizações concorrentes para o mesmo campo.

Com reducer, os resultados dos dois ramos foram preservados.

## O que não fica no estado

Não são armazenados diretamente como campos do estado:

- configurações;
- preços dos modelos;
- conteúdo integral dos prompts;
- corpus completo;
- conexões com bancos;
- cliente da API;
- índice textual;
- chave de idempotência derivável;
- tempo decorrido derivável.

Esses valores são carregados ou calculados quando necessário. Guardar cópias deles no estado criaria múltiplas fontes de verdade.

O total de tokens é obtido pela soma dos contadores. O tempo decorrido é calculado a partir de `inicio_turno_epoch`. A chave de idempotência é derivada do conteúdo.

## Mensagens

A lista `mensagens` armazena somente o protocolo necessário para conversar com a API:

- solicitação do proprietário;
- resposta do modelo;
- chamada de ferramenta;
- retorno da ferramenta.

Memória, configuração, trajetória e orçamento possuem campos próprios e não dependem da lista de mensagens.

## Proteção contra laço

Cada conjunto de chamadas de ferramenta recebe uma assinatura SHA-256 calculada a partir:

- do identificador do turno;
- do nome da ferramenta;
- dos argumentos.

Se a mesma decisão for repetida três vezes, o sistema encerra com:

```text
LACO_DETECTADO
```

O limite é configurado por:

```text
LOOP_REPEAT_LIMIT=3
```

## O que o LangGraph fornece

O framework fornece:

- grafo com nós e arestas;
- estado tipado;
- reducers;
- checkpointer;
- `interrupt`;
- retomada com `Command`;
- limite de recursão.

## O que foi implementado pelo projeto

O projeto implementa:

| Recurso | Implementação |
|---|---|
| Motivos de término | Taxonomia própria |
| Limites de passos | Contador verificado antes do modelo |
| Limite de ferramentas | Contador por turno |
| Limite de tokens | Soma de entrada e saída |
| Limite de tempo | Comparação com o início do turno |
| Limite de custo | Cálculo pelos preços configurados |
| Detector de laço | Assinatura SHA-256 das decisões |
| Erro recuperável | Retorno da ferramenta enviado ao modelo |
| Erro fatal | Transformação em saída validada |
| Idempotência | Hash canônico e restrição única |
| RAG | Índice lexical e filtro de vigência |
| Memória | Política semântica, episódica e procedural |

## Decisões transformadas em parâmetros

As decisões abaixo não dependem dos padrões internos das bibliotecas:

```text
GRAPH_RECURSION_LIMIT=24
LOOP_REPEAT_LIMIT=3
CONVERSATION_MAX_TURNS=6
RAG_MAX_RESULTS=3
RAG_MIN_SCORE=0.001
APPROVAL_TIMEOUT_HOURS=24
MEMORY_EPISODE_HALF_LIFE_DAYS=90
```

Esses valores estão declarados no `.env.example` e são carregados por `src/config.py`.

## Evidência da topologia

A topologia compilada foi conferida com:

```powershell
python.exe conferir_grafo.py
```

O resultado confirmou os nós:

```text
preparar_contexto
chamar_modelo
executar_ferramentas
aprovar_plano
validar_saida
memorizar_episodio
```

Também confirmou as arestas diretas e condicionais previstas na arquitetura.