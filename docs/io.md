# Contratos de entrada e saída

## Entrada

A entrada pública do sistema é validada pelo modelo Pydantic `EntradaAgente`:

```json
{
  "texto": "texto livre digitado pelo proprietário",
  "usuario_id": "proprietario",
  "thread_id": "identificador da conversa"
}
```

Somente o campo `texto` representa a solicitação digitada pelo proprietário. Os campos `usuario_id` e `thread_id` são metadados fornecidos pela interface de terminal ou por um futuro sistema consumidor do agente.

O campo `thread_id` identifica a conversa:

- a mesma `thread_id` recupera o checkpoint e continua a conversa;
- uma nova `thread_id` começa uma conversa sem estado anterior;
- conversas diferentes podem acessar as mesmas memórias de longo prazo do proprietário.

O texto pode conter uma consulta, uma solicitação de recomendação, uma pergunta sobre regras ou um pedido de registro de plano.

Exemplo:

```json
{
  "texto": "Calcule uma recomendação de produção para a feira QUA.",
  "usuario_id": "proprietario",
  "thread_id": "proprietario-principal"
}
```

## Saída

Toda execução devolve um objeto validado pelo modelo Pydantic `SaidaAgente`:

```json
{
  "status": "concluido | precisa_informacao | recusado | aguardando_aprovacao | erro",
  "resultado": null,
  "fontes": [],
  "suficiente": false,
  "motivo": "justificativa obrigatória",
  "proxima_acao": null
}
```

Os campos possuem as seguintes funções:

| Campo | Função |
|---|---|
| `status` | Informa como a execução terminou |
| `resultado` | Contém o resultado apresentado ao proprietário |
| `fontes` | Identifica documentos, registros ou ferramentas realmente utilizados |
| `suficiente` | Informa se os dados disponíveis sustentam a resposta |
| `motivo` | Explica por que a resposta foi ou não concluída |
| `proxima_acao` | Informa o que o proprietário pode fazer em seguida |

Uma recusa também é uma saída válida. Quando o sistema não possui informação suficiente, ele não deve inventar um resultado. Nesse caso, devolve `suficiente=false` e explica o motivo.

As fontes incluídas no objeto final pertencem somente ao turno atual. O sistema não apresenta como fonte um documento ou registro que não tenha sido efetivamente consultado.

## Exemplos reais

Os exemplos abaixo serão inseridos automaticamente a partir dos logs das execuções demonstradas, sem edição manual.

Os comandos responsáveis pela geração são:

```powershell
python.exe -m scripts.executar_casos_parte2
python.exe -m scripts.gerar_io
```

O primeiro comando executa e registra os seis casos da Parte 2. O segundo lê os logs oficiais e insere exemplos reais neste documento.

<!-- INICIO_EXEMPLOS_REAIS -->

`[PENDENTE: executar os seis casos com o MySQL e a API configurados]`

<!-- FIM_EXEMPLOS_REAIS -->

## Entradas não atendíveis

### Entrada incompleta

Exemplo:

```text
Calcule uma recomendação para a próxima feira.
```

O sistema não pode escolher uma feira silenciosamente. A saída deve utilizar `status=precisa_informacao`, informar que a feira está ausente e não chamar a ferramenta de recomendação.

### Entrada ambígua

Exemplo:

```text
Planeje a produção de sábado.
```

Existem duas feiras diferentes no sábado: `SAB_C` e `SAB_E`. O sistema deve perguntar se o proprietário deseja uma delas ou ambas.

### Registro inexistente

Exemplo:

```text
Consulte a operação 999999.
```

A consulta deve ser enviada ao MySQL. Se o identificador não existir, o erro retornado pela ferramenta deve ser tratado como dado. O agente não pode transformar a ausência em valores iguais a zero nem inventar uma operação.

### Pergunta fora do corpus

Exemplo:

```text
Qual é o fornecedor da massa e o prazo de entrega combinado?
```

Essa informação não está documentada no corpus atual. A saída deve utilizar `suficiente=false`, recusar a resposta e informar qual documento ou conhecimento está faltando.

### Ação fora do escopo

Solicitações de compra de ingredientes, contato com fornecedores, movimentação financeira ou início da produção física estão fora do escopo. O agente pode explicar o limite e sugerir uma ação permitida, mas não deve executar nem simular essas operações.