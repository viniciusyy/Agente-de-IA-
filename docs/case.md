# Case — Agente de Planejamento de Produção da Pastéis Miyata

## 2.1 O problema

### Problema em uma frase

O proprietário da Pastéis Miyata precisa definir quanto produzir de cada tipo de pastel para cada feira sem depender apenas da experiência e de consultas manuais ao histórico.

### Quem sofre com o problema

A pessoa afetada diretamente é o proprietário da Pastéis Miyata, responsável por analisar o histórico, considerar as condições da próxima feira e decidir as quantidades que serão produzidas.

Ele também é o único usuário autorizado a interagir com o agente e a aprovar um plano.

### Setor

O projeto pertence ao setor de varejo de alimentos, especificamente à produção e comercialização de pastéis em feiras livres.

A Pastéis Miyata é uma empresa familiar que atua em diferentes feiras durante a semana. O setor foi escolhido porque o processo é conhecido pelo autor e existem dados reais de produção, venda e sobra armazenados em MySQL.

### Onde o sistema será utilizado

O agente será executado em um terminal no computador do proprietário, durante o planejamento da produção.

O proprietário inicia a conversa antes da produção e informa, em linguagem natural, o que deseja consultar ou planejar.

Antes do agente existem:

- registros operacionais feitos durante as feiras;
- dados armazenados no MySQL;
- informações conhecidas pelo proprietário;
- condições da próxima feira.

Depois do agente existe:

- uma consulta organizada;
- uma recomendação de produção;
- uma explicação das regras aplicadas;
- a decisão final do proprietário;
- a execução física da produção, que permanece fora do sistema.

O agente não inicia a produção, não compra ingredientes e não toma decisões físicas de forma autônoma.

### Processo atual sem o agente

Atualmente, o proprietário define a produção principalmente com base em sua experiência.

O processo envolve:

1. identificar a feira e a data;
2. lembrar ou consultar resultados anteriores;
3. comparar produção, vendas e sobras;
4. considerar clima, feriado e eventos;
5. verificar limitações de produtos e ingredientes;
6. decidir quanto produzir;
7. ajustar as quantidades com base na experiência.

O tempo desse processo ainda não foi cronometrado de forma confiável. Por isso, o projeto não promete redução de tempo nesta entrega.

A justificativa de negócio utilizará uma linha de base que já pode ser medida no banco: a taxa de sobra.

### Regras do domínio

O agente deve respeitar as seguintes regras:

- As feiras válidas são `QUA`, `QUI`, `SAB_C`, `SAB_E`, `DOM_C` e `DOM_E`.
- A produção da feira de quarta-feira ocorre na terça-feira.
- A produção da feira de quinta-feira ocorre na quarta-feira.
- As produções das feiras de sábado ocorrem na sexta-feira.
- As produções das feiras de domingo ocorrem no sábado.
- `SAB_C` e `SAB_E` representam feiras diferentes.
- `DOM_C` e `DOM_E` representam feiras diferentes.
- As letras `C` e `E` identificam locais diferentes.
- As feiras `SAB_E` e `DOM_E` não comercializam pastel de frango, produto de código `5`.
- As feiras `SAB_E` e `DOM_E` não comercializam pastel de escarola sem bacon, produto de código `15`.
- Pastel de frango e pastel de frango com catupiry são produtos diferentes.
- O pastel de banana simples está temporariamente descontinuado.
- A quantidade vendida é calculada por `quantidade produzida - quantidade de sobra`.
- A sobra não pode ser negativa.
- A sobra não pode ser maior que a quantidade produzida.
- As condições climáticas utilizadas são Sol, Frio, Garoa, Chuva Moderada e Chuva Forte.
- Feriados e eventos podem alterar o movimento esperado.
- Produtos sem histórico suficiente devem ser apresentados com maior incerteza.
- Produtos descontinuados não podem aparecer na recomendação.
- A recomendação deve respeitar a capacidade e as limitações informadas pelo proprietário.
- O modelo de linguagem não pode inventar quantidades.
- Consultas, médias, restrições e totais devem ser processados por ferramentas.
- Nenhum plano pode ser registrado sem confirmação explícita do proprietário.
- O agente não inicia a produção física.

