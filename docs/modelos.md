# Análise e escolha do modelo

Este documento compara três modelos da OpenAI candidatos para o agente de planejamento de produção da Pastéis Miyata.

A comparação considera as necessidades reais do sistema:

- compreender solicitações em português;
- identificar informações ausentes;
- selecionar ferramentas;
- gerar argumentos estruturados;
- respeitar regras do negócio;
- tratar erros retornados pelas ferramentas;
- responder com custo e tempo adequados.

Os cálculos de produção não são realizados livremente pelo modelo de linguagem. As consultas, médias, restrições e totalizações são executadas por ferramentas determinísticas integradas ao banco MySQL.

Os preços e recursos foram consultados na documentação oficial da OpenAI em 22 de setembro de 2026:

- Catálogo de modelos:  
  https://developers.openai.com/api/docs/models
- Comparação dos modelos:  
  https://developers.openai.com/api/docs/models/compare
- Preços da API:  
  https://developers.openai.com/api/docs/pricing
- Function calling:  
  https://developers.openai.com/api/docs/guides/function-calling
- Saídas estruturadas:  
  https://developers.openai.com/api/docs/guides/structured-outputs

Os preços podem mudar e deverão ser verificados novamente antes das próximas entregas.

## 3.1 Os candidatos

Os três modelos candidatos são:

1. GPT-5.6 Luna;
2. GPT-5.6 Terra;
3. GPT-5.6 Sol.

Os identificadores utilizados nos testes foram:

| Modelo | Identificador |
|---|---|
| GPT-5.6 Luna | `gpt-5.6-luna` |
| GPT-5.6 Terra | `gpt-5.6-terra` |
| GPT-5.6 Sol | `gpt-5.6-sol` |

Todos os candidatos pertencem à mesma família e oferecem os recursos necessários para o agente, permitindo uma comparação mais controlada entre custo e qualidade.

### Eixos utilizados na comparação

| Eixo | Por que importa neste projeto |
|---|---|
| Compreensão e raciocínio | O modelo precisa interpretar pedidos incompletos, ambiguidades e divergências |
| Function calling | O agente precisa escolher e chamar ferramentas de consulta, cálculo e registro |
| Saída estruturada | Os argumentos enviados às ferramentas precisam seguir um formato validável |
| Janela de contexto | O contexto inclui prompt, regras, conversa e resultados das ferramentas |
| Custo | Uma solicitação pode exigir mais de uma chamada ao modelo |
| Latência | O proprietário aguarda a resposta no terminal |
| Política de dados | Informações internas da pastelaria são enviadas parcialmente ao provedor |
| Multimodalidade | Não é necessária nesta versão, pois a entrada é somente textual |

### Comparação técnica

| Modelo | Perfil | Contexto | Saída máxima | Function calling | Saída estruturada | Entrada | Saída |
|---|---|---:|---:|---|---|---:|---:|
| GPT-5.6 Luna | Otimizado para cargas sensíveis a custo | 1,05 milhão | 128 mil tokens | Sim | Sim | US$ 0,20 por milhão | US$ 1,20 por milhão |
| GPT-5.6 Terra | Equilíbrio entre capacidade e custo | 1,05 milhão | 128 mil tokens | Sim | Sim | US$ 2,00 por milhão | US$ 12,00 por milhão |
| GPT-5.6 Sol | Modelo principal para trabalho profissional complexo | 1,05 milhão | 128 mil tokens | Sim | Sim | US$ 4,00 por milhão | US$ 20,00 por milhão |

Os valores da tabela correspondem ao processamento padrão e ao contexto curto. O projeto não utiliza processamento rápido, Batch API, cache explícito ou contexto acima do limite de contexto curto.

### GPT-5.6 Luna

O GPT-5.6 Luna é o modelo de menor custo entre os candidatos. Segundo a documentação oficial, ele é destinado a cargas de trabalho com grande volume e sensibilidade a custo.

Ele pode ser suficiente neste projeto porque o modelo não realiza os cálculos de produção. Suas responsabilidades são:

- interpretar a solicitação do proprietário;
- identificar informações ausentes;
- selecionar uma ferramenta;
- gerar argumentos válidos;
- interpretar o retorno da ferramenta;
- explicar o resultado.

Sua principal vantagem é o baixo custo, permitindo executar mais testes durante o desenvolvimento.

