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

### Caminho feliz

- Data: `2026-10-19T21:56:34.515954`
- Commit: `00bab3576c181c4ea08360a37714eb49d9ad94b3`
- Log: `logs/01_caso_simples.json`

Entrada exata:

```text
Calcule uma recomendação de produção para a feira QUA.
```

Saída completa:

```json
{
  "status": "concluido",
  "resultado": {
    "ok": true,
    "fonte": "mysql:pasteis_miyata.operacoes/QUA",
    "metodo": "baseline_media_vendas_5_operacoes",
    "feira": "QUA",
    "operacoes_consideradas": 5,
    "recomendacoes": [
      {
        "id_produto": 1,
        "produto": "Carne",
        "demanda_media": 46.8,
        "quantidade_recomendada": 47
      },
      {
        "id_produto": 2,
        "produto": "Carne com queijo",
        "demanda_media": 62.4,
        "quantidade_recomendada": 62
      },
      {
        "id_produto": 3,
        "produto": "Carne com ovo",
        "demanda_media": 13.6,
        "quantidade_recomendada": 14
      },
      {
        "id_produto": 4,
        "produto": "Carne seca",
        "demanda_media": 23.2,
        "quantidade_recomendada": 23
      },
      {
        "id_produto": 5,
        "produto": "Frango",
        "demanda_media": 3.4,
        "quantidade_recomendada": 3
      },
      {
        "id_produto": 6,
        "produto": "Frango catupiri",
        "demanda_media": 65.0,
        "quantidade_recomendada": 65
      },
      {
        "id_produto": 7,
        "produto": "Queijo",
        "demanda_media": 40.4,
        "quantidade_recomendada": 40
      },
      {
        "id_produto": 8,
        "produto": "Pizza",
        "demanda_media": 42.2,
        "quantidade_recomendada": 42
      },
      {
        "id_produto": 9,
        "produto": "Bauru",
        "demanda_media": 13.4,
        "quantidade_recomendada": 13
      },
      {
        "id_produto": 10,
        "produto": "4 queijos",
        "demanda_media": 13.8,
        "quantidade_recomendada": 14
      },
      {
        "id_produto": 11,
        "produto": "Calabresa com queijo",
        "demanda_media": 15.8,
        "quantidade_recomendada": 16
      },
      {
        "id_produto": 12,
        "produto": "Calabresa com catupiri",
        "demanda_media": 8.4,
        "quantidade_recomendada": 8
      },
      {
        "id_produto": 13,
        "produto": "Salame",
        "demanda_media": 5.6,
        "quantidade_recomendada": 6
      },
      {
        "id_produto": 14,
        "produto": "Escarola com bacon",
        "demanda_media": 6.6,
        "quantidade_recomendada": 7
      },
      {
        "id_produto": 15,
        "produto": "Escarola sem bacon",
        "demanda_media": 1.4,
        "quantidade_recomendada": 1
      },
      {
        "id_produto": 16,
        "produto": "Caipira",
        "demanda_media": 17.4,
        "quantidade_recomendada": 17
      },
      {
        "id_produto": 17,
        "produto": "Palmito",
        "demanda_media": 13.4,
        "quantidade_recomendada": 13
      },
      {
        "id_produto": 18,
        "produto": "Camarão",
        "demanda_media": 22.2,
        "quantidade_recomendada": 22
      },
      {
        "id_produto": 19,
        "produto": "Portuguesa",
        "demanda_media": 11.6,
        "quantidade_recomendada": 12
      },
      {
        "id_produto": 20,
        "produto": "Especial de carne",
        "demanda_media": 9.6,
        "quantidade_recomendada": 10
      },
      {
        "id_produto": 21,
        "produto": "Especial de frango",
        "demanda_media": 2.8,
        "quantidade_recomendada": 3
      },
      {
        "id_produto": 22,
        "produto": "Especial de calabresa",
        "demanda_media": 1.6,
        "quantidade_recomendada": 2
      },
      {
        "id_produto": 23,
        "produto": "Especial de pizza",
        "demanda_media": 1.6,
        "quantidade_recomendada": 2
      },
      {
        "id_produto": 24,
        "produto": "Especial de portuguesa",
        "demanda_media": 1.8,
        "quantidade_recomendada": 2
      },
      {
        "id_produto": 25,
        "produto": "Chocolate",
        "demanda_media": 27.8,
        "quantidade_recomendada": 28
      },
      {
        "id_produto": 26,
        "produto": "Banana com chocolate",
        "demanda_media": 2.4,
        "quantidade_recomendada": 2
      },
      {
        "id_produto": 27,
        "produto": "Banana com doce de leite",
        "demanda_media": 2.0,
        "quantidade_recomendada": 2
      }
    ],
    "total_recomendado": 476,
    "regras_aplicadas": {
      "produtos_excluidos": [],
      "produtos_descontinuados_excluidos": [
        "Banana simples"
      ]
    },
    "aviso": "Este baseline é verificável e não é a previsão definitiva do TCC. O LLM não calculou as quantidades."
  },
  "fontes": [
    {
      "tipo": "mysql",
      "referencia": "mysql:pasteis_miyata.operacoes/QUA",
      "detalhe": "Retornado pela ferramenta calcular_recomendacao."
    }
  ],
  "suficiente": true,
  "motivo": "A recomendação foi calculada por uma ferramenta determinística e validada pelo código.",
  "proxima_acao": "Revise o plano e solicite o registro se desejar submetê-lo à aprovação."
}
```

Leia `status=concluido`, `suficiente=true` e as fontes provenientes do MySQL.

### Entrada incompleta

- Data: `2026-10-19T21:56:42.497377`
- Commit: `00bab3576c181c4ea08360a37714eb49d9ad94b3`
- Log: `logs/04_acao_nao_permitida.json`

Entrada exata:

```text
Calcule uma recomendação para a próxima feira.
```

Saída completa:

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

Leia `status=precisa_informacao`, `suficiente=false` e a solicitação da feira ausente.

### Recusa fora do corpus

- Data: `2026-10-19T21:56:44.873025`
- Commit: `00bab3576c181c4ea08360a37714eb49d9ad94b3`
- Log: `logs/05_pergunta_fora_corpus.json`

Entrada exata:

```text
Qual é o fornecedor da massa e o prazo de entrega combinado?
```

Saída completa:

```json
{
  "status": "recusado",
  "resultado": null,
  "fontes": [
    {
      "tipo": "sistema",
      "referencia": "src/prompts/orquestrador_v2.md",
      "detalhe": "Contrato e limites do agente."
    }
  ],
  "suficiente": false,
  "motivo": "Nenhum documento vigente do corpus sustenta a identificação do fornecedor da massa ou do prazo de entrega combinado.",
  "proxima_acao": "Forneça um documento vigente ou registre essas informações no corpus da Pastéis Miyata."
}
```

Leia `status=recusado`, `suficiente=false`, o motivo da recusa e a próxima ação possível.

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