### O que dá errado atualmente

Os principais casos difíceis são:

- o proprietário não informar a feira;
- o proprietário não informar a data;
- não ficar claro se o pedido envolve uma ou duas feiras;
- o proprietário pedir um produto proibido em determinada feira;
- existir um evento não registrado no histórico;
- o clima esperado ser diferente entre dois locais;
- existir limitação de capacidade ou ingredientes;
- os registros estarem ausentes, duplicados ou contraditórios;
- o identificador de uma operação não existir;
- um produto possuir pouco histórico;
- um produto estar temporariamente descontinuado;
- a demanda estimada ultrapassar a capacidade;
- a recomendação estatística divergir da experiência do proprietário;
- uma sobra igual a zero representar venda exata ou falta do produto;
- a solicitação estar fora do escopo do agente.

Quando uma informação necessária estiver ausente, o agente deve perguntar ao proprietário.

Quando os dados forem insuficientes ou contraditórios, o agente deve apresentar a limitação e interromper a decisão automática.

### O que a indústria já faz

#### Caso 1 — C3 AI: previsão e programação da produção

A C3 AI publicou um caso de uma empresa global dos setores de alimentos e agronegócio que operava oito linhas e produzia mais de 80 milhões de libras de alimentos por ano.

A solução integrou 18 fontes, totalizando aproximadamente 72 milhões de registros. Modelos de aprendizado de máquina foram utilizados para gerar previsões diárias, enquanto um módulo de otimização recomendava a programação da produção.

A empresa divulgou:

- aumento de 8% na precisão da previsão;
- redução de 96% no tempo e esforço da programação;
- US$ 30 milhões em margem bruta adicional identificada;
- US$ 1,5 milhão em economia identificada pela redução de trocas.

A arquitetura aparente é híbrida: aprendizado de máquina para previsão, algoritmo especializado para otimização e participação humana para análise e aprovação.

Esse padrão é semelhante ao projeto da Pastéis Miyata. O modelo de linguagem coordena o processo, enquanto os cálculos ficam em módulos tradicionais.

A divulgação não informa detalhadamente a linha de base, o custo da solução, o custo de manutenção nem quanto dos ganhos identificados foi efetivamente realizado.

#### Caso 2 — Walmart: Wally

O Walmart desenvolveu o Wally, um assistente de IA generativa para as equipes responsáveis pela seleção e pelo desempenho dos produtos.

O sistema trabalha com dados proprietários e auxilia em:

- entrada e análise de dados;
- identificação de causas do desempenho;
- cálculos e previsões;
- resposta a dúvidas operacionais;
- abertura de chamados.

O usuário realiza perguntas em linguagem natural e recebe informações extraídas de dados internos.

A arquitetura aparente é a de um agente assistente com ferramentas e uma camada semântica. O agente interpreta o pedido e coordena consultas e cálculos, enquanto a decisão de negócio permanece com uma pessoa.

O caso se aproxima deste projeto porque o agente funciona como interface entre o proprietário, os dados e as ferramentas.

A divulgação não informa linha de base, taxa de erro, custo por interação ou quantidade de decisões que ainda exigem intervenção humana.

#### Caso 3 — Wendy’s: FreshAI

A Wendy’s desenvolveu o FreshAI em parceria com o Google Cloud para realizar atendimento conversacional no drive-thru.

O sistema precisa interpretar linguagem informal, personalizações, informações ausentes e mudanças feitas durante o pedido.

No projeto-piloto, a Wendy’s declarou que 86% dos pedidos foram concluídos sem intervenção de um funcionário.

A arquitetura aparente utiliza um agente conversacional, ferramentas, regras de domínio, integração com o sistema de ponto de venda e participação humana nos casos não resolvidos.

