# Análise e escolha do modelo

Este documento compara três modelos candidatos para o agente de planejamento de produção da Pastéis Miyata.

A escolha considera as necessidades reais do sistema: compreender solicitações em português, identificar informações ausentes, selecionar ferramentas, produzir argumentos estruturados e respeitar as regras do negócio.

Os cálculos de previsão, otimização e validação das quantidades não serão realizados pelo modelo de linguagem. Eles serão executados por ferramentas determinísticas integradas ao banco MySQL.

Os preços e recursos apresentados foram consultados na documentação oficial da OpenAI em 21 de setembro de 2026:

- Modelos: https://developers.openai.com/api/docs/models/all
- Comparação: https://developers.openai.com/api/docs/models/compare
- Preços: https://developers.openai.com/api/docs/pricing
- Privacidade: https://openai.com/enterprise-privacy/

## 3.1 Os candidatos

Os três modelos candidatos são:

1. `gpt-5.6-luna`;
2. `gpt-5.6-terra`;
3. `gpt-5.6-sol`.

Eles foram escolhidos porque pertencem à mesma família, utilizam a mesma API e oferecem suporte a chamadas de ferramentas e saídas estruturadas.

Isso permite comparar os modelos sem alterar a arquitetura ou as ferramentas do agente.

### Eixos utilizados na comparação

| Eixo | Por que importa neste projeto |
|---|---|
| Compreensão e raciocínio | O modelo precisa interpretar pedidos incompletos, identificar ambiguidades e decidir qual ferramenta utilizar |
| Tool calling | O agente precisa chamar ferramentas de consulta ao MySQL, previsão, otimização e registro |
| Saída estruturada | Os argumentos das ferramentas devem seguir um formato previsível e validável |
| Janela de contexto | Deve comportar instruções, regras do negócio, histórico da conversa e resultados das ferramentas |
| Latência | O proprietário estará esperando a resposta no terminal |
| Custo | Cada planejamento pode exigir várias chamadas ao modelo |
| Política de dados | Informações internas do negócio serão enviadas ao provedor |
| Multimodalidade | Não é prioridade nesta primeira versão, pois a entrada será somente textual |

### Comparação técnica

| Modelo | Perfil | Contexto | Saída máxima | Tool calling | Saída estruturada | Entrada | Saída |
|---|---|---:|---:|---|---|---:|---:|
| `gpt-5.6-luna` | Modelo econômico para tarefas bem definidas | 1,05 milhão de tokens | 128 mil tokens | Sim | Sim | US$ 0,10 por milhão de tokens | US$ 0,60 por milhão de tokens |
| `gpt-5.6-terra` | Equilíbrio entre capacidade e custo | 1,05 milhão de tokens | 128 mil tokens | Sim | Sim | US$ 1,00 por milhão de tokens | US$ 6,00 por milhão de tokens |
| `gpt-5.6-sol` | Modelo de maior capacidade para tarefas complexas | 1,05 milhão de tokens | 128 mil tokens | Sim | Sim | US$ 2,00 por milhão de tokens | US$ 10,00 por milhão de tokens |

Os valores apresentados consideram a modalidade padrão de processamento e devem ser verificados novamente antes da entrega, pois o provedor pode alterar seus preços.

### `gpt-5.6-luna`

O `gpt-5.6-luna` é o candidato de menor custo.

Ele pode ser suficiente porque o modelo não será responsável por calcular as quantidades de produção. Sua responsabilidade será:

- interpretar a solicitação do proprietário;
- identificar informações ausentes;
- decidir qual ferramenta deve ser utilizada;
- gerar argumentos estruturados;
- interpretar erros retornados pelas ferramentas;
- explicar os resultados calculados pelo sistema.

Sua principal vantagem é permitir um número maior de testes e execuções com custo reduzido.

O principal risco é apresentar menor consistência em situações ambíguas, em argumentos mais complexos ou em sequências com várias chamadas de ferramentas.

### `gpt-5.6-terra`

O `gpt-5.6-terra` é uma alternativa intermediária entre custo e capacidade.

Ele será considerado caso o `gpt-5.6-luna` apresente dificuldade para:

- escolher a ferramenta correta;
- identificar informações ausentes;
- gerar argumentos válidos;
- respeitar simultaneamente várias regras;
- interpretar erros devolvidos pelas ferramentas;
- corrigir uma trajetória depois de uma falha.

O modelo possui custo maior, mas pode apresentar mais consistência em tarefas com várias etapas.

### `gpt-5.6-sol`

O `gpt-5.6-sol` é o candidato de maior capacidade e também o de maior custo entre os três.

Ele pode apresentar melhor desempenho em situações complexas ou ambíguas. Entretanto, essa capacidade pode ser desnecessária para a primeira versão porque os cálculos e as validações críticas permanecerão em código tradicional.

Sua adoção somente será justificada se os testes demonstrarem uma melhoria relevante em relação aos modelos menores.

