# Base de conhecimento v1 — Agente de Planejamento de Produção

## Visão geral

O agente da Pastéis Miyata será utilizado exclusivamente pelo proprietário para consultar informações, solicitar previsões, simular cenários e receber recomendações de produção.

O modelo de linguagem possui conhecimento geral sobre previsão de demanda, séries temporais, varejo de alimentos e otimização. Entretanto, ele não conhece os dados privados da Pastéis Miyata, as regras específicas das feiras, as exceções dos produtos, o histórico das operações nem as limitações dos modelos desenvolvidos para o projeto.

A base de conhecimento será dividida em duas partes:

1. **dados estruturados**, consultados diretamente no banco MySQL ou nas ferramentas do sistema;
2. **documentos textuais**, recuperados por busca semântica para explicar regras, processos e limitações.

Essa separação evita utilizar embeddings para informações que podem ser recuperadas com precisão por identificadores, datas, códigos e filtros SQL.

---

## 1. Qual informação especializada o agente precisa, e por que ela não está no modelo

### Conhecimento especializado necessário

| Informação | Por que o agente precisa | Por que não está no modelo |
|---|---|---|
| Histórico de produção, venda e sobra | Permite analisar o comportamento de cada feira e fornecer dados ao módulo de previsão | É uma informação privada e atualizada continuamente pela Pastéis Miyata |
| Regras específicas das feiras | Impede que o agente recomende produtos não comercializados ou utilize datas incorretas | São regras internas e específicas do negócio |
| Cadastro de produtos e categorias | Permite identificar corretamente os produtos comuns, especiais e doces | O catálogo é privado, específico e pode ser alterado |
| Significado dos códigos das feiras | Permite interpretar corretamente códigos como `SAB_C`, `SAB_E`, `DOM_C` e `DOM_E` | Os códigos foram criados internamente e não possuem significado público |
| Processo de produção e venda | Permite relacionar corretamente a data de produção com a data da feira | É um processo interno da Pastéis Miyata |
| Categorias de clima utilizadas | Garante que o agente use apenas os valores aceitos pelo sistema | As categorias foram definidas especificamente para o projeto |
| Feriados, eventos e situações especiais | Permite considerar condições que podem alterar o movimento da feira | São informações recentes, locais e dependentes de cada operação |
| Capacidade e limitações de ingredientes | Permite que o Simplex produza um plano possível de ser executado | São informações privadas e podem mudar a cada solicitação |
| Funcionamento do modelo de previsão | Permite explicar ao proprietário como a previsão foi produzida | A implementação, a granularidade e o modelo escolhido são específicos do TCC |
| Limitações da previsão | Permite alertar sobre poucos dados, demanda censurada e situações diferentes do histórico | Essas limitações foram identificadas durante o desenvolvimento do projeto |
| Regras da otimização por Simplex | Permite explicar quais restrições foram consideradas na recomendação | A função objetivo e as restrições pertencem ao sistema desenvolvido |
| Critérios de validação do plano | Permite informar por que um plano foi aceito, ajustado ou recusado | São regras próprias da aplicação |

### Classificação das razões

As informações especializadas podem ser classificadas da seguinte forma:

| Razão | Informações relacionadas |
|---|---|
| **Privadas** | histórico de operações, vendas, sobras, capacidade, ingredientes e regras internas |
| **Recentes demais** | novos registros, previsão do clima, eventos, feriados, produtos descontinuados e métricas atualizadas |
| **Específicas demais** | códigos das feiras, produtos bloqueados, relação entre produção e venda, categorias de clima e limitações do modelo |

O LLM não deverá tentar responder essas questões utilizando apenas seu conhecimento interno. Ele deverá consultar a fonte correspondente.

### Conhecimento que não precisa ser indexado

O modelo de linguagem já possui conhecimento geral suficiente sobre:

- o conceito de previsão de demanda;
- médias móveis, regressão linear, árvores e redes neurais;
- o funcionamento geral de uma MLP;
- o conceito de programação linear;
- o funcionamento geral do método Simplex;
- conceitos básicos de produção, vendas e desperdício;
- conceitos gerais de clima, feriado e evento;
- interpretação de linguagem natural em português.

Essas informações não serão colocadas no índice porque já são conhecimentos gerais e não acrescentariam informações específicas da Pastéis Miyata.