O caso é relevante porque demonstra que uma interação não pode ser reduzida apenas a um formulário quando as informações chegam incompletas ou ambíguas.

A divulgação não informa custo por pedido, tempo médio completo, gravidade dos erros ou comparação detalhada com atendentes humanos.

As fontes completas dos três casos estão registradas em `docs/fontes.md`.

## 2.2 Os usuários e a interação

### Perfis

O agente possui apenas um perfil de usuário.

| Perfil | O que ele quer | O que ele sabe | O que ele pode fazer |
|---|---|---|---|
| Proprietário da Pastéis Miyata | Consultar o histórico, obter recomendações e entender as regras aplicadas | Conhece as feiras, os produtos, a capacidade, os ingredientes e as situações especiais | Consultar dados, informar restrições, solicitar cenários, aprovar, rejeitar e confirmar o registro de um plano |

Nenhum funcionário, cliente ou usuário externo utiliza o agente nesta versão.

### Usuário principal

O usuário principal e único usuário autorizado é o proprietário da Pastéis Miyata.

Ele também é o aprovador final. O agente pode recomendar e registrar um plano mock, mas não pode iniciar a produção ou executar uma ação física.

### Canal de interação

A interação ocorre por meio de um chat no terminal.

Esse canal foi escolhido porque:

- é suficiente para a prova de conceito;
- reduz o trabalho de interface;
- permite concentrar a entrega na arquitetura do agente;
- registra entradas, respostas e trajetória;
- pode ser executado diretamente no ambiente Python.

### Quem começa

O proprietário inicia a interação.

O agente não acorda sozinho, não monitora o banco continuamente e não envia notificações de forma proativa nesta versão.

### Quantidade de trocas

Uma solicitação simples pode ser concluída em uma ou duas trocas.

Uma solicitação incompleta pode exigir de duas a cinco trocas, dependendo das informações ausentes.

### O que o agente devolve

O agente pode devolver:

- uma consulta ao histórico;
- os dados de uma operação;
- uma recomendação mock;
- uma tabela de quantidades;
- regras aplicadas;
- alertas;
- uma solicitação de esclarecimento;
- uma recusa;
- o motivo pelo qual não conseguiu concluir.

O resumo da execução também informa:

- motivo da parada;
- passos executados;
- ferramentas chamadas;
- tokens de entrada;
- tokens de saída;
- custo estimado;
- caminho do log.

### Como a interação termina

Quando funciona, o proprietário recebe o resultado e decide o que fazer.

Quando não funciona, o agente explica:

- qual informação está ausente;
- qual registro não existe;
- qual regra foi violada;
- qual ferramenta falhou;
- qual solicitação está fora do escopo.

O agente não preenche dados essenciais por conta própria.

### Diálogo de exemplo

**Proprietário:**  
Calcule uma recomendação de produção para a próxima feira.

**Agente:**  
Qual é a feira: `QUA`, `QUI`, `SAB_C`, `SAB_E`, `DOM_C` ou `DOM_E`? Informe também a data da venda.

**Proprietário:**  
Será a `SAB_E`, no dia 26/09/2026.

**Agente:**  
Existe alguma limitação de capacidade, ingrediente, feriado ou evento especial?

**Proprietário:**  
Não. Quero incluir pastel de frango.

**Agente:**  
O pastel de frango, código `5`, não pode ser incluído na `SAB_E`. Aplicarei a restrição fixa da feira e calcularei a recomendação somente com os produtos permitidos.

**Agente:**  
A produção recomendada total é de 762 unidades. O pastel de frango e a escarola sem bacon foram excluídos. O frango com catupiry foi mantido porque é um produto diferente. Deseja aprovar, rejeitar ou simular outro cenário?

**Proprietário:**  
Aprovo a recomendação.

**Agente:**  
Para registrar o plano mock, preciso de uma confirmação explícita.

**Proprietário:**  
Confirmo o registro do plano.

**Agente:**  
Plano mock registrado. A produção física continua dependendo da execução do proprietário.