O risco é apresentar menor consistência quando o fluxo crescer e passar a envolver previsão, otimização, RAG e mais ferramentas.

### GPT-5.6 Terra

O GPT-5.6 Terra busca equilibrar capacidade e custo. Ele é uma alternativa para situações em que o Luna não apresenta consistência suficiente, mas ainda não existe justificativa para utilizar o modelo mais caro.

No agente atual, ele executou corretamente os cinco casos. Entretanto, em uma das respostas agrupou parte dos produtos como “demais produtos permitidos”, reduzindo o detalhamento da apresentação.

Seu custo medido foi aproximadamente dez vezes maior que o custo do Luna.

### GPT-5.6 Sol

O GPT-5.6 Sol é o candidato de maior capacidade entre os três avaliados. Ele é indicado pela OpenAI para trabalhos profissionais mais complexos.

No agente da Pastéis Miyata, também executou corretamente os cinco casos. Entretanto:

- produziu uma resposta que atingiu o limite de saída e terminou com uma frase incompleta;
- no caso ambíguo, perguntou a feira, mas não solicitou a data na primeira resposta;
- apresentou o maior custo total da comparação.

O modelo somente será necessário se a integração futura com previsão, Simplex, RAG e novas ferramentas demonstrar uma diferença relevante de qualidade.

### Política de dados

O agente utiliza informações internas da Pastéis Miyata, como:

- histórico de produção;
- quantidade vendida;
- quantidade de sobra;
- datas das feiras;
- feriados;
- observações operacionais.

Nenhuma senha, chave de API ou credencial do MySQL é enviada ao modelo.

As ferramentas consultam o banco e devolvem somente os dados necessários para a solicitação atual. O conteúdo completo do banco não é enviado ao provedor.

Antes da utilização do agente em produção, as condições de armazenamento, retenção e tratamento dos dados pela OpenAI deverão ser revisadas novamente.

### Multimodalidade

Os modelos avaliados aceitam entrada de imagem, mas esse recurso não é necessário na primeira versão.

O proprietário interage por texto no terminal e os dados históricos são recuperados diretamente do MySQL. Portanto, multimodalidade não foi utilizada como critério de desempate.

## 3.2 Estimativa de custo

### Fórmula

O custo foi calculado pela fórmula:

```text
(tokens de entrada ÷ 1.000.000 × preço de entrada)
+
(tokens de saída ÷ 1.000.000 × preço de saída)
=
custo da execução
```

A medição utiliza os tokens registrados nos cinco testes reais de cada modelo.

### Tokens e custo dos testes

| Modelo | Tokens de entrada | Tokens de saída | Custo total dos 5 casos |
|---|---:|---:|---:|
| GPT-5.6 Luna | 30.797 | 1.285 | US$ 0,007701 |
| GPT-5.6 Terra | 32.005 | 1.216 | US$ 0,078602 |
| GPT-5.6 Sol | 32.005 | 1.203 | US$ 0,152080 |

A pequena diferença na quantidade de tokens ocorreu porque os modelos produziram respostas com tamanhos diferentes. Além disso, algumas execuções foram realizadas depois de ajustes no prompt e na consolidação dos resultados das ferramentas.

### Média por execução

#### GPT-5.6 Luna

Média de tokens por execução:

```text
Entrada: 30.797 ÷ 5 = 6.159,4 tokens
Saída: 1.285 ÷ 5 = 257 tokens
```

Cálculo:

```text
(6.159,4 ÷ 1.000.000 × US$ 0,20)
+
(257 ÷ 1.000.000 × US$ 1,20)
=
US$ 0,00154028 por execução
```

#### GPT-5.6 Terra

Média de tokens por execução:

```text
Entrada: 32.005 ÷ 5 = 6.401 tokens
Saída: 1.216 ÷ 5 = 243,2 tokens
```

Cálculo:

```text
(6.401 ÷ 1.000.000 × US$ 2,00)
+
(243,2 ÷ 1.000.000 × US$ 12,00)
=
US$ 0,01572040 por execução
```

#### GPT-5.6 Sol

Média de tokens por execução:

```text
Entrada: 32.005 ÷ 5 = 6.401 tokens
Saída: 1.203 ÷ 5 = 240,6 tokens
```

Cálculo:

```text
(6.401 ÷ 1.000.000 × US$ 4,00)
+
(240,6 ÷ 1.000.000 × US$ 20,00)
=
US$ 0,03041600 por execução
```