### Política de dados

O agente utilizará informações internas da Pastéis Miyata, incluindo:

- histórico de produção;
- quantidade vendida;
- quantidade de sobra;
- datas das feiras;
- clima registrado;
- feriados;
- observações operacionais.

As ferramentas consultarão o MySQL e devolverão somente os dados necessários para atender à solicitação atual. O conteúdo completo das tabelas não será enviado ao modelo.

Nenhuma senha, chave de API ou credencial do MySQL será enviada ao modelo.

Segundo a política empresarial da OpenAI, os dados enviados pela API não são utilizados para treinar os modelos por padrão. Mesmo assim, o projeto deverá minimizar as informações enviadas e revisar as condições do provedor antes da utilização com dados reais.

Fonte:

https://openai.com/enterprise-privacy/

## 3.2 Estimativa de custo

### Hipóteses da primeira versão

Para estimar o custo de uma execução, serão consideradas:

- quatro chamadas ao modelo por planejamento;
- 1.500 tokens de entrada por chamada;
- 300 tokens de saída por chamada;
- modalidade padrão de processamento;
- 1.000 execuções durante o semestre.

Assim, uma execução terá aproximadamente:

```text
Entrada:
1.500 tokens × 4 chamadas = 6.000 tokens

Saída:
300 tokens × 4 chamadas = 1.200 tokens
```

### Fórmula

```text
Custo da entrada:
(tokens de entrada ÷ 1.000.000) × preço de entrada

Custo da saída:
(tokens de saída ÷ 1.000.000) × preço de saída

Custo por execução:
custo da entrada + custo da saída
```

### Custo estimado do `gpt-5.6-luna`

```text
Entrada:
(6.000 ÷ 1.000.000) × US$ 0,10 = US$ 0,00060

Saída:
(1.200 ÷ 1.000.000) × US$ 0,60 = US$ 0,00072

Total por execução:
US$ 0,00060 + US$ 0,00072 = US$ 0,00132
```

### Custo estimado do `gpt-5.6-terra`

```text
Entrada:
(6.000 ÷ 1.000.000) × US$ 1,00 = US$ 0,00600

Saída:
(1.200 ÷ 1.000.000) × US$ 6,00 = US$ 0,00720

Total por execução:
US$ 0,00600 + US$ 0,00720 = US$ 0,01320
```

### Custo estimado do `gpt-5.6-sol`

```text
Entrada:
(6.000 ÷ 1.000.000) × US$ 2,00 = US$ 0,01200

Saída:
(1.200 ÷ 1.000.000) × US$ 10,00 = US$ 0,01200

Total por execução:
US$ 0,01200 + US$ 0,01200 = US$ 0,02400
```

### Comparação dos custos

| Modelo | Uma execução | 100 execuções | 1.000 execuções |
|---|---:|---:|---:|
| `gpt-5.6-luna` | US$ 0,00132 | US$ 0,132 | US$ 1,32 |
| `gpt-5.6-terra` | US$ 0,01320 | US$ 1,32 | US$ 13,20 |
| `gpt-5.6-sol` | US$ 0,02400 | US$ 2,40 | US$ 24,00 |

Esses valores são estimativas.

O custo real dependerá:

- do tamanho final do system prompt;
- da duração da conversa;
- da quantidade de resultados devolvidos pelas ferramentas;
- do número efetivo de chamadas;
- da quantidade de tentativas de correção;
- da modalidade de processamento contratada.

O programa deverá registrar o uso de tokens de cada execução para permitir a comparação entre a estimativa e o custo observado.

## 3.3 Verificação mínima

Os três modelos deverão ser avaliados com:

- o mesmo system prompt;
- as mesmas ferramentas;
- os mesmos parâmetros;
- os mesmos cinco casos;
- a mesma regra de correção.

A temperatura deverá permanecer em `0` ou no menor valor permitido pelo modelo, reduzindo variações entre as execuções.

### Casos de teste

| Caso | Entrada | Comportamento esperado |
|---|---|---|
| M01 — Consulta simples | “Como foi a última feira `QUA`?” | Consultar o MySQL e apresentar os dados encontrados sem inventar valores |
| M02 — Planejamento completo | “Planeje a feira `QUA` de 23/09/2026. Clima de sol, sem evento e sem limitação.” | Selecionar as ferramentas corretas e devolver a recomendação calculada |
| M03 — Informação ausente | “Planeje a produção de sábado.” | Perguntar a data e identificar se o proprietário deseja `SAB_C`, `SAB_E` ou ambas |
| M04 — Regra contradita | “Inclua pastel de frango na produção da `SAB_E`.” | Informar que o produto não é vendido nessa feira e não o incluir no plano |
| M05 — Fora do escopo | “Faça um pedido de ingredientes ao fornecedor.” | Explicar que não pode realizar compras e não executar nenhuma escrita |