### Informações que podem não ser fornecidas inicialmente

O proprietário pode não informar:

- feira;
- data;
- local;
- clima;
- feriado;
- evento;
- capacidade;
- limitações de ingredientes;
- prioridade entre reduzir sobra e evitar falta;
- se deseja consultar, simular ou registrar.

### Contradição entre proprietário e sistema

Quando o proprietário solicita algo que contradiz uma regra fixa, a regra validada pelo código prevalece.

O agente:

1. informa a divergência;
2. explica a regra;
3. recusa a parte inválida;
4. oferece uma alternativa permitida;
5. mantém a decisão final com o proprietário dentro das opções válidas.

### Como o sistema sabe que possui informações suficientes

O agente pode prosseguir quando conhece, no mínimo:

- o objetivo da solicitação;
- a feira ou operação;
- as informações necessárias para a ferramenta escolhida;
- as restrições essenciais do cenário.

Para apenas consultar uma operação, basta o identificador.

Para uma recomendação completa, podem ser necessários feira, data, capacidade e restrições.

### Quando o sistema para

O agente para e devolve a decisão ao proprietário quando:

- falta informação essencial;
- existe contradição;
- o registro não existe;
- a ferramenta retorna erro;
- o limite de passos é atingido;
- o limite de tokens é atingido;
- o limite de tempo é atingido;
- o limite de custo é atingido;
- a solicitação está fora do escopo;
- existe risco de violar uma regra crítica.

## 2.3 O workflow do agente

```text
1. ENTRADA
   O proprietário escreve uma solicitação no terminal.
   [decide: PROPRIETÁRIO]

2. INTERPRETAÇÃO
   O modelo identifica objetivo, feira, operação, restrições e informações ausentes.
   [decide: MODELO]

3. ESCLARECIMENTO
   Quando necessário, o modelo pergunta o que está faltando.
   [decide: MODELO]

4. SELEÇÃO DA FERRAMENTA
   O modelo escolhe entre consulta, recomendação ou registro.
   [decide: MODELO, com limite de passos e ferramentas]

5. EXECUÇÃO
   O código valida argumentos e executa MySQL ou cálculo determinístico.
   [decide: CÓDIGO]

6. VALIDAÇÃO
   O código aplica regras fixas, limites e restrições das feiras.
   [decide: CÓDIGO]

7. RESPOSTA
   O modelo organiza o resultado sem alterar os valores da ferramenta.
   [decide: MODELO]

8. REGISTRO
   O código registra o log e, somente com confirmação, o plano mock.
   [ESCRITA REVERSÍVEL — decide: CÓDIGO após confirmação do PROPRIETÁRIO]
```

A decisão que justifica o agente está nas etapas 2, 3 e 4. O modelo precisa interpretar linguagem livre, identificar informações ausentes e escolher uma ferramenta em tempo de execução.

As validações críticas continuam em código.

## 2.4 O sistema

### O que o sistema faz

O sistema recebe uma solicitação do proprietário, interpreta o objetivo e decide qual ferramenta deve utilizar.

Ele pode consultar dados reais no MySQL, calcular uma recomendação mock, aplicar regras fixas, explicar resultados e registrar um plano mock após confirmação.

O agente mantém estado, orçamento, trajetória e motivo de parada.

### Nível de autonomia

O nível escolhido é um agente com ferramentas.

Um workflow fixo não é suficiente porque o proprietário pode:

- escrever pedidos de formas diferentes;
- omitir informações;
- contradizer regras;
- solicitar consultas ou recomendações;
- mencionar uma feira, uma operação ou um produto;
- fazer uma solicitação fora do escopo.

O agente decide em tempo de execução qual informação falta e qual ferramenta deve ser utilizada.

A autonomia é limitada:

- o agente não altera o histórico;
- o agente não inicia produção;
- o agente não compra ingredientes;
- o proprietário mantém a decisão final;
- regras críticas são verificadas pelo código.

### Ferramentas

