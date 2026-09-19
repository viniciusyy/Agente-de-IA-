# Arquitetura v1 — Agente de Planejamento de Produção

## Visão geral

O sistema será utilizado exclusivamente pelo proprietário da Pastéis Miyata para consultar dados históricos, solicitar previsões, simular cenários e obter recomendações de produção.

O LLM será responsável por interpretar as mensagens, identificar a intenção do proprietário, descobrir informações ausentes e selecionar a rota adequada.

Os cálculos de previsão de demanda, otimização por Simplex e validação das regras serão executados por ferramentas externas e determinísticas. O LLM não poderá inventar quantidades nem aprovar um plano em nome do proprietário.

A arquitetura inicial utiliza os seguintes padrões:

- **Router:** identifica a intenção do proprietário;
- **Sequencial com portões:** executa as etapas conhecidas do planejamento;
- **Ferramentas determinísticas:** realizam consultas, previsões, otimização e validações;
- **Humano no laço:** exige a confirmação do proprietário antes de registrar a aprovação.

---

## 1. Entrada

### O que chega ao sistema

A entrada será uma mensagem de texto livre enviada pelo proprietário por meio de um chat executado inicialmente no terminal.

Exemplos:

- “Planeje a produção para as feiras de sábado.”
- “Quanto foi vendido na última feira de quarta-feira?”
- “Simule o plano considerando chuva forte.”
- “Por que a recomendação da `SAB_E` ficou menor?”
- “Aprovo esse plano.”

Na primeira versão, o sistema não receberá arquivos, formulários ou eventos automáticos de outros sistemas.

### Origem e disparo

O proprietário sempre iniciará a interação. O agente não acordará sozinho, não realizará planejamentos automaticamente e não enviará recomendações sem uma solicitação.

O agente será utilizado somente pelo proprietário da Pastéis Miyata.

### Heterogeneidade das entradas

Apesar de todas as entradas serem mensagens de texto, elas podem representar intenções diferentes.

A proporção inicial estimada é:

| Tipo de entrada | Proporção estimada | Exemplo |
|---|---:|---|
| Solicitação de planejamento | 60% | “Planeje a produção de sábado.” |
| Consulta ou explicação | 20% | “Quanto sobrou na última feira?” |
| Continuação, simulação ou aprovação | 15% | “Refaça considerando chuva forte.” |
| Solicitação fora do escopo ou inválida | 5% | “Faça uma atividade que não está relacionada à produção.” |

Essas proporções são estimativas iniciais e poderão ser atualizadas após o uso do sistema.

Como existem diferentes intenções, será utilizado um **Router** para escolher uma entre quatro rotas conhecidas:

1. planejamento;
2. consulta ou explicação;
3. continuidade de um plano;
4. solicitação fora do escopo.

---

## 2. System

### System prompt

> Você é um agente de apoio ao planejamento da Pastéis Miyata: interpreta os pedidos do proprietário e coordena ferramentas de consulta, previsão, otimização e validação, mas não inventa quantidades, não aprova decisões e não executa fisicamente a produção.

### Ferramentas

| Ferramenta | Função | Tipo | Escrita | Reversibilidade |
|---|---|---|---|---|
| `consultar_historico` | Consulta no MySQL os registros de produção, venda, sobra, clima, feira e feriado | Leitura | Não | Não se aplica |
| `consultar_regras_feira` | Consulta produtos permitidos, dias de produção e demais regras das feiras | Leitura | Não | Não se aplica |
| `executar_previsao` | Executa o modelo de previsão escolhido e devolve a demanda prevista | Processamento | Não | Pode ser executada novamente |
| `otimizar_producao` | Utiliza o Simplex para calcular a recomendação de produção respeitando as restrições | Processamento | Não | Pode ser executada novamente |
| `validar_plano` | Verifica capacidade, quantidades, produtos permitidos e consistência do plano | Processamento | Não | Pode ser executada novamente |
| `registrar_plano_aprovado` | Registra que determinado plano foi aprovado pelo proprietário | Escrita idempotente | Sim | Reversível por cancelamento |

A ferramenta `registrar_plano_aprovado` somente poderá ser chamada depois de uma confirmação explícita do proprietário.

A operação será idempotente: uma mesma execução não poderá registrar duas aprovações iguais. A identificação será realizada pelo `execucao_id` e pelo identificador do plano.

O cancelamento não apagará o registro original. O plano será marcado como cancelado para preservar o histórico da decisão.

A aprovação registrada não inicia a produção. Ela apenas registra a decisão do proprietário.

### Estado

O estado não será composto apenas pelo histórico de mensagens. As informações importantes serão armazenadas em campos estruturados.