O agente também não utilizará documentos textuais para realizar os cálculos de previsão ou otimização. Esses cálculos serão executados por ferramentas próprias do sistema.

---

## 2. Onde esses dados estão, e em que estado

### Fontes identificadas

| Fonte | Onde está | Formato | Responsável | Frequência de mudança | Acesso | Tratamento |
|---|---|---|---|---|---|---|
| Histórico de produção, venda e sobra | Banco `pasteis_miyata` | Tabelas MySQL | Pastéis Miyata | Após cada feira | Disponível | Consulta SQL |
| Cadastro de feiras | Tabela `feiras` | Registro estruturado | Pastéis Miyata | Raramente | Disponível | Consulta SQL |
| Cadastro de produtos e categorias | Tabelas `produtos` e `categorias` | Registro estruturado | Pastéis Miyata | Quando o catálogo mudar | Disponível | Consulta SQL |
| Operações das feiras | Tabela `operacoes` | Registro estruturado | Pastéis Miyata | Após cada operação | Disponível | Consulta SQL |
| Quantidades produzidas, vendidas e de sobra | Tabela `registros_producao` | Registro estruturado | Pastéis Miyata | Após cada operação | Disponível | Consulta SQL |
| Regras e exceções do negócio | `docs/case.md`, configurações do sistema e conhecimento do proprietário | Markdown e conhecimento ainda não totalmente formalizado | Proprietário | Quando alguma regra mudar | Disponível | Consolidar em documento e indexar |
| Manual do processo operacional | Processo atualmente conhecido pelo proprietário e pelo desenvolvedor | Conhecimento parcialmente documentado | Proprietário | Ocasionalmente | Disponível | Formalizar em Markdown e indexar |
| Documentação do modelo de previsão | Projeto Python, relatórios, resultados e documentação do TCC | Markdown, CSV, JSON e código | Desenvolvedor do projeto | Quando o modelo for treinado ou substituído | Disponível | Parte textual no índice; valores atuais por consulta estruturada |
| Regras do Simplex | Código e documentação do módulo de otimização | Python, configuração e Markdown | Desenvolvedor do projeto | Quando as restrições mudarem | Disponível | Regras explicativas no índice; cálculo na ferramenta |
| Clima esperado | Informado pelo proprietário durante a conversa | Estado da execução | Proprietário | A cada planejamento | Disponível | Não indexar |
| Capacidade e ingredientes disponíveis | Informados pelo proprietário durante a conversa | Estado da execução | Proprietário | A cada planejamento | Disponível | Não indexar |
| Feriados e eventos | Banco de dados ou informação fornecida pelo proprietário | Registro estruturado e estado da execução | Proprietário | Conforme a data | Disponível | Consulta estruturada |

### Estado atual das fontes

Os dados históricos já estão organizados em um banco MySQL. Portanto, o agente poderá acessá-los por ferramentas de consulta estruturada.

As regras do negócio já aparecem parcialmente em documentos como o `case.md`, no código e nas configurações do sistema. Entretanto, algumas regras ainda existem apenas no conhecimento do proprietário ou do desenvolvedor.

Antes da criação do índice, essas informações deverão ser consolidadas em documentos próprios:

- `docs/regras-de-negocio.md`;
- `docs/manual-operacional.md`;
- `docs/modelo-de-previsao.md`;
- `docs/otimizacao-simplex.md`.

O proprietário deverá revisar as regras antes da indexação. Um erro no documento seria recuperado pelo agente como se fosse uma regra válida.

Nenhuma das fontes previstas para a primeira versão depende de acesso ainda não autorizado.

### Documentos escaneados

A primeira versão não utilizará PDFs escaneados como fonte principal.

Os registros originalmente anotados em folhas ou fotografias serão conferidos e inseridos no MySQL. O agente consultará os dados estruturados do banco, e não as imagens das folhas.

Caso documentos escaneados sejam incluídos futuramente, será necessária uma etapa própria de OCR, conferência e correção antes da indexação.

---

## 3. O que vai para o índice — e o que não vai

### Conteúdo que será indexado

O índice semântico será utilizado apenas para informações textuais que podem ser perguntadas de diferentes maneiras.