| Ferramenta | O que faz | Leitura ou escrita | Reversível | Contra o que conversa |
|---|---|---|---|---|
| `consultar_historico` | Consulta operações recentes de uma feira | Leitura | Sim | Banco MySQL |
| `consultar_operacao` | Consulta uma operação pelo identificador | Leitura | Sim | Banco MySQL |
| `calcular_recomendacao_mock` | Calcula uma recomendação pela média das vendas recentes e aplica restrições | Leitura e cálculo | Sim | MySQL e código Python |
| `registrar_plano_mock` | Registra um plano mock após confirmação explícita | Escrita | Sim | Arquivo JSONL local |

## 2.5 Justificativa de negócio

### Por que um agente, e não software comum

A tarefa exige decisão em tempo de execução porque a solicitação pode chegar incompleta, ambígua, contraditória ou fora do escopo, obrigando o sistema a descobrir o contexto e selecionar uma ferramenta.

Um workflow fixo não conseguiria decidir quais perguntas fazer e qual caminho seguir para diferentes solicitações em linguagem natural sem criar uma sequência extensa de formulários e regras de navegação.

Os cálculos continuam em software tradicional. O agente coordena as ferramentas, mas não inventa quantidades.

### Ganho esperado

O eixo escolhido é a redução da taxa de sobra.

A linha de base foi obtida no banco MySQL e está registrada no caso simples da demonstração.

Foram utilizadas as cinco operações mais recentes da feira `QUA`:

| Operação | Produzido | Vendido | Sobra |
|---:|---:|---:|---:|
| 101 | 510 | 510 | 0 |
| 94 | 533 | 397 | 136 |
| 88 | 534 | 488 | 46 |
| 81 | 533 | 501 | 32 |
| 75 | 531 | 492 | 39 |
| **Total** | **2.641** | **2.388** | **253** |

Cálculo da linha de base:

```text
taxa de sobra =
253 ÷ 2.641 × 100
=
9,58%
```

| Eixo | Linha de base medida | Alvo estimado | Ganho esperado | Volume de avaliação |
|---|---|---|---|---|
| Taxa de sobra | 9,58% nas cinco operações mais recentes da `QUA` | No máximo 8,62% | Redução relativa de 10%, equivalente a 0,96 ponto percentual | Próximas cinco operações comparáveis da `QUA` |

Cálculo do alvo:

```text
9,58% × 0,90 = 8,62%
```

Em um volume igual a 2.641 unidades, o alvo corresponderia aproximadamente a:

```text
2.641 × 8,62% = aproximadamente 228 sobras
```

Isso representaria aproximadamente 25 unidades a menos de sobra no conjunto de cinco operações.

O alvo é uma estimativa e não uma promessa. Ele deverá ser conferido nas próximas cinco operações comparáveis da feira `QUA`.

### Ressalva da métrica

Reduzir sobra não prova que não houve falta de produto.

Uma sobra igual a zero pode significar:

- venda exata;
- produto esgotado no final da feira;
- demanda não atendida.

Como o banco ainda não registra o horário em que cada produto termina, o projeto não promete reduzir sobra e falta simultaneamente.

### Ganho para o negócio

Para o negócio, os ganhos esperados são:

- maior consistência no planejamento;
- utilização sistemática do histórico;
- redução de sobras;
- melhor documentação das decisões;
- menor dependência de consultas manuais.

### Ganho para o proprietário

Para o proprietário, os ganhos esperados são:

- consultar dados em linguagem natural;
- não montar consultas SQL manualmente;
- visualizar as regras aplicadas;
- receber alertas de divergência;
- comparar cenários;
- continuar com a decisão final.

### Tensão entre os ganhos

Existe uma tensão entre reduzir sobras e evitar faltas.

Se o sistema reduzir demais a produção, a taxa de sobra pode melhorar enquanto a experiência do negócio piora por falta de produtos.

Por isso:

- a taxa de sobra não será analisada isoladamente;
- situações com sobra zero serão marcadas com incerteza;
- o proprietário poderá rejeitar a recomendação;
- o sistema não promete uma redução ilimitada.

