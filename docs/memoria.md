# Memória do agente

## Curto e longo prazo

| | Curto prazo | Longo prazo |
|---|---|---|
| O que é | Estado da conversa identificada por `thread_id` | Informação selecionada que atravessa conversas |
| Conteúdo no case | Mensagens, objetivo do turno, trajetória, fontes, último plano, contadores e aprovação pendente | Episódios concluídos, preferências operacionais e procedimento do agente |
| Persistência | `dados/checkpoints.sqlite3`, pelo `SqliteSaver` | `dados/memoria.sqlite3` e arquivos em `src/prompts/` |
| Ciclo de vida | Retomado enquanto a thread existir | Compartilhado entre threads do mesmo `usuario_id` |

O checkpoint contém tudo que permite retomar a execução sem repetir uma escrita:

- mensagens;
- pedido de ferramenta;
- argumentos do plano;
- ponto de `interrupt`;
- estado do grafo.

Como a escrita acontece somente depois do `interrupt`, a retomada não reaplica um efeito colateral anterior à decisão humana.

## Checkpoint, memória e RAG

| Estrutura | No case | Para que serve | Quem escreve |
|---|---|---|---|
| Checkpoint | Estado da thread e aprovação pendente | Retomar uma execução | LangGraph |
| Memória | Preferências e episódios selecionados | Lembrar informações entre conversas | Código, seguindo uma política explícita |
| RAG | Documentos curados da Pastéis Miyata | Consultar regras e conhecimento do domínio | Responsável pelo corpus |

Serializar todas as execuções não produziria uma memória útil.

A recuperação episódica devolve somente os três episódios mais semelhantes ao pedido atual e aplica decaimento temporal.

Trajetórias irrelevantes permanecem nos logs e checkpoints, mas não ocupam o prompt.

## Três tipos de memória

| Tipo | Conteúdo | Estrutura | Leitura |
|---|---|---|---|
| Episódica | Resumo de execuções conclusivas | Tabela SQLite e similaridade lexical | Até três episódios por relevância |
| Semântica | Preferências estáveis declaradas pelo proprietário | Chave-valor versionado no SQLite | Versão mais recente de cada chave |
| Procedural | Processo utilizado para consultar, calcular e aprovar | `src/prompts/procedimento_planejamento_v1.md` | Incluída em toda chamada do modelo |

## Política de escrita

A política de escrita é híbrida e conservadora:

- o código grava no máximo um episódio quando a saída é conclusiva e suficiente;
- o modelo pode chamar `salvar_preferencia`, mas somente para uma declaração explícita do proprietário;
- a chave de idempotência é calculada com SHA-256 sobre o conteúdo canônico;
- a resposta de toda escrita informa `ja_existia`.

O volume esperado por execução é:

- zero ou um episódio, normalmente abaixo de 1.000 caracteres;
- zero ou um fato semântico, somente quando houver declaração explícita.

## Contradição e versionamento

Uma preferência contraditória cria uma nova versão com carimbo de tempo.

A leitura utiliza a versão de maior identificador sem apagar a versão anterior.

Exemplo:

1. o proprietário informa que a prioridade é reduzir sobra;
2. posteriormente, informa que a prioridade é evitar falta;
3. a segunda informação cria uma nova versão;
4. a leitura passa a utilizar a versão mais recente.

## Decaimento

Os episódios sofrem decaimento de relevância com meia-vida configurável de 90 dias.

O decaimento rebaixa episódios antigos, mas não os apaga automaticamente.

Não foi implementada remoção de titular nesta versão porque:

- o sistema é usado somente pelo proprietário;
- não são armazenados dados pessoais de clientes.

Uma remoção completa exigiria limpar:

- memória de longo prazo;
- checkpoints;
- logs.

Não seria correto prometer essa cobertura sem implementá-la.

## Conversa

O `thread_id` padrão é:

`proprietario-principal`

Ele pode ser alterado pela variável:

`AGENT_THREAD_ID`

Duas conversas simultâneas precisam utilizar identificadores diferentes.

Elas não compartilham checkpoints, mas podem ler as mesmas memórias de longo prazo do:

`usuario_id=proprietario`

O checkpointer utiliza SQLite. Portanto, a conversa e uma aprovação pendente sobrevivem ao encerramento do programa.

