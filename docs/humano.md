# Human-in-the-loop

## Ponto de parada

O grafo para no nó:

```text
aprovar_plano
```

A interrupção acontece antes da escrita na tabela `planos_aprovados`, armazenada em `dados/memoria.sqlite3`.

O critério é objetivo: registrar um plano cria estado persistente que poderá orientar a produção da pastelaria.

As operações abaixo não interrompem o grafo porque são somente leitura ou cálculo:

- consultar histórico;
- consultar operação;
- buscar conhecimento;
- calcular recomendação.

O registro de uma preferência explicitamente declarada também não exige o mesmo nível de confirmação porque pode ser substituído por uma versão posterior. Já o plano aprovado representa uma decisão operacional e exige confirmação.

## Como a pausa é acionada

O modelo pode chamar a ferramenta:

```text
registrar_plano
```

Essa chamada não grava o plano diretamente. A aresta condicional encaminha a execução para `aprovar_plano`, que utiliza:

```python
interrupt(pedido)
```

O grafo é pausado e o estado fica salvo no checkpointer.

## O que o proprietário vê

O pedido de aprovação apresenta:

- ação exata: `registrar_plano`;
- feira;
- total recomendado;
- quantidades por produto;
- resumo;
- consequência da escrita;
- local da escrita;
- horário de expiração;
- respostas aceitas.

Exemplo estrutural:

```json
{
  "acao": "registrar_plano",
  "argumentos": {
    "feira": "QUA",
    "total_recomendado": 500,
    "resumo_plano": "Plano semanal calculado pelo agente.",
    "plano": []
  },
  "consequencia": "O plano será gravado em dados/memoria.sqlite3.",
  "respostas_aceitas": [
    "aprovar",
    "rejeitar",
    "editar"
  ],
  "expira_em": "data e hora em UTC"
}
```

O sistema não mostra apenas uma pergunta genérica como “confirma?”. O proprietário recebe os argumentos e a consequência da ação.

## Respostas aceitas

### Aprovar

```json
{
  "acao": "aprovar"
}
```

O plano é gravado exatamente com os argumentos apresentados.

### Rejeitar

```json
{
  "acao": "rejeitar"
}
```

Nenhuma escrita é realizada. O resultado da ferramenta informa que a aprovação foi rejeitada.

### Editar

```json
{
  "acao": "editar",
  "resumo_plano": "Plano semanal aprovado com revisão do proprietário."
}
```

O proprietário pode editar o resumo antes da escrita.

A feira, as quantidades e o total não são editados diretamente no ponto de aprovação. Alterar esses valores isoladamente quebraria a consistência do plano calculado. Para modificá-los, o proprietário deve solicitar outra simulação.

### Expirar

```json
{
  "acao": "expirar"
}
```

Essa decisão é aplicada pelo código quando a retomada acontece depois do prazo permitido.

## Retomada

A retomada utiliza:

```python
Command(resume=decisao)
```

Ela precisa utilizar a mesma `thread_id` da conversa que gerou a interrupção.

O checkpointer recupera:

- mensagens;
- plano calculado;
- pedido de ferramenta;
- argumentos;
- trajetória;
- ponto de interrupção.

O nó `aprovar_plano` reinicia desde o início, conforme o comportamento do `interrupt`. Antes do ponto de interrupção existem somente leitura do estado e montagem do pedido. A escrita ocorre somente depois da retomada.

## Persistência da pausa

O checkpointer utiliza:

```text
dados/checkpoints.sqlite3
```

Por isso, a aprovação pendente sobrevive:

- ao encerramento do programa;
- à reabertura do terminal;
- à criação de uma nova instância da fachada.

Desde que seja utilizada a mesma `thread_id`, o agente consegue localizar a aprovação pendente.

## Silêncio do proprietário

O prazo padrão é:

```text
APPROVAL_TIMEOUT_HOURS=24
```

Se o proprietário não responder, a execução permanece pausada e persistida.

Quando houver uma tentativa posterior de retomada, o código compara o horário atual com `expira_em`.

Se o prazo tiver vencido:

- a decisão passa a ser `expirar`;
- nenhuma escrita é realizada;
- o agente informa que a aprovação expirou.

O sistema nunca aprova automaticamente por silêncio.

## Idempotência

O conteúdo do plano recebe uma chave SHA-256.

A tabela `planos_aprovados` possui uma restrição única para essa chave.

Na primeira gravação:

```json
{
  "ok": true,
  "ja_existia": false
}
```

Em uma repetição com o mesmo conteúdo:

```json
{
  "ok": true,
  "ja_existia": true
}
```

A contagem permanece igual a um.

Essa proteção cobre retomadas repetidas, falhas de comunicação e novas tentativas com o mesmo payload.

## Usuário autorizado

O único usuário autorizado é o proprietário.

A identidade padrão é configurada por:

```text
AGENT_USER_ID=proprietario
```

Nesta versão não existem outros perfis com permissão para registrar o plano.

## Evidências

O teste automatizado de idempotência foi executado junto com a suíte:

```powershell
python.exe -m unittest discover -s tests -v
```

Resultado:

```text
Ran 8 tests in 0.161s

OK
```

O caso integrado número 6 também demonstrará:

1. cálculo de uma recomendação;
2. solicitação de registro;
3. pausa do grafo;
4. retomada com edição do resumo;
5. escrita aprovada;
6. repetição idempotente;
7. permanência de apenas um registro.

A evidência será salva em:

```text
logs/06_human_in_the_loop.json
```