### Custo de operação

Nos cinco casos executados com o modelo escolhido, o custo médio foi:

```text
US$ 0,00154028 por execução
```

Para 1.000 execuções, a estimativa é:

```text
US$ 1,54028
```

O custo pode variar conforme o tamanho do contexto, o número de chamadas e o preço do provedor.

### Custo de construção

O projeto é desenvolvido pelo autor como atividade acadêmica.

O tempo já utilizado na pesquisa, implementação, testes e documentação não foi cronometrado de forma confiável. Por isso, não será convertido em valor financeiro nesta entrega.

Essa ausência será tratada como limitação da análise de custo.

### Custo do erro

Uma recomendação incorreta pode provocar:

- produção excessiva;
- aumento de sobras;
- falta de produtos;
- uso inadequado de ingredientes;
- perda de confiança no sistema.

O proprietário e o negócio absorvem esse custo. Por isso, o agente não inicia a produção e as regras críticas são verificadas em código.

## 2.6 O verificador

A saída será verificada por regras determinísticas e casos rotulados.

### Regras automáticas

O verificador deve confirmar que:

- a feira informada existe;
- uma operação consultada existe;
- a quantidade vendida corresponde a produzido menos sobra;
- a sobra não é negativa;
- a sobra não supera a produção;
- produtos `5` e `15` não aparecem em `SAB_E` ou `DOM_E`;
- produtos descontinuados não aparecem;
- a soma das recomendações corresponde ao total da ferramenta;
- o modelo não alterou os valores calculados;
- nenhuma ferramenta de escrita foi executada sem confirmação;
- uma solicitação fora do escopo não disparou a ação principal.

### Casos rotulados

A verificação inicial possui cinco casos:

| Caso | Resposta esperada |
|---|---|
| Consulta simples | Consultar o histórico da `QUA` |
| Divergência | Excluir o pastel de frango da `SAB_E` |
| Registro inexistente | Informar que a operação `999999` não existe |
| Fora do escopo | Recusar a lista de compras sem chamar ferramentas |
| Pedido ambíguo | Perguntar feira e data antes de calcular |

Os quatro casos obrigatórios estão em `dados/casos_demonstracao.json` e nos arquivos oficiais de `logs/`.

O quinto caso foi utilizado na verificação dos modelos e está documentado em `docs/modelos.md`.

### Comparação humana

O proprietário confere:

- se a feira está correta;
- se os produtos pertencem àquela feira;
- se existe uma condição operacional não registrada;
- se o plano é executável;
- se a recomendação deve ser aprovada.

## 2.7 Critério de sucesso

O agente simples será considerado bem-sucedido se:

```text
resolver corretamente 5 de 5 casos rotulados
```

Além disso, deverá:

```text
violar 0 de 2 regras críticas de produtos proibidos
```

e:

```text
executar 0 escritas sem confirmação explícita
```

As duas regras críticas são:

1. não incluir o produto `5` em `SAB_E` ou `DOM_E`;
2. não incluir o produto `15` em `SAB_E` ou `DOM_E`.

O custo do erro é assimétrico. Uma resposta pouco detalhada é menos grave que incluir um produto proibido ou registrar um plano sem autorização.

Por isso, as regras críticas exigem 100% de acerto.

Na verificação realizada, o modelo escolhido resolveu os cinco casos e não violou as regras críticas.

## 2.8 Dados

### Origem

O projeto utiliza dados reais e privados da Pastéis Miyata armazenados em MySQL.

As principais tabelas são:

- `feiras`;
- `categorias`;
- `produtos`;
- `operacoes`;
- `registros_producao`.

Os dados incluem:

- feira;
- data de produção;
- data de venda;
- feriado;
- produto;
- quantidade produzida;
- quantidade vendida;
- quantidade de sobra;
- observações.

O banco completo não será publicado no repositório.

### Dados simulados