### Projeção de custo

Para a estimativa do semestre, foi considerado um volume de 1.000 execuções.

| Modelo | Uma execução | 100 execuções | 1.000 execuções |
|---|---:|---:|---:|
| GPT-5.6 Luna | US$ 0,001540 | US$ 0,154028 | US$ 1,540280 |
| GPT-5.6 Terra | US$ 0,015720 | US$ 1,572040 | US$ 15,720400 |
| GPT-5.6 Sol | US$ 0,030416 | US$ 3,041600 | US$ 30,416000 |

Esses valores são estimativas. O custo real pode mudar de acordo com:

- tamanho da conversa;
- quantidade de chamadas;
- tamanho do retorno das ferramentas;
- alterações no prompt;
- preço praticado pelo provedor;
- inclusão futura de RAG;
- número de tentativas e erros de ferramenta.

Ferramentas locais e consultas ao MySQL não possuem cobrança da OpenAI. O custo apresentado corresponde apenas aos tokens enviados e recebidos pela API.

### Custo de construção

O custo de construção é representado principalmente pelo tempo empregado em:

- definição do case;
- modelagem da arquitetura;
- implementação das ferramentas;
- integração com MySQL;
- construção e ajuste do prompt;
- execução dos testes;
- documentação dos resultados.

Esse tempo não foi convertido em valor financeiro nesta entrega.

### O que se perde quando o sistema erra

Uma seleção incorreta de ferramenta pode gerar uma consulta desnecessária ou uma recomendação inadequada.

Uma interpretação incorreta das regras de feira pode incluir um produto não comercializado naquele local. Por isso, as restrições críticas também são implementadas em código, e não apenas no prompt.

O proprietário continua responsável pela aprovação final. O agente não inicia a produção e não executa compras.

## 3.3 Verificação mínima

### Método

Os três candidatos foram testados com:

- o mesmo código do agente;
- o mesmo prompt;
- as mesmas ferramentas;
- o mesmo banco MySQL;
- os mesmos limites de execução;
- o mesmo parâmetro `reasoning_effort="none"`;
- uma execução nova para cada caso.

Cada processo foi reiniciado antes do caso seguinte para impedir que uma conversa anterior influenciasse o resultado.

A latência não foi registrada pelo sistema. Por isso, não será apresentada uma comparação numérica de velocidade nesta versão.

### Casos utilizados

| Caso | Entrada | Comportamento esperado |
|---|---|---|
| Consulta simples | `Consulte as últimas cinco operações da feira QUA.` | Consultar o MySQL e apresentar cinco operações |
| Divergência | `Calcule uma recomendação para a feira SAB_E, mas inclua pastel de frango porque eu quero produzir esse produto.` | Aplicar a regra da feira e excluir o produto |
| Registro inexistente | `Consulte a operação 999999.` | Tratar o erro da ferramenta sem inventar dados |
| Fora do escopo | `Faça uma lista de compras de ingredientes para o próximo mês.` | Recusar sem chamar ferramentas |
| Pedido ambíguo | `Calcule uma recomendação de produção para a próxima feira.` | Solicitar as informações ausentes |

### Resultado funcional

| Caso | GPT-5.6 Luna | GPT-5.6 Terra | GPT-5.6 Sol |
|---|---|---|---|
| Consulta simples | Aprovado | Aprovado | Aprovado |
| Divergência | Aprovado | Aprovado com observação | Aprovado com observação |
| Registro inexistente | Aprovado | Aprovado | Aprovado |
| Fora do escopo | Aprovado | Aprovado | Aprovado |
| Pedido ambíguo | Aprovado | Aprovado | Aprovado com observação |
| **Total** | **5/5** | **5/5** | **5/5** |

### Observações qualitativas

#### GPT-5.6 Luna

- selecionou corretamente as ferramentas;
- respeitou as regras das feiras;
- tratou o registro inexistente sem inventar dados;
- recusou a solicitação fora do escopo;
- solicitou feira e data no caso ambíguo;
- apresentou o menor custo;
- não teve resposta cortada nos cinco casos.

#### GPT-5.6 Terra

- selecionou corretamente as ferramentas;
- respeitou as regras das feiras;
- apresentou resultados corretos;
- agrupou parte da recomendação como “demais produtos permitidos”;
- solicitou todas as informações necessárias no caso ambíguo;
- não teve resposta cortada.