### Critérios de avaliação

Cada resultado será avaliado considerando se o modelo:

1. interpretou corretamente a intenção;
2. identificou informações obrigatórias ausentes;
3. selecionou a ferramenta correta;
4. gerou argumentos válidos;
5. respeitou as regras do domínio;
6. evitou inventar informações;
7. evitou realizar escrita sem confirmação;
8. respondeu em português de maneira objetiva.

### Erros críticos

São considerados erros críticos:

- inventar quantidades como se tivessem vindo do MySQL;
- recomendar produto proibido para uma feira;
- executar uma escrita sem confirmação do proprietário;
- continuar o planejamento sem informações obrigatórias;
- realizar uma ação fora do escopo;
- ignorar um erro retornado por uma ferramenta;
- apresentar uma recomendação não calculada como se fosse um resultado real.

### Tabela de resultados

Esta tabela deverá ser preenchida somente depois da execução real dos testes.

| Caso | `gpt-5.6-luna` | `gpt-5.6-terra` | `gpt-5.6-sol` |
|---|---|---|---|
| M01 — Consulta simples | Pendente | Pendente | Pendente |
| M02 — Planejamento completo | Pendente | Pendente | Pendente |
| M03 — Informação ausente | Pendente | Pendente | Pendente |
| M04 — Regra contradita | Pendente | Pendente | Pendente |
| M05 — Fora do escopo | Pendente | Pendente | Pendente |
| **Acertos** | **Pendente/5** | **Pendente/5** | **Pendente/5** |
| **Erros críticos** | **Pendente** | **Pendente** | **Pendente** |
| **Latência média** | **Pendente** | **Pendente** | **Pendente** |
| **Custo observado** | **Pendente** | **Pendente** | **Pendente** |

Os resultados não foram preenchidos antecipadamente porque a atividade exige saídas obtidas em execuções reais.

Inventar os resultados eliminaria a validade da comparação. A tabela será atualizada quando o agente estiver funcionando e os mesmos cinco casos forem executados nos três modelos.

### Critério mínimo para aprovação

O modelo deverá:

- resolver corretamente pelo menos 4 dos 5 casos;
- não cometer nenhum erro crítico;
- gerar argumentos válidos nas chamadas de ferramentas;
- não executar a ação principal nos casos M03 e M05;
- manter custo compatível com o orçamento do projeto;
- apresentar latência adequada para utilização no terminal.

## 3.4 Decisão

A escolha inicial é o modelo:

```text
gpt-5.6-luna
```

Essa decisão é provisória e deverá ser confirmada pela verificação mínima.

O modelo foi escolhido inicialmente porque possui o menor custo entre os candidatos e oferece os recursos necessários de tool calling e saída estruturada.

A tarefa do modelo será limitada à:

- interpretação da solicitação;
- identificação de informações ausentes;
- escolha das ferramentas;
- geração dos argumentos;
- interpretação dos resultados;
- apresentação da resposta ao proprietário.

A previsão, a otimização e a validação das regras serão executadas por código tradicional, reduzindo a necessidade de utilizar o modelo mais caro.

### Condições para manter a escolha

O `gpt-5.6-luna` será mantido se:

- acertar pelo menos 4 dos 5 casos;
- não apresentar erro crítico;
- produzir chamadas de ferramentas válidas;
- respeitar as regras das feiras;
- apresentar latência adequada;
- manter o custo dentro do orçamento.

### Condições para mudar de modelo

A escolha será alterada para o `gpt-5.6-terra` se o `gpt-5.6-luna`:

- errar dois ou mais casos;
- produzir argumentos inválidos com frequência;
- chamar ferramentas sem possuir os dados obrigatórios;
- desrespeitar regras importantes do negócio;
- não conseguir corrigir a trajetória após um erro de ferramenta;
- apresentar respostas difíceis de corrigir apenas com mudanças no prompt.

O `gpt-5.6-sol` será escolhido somente se demonstrar uma melhoria relevante nos testes e se essa melhoria justificar o custo adicional.

Caso nenhum dos três modelos alcance o critério mínimo, primeiro serão revisados:

- o system prompt;
- as descrições das ferramentas;
- os contratos de entrada e saída;
- as validações realizadas em código;
- as mensagens de erro devolvidas pelas ferramentas.

Um modelo mais caro não será utilizado para compensar regras mal especificadas ou ferramentas mal projetadas.

## Conclusão

O `gpt-5.6-luna` é a escolha inicial para o agente de planejamento da Pastéis Miyata.

O modelo possui os recursos necessários para interpretar as solicitações do proprietário e coordenar as ferramentas, enquanto o MySQL, o módulo de previsão e o Simplex permanecem responsáveis pelos dados e cálculos confiáveis.

A decisão final dependerá da execução dos cinco casos nos três modelos. Até que essa verificação seja realizada, a escolha deve ser considerada provisória.