O estado deverá manter:

```json
{
  "execucao_id": "identificador único",
  "objetivo": "objetivo original do proprietário",
  "rota": "planejamento | consulta | continuidade | fora_escopo",
  "contexto": {
    "data_venda": null,
    "feiras": [],
    "clima_por_feira": {},
    "feriado": null,
    "evento": null,
    "capacidade_maxima": null,
    "ingredientes_indisponiveis": [],
    "prioridade": null
  },
  "campos_faltantes": [],
  "historico_consultado": null,
  "previsao": null,
  "restricoes": [],
  "plano_recomendado": null,
  "validacao": null,
  "passos_executados": [],
  "erros": [],
  "tokens_gastos": 0,
  "tempo_gasto_segundos": 0,
  "pendencia_confirmacao": null,
  "termino": null
}
```

O texto original do proprietário será interpretado na entrada. As etapas seguintes receberão principalmente os campos estruturados extraídos, evitando repetir a mensagem completa em todas as chamadas.

O estado também registrará:

- quais ferramentas foram chamadas;
- quais argumentos foram utilizados;
- os resultados devolvidos;
- os erros encontrados;
- quantos passos foram executados;
- quantos tokens foram consumidos;
- por que a execução terminou;
- se existe uma confirmação pendente.

### Orçamento

A arquitetura inicial utilizará os seguintes limites:

```text
MAX_PASSOS_INTERNOS = 8
MAX_CHAMADAS_LLM = 4
MAX_TOKENS_TOTAL = 12000
MAX_TEMPO_SEGUNDOS = 60
MAX_PERGUNTAS_AO_PROPRIETARIO = 3
MAX_AJUSTES_DO_PLANO = 2
MAX_CENARIOS_POR_CONVERSA = 3
```

Se algum limite for atingido, o agente deverá interromper a execução e explicar o motivo ao proprietário.

Exemplo:

> Não consegui concluir o planejamento dentro do limite de execução. Nenhum plano foi registrado. Verifique as informações fornecidas e tente novamente.

---

## 3. Processamento

### Esboço do fluxo

```text
1. ENTRADA
   recebe uma mensagem de texto livre do proprietário
   [—]

2. TRIAGEM
   identifica a intenção e extrai as informações já fornecidas
   [ROUTER — 4 rotas, 1 chamada ao LLM]

      planejamento  -> segue para a etapa 3
      consulta      -> consulta os dados necessários e segue para a etapa 8
      continuidade  -> recupera o estado do plano:
                        simulação -> retorna à etapa 3
                        aprovação ou rejeição -> segue para a etapa 8
      fora_escopo   -> recusa explicada e segue para a etapa 8

3. CONTEXTO
   verifica os campos obrigatórios e pergunta apenas o que estiver faltando
   [SEQUENCIAL + PORTÃO EM CÓDIGO — MAX_PERGUNTAS = 3]

4. HISTÓRICO
   consulta os dados e as regras relacionadas às feiras solicitadas
   [LEITURA — sem escrita]

5. PREVISÃO
   executa o modelo de previsão com os dados estruturados
   [FERRAMENTA DETERMINÍSTICA — sem escrita]

6. OTIMIZAÇÃO
   utiliza o Simplex para transformar a previsão em uma recomendação
   [SEQUENCIAL — sem escrita]

7. VALIDAÇÃO
   verifica capacidade, regras das feiras e consistência das quantidades
   [PORTÃO EM CÓDIGO — MAX_AJUSTES = 2]

      válido          -> segue para a etapa 8
      inválido        -> retorna à etapa 6 com as violações encontradas
      ainda inválido  -> encerra sem recomendar nem registrar um plano

8. RETORNO E APROVAÇÃO
   apresenta o resultado e aguarda a decisão do proprietário
   [HUMANO NO LAÇO]

      consultar ou simular -> nenhuma escrita
      rejeitar             -> nenhuma escrita
      aprovar              -> registra após confirmação explícita
                              [ESCRITA IDEMPOTENTE — reversível por cancelamento]
```

---

## O que sai de cada etapa

### 1. Entrada

**Entra:**

```json
{
  "texto": "Planeje a produção para as duas feiras de sábado."
}
```

**Sai:**

```json
{
  "execucao_id": "8f31c0a2",
  "mensagem_recebida": true
}
```

### 2. Triagem

**Entra:**

```json
{
  "execucao_id": "8f31c0a2",
  "texto": "Planeje a produção para as duas feiras de sábado."
}
```

**Sai:**

```json
{
  "rota": "planejamento",
  "confianca": 0.96,
  "justificativa": "O proprietário solicitou uma recomendação de produção.",
  "dados_extraidos": {
    "feiras": ["SAB_C", "SAB_E"]
  }
}
```