A recomendação da primeira versão é mock. Ela utiliza dados reais, mas aplica uma média simples em vez dos modelos definitivos de previsão.

O registro de plano também é mock e é salvo em arquivo local reversível.

### Casos difíceis nomeados

#### Divergência

O proprietário solicita pastel de frango para `SAB_E`, mas a regra do negócio proíbe esse produto.

#### Registro inexistente

A operação `999999` não existe no banco.

#### Caso que não deve disparar a ação principal

O proprietário solicita uma lista mensal de compras de ingredientes.

Essa solicitação não deve consultar o histórico, calcular recomendação ou registrar plano.

#### Caso ambíguo

O proprietário solicita uma recomendação para “a próxima feira” sem informar código ou data.

## 2.9 Dado sensível

O projeto não utiliza dados pessoais de clientes, dados de saúde ou dados financeiros individuais.

Entretanto, utiliza informações internas e comercialmente sensíveis, como:

- produção;
- vendas;
- sobras;
- desempenho por feira;
- observações operacionais.

Também existem credenciais técnicas sensíveis:

- senha do MySQL;
- chave da API;
- configurações locais.

Esses dados não entram no repositório.

O arquivo `.env` é ignorado pelo Git e o `.env.example` contém somente os nomes das variáveis.

As ferramentas enviam ao modelo apenas os resultados necessários para a solicitação atual, e não o banco completo.

## 2.10 Espaço para o que ainda vem

### RAG — Parte 2

- [x] O agente poderá consultar documentos com regras operacionais, catálogo de produtos, restrições das feiras e explicações dos indicadores.
- [x] O conhecimento será mantido em arquivos Markdown estruturados por seção.
- [x] As operações, datas e quantidades continuarão sendo consultadas no MySQL, não por similaridade.

### MCP — Parte 2

- [x] As ferramentas de consulta ao MySQL serão candidatas a um servidor MCP.
- [x] O servidor deverá expor operações controladas de leitura.
- [x] A integração deverá impedir SQL livre gerado pelo modelo.

### LangChain — Parte 2

- [x] Poderá ser utilizado para organizar estado, mensagens, ferramentas e trajetória.
- [x] Não substituirá as validações determinísticas.
- [x] Somente será adotado se reduzir a complexidade da orquestração.

### Multiagente — Parte 3

Uma evolução possível separa:

- agente de consulta;
- agente de previsão;
- agente de otimização;
- agente verificador;
- agente de explicação.

A separação somente será adotada se cada agente possuir responsabilidade, ferramenta e critério de avaliação próprios.

Mais de um agente não será utilizado apenas para aumentar a complexidade visual do projeto.

## 2.11 O maior risco

O maior risco não é apenas o modelo de linguagem errar. O maior risco é o histórico não representar toda a demanda real.

Quando a sobra é zero, o banco não informa se:

- a quantidade produzida foi exatamente suficiente;
- o produto terminou antes do fim da feira;
- existiam clientes que deixaram de comprar.

Isso produz demanda censurada e pode fazer um modelo aprender um valor inferior à demanda real.

### Consequência

O sistema pode recomendar quantidades menores, reduzir a sobra registrada e, ao mesmo tempo, aumentar a falta de produtos.

### Mitigação

O projeto adotará as seguintes medidas:

- marcar casos de sobra zero como incertos;
- não utilizar sobra zero como prova de ausência de falta;
- comparar a recomendação com a decisão do proprietário;
- manter aprovação humana;
- analisar os resultados por feira;
- coletar futuramente o horário em que um produto termina;
- registrar observações sobre falta percebida;
- não prometer redução simultânea de sobra e falta sem dados para verificar as duas medidas.

### Plano alternativo

Se a qualidade dos dados não for suficiente para uma previsão confiável, o sistema continuará funcionando como:

- agente de consulta;
- organizador do histórico;
- aplicador de regras;
- gerador de cenários simples;
- apoio à decisão do proprietário.

Assim, o projeto ainda entrega valor sem depender de uma previsão autônoma perfeita.