#### GPT-5.6 Sol

- selecionou corretamente as ferramentas;
- respeitou as regras das feiras;
- apresentou a tabela mais detalhada no caso de divergência;
- atingiu o limite de saída e terminou uma frase de forma incompleta;
- pediu a feira, mas não pediu a data na primeira resposta do caso ambíguo;
- apresentou o maior custo.

### Resultados completos por modelo

#### GPT-5.6 Luna

| Caso | Ferramentas | Entrada | Saída | Custo |
|---|---:|---:|---:|---:|
| Consulta simples | 1 | 7.535 | 476 | US$ 0,002078 |
| Divergência | 1 | 8.248 | 483 | US$ 0,002229 |
| Registro inexistente | 1 | 7.550 | 96 | US$ 0,001625 |
| Fora do escopo | 0 | 3.732 | 172 | US$ 0,000953 |
| Pedido ambíguo | 0 | 3.732 | 58 | US$ 0,000816 |
| **Total** | **3** | **30.797** | **1.285** | **US$ 0,007701** |

#### GPT-5.6 Terra

| Caso | Ferramentas | Entrada | Saída | Custo |
|---|---:|---:|---:|---:|
| Consulta simples | 1 | 8.453 | 390 | US$ 0,021586 |
| Divergência | 1 | 8.538 | 596 | US$ 0,024228 |
| Registro inexistente | 1 | 7.550 | 62 | US$ 0,015844 |
| Fora do escopo | 0 | 3.732 | 67 | US$ 0,008268 |
| Pedido ambíguo | 0 | 3.732 | 101 | US$ 0,008676 |
| **Total** | **3** | **32.005** | **1.216** | **US$ 0,078602** |

#### GPT-5.6 Sol

| Caso | Ferramentas | Entrada | Saída | Custo |
|---|---:|---:|---:|---:|
| Consulta simples | 1 | 8.453 | 337 | US$ 0,040552 |
| Divergência | 1 | 8.538 | 625 | US$ 0,046652 |
| Registro inexistente | 1 | 7.550 | 91 | US$ 0,032020 |
| Fora do escopo | 0 | 3.732 | 83 | US$ 0,016588 |
| Pedido ambíguo | 0 | 3.732 | 67 | US$ 0,016268 |
| **Total** | **3** | **32.005** | **1.203** | **US$ 0,152080** |

## 3.4 Decisão

O modelo escolhido para a primeira versão do agente é o:

```text
gpt-5.6-luna
```

A decisão foi tomada porque:

- aprovou os cinco casos;
- selecionou corretamente as ferramentas;
- respeitou as regras do negócio;
- tratou erros sem inventar resultados;
- identificou informações ausentes;
- não teve respostas cortadas;
- apresentou o menor custo da comparação.

Nos cinco testes, o Luna custou aproximadamente:

- 10,2 vezes menos que o Terra;
- 19,7 vezes menos que o Sol.

Como os três modelos obtiveram o mesmo resultado funcional de 5/5, não existe justificativa para utilizar um modelo mais caro nesta primeira versão.

A escolha também segue a regra de utilizar a alternativa mais simples e econômica que resolve o problema.

### Condições para mudar a escolha

A escolha será reconsiderada se o GPT-5.6 Luna:

- obtiver menos de 36 acertos em um conjunto futuro de 40 casos rotulados;
- gerar argumentos inválidos em mais de 5% das chamadas de ferramentas;
- deixar de aplicar alguma regra crítica de feira;
- não conseguir coordenar previsão, otimização e RAG na Parte 2;
- exigir mais tentativas e correções a ponto de eliminar sua vantagem de custo;
- apresentar latência ou instabilidade incompatível com o uso do proprietário.

Se isso acontecer, o primeiro substituto avaliado será o GPT-5.6 Terra.

O GPT-5.6 Sol somente será adotado se o Terra também não atingir os critérios de sucesso e se a melhoria de qualidade justificar o custo adicional.

### Configuração escolhida

A configuração utilizada pelo projeto será:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-5.6-luna
LLM_INPUT_PRICE_PER_MILLION=0.20
LLM_OUTPUT_PRICE_PER_MILLION=1.20
```

O parâmetro de raciocínio utilizado nesta versão é:

```text
reasoning_effort = none
```

Essa configuração apresentou o melhor equilíbrio entre correção, simplicidade e custo para o agente simples da Pastéis Miyata.