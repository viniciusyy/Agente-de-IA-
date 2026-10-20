# Arquitetura do agente

## Visão geral

O sistema recebe uma solicitação em texto livre feita pelo proprietário da Pastéis Miyata. O agente interpreta o pedido, recupera memória e conhecimento, escolhe ferramentas e devolve uma saída validada.

Os cálculos de produção não são realizados pelo modelo de linguagem. O modelo atua como orquestrador, enquanto consultas, regras, médias e registros são executados por código e sistemas externos.

```text
ENTRADA: texto livre + usuario_id + thread_id
                         |
                         v
                +-------------------+
                | preparar_contexto | [CÓDIGO]
                | memória semântica |
                | memória episódica |
                +---------+---------+
                          |
                          v
                +-------------------+
        +------>|   chamar_modelo   | [MODELO]
        |       | decide responder  |
        |       | ou pedir 1 tool   |
        |       +---------+---------+
        |                 |
        |       [ARESTA CONDICIONAL — CÓDIGO]
        |          /      |       \
        |         /       |        \
        |        v        v         v
        | +-----------+ +-------------+ +--------------+
        | | executar  | | aprovar     | | validar      |
        | | ferramentas| | plano       | | saída        |
        | | [CÓDIGO]  | | interrupt() | | [CÓDIGO]     |
        | +-----+-----+ +------+------+ +------+-------+
        |       |              |               |
        |       |       HUMANO: aprovar,        v
        |       |       rejeitar ou editar  +-------------------+
        +-------+--------------+             | memorizar episódio|
                                             | [CÓDIGO]           |
                                             +---------+---------+
                                                       |
                                                       v
                                                      END
```

## Três camadas

### 1. Entrada

A entrada pública é formada por:

```json
{
  "texto": "solicitação em linguagem natural",
  "usuario_id": "proprietario",
  "thread_id": "identificador da conversa"
}
```

O proprietário inicia a interação por meio do terminal.

As entradas podem ser:

- consulta de histórico;
- consulta de uma operação;
- pergunta sobre regra;
- solicitação de recomendação;
- declaração de preferência;
- pedido de registro de plano;
- solicitação incompleta;
- solicitação fora do escopo.

A entrada é heterogênea porque diferentes pedidos exigem ferramentas e caminhos distintos. Entretanto, não existe um nó Router separado. O próprio nó `chamar_modelo`, usando tool calling, decide se deve responder ou selecionar uma ferramenta.

### 2. System

O system prompt define o agente como:

> Agente de planejamento da Pastéis Miyata que atende somente ao proprietário, interpreta texto livre, seleciona ferramentas e não calcula livremente quantidades nem substitui a decisão humana.

Em torno do modelo existem:

- ferramentas;
- estado explícito;
- memória;
- RAG;
- banco MySQL;
- validação Pydantic;
- orçamento;
- detector de laço;
- checkpointer;
- human-in-the-loop;
- logs.

### 3. Processamento

O processamento acontece em seis etapas principais:

1. preparar o contexto;
2. chamar o modelo;
3. executar ferramenta, solicitar aprovação ou validar a saída;
4. retornar ao modelo quando houver resultado de ferramenta;
5. validar o contrato final;
6. memorizar uma execução conclusiva.

A sequência não é completamente fixa. O modelo pode solicitar ferramentas diferentes conforme a entrada, mas as bifurcações verificáveis são controladas por código.

## Ferramentas

| Ferramenta | O que faz | Operação | Reversível? | Fronteira |
|---|---|---|---|---|
| `consultar_historico` | Consolida operações recentes de uma feira | Leitura | Não se aplica | MySQL |
| `consultar_operacao` | Busca uma operação pelo identificador | Leitura | Não se aplica | MySQL |
| `buscar_conhecimento` | Recupera regras e exceções vigentes | Leitura | Não se aplica | Corpus Markdown |
| `calcular_recomendacao` | Calcula um baseline fora do LLM | Leitura e cálculo | Não altera dados | MySQL e Python |
| `salvar_preferencia` | Versiona uma preferência declarada pelo proprietário | Escrita idempotente | Pode ser substituída por versão posterior | SQLite |
| `registrar_plano` | Registra o último plano após aprovação humana | Escrita idempotente | Sim, por remoção auditada do registro local | SQLite |

O MySQL permanece como banco operacional da pastelaria. Os arquivos SQLite são utilizados apenas para checkpoints, memória e planos aprovados.

## O laço do agente

Em cada volta, o modelo recebe:

- prompt do orquestrador;
- memória procedural;
- memória semântica recuperada;
- episódios relevantes;
- janela recente da conversa;
- retornos das ferramentas do turno.

O modelo devolve uma das duas possibilidades:

1. chamada de uma ferramenta;
2. resposta final em JSON.

O prompt limita o modelo a uma ferramenta por resposta. Depois da execução da ferramenta, o resultado retorna ao modelo para nova decisão.

Esse ciclo continua até:

- o modelo produzir a resposta final;
- o grafo entrar em aprovação humana;
- algum orçamento ser atingido;
- um laço ser detectado;
- ocorrer um erro fatal.

## Estado explícito

O estado contém:

