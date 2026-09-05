# A escolha do case

## 1. O case — indústria e problema

### Setor

O projeto está inserido no setor de varejo de alimentos, mais especificamente na produção e comercialização de alimentos em feiras livres.

O contexto estudado é o da Pastéis Miyata, uma pequena empresa familiar que produz pastéis para diferentes feiras ao longo da semana. Esse setor foi escolhido porque o processo é conhecido por dentro e já existem dados reais de produção, vendas e sobras sendo coletados e armazenados em um banco de dados.

### Problema, em uma frase

O proprietário da Pastéis Miyata precisa definir quanto produzir de cada tipo de pastel para cada feira sem depender apenas de sua experiência e de consultas manuais ao histórico.

### Contexto atual

Atualmente, a quantidade de pastéis a ser produzida é definida principalmente com base na experiência do proprietário. Para tomar essa decisão, ele considera fatores como o movimento esperado da feira, o dia da semana, o clima, os feriados, os eventos e o histórico recente de vendas.

Os registros de produção e sobras são inicialmente feitos de forma manual. Posteriormente, esses dados são organizados e inseridos em um banco MySQL. Para analisar o histórico, o proprietário precisa consultar os registros, comparar diferentes dias e interpretar manualmente o efeito de fatores como chuva, frio ou feriado.

O tempo utilizado nesse processo ainda precisa ser medido. Para estabelecer uma linha de base confiável, serão cronometrados dez planejamentos reais realizados pelo proprietário, desde o início da consulta aos dados até a definição final das quantidades.

Sem o novo sistema, o processo atual envolve:

1. identificar para qual feira e data a produção será realizada;
2. consultar ou lembrar o desempenho de feiras anteriores;
3. considerar clima, feriados e acontecimentos especiais;
4. verificar possíveis limitações de produtos, ingredientes ou capacidade;
5. decidir manualmente quanto produzir;
6. ajustar as quantidades com base na experiência do proprietário.

### Regras do domínio

O agente deverá respeitar as seguintes regras:

- As feiras são identificadas pelos códigos `QUA`, `QUI`, `SAB_C`, `SAB_E`, `DOM_C` e `DOM_E`.
- A produção da feira de quarta-feira ocorre na terça-feira.
- A produção da feira de quinta-feira ocorre na quarta-feira.
- As produções das feiras de sábado ocorrem na sexta-feira.
- As produções das feiras de domingo ocrem no sábado.
- `SAB_C` e `SAB_E` representam duas feiras diferentes realizadas no sábado.
- `DOM_C` e `DOM_E` representam duas feiras diferentes realizadas no domingo.
- As feiras `SAB_E` e `DOM_E` não vendem pastel de frango nem pastel de escarola sem bacon.
- A quantidade vendida é calculada pela diferença entre a quantidade produzida e a quantidade que sobrou.
- A quantidade de sobra não pode ser negativa nem maior que a quantidade produzida.
- Os climas utilizados no sistema são: Sol, Frio, Garoa, Chuva Moderada e Chuva Forte.
- Feriados, eventos locais e condições climáticas podem alterar o movimento esperado.
- Produtos sem histórico suficiente devem ser tratados com maior incerteza.
- Produtos temporariamente descontinuados não devem aparecer na recomendação.
- A soma das quantidades recomendadas deve respeitar a capacidade de produção e eventuais limitações de ingredientes informadas pelo proprietário.
- A recomendação deve ser calculada por módulos próprios de previsão e otimização, e não inventada pelo modelo de linguagem.
- Somente o proprietário poderá utilizar o agente.
- Somente o proprietário poderá aprovar, rejeitar ou solicitar alterações em uma recomendação.
- O agente pode sugerir um plano, mas não pode considerá-lo aprovado sem a confirmação explícita do proprietário.
- O agente não pode iniciar ou executar fisicamente a produção.

### O que dá errado atualmente

Os principais casos difíceis do processo são:

- o proprietário pedir uma recomendação sem informar a data ou a feira;
- não ficar claro se o pedido é para uma ou para as duas feiras do mesmo dia;
- o clima esperado ser diferente entre os locais das feiras;
- existir um feriado ou evento que não aparece claramente no histórico;
- os dados de uma operação estarem ausentes, duplicados ou contraditórios;
- ocorrer sobra igual a zero sem ser possível saber se houve venda exata ou falta do produto;
- um produto ter pouco histórico de vendas;
- um produto ter sido criado, removido ou temporariamente descontinuado;
- uma recomendação incluir um produto que não é vendido em determinada feira;
- a demanda prevista ser maior que a capacidade disponível;
- existirem restrições de ingredientes que obriguem a redistribuição da produção;
- a previsão estatística entrar em conflito com a experiência prática do proprietário;
- ocorrer uma situação muito diferente das existentes no histórico.