| Documento | Conteúdo | Volume inicial estimado | Chunks estimados |
|---|---|---:|---:|
| `regras-de-negocio.md` | Regras das feiras, produtos bloqueados, datas e exceções | 10 a 20 seções | 10 a 20 |
| `manual-operacional.md` | Processo de planejamento, registro, produção, venda e interpretação das sobras | 10 a 20 seções ou perguntas | 10 a 25 |
| `modelo-de-previsao.md` | Granularidade, atributos, validação temporal, modelo escolhido e limitações | 8 a 15 seções | 8 a 15 |
| `otimizacao-simplex.md` | Objetivo, restrições e interpretação da recomendação | 5 a 10 seções | 5 a 10 |

A estimativa inicial é de:

- 4 documentos;
- aproximadamente 15 a 30 páginas;
- entre 35 e 70 chunks.

O corpus será pequeno. Por isso, a primeira versão não precisa de um banco vetorial dedicado.

Os embeddings poderão ser armazenados em uma matriz NumPy, enquanto o texto e os metadados poderão ser armazenados em JSON. O índice será reconstruído apenas quando algum documento ou modelo de embedding mudar.

Se o corpus crescer para milhares de chunks, incluir muitos documentos externos ou exigir atualizações frequentes, poderá ser avaliada a migração para Chroma ou outro banco vetorial persistente.

### Conteúdo que ficará fora do índice

Não serão indexados:

- registros individuais de produção;
- quantidades vendidas;
- quantidades de sobra;
- datas das operações;
- identificadores de feiras;
- identificadores de produtos;
- previsões calculadas;
- recomendações produzidas pelo Simplex;
- capacidade informada na conversa;
- ingredientes disponíveis ou indisponíveis;
- clima informado para uma execução;
- credenciais do banco de dados;
- senhas, tokens ou configurações secretas;
- histórico completo das conversas;
- código-fonte integral do projeto;
- imagens das folhas de produção.

Essas informações ficarão de fora porque são estruturadas, temporárias, sensíveis ou produzidas durante a própria execução.

### Consulta estruturada e busca semântica

| Pergunta do proprietário | Forma correta de responder |
|---|---|
| “Quanto foi vendido na feira `QUA` em determinada data?” | Consulta SQL |
| “Qual foi a sobra do pastel de carne no sábado?” | Consulta SQL |
| “Quais produtos pertencem à categoria Doces?” | Consulta SQL |
| “Qual é o código da feira de domingo?” | Consulta SQL ou configuração |
| “Qual era o clima registrado em determinada operação?” | Consulta SQL |
| “Qual é a previsão para a próxima feira?” | Ferramenta de previsão |
| “Quanto devo produzir?” | Previsão seguida do Simplex |
| “A capacidade de 1.200 unidades foi respeitada?” | Validação determinística |
| “Por que o frango não aparece na `SAB_E`?” | Regra estruturada e explicação recuperada do documento |
| “Como o sistema interpreta uma sobra igual a zero?” | Busca semântica no manual |
| “Por que a previsão possui incerteza?” | Busca semântica na documentação do modelo |
| “Por que foi utilizada validação temporal?” | Busca semântica na documentação do modelo |
| “Quais restrições o Simplex considera?” | Busca semântica na documentação da otimização |

Datas, quantidades, faixas de valores, códigos e identificadores serão resolvidos com SQL ou regras em código. Esses elementos não devem ser decididos por similaridade de cosseno.

A busca semântica será usada principalmente para responder perguntas explicativas, nas quais o proprietário pode utilizar palavras diferentes das presentes nos documentos.

### Separação entre regra e explicação

Algumas informações existirão tanto em configuração estruturada quanto em documentos.

Por exemplo, a proibição de pastel de frango na `SAB_E` deverá existir em uma regra de código ou configuração para impedir a recomendação. O documento textual será utilizado apenas para explicar essa regra ao proprietário.

Assim:

- o **código aplica a regra**;
- o **RAG explica a regra**;
- o **LLM não decide se a regra existe**.

### Fluxo de recuperação

Quando o proprietário fizer uma pergunta, o Router deverá decidir entre:

1. **consulta estruturada**, para dados exatos;
2. **busca semântica**, para regras e explicações;
3. **ferramenta de previsão ou otimização**, para cálculos;
4. **combinação das fontes**, quando a resposta exigir dados e explicação.