Se a solicitação estiver fora do escopo:

```json
{
  "rota": "fora_escopo",
  "confianca": 0.91,
  "justificativa": "A solicitação não está relacionada ao planejamento ou aos dados da Pastéis Miyata."
}
```

### 3. Contexto

**Entra:**

```json
{
  "rota": "planejamento",
  "dados_extraidos": {
    "feiras": ["SAB_C", "SAB_E"]
  }
}
```

**Sai quando faltarem informações:**

```json
{
  "status": "aguardando_informacoes",
  "campos_faltantes": [
    "data_venda",
    "clima_por_feira",
    "capacidade_maxima"
  ],
  "pergunta": "Qual é a data da venda, o clima esperado em cada feira e a capacidade máxima disponível?"
}
```

**Sai depois que o contexto estiver completo:**

```json
{
  "status": "contexto_completo",
  "contexto": {
    "data_venda": "2026-09-05",
    "feiras": ["SAB_C", "SAB_E"],
    "clima_por_feira": {
      "SAB_C": "GAROA",
      "SAB_E": "CHUVA_MODERADA"
    },
    "feriado": false,
    "evento": null,
    "capacidade_maxima": 1200,
    "ingredientes_indisponiveis": [],
    "prioridade": "equilibrar_sobra_e_falta"
  }
}
```

### 4. Histórico

**Entra:**

```json
{
  "data_venda": "2026-09-05",
  "feiras": ["SAB_C", "SAB_E"],
  "clima_por_feira": {
    "SAB_C": "GAROA",
    "SAB_E": "CHUVA_MODERADA"
  }
}
```

**Sai:**

```json
{
  "historico": {
    "quantidade_registros": 540,
    "feiras_encontradas": ["SAB_C", "SAB_E"],
    "periodo_inicial": "2026-06-06",
    "periodo_final": "2026-08-29"
  },
  "regras": {
    "SAB_E": {
      "produtos_bloqueados": [
        "Frango",
        "Escarola sem bacon"
      ]
    }
  },
  "alertas_qualidade": [
    "Parte dos registros pode representar demanda censurada."
  ]
}
```

### 5. Previsão

**Entra:**

```json
{
  "contexto": {
    "data_venda": "2026-09-05",
    "feiras": ["SAB_C", "SAB_E"],
    "clima_por_feira": {
      "SAB_C": "GAROA",
      "SAB_E": "CHUVA_MODERADA"
    }
  },
  "historico": "dados estruturados retornados pela etapa 4"
}
```

**Sai:**

```json
{
  "modelo_utilizado": "modelo selecionado pela validação temporal",
  "granularidade": "categoria_e_feira",
  "previsoes": [
    {
      "feira": "SAB_C",
      "demanda_prevista": 620
    },
    {
      "feira": "SAB_E",
      "demanda_prevista": 540
    }
  ],
  "alertas": [
    "A previsão da SAB_E possui maior incerteza devido à chuva moderada."
  ]
}
```

O LLM não cria esses números. Eles são devolvidos pelo módulo de previsão.

### 6. Otimização

**Entra:**

```json
{
  "previsoes": [
    {
      "feira": "SAB_C",
      "demanda_prevista": 620
    },
    {
      "feira": "SAB_E",
      "demanda_prevista": 540
    }
  ],
  "restricoes": {
    "capacidade_maxima": 1200,
    "produtos_bloqueados": {
      "SAB_E": [
        "Frango",
        "Escarola sem bacon"
      ]
    }
  }
}
```

**Sai:**

```json
{
  "status_simplex": "otimo",
  "plano": [
    {
      "feira": "SAB_C",
      "demanda_prevista": 620,
      "producao_recomendada": 610
    },
    {
      "feira": "SAB_E",
      "demanda_prevista": 540,
      "producao_recomendada": 530
    }
  ],
  "total_recomendado": 1140
}
```

### 7. Validação

**Entra:**

```json
{
  "plano": [
    {
      "feira": "SAB_C",
      "producao_recomendada": 610
    },
    {
      "feira": "SAB_E",
      "producao_recomendada": 530
    }
  ],
  "capacidade_maxima": 1200,
  "regras": "regras estruturadas retornadas pela etapa 4"
}
```

**Sai quando o plano for válido:**

```json
{
  "valido": true,
  "total_recomendado": 1140,
  "capacidade_respeitada": true,
  "regras_respeitadas": true,
  "violacoes": []
}
```

**Sai quando o plano for inválido:**