Quando alguma informação essencial estiver ausente, o agente deverá perguntar ao proprietário antes de executar a recomendação. Quando houver dados contraditórios ou insuficientes, deverá informar claramente a limitação e deixar a decisão final com o proprietário.

### O que a indústria já faz

#### Caso 1 — C3 AI: previsão de demanda e programação da produção

A C3 AI divulgou um caso de uma empresa global do setor de alimentos e agronegócio que precisava melhorar sua previsão de demanda e sua programação de produção. A fábrica possuía oito linhas de produção, fabricava mais de 80 milhões de libras de alimentos por ano e trabalhava com mais de 90 códigos de produtos.

A solução integrou 18 fontes diferentes, totalizando aproximadamente 72 milhões de registros. Foram utilizados modelos de aprendizado de máquina para gerar previsões diárias de demanda e um módulo de otimização para recomendar a programação da produção.

Segundo a divulgação, a solução aumentou a precisão da previsão em 8% e reduziu em 96% o tempo e o esforço necessários para gerar as programações. A empresa também declarou ter identificado US$ 30 milhões em margem bruta adicional e US$ 1,5 milhão em economia relacionada à redução de trocas nas linhas de produção.

A arquitetura aparentemente segue um modelo híbrido: modelos de aprendizado de máquina realizam a previsão, um algoritmo especializado realiza a otimização e uma interface apresenta os resultados para avaliação humana. A solução permite que os responsáveis examinem indicadores, alterem parâmetros, simulem cenários e aprovem as recomendações.

Essa arquitetura é semelhante à proposta deste projeto porque os cálculos não ficam sob responsabilidade do modelo de linguagem. No agente da Pastéis Miyata, o LLM deverá interpretar o pedido do proprietário, descobrir informações ausentes e coordenar as ferramentas, enquanto os módulos de previsão e Simplex executarão os cálculos.

A divulgação não apresenta o nome da empresa atendida, os valores anteriores das métricas, o custo de implantação, o custo de manutenção nem quanto dos ganhos identificados foi efetivamente realizado. Também não permite concluir que o LLM, sozinho, tomou decisões de produção.

#### Caso 2 — Walmart: Wally

O Walmart desenvolveu o Wally, um assistente baseado em IA generativa destinado às equipes responsáveis pela seleção e pelo desempenho dos produtos vendidos pela empresa.

O sistema trabalha sobre dados proprietários do Walmart e auxilia em atividades como entrada e análise de dados, identificação das causas do desempenho de produtos, realização de cálculos, geração de previsões, resposta a dúvidas operacionais e abertura de chamados quando um problema não é resolvido.

O Walmart afirma que os usuários conseguem fazer perguntas em linguagem natural e receber informações úteis em segundos. A empresa também informa que pretende aumentar gradualmente a autonomia do sistema, permitindo que ele execute ações dentro de limites configuráveis.

Pelas informações publicadas, a arquitetura provavelmente é a de um agente assistente ou copiloto com uso de ferramentas. Uma camada semântica permite que o modelo interprete os dados internos, enquanto serviços especializados realizam consultas, cálculos e abertura de chamados. O usuário humano continua responsável pelas decisões de negócio. Portanto, o sistema está no lado assistido do espectro de autonomia, embora o Walmart declare a intenção de avançar para ações autônomas com salvaguardas.

Esse caso se aproxima do projeto porque mostra um agente utilizado como interface entre uma pessoa e diferentes fontes de dados e ferramentas analíticas. O agente não substitui os sistemas tradicionais; ele permite que o usuário faça perguntas em linguagem natural e coordena os recursos necessários para respondê-las.

A divulgação não apresenta uma linha de base numérica. A expressão “em segundos” não informa quanto tempo a mesma atividade levava anteriormente. Também não são divulgadas métricas de precisão, taxa de respostas incorretas, custo por interação ou quantidade de decisões que ainda exigem intervenção humana.

#### Caso 3 — Wendy’s: FreshAI

A rede de restaurantes Wendy’s desenvolveu o FreshAI em parceria com o Google Cloud para atender clientes no drive-thru por meio de conversação.

O problema possui elevada complexidade porque os clientes podem utilizar linguagem informal, alterar ingredientes, fazer pedidos incompletos e mudar de ideia durante a conversa. A empresa afirma que existem mais de 200 bilhões de formas de configurar um de seus sanduíches.