Exemplo:

> “Por que a recomendação da `SAB_E` ficou menor e quanto foi vendido na última feira?”

Nesse caso, o agente poderá:

1. consultar no MySQL quanto foi vendido;
2. consultar as restrições aplicadas pelo otimizador;
3. recuperar do índice a explicação da regra da feira;
4. produzir uma resposta que diferencie claramente dados, cálculo e regra.

---

## 4. A estratégia de chunking

Não será aplicada uma única estratégia de chunking a todos os documentos. Cada tipo de documento será dividido de acordo com sua unidade natural.

O critério principal será:

> Cada chunk deve fazer sentido quando recuperado sozinho, sem depender do trecho anterior.

### Documento de regras do negócio

O arquivo `regras-de-negocio.md` será dividido por regra ou seção.

Exemplo de estrutura:

```text
Regra FEIRA-SAB-E-001
Título: Produtos não comercializados na SAB_E
Descrição: A feira SAB_E não comercializa pastel de frango nem pastel de escarola sem bacon.
Aplicação: Os produtos devem ser removidos antes da otimização.
```

Cada regra formará um chunk. O título e o identificador da regra serão incluídos no próprio texto para que o trecho seja compreensível isoladamente.

Metadados:

```json
{
  "documento": "regras-de-negocio",
  "tipo": "regra",
  "regra_id": "FEIRA-SAB-E-001",
  "feira": "SAB_E",
  "produtos_relacionados": [5, 15],
  "versao": "1.0",
  "atualizado_em": "2026-09-18",
  "responsavel": "proprietario"
}
```

### Manual operacional

O arquivo `manual-operacional.md` será dividido por procedimento ou item de FAQ.

Exemplos de unidades naturais:

- “Como registrar uma operação”;
- “Como interpretar a quantidade vendida”;
- “Como tratar uma sobra igual a zero”;
- “Como informar um evento especial”;
- “O que fazer quando um dado estiver ausente”.

Cada procedimento ou pergunta com sua resposta será um chunk.

Se um procedimento possuir várias etapas dependentes, o título será repetido em cada chunk.

Um trecho como:

> “Depois disso, execute o próximo passo.”

não deverá ser indexado isoladamente. Ele precisará herdar o nome do procedimento e a descrição da etapa anterior ou ser unido ao mesmo chunk.

Metadados:

```json
{
  "documento": "manual-operacional",
  "tipo": "procedimento",
  "topico": "registro_de_operacao",
  "etapa": 2,
  "feira": null,
  "versao": "1.0",
  "atualizado_em": "2026-09-18"
}
```

### Documentação do modelo de previsão

O arquivo `modelo-de-previsao.md` será dividido por seção temática.

As unidades naturais serão:

- objetivo do modelo;
- dados utilizados;
- granularidade;
- atributos;
- validação temporal;
- métricas;
- modelo selecionado;
- interpretação da previsão;
- demanda censurada;
- limitações;
- situações em que a previsão deve ser tratada com cautela.

Cada chunk herdará o título da seção e a versão do modelo.

Metadados:

```json
{
  "documento": "modelo-de-previsao",
  "tipo": "documentacao_modelo",
  "secao": "limitacoes",
  "versao_modelo": "v1",
  "granularidade": "categoria_e_feira",
  "periodo_treinamento": "informado_pelo_sistema",
  "atualizado_em": "data_do_treinamento"
}
```

Valores numéricos atuais, como MAE, RMSE ou período de treinamento, deverão ser consultados no relatório estruturado da versão do modelo. O índice será utilizado para explicar o significado e as limitações dessas informações.

### Documentação da otimização por Simplex

O arquivo `otimizacao-simplex.md` será dividido por objetivo e restrição.

As unidades naturais serão:

- função objetivo;
- capacidade máxima;
- produtos permitidos;
- ingredientes disponíveis;
- quantidades mínimas e máximas;
- interpretação de solução ótima;
- tratamento de problema inviável;
- limitações da recomendação.

Cada restrição deverá formar um chunk autossuficiente.

Metadados:

