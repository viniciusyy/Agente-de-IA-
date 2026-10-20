# Plano de prompt engineering

## Prompts executáveis

Os prompts carregados durante a execução ficam em `src/prompts/`. Esses arquivos são a fonte efetivamente utilizada pelo programa e permanecem versionados no repositório.

A documentação apresenta as decisões do plano, enquanto os arquivos executáveis são:

- `src/prompts/orquestrador_v2.md`;
- `src/prompts/procedimento_planejamento_v1.md`.

## Técnicas utilizadas

| Etapa | Técnica | Por que foi escolhida | Contrato | Como é testada |
|---|---|---|---|---|
| Orquestração | Few-shot curto, zero-shot para solicitações novas e tool calling | As solicitações chegam em texto livre, mas quatro exemplos fixam comportamentos críticos: informação ausente, registro inexistente, fora do escopo e divergência com regra | O modelo chama uma das ferramentas declaradas ou devolve um objeto compatível com `SaidaAgente`, em JSON e sem Markdown | Seis casos integrados: caminho feliz, divergência, registro inexistente, entrada incompleta, pergunta fora do corpus e aprovação humana |
| Procedimento de planejamento | Decomposição em sete passos | Evita que o modelo misture interpretação, recuperação, cálculo, apresentação e aprovação | Não produz uma saída independente; funciona como memória procedural anexada ao `system prompt` | A trajetória deve mostrar consulta antes da conclusão, cálculo fora do LLM e escrita somente depois do `interrupt` |

Não foi solicitada cadeia de pensamento ao modelo. As decisões observáveis são representadas pelo grafo, pelas chamadas de ferramentas e pela trajetória registrada no log. O sistema não depende da exposição do raciocínio interno do provedor.

## Prompt do orquestrador

O prompt `orquestrador_v2.md` define que o agente:

- atende somente ao proprietário;
- interpreta solicitações em texto livre;
- decide quais ferramentas devem ser chamadas;
- não calcula quantidades;
- não inventa registros;
- não substitui a aprovação humana;
- trata erro de ferramenta como dado;
- consulta o RAG quando a decisão depende de regras ou conhecimento documental;
- utiliza o MySQL para registros estruturados;
- recusa perguntas que não possam ser sustentadas pelo corpus ou pelas ferramentas.

O prompt também proíbe o modelo de considerar produtos de nomes semelhantes como se fossem o mesmo produto. Por exemplo, “Frango”, “Frango com catupiri” e “Especial de frango” são itens diferentes.

## Memória procedural

O arquivo `procedimento_planejamento_v1.md` estabelece o seguinte procedimento:

1. identificar a intenção;
2. verificar informações obrigatórias;
3. escolher entre consulta estruturada e busca textual;
4. executar cálculos em ferramenta determinística;
5. apresentar método, limitações, restrições e fontes;
6. interromper o grafo antes de registrar um plano;
7. encerrar declarando suficiência e próxima ação.

Esse procedimento é separado do prompt principal porque representa conhecimento sobre como executar a tarefa. Ele poderá ser versionado independentemente das regras de comportamento do orquestrador.

## Contrato exato de saída

O schema `SaidaAgente`, definido em `src/schemas.py`, aceita:

- `status`: `concluido`, `precisa_informacao`, `recusado`, `aguardando_aprovacao` ou `erro`;
- `resultado`: texto, objeto, lista ou `null`;
- `fontes`: lista de fontes verificáveis;
- `suficiente`: valor booleano;
- `motivo`: justificativa obrigatória;
- `proxima_acao`: texto opcional.

É proibido:

- devolver campos adicionais;
- envolver o JSON em cercas Markdown;
- inventar quantidades;
- alterar números devolvidos por ferramentas;
- citar registros ou documentos que não foram consultados;
- afirmar que uma escrita aconteceu antes da confirmação humana.

Se o modelo produzir um formato inválido, o nó `validar_saida` cria um objeto Pydantic válido e registra que a resposta precisou ser normalizada pelo código.

## Tool calling

O agente possui seis ferramentas declaradas:

| Ferramenta | Função |
|---|---|
| `consultar_historico` | Consulta no MySQL as operações recentes de uma feira |
| `consultar_operacao` | Consulta uma operação pelo identificador |
| `buscar_conhecimento` | Recupera regras e informações do corpus |
| `calcular_recomendacao` | Calcula uma recomendação determinística |
| `salvar_preferencia` | Registra uma preferência explicitamente declarada |
| `registrar_plano` | Solicita a escrita de um plano e aciona a aprovação humana |

O prompt permite no máximo uma ferramenta por resposta do modelo. O agente deve aguardar o resultado antes de tomar a próxima decisão.

## Carimbo por execução

Cada log registra as versões dos prompts, o modelo e os principais parâmetros:

```text
prompt_versions:
  orquestrador: orquestrador_v2
  procedural: procedimento_planejamento_v1

modelo: valor de LLM_MODEL

parametros:
  limite de passos
  limite de ferramentas
  limite de tokens
  limite de tempo
  limite de custo
  recursion_limit
```

Esse carimbo permite relacionar cada resultado à combinação de prompt, modelo e configuração que o produziu.

## Experimento de remoção de frase

A frase redundante:

```text
Responda sempre em português brasileiro.
```

foi retirada da versão 2 do prompt. O idioma já é induzido:

- pela solicitação do proprietário;
- pelos nomes dos campos;
- pelos exemplos;
- pelo restante das instruções;
- pelos resultados das ferramentas.

O experimento será considerado aprovado se os seis casos reais permanecerem em português e respeitarem o mesmo contrato de saída.

**Resultado da execução real:** `[PREENCHER APÓS EXECUTAR OS SEIS CASOS]`.

Se algum caso mudar de idioma, a instrução será restaurada na versão 3. Caso todos permaneçam em português, ela continuará removida, reduzindo tokens em todas as chamadas.

## Falhas que cada instrução procura impedir

| Instrução | Falha evitada |
|---|---|
| Não calcular quantidades | Impede que o LLM invente a produção |
| Consultar o MySQL para registros | Impede respostas baseadas somente na memória do modelo |
| Buscar conhecimento para regras | Impede que detalhes privados sejam respondidos sem fonte |
| Tratar erro como dado | Impede que uma falha de ferramenta encerre o processo sem explicação |
| Não deduzir preferências | Impede gravação de uma preferência não declarada |
| Confirmar antes do registro | Impede escrita sem autorização do proprietário |
| Recusar quando a base for insuficiente | Impede alucinação diante de informação ausente |
| Uma ferramenta por resposta | Facilita rastreamento e reduz decisões paralelas conflitantes |