Durante o projeto-piloto, o FreshAI conseguiu concluir, em média, 86% dos pedidos sem a intervenção de um funcionário. Na época da divulgação, a solução estava ativa em quatro restaurantes da empresa na região de Columbus, nos Estados Unidos.

A arquitetura provavelmente é a de um agente conversacional com uso de ferramentas, regras de domínio e participação humana. O modelo interpreta o pedido, consulta informações do cardápio, respeita regras e restrições e envia o resultado ao sistema de ponto de venda. Quando não consegue resolver a situação com segurança, um funcionário assume o atendimento.

Embora o FreshAI não faça previsão de demanda, ele é relevante para este projeto porque demonstra por que alguns problemas não podem ser resolvidos apenas por um formulário e regras fixas. Assim como um cliente pode omitir informações de seu pedido, o proprietário da Pastéis Miyata pode não informar inicialmente a feira, a data, o clima, uma limitação de ingredientes ou um evento especial. O agente precisa descobrir essas informações por meio da conversa.

A divulgação define claramente a cobertura sem intervenção humana, mas não informa a linha de base da precisão dos atendentes, o custo por pedido, o tempo médio completo antes e depois do sistema ou a gravidade dos erros ocorridos. Além disso, o resultado inicial veio de apenas quatro restaurantes, o que limita a generalização.

## 2. Os usuários, e como será a interação

### Perfil de usuário

O agente será utilizado exclusivamente pelo proprietário da Pastéis Miyata. Outros funcionários ou pessoas relacionadas ao negócio não utilizarão o agente nem poderão aprovar suas recomendações.

| Perfil | O que ele quer | O que ele sabe | O que ele pode fazer |
|---|---|---|---|
| Proprietário da Pastéis Miyata | Obter recomendações de produção para cada feira e compreender os motivos do plano | Conhece a rotina da produção, as feiras, os produtos, os custos, a capacidade e as situações especiais do negócio | Informar restrições, definir objetivos, solicitar cenários, consultar previsões e aprovar, rejeitar ou solicitar alterações na recomendação |

### Usuário principal

O proprietário da Pastéis Miyata é o usuário principal e o único usuário autorizado a utilizar o agente.

O sistema será projetado para ajudá-lo a tomar decisões com menos consultas manuais, sem retirar seu controle sobre o resultado. A prioridade será apresentar recomendações claras e seguras, respeitando as regras do negócio e mantendo a decisão final com o proprietário.

### Forma de interação

Na primeira versão, a interação ocorrerá por meio de um chat executado no terminal. O proprietário iniciará a conversa solicitando o planejamento de uma produção.

O agente deverá:

1. interpretar o objetivo do proprietário;
2. identificar informações ausentes;
3. perguntar apenas o que for necessário;
4. consultar os dados históricos;
5. acionar o módulo de previsão;
6. acionar o módulo de otimização por Simplex;
7. validar as regras da feira;
8. apresentar a recomendação;
9. solicitar a aprovação do proprietário.

Espera-se que uma solicitação normal seja resolvida em aproximadamente duas a cinco trocas de mensagens. O resultado será apresentado em uma tabela contendo, no mínimo:

- feira;
- produto ou categoria;
- demanda prevista;
- quantidade recomendada;
- restrições consideradas;
- alertas de incerteza.

Quando o agente não conseguir resolver uma solicitação, deverá explicar o motivo de forma objetiva ao proprietário. Ele não poderá completar dados ausentes por conta própria, esconder falhas das ferramentas ou apresentar uma quantidade inventada como se tivesse sido calculada.

### Diálogo de exemplo

Os números abaixo são ilustrativos e servem apenas para descrever a interação esperada.

**Proprietário:**  
Planeje a produção para as feiras de sábado.

**Agente:**  
Para qual data? O planejamento será para `SAB_C`, `SAB_E` ou para as duas feiras?

**Proprietário:**  
Para 5 de setembro de 2026, nas duas feiras.

**Agente:**  
Preciso confirmar três informações: qual é o clima esperado em cada local, existe algum evento especial e há alguma limitação de ingredientes ou de capacidade?

**Proprietário:**  
Garoa na `SAB_C`, chuva moderada na `SAB_E`, sem evento especial e capacidade máxima de 1.200 pastéis.

**Agente:**  
Entendido. Vou consultar o histórico das duas feiras, executar a previsão e calcular um plano que respeite a capacidade máxima e as restrições de produtos.