```json
{
  "documento": "otimizacao-simplex",
  "tipo": "restricao",
  "restricao_id": "CAPACIDADE-001",
  "categoria": "capacidade",
  "versao": "1.0",
  "atualizado_em": "2026-09-18"
}
```

### Documentos sem estrutura natural

Se futuramente for incluído algum texto sem títulos, seções ou perguntas, será utilizado corte por caracteres com os seguintes valores iniciais:

- tamanho aproximado: 800 caracteres;
- sobreposição: 120 caracteres.

A sobreposição será utilizada apenas para evitar que uma frase ou explicação seja dividida entre dois chunks.

Esses valores são iniciais e deverão ser avaliados. Documentos que possuam estrutura natural não serão cortados por uma quantidade fixa de caracteres.

### Metadados comuns

Todos os chunks deverão possuir, no mínimo:

- identificador único;
- documento de origem;
- tipo do conteúdo;
- seção ou regra;
- versão;
- data da atualização;
- responsável;
- feira relacionada, quando aplicável;
- produto ou categoria relacionada, quando aplicável.

Os metadados permitirão filtrar o corpus antes da comparação por similaridade.

Por exemplo, se a pergunta estiver relacionada à `SAB_E`, o sistema poderá priorizar chunks que tenham:

```json
{
  "feira": "SAB_E"
}
```

O filtro de metadados será utilizado para restringir o espaço de busca. A similaridade será utilizada somente depois do filtro.

### Quantidade de chunks recuperados

O valor inicial será:

```text
TOP_K = 3
```

Serão recuperados inicialmente até três chunks, pois utilizar apenas o primeiro resultado pode esconder o trecho correto, enquanto recuperar muitos trechos aumenta o contexto e pode introduzir informações irrelevantes.

Esse valor não será considerado definitivo.

### Avaliação da recuperação

Será criado um conjunto inicial de 15 a 25 perguntas com respostas conhecidas.

Exemplos:

| Pergunta | Chunk esperado |
|---|---|
| “Quais produtos não são vendidos na `SAB_E`?” | `FEIRA-SAB-E-001` |
| “Uma sobra igual a zero prova que houve falta?” | seção sobre demanda censurada |
| “Por que a validação precisa ser temporal?” | seção sobre validação temporal |
| “O que acontece quando a capacidade é menor que a demanda?” | restrição de capacidade do Simplex |
| “Quem pode aprovar a recomendação?” | regra de aprovação do proprietário |

A recuperação será medida com `recall@k`, verificando se o chunk esperado aparece entre os primeiros resultados.

Também serão incluídas perguntas sem resposta no corpus, como forma de avaliar se o sistema deve recusar ou direcionar a solicitação para outra ferramenta.

O objetivo inicial será medir:

- `recall@1`;
- `recall@3`;
- perguntas recuperadas incorretamente;
- perguntas sem resposta;
- filtros de metadados aplicados incorretamente.

Não será utilizado um limite de similaridade escolhido apenas por intuição. O portão entre a recuperação e a geração deverá ser calibrado com perguntas que possuem resposta e perguntas que não possuem resposta.

---

## Decisão inicial

A primeira versão utilizará:

- MySQL para dados históricos e informações exatas;
- ferramentas Python para previsão e otimização;
- regras em código para validações obrigatórias;
- arquivos Markdown para conhecimento textual;
- embeddings para recuperar explicações e regras;
- matriz NumPy e metadados em JSON para o índice inicial;
- `TOP_K = 3`, sujeito à avaliação por `recall@k`;
- confirmação do proprietário antes de qualquer registro de aprovação.

A arquitetura de conhecimento pode ser resumida da seguinte forma:

```text
Pergunta do proprietário
          |
          v
       Router
          |
          +--> Dado exato ou histórico
          |        |
          |        +--> Consulta SQL no MySQL
          |
          +--> Previsão ou recomendação
          |        |
          |        +--> Modelo de previsão + Simplex
          |
          +--> Regra ou explicação
          |        |
          |        +--> Busca semântica nos documentos
          |
          +--> Resposta combinada
                   |
                   +--> SQL + ferramentas + chunks recuperados
```

O RAG não substituirá o banco de dados, o modelo de previsão, o Simplex nem as validações. Ele será utilizado somente para fornecer ao LLM o conhecimento textual privado e específico necessário para explicar as decisões ao proprietário.

---