Os arquivos SQLite são locais e ignorados pelo Git.

## Controle da janela de contexto

Quando a conversa cresce, o código envia ao modelo somente os últimos seis turnos completos.

O descarte acontece nesta ordem:

1. turnos conversacionais antigos e seus retornos de ferramentas;
2. episódios recuperados de menor relevância;
3. nunca são descartados o prompt procedural, o objetivo atual e os retornos de ferramentas do turno atual.

O checkpoint continua mantendo o estado completo.

Somente a janela enviada ao modelo é reduzida.

Ao final da conversa, sobrevivem apenas:

- preferências explícitas;
- resumos de saídas conclusivas;
- procedimento versionado do agente.

## Fronteira com o MySQL

O MySQL não funciona como memória conversacional do agente. Ele continua sendo o sistema tradicional responsável pelos dados operacionais da Pastéis Miyata, incluindo:

- operações;
- produção;
- sobras;
- vendas;
- feiras;
- produtos;
- feriados.

O SQLite é utilizado somente para:

- checkpoints do LangGraph;
- memória semântica;
- memória episódica;
- registro de planos aprovados.

Essa separação impede que estado de conversa seja misturado com os registros operacionais reais do negócio.

## Planos aprovados e idempotência

Os planos aprovados são registrados em `dados/memoria.sqlite3`.

Antes da escrita, o conteúdo do plano é transformado em JSON canônico e recebe uma chave calculada com:

```text
SHA-256(JSON ordenado do plano)
```

Essa chave funciona como chave de idempotência. Se o mesmo plano for enviado novamente, o sistema devolve:

```json
{
  "ok": true,
  "ja_existia": true
}
```

O banco permanece com apenas um registro para aquele conteúdo.

Essa proteção evita duplicidade caso uma execução seja retomada depois de uma interrupção, reinício do programa ou repetição acidental da mesma solicitação.

## Memória e human-in-the-loop

O pedido de aprovação pendente pertence ao checkpoint da conversa.

Antes de registrar um plano, o grafo apresenta:

- a ação solicitada;
- a feira;
- o total recomendado;
- o resumo;
- as quantidades;
- a consequência da escrita;
- o prazo para resposta.

O proprietário pode:

- aprovar;
- rejeitar;
- editar;
- não responder.

Somente uma aprovação ou edição válida permite que o plano seja gravado na memória de longo prazo.

Se o proprietário rejeitar ou se o prazo expirar, nenhuma escrita é realizada.

## Três causas de esquecimento

### 1. Limite da janela de contexto

Conversas antigas deixam de ser enviadas integralmente ao modelo.

A cobertura utilizada é:

- checkpoint para preservar o estado;
- memória episódica para recuperar experiências relevantes;
- memória semântica para preservar preferências estáveis.

### 2. Encerramento do processo

Sem persistência, o encerramento do programa apagaria a conversa e qualquer aprovação pendente.

A cobertura utilizada é:

- `SqliteSaver` para os checkpoints;
- SQLite para memórias e planos;
- retomada pela mesma `thread_id`.

### 3. Informação substituída ou contraditória

Uma preferência nova pode contradizer uma preferência anterior.

A cobertura utilizada é:

- criação de uma nova versão;
- armazenamento do carimbo de tempo;
- leitura da versão mais recente;
- preservação da versão anterior para auditoria.

## O que não entra na memória

Não são armazenados como memória permanente:

- todas as mensagens digitadas pelo proprietário;
- respostas recusadas;
- resultados incompletos;
- erros temporários de ferramenta;
- cadeia de pensamento do modelo;
- chave da API;
- senha do MySQL;
- outras credenciais;
- dados pessoais de clientes.

A trajetória completa pode permanecer nos logs e checkpoints para auditoria, mas não é automaticamente transformada em preferência ou fato permanente.

## Evidência de teste

Os testes automatizados verificaram:

- criação de duas versões de uma preferência;
- leitura da versão mais recente;
- registro idempotente de um plano;
- repetição da mesma escrita sem duplicidade.

Comando executado:

```powershell
python.exe -m unittest discover -s tests -v
```

Resultado:

```text
Ran 8 tests in 0.161s

OK
```

Os testes de memória utilizaram bancos SQLite temporários. Nenhum dado operacional do MySQL foi alterado.