```json
{
  "valido": false,
  "violacoes": [
    {
      "regra": "capacidade_maxima",
      "mensagem": "A recomendação ultrapassou a capacidade em 40 unidades."
    }
  ],
  "acao": "reotimizar"
}
```

A validação será realizada por código porque seus critérios são objetivos e executáveis. Não será necessário utilizar outro LLM como avaliador.

### 8. Retorno e aprovação

**Entra:**

```json
{
  "plano": "plano validado",
  "alertas": "alertas da previsão e da validação",
  "pendencia_confirmacao": null
}
```

**Sai antes da aprovação:**

```json
{
  "status": "aguardando_confirmacao",
  "plano_id": "PL-8f31c0a2",
  "opcoes": [
    "aprovar",
    "rejeitar",
    "consultar_detalhes",
    "simular_outro_cenario"
  ]
}
```

Se o proprietário disser apenas “pode continuar”, o agente deverá pedir uma confirmação mais clara:

> Você confirma a aprovação do plano `PL-8f31c0a2`, com produção total de 1.140 pastéis?

Somente depois de uma resposta explícita, como “Confirmo a aprovação”, o registro poderá ser realizado.

**Sai depois da aprovação:**

```json
{
  "status": "aprovado",
  "plano_id": "PL-8f31c0a2",
  "aprovado_pelo_proprietario": true,
  "producao_iniciada": false
}
```

---

## Saída final apresentada ao proprietário

Exemplo de resposta que o proprietário verá:

> Para 5 de setembro de 2026, a recomendação é produzir 610 pastéis para a `SAB_C` e 530 para a `SAB_E`, totalizando 1.140 unidades. O plano respeita a capacidade máxima de 1.200 e as restrições das duas feiras. Deseja aprovar ou simular outro cenário?

Os números são apenas ilustrativos para demonstrar o formato da interação. Na execução real, serão produzidos pelos módulos de previsão e otimização.

---

## Justificativa dos padrões escolhidos

### Router

O **Router** foi escolhido porque a mesma interface recebe quatro tipos diferentes de intenção: planejamento, consulta, continuidade e solicitações fora do escopo.

Um fluxo sequencial único não seria suficiente, pois obrigaria consultas simples, aprovações e novos planejamentos a percorrerem etapas desnecessárias. O Router classifica a intenção e o código direciona a execução para uma das rotas previamente definidas.

### Sequencial com portões

Depois que a rota de planejamento é selecionada, as etapas são conhecidas e dependem umas das outras: a previsão depende do histórico, a otimização depende da previsão e a validação depende do plano.

Um prompt único não seria suficiente porque misturaria interpretação, consulta, previsão, otimização e validação em uma única chamada, dificultando a verificação e permitindo que o LLM inventasse resultados.

### Ferramentas determinísticas

Os módulos de previsão, Simplex e validação serão ferramentas determinísticas porque possuem entradas e saídas definidas e critérios verificáveis.

Não é necessário utilizar um LLM como avaliador, pois regras como capacidade máxima, quantidade negativa e produtos bloqueados podem ser verificadas diretamente por código.

### Humano no laço

A aprovação pertence exclusivamente ao proprietário. O agente poderá apresentar e explicar a recomendação, mas deverá interromper o fluxo antes da escrita e aguardar uma confirmação explícita.

Uma aprovação automática não seria adequada porque representa uma decisão do negócio e pode influenciar diretamente a produção.

---

## Aplicação da tabela de decisão

A tabela de decisão foi lida de cima para baixo:

1. **Prompt único:** não resolve, pois existem ferramentas, validações e confirmação;
2. **Sequencial com portão:** resolve cada rota individual, mas não identifica qual rota deve ser executada;
3. **Router:** é o primeiro padrão que resolve a variação das entradas;
4. **Sectioning e paralelização:** não são necessários porque as etapas dependem umas das outras;
5. **Orquestrador-trabalhador:** não é necessário porque as subtarefas já podem ser enumeradas antes da execução;
6. **Avaliador-otimizador:** não é necessário porque os critérios de validação podem ser executados por código;
7. **Agente autônomo:** não é necessário porque existe um fluxograma conhecido e o número de etapas pode ser limitado previamente.

Portanto, embora o sistema seja chamado de agente no contexto do trabalho, sua primeira versão será tecnicamente um **workflow com Router, ferramentas e portões determinísticos**.

Essa escolha segue o princípio de utilizar a menor autonomia capaz de resolver o problema.

Se, no futuro, o sistema precisar investigar situações com quantidade imprevisível de passos ou escolher subtarefas que não possam ser enumeradas previamente, a arquitetura poderá evoluir para um orquestrador ou agente com orçamento explícito.