**Agente:**  
A recomendação calculada foi:

| Feira | Demanda prevista | Produção recomendada | Observação |
|---|---:|---:|---|
| `SAB_C` | 620 | 610 | Garoa considerada no cálculo |
| `SAB_E` | 540 | 530 | Chuva moderada; frango e escarola sem bacon excluídos |
| **Total** | **1.160** | **1.140** | Dentro da capacidade máxima de 1.200 |

A recomendação utiliza 1.140 unidades da capacidade disponível. O resultado da `SAB_E` possui maior incerteza devido à previsão de chuva moderada. Deseja consultar os valores por produto, simular outro cenário ou aprovar o plano?

**Proprietário:**  
Por que não há pastel de frango na `SAB_E`?

**Agente:**  
Porque a regra dessa feira informa que o pastel de frango não é comercializado na `SAB_E`. O otimizador excluiu esse produto e distribuiu a capacidade entre os produtos permitidos.

**Proprietário:**  
Pode aprovar o plano.

**Agente:**  
Plano marcado como aprovado pelo proprietário. A produção ainda depende de execução humana, pois o sistema não inicia nenhuma atividade física de produção.

### Informações que o proprietário pode não fornecer inicialmente

A necessidade de interação existe porque o proprietário pode não informar inicialmente:

- a data da produção;
- a feira desejada;
- se o pedido envolve uma ou duas feiras;
- o clima esperado em cada local;
- a existência de feriado ou evento;
- a capacidade disponível;
- a falta de algum ingrediente;
- a prioridade entre reduzir sobra e evitar falta;
- se deseja apenas consultar, simular ou aprovar um plano.

Essas informações mudam a escolha dos dados, das ferramentas e das restrições. Por isso, o problema exige decisão em tempo de execução e não pode ser tratado apenas como o preenchimento de um formulário fixo.

## 3. Os ganhos esperados

### Por que um agente, e não software comum

O agente é necessário porque a solicitação do proprietário pode chegar incompleta ou ambígua, exigindo que o sistema descubra o contexto, faça perguntas, selecione ferramentas e trate exceções durante a execução.

Os cálculos continuarão em software tradicional: o agente coordenará a consulta ao banco, o modelo de previsão e o Simplex, mas as quantidades não serão calculadas livremente pelo LLM.

### Eixos de ganho

| Eixo | Linha de base | Alvo | Ganho | Volume |
|---|---|---|---|---|
| Tempo por planejamento | Média de dez planejamentos manuais realizados pelo proprietário: **[PREENCHER APÓS A CRONOMETRAGEM]** | Reduzir o tempo médio em pelo menos 60% | `tempo médio atual - tempo médio com o agente` | Até seis planos de feira por semana |
| Taxa de sobra | `total de sobras ÷ total produzido × 100`, calculado sobre o período histórico definido: **[PREENCHER COM O BANCO]** | Reduzir a taxa de sobra em pelo menos 10% em relação à linha de base, sem violar as restrições do negócio | `taxa atual - taxa com o sistema` | Todas as operações registradas no período de avaliação |

O ganho semanal de tempo será calculado pela fórmula:

`6 × (tempo médio manual - tempo médio com o agente)`

A redução relativa da sobra será calculada pela fórmula:

`((taxa de sobra anterior - taxa de sobra com o sistema) ÷ taxa de sobra anterior) × 100`

Os valores finais somente serão declarados depois da medição. O projeto não utilizará uma taxa de ruptura, pois atualmente não é registrado o momento em que cada produto termina. Uma sobra igual a zero não prova, sozinha, que houve perda de vendas.

### Ganho para o proprietário

Para o proprietário, o principal ganho será reduzir o trabalho de procurar registros, comparar dias e realizar cálculos manualmente. Ele receberá uma recomendação organizada, acompanhada das regras consideradas, das limitações encontradas e de uma explicação do resultado.

O proprietário continuará tendo a decisão final. Ele poderá aprovar, rejeitar ou solicitar outro cenário quando possuir alguma informação prática que ainda não esteja registrada no sistema.

Para o negócio, os ganhos esperados são maior consistência no planejamento, melhor aproveitamento do histórico e redução de sobras. Entretanto, existe uma tensão: reduzir excessivamente a produção pode diminuir as sobras, mas também pode aumentar o risco de faltar produto.

Como o banco atual não registra o horário em que um produto termina, essa possível falta deverá ser tratada como uma limitação da avaliação. O sistema não prometerá reduzir simultaneamente sobra e falta sem possuir dados capazes de verificar as duas medidas.