- mensagens;
- solicitação atual;
- `usuario_id`;
- `thread_id`;
- `turno_id`;
- memória semântica;
- memória episódica;
- fontes;
- trajetória;
- assinatura das decisões;
- número de passos;
- número de ferramentas;
- tokens de entrada;
- tokens de saída;
- custo;
- horário inicial;
- último plano;
- saída validada;
- erro fatal;
- motivo de término.

A lista de mensagens contém somente o protocolo conversacional necessário para a API: mensagens do usuário, respostas do modelo, chamadas e retornos de ferramentas.

## Orçamento

| Limite | Valor padrão | Proteção |
|---|---:|---|
| Passos do modelo | 10 | Evita laços longos |
| Chamadas de ferramentas | 8 | Evita uso excessivo das integrações |
| Tokens totais | 12.000 | Limita contexto e custo |
| Tempo | 90 segundos | Encerra uma execução excessivamente lenta |
| Custo | US$ 0,15 | Interrompe antes de ultrapassar o orçamento |
| Recursão do grafo | 24 | Limita o dano se outra proteção falhar |
| Repetições idênticas | 3 | Detecta repetição da mesma decisão |

Os valores são configurados no `.env` e documentados no `.env.example`.

## Motivos de término

O sistema registra por que uma execução terminou.

Os principais motivos são:

- `CONCLUIDO`;
- `PRECISA_INFORMACAO`;
- `RECUSADO`;
- `AGUARDANDO_APROVACAO`;
- `APROVACAO_REJEITADA`;
- `APROVACAO_EXPIRADA`;
- `LIMITE_DE_PASSOS`;
- `LIMITE_DE_FERRAMENTAS`;
- `LIMITE_DE_TOKENS`;
- `LIMITE_DE_TEMPO`;
- `LIMITE_DE_CUSTO`;
- `LACO_DETECTADO`;
- `ERRO_DO_MODELO`;
- `ERRO_VALIDADO`.

O motivo aparece no retorno da fachada e no log da execução.

## Human-in-the-loop

O único perfil autorizado a aprovar uma escrita é o proprietário.

O grafo para no nó `aprovar_plano` antes de registrar um plano. A interrupção apresenta:

- ação;
- feira;
- total recomendado;
- quantidades;
- resumo;
- consequência da escrita;
- prazo de expiração;
- respostas aceitas.

O proprietário pode:

- aprovar;
- rejeitar;
- editar o resumo;
- não responder.

A aprovação expira em 24 horas. O sistema nunca aprova por padrão.

O `SqliteSaver` mantém a interrupção mesmo que o programa seja encerrado.

## Persistência

```text
dados/checkpoints.sqlite3
    estado das threads
    interrupções pendentes
    retomada do grafo

dados/memoria.sqlite3
    preferências
    episódios
    planos aprovados
```

Os arquivos SQLite são locais e não são enviados ao GitHub.

Os dados de produção permanecem no MySQL:

```text
pasteis_miyata
```

## Nível de autonomia

O sistema é um agente com laço de ferramentas e autonomia limitada.

A decisão que justifica o agente está no nó `chamar_modelo`. Diante de texto livre, o modelo precisa decidir em tempo de execução se deve:

- pedir informação;
- consultar uma operação;
- consultar histórico;
- buscar uma regra;
- calcular uma recomendação;
- salvar uma preferência;
- solicitar o registro de um plano;
- recusar;
- responder.

Um workflow linear não resolveria porque entradas diferentes exigem caminhos diferentes.

Exemplos:

```text
Planeje sábado.
```

Essa entrada exige descobrir se o proprietário deseja `SAB_C`, `SAB_E` ou ambas.

```text
Consulte a operação 101.
```

Essa entrada exige consulta estruturada ao MySQL.

```text
Frango pode ser vendido na SAB_E?
```

Essa entrada exige recuperação de conhecimento documental.

Apesar da decisão do modelo, as condições verificáveis permanecem em código:

- orçamento;
- nome das ferramentas;
- validação dos argumentos;
- vigência dos documentos;
- regras fixas das feiras;
- validação da saída;
- idempotência;
- confirmação humana.

## Menor autonomia que resolve

Não foram adotados:

- sistema multiagente;
- router separado;
- paralelização;
- orquestrador com trabalhadores;
- avaliador-otimizador.

Um único agente com ferramentas e portões determinísticos atende ao escopo atual. Essa escolha segue a regra de utilizar a menor autonomia que resolve o problema.

## Conferência do desenho contra o código

O grafo foi inspecionado com:

```powershell
python.exe conferir_grafo.py
```

Resultado:

```text
========================================================================
NÓS DO GRAFO
========================================================================
- __end__
- __start__
- aprovar_plano
- chamar_modelo
- executar_ferramentas
- memorizar_episodio
- preparar_contexto
- validar_saida

========================================================================
ARESTAS DO GRAFO
========================================================================
- __start__ -> preparar_contexto [direta]
- aprovar_plano -> chamar_modelo [direta]
- chamar_modelo -> aprovar_plano [condicional]
- chamar_modelo -> executar_ferramentas [condicional]
- chamar_modelo -> validar_saida [condicional]
- executar_ferramentas -> chamar_modelo [direta]
- preparar_contexto -> chamar_modelo [direta]
- validar_saida -> memorizar_episodio [direta]
- memorizar_episodio -> __end__ [direta]
```

Essa conferência mostra que o desenho documentado corresponde ao grafo compilado.