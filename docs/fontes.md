# Fontes consultadas

Este documento reúne as fontes utilizadas na definição do case, na arquitetura do agente, na base de conhecimento, na análise dos modelos e na implementação do agente simples da Pastéis Miyata.

As fontes estão divididas em:

1. materiais da disciplina;
2. casos da indústria;
3. documentação da OpenAI;
4. fontes internas do projeto.

Última atualização: 22 de setembro de 2026.

## 1. Materiais da disciplina

### 1.1 Visão geral do trabalho

CRIVELARO, Celso. **Trabalho da disciplina — Visão geral**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/trabalho/00-visao-geral.md

Acesso em: 22 set. 2026.

Uso no projeto:

- compreensão das três entregas da disciplina;
- identificação dos quatro anti-padrões;
- definição do escopo do agente;
- organização dos arquivos do repositório;
- entendimento de que o mesmo sistema continuará nas Partes 2 e 3.

### 1.2 Parte 1 — Escolher e provar o terreno

CRIVELARO, Celso. **Trabalho da disciplina — Parte 1: Escolher e provar o terreno**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/trabalho/01-primeira-entrega.md

Acesso em: 22 set. 2026.

Uso no projeto:

- detalhamento do problema;
- definição do usuário principal;
- definição da interação;
- workflow do agente;
- justificativa de negócio;
- definição do verificador;
- análise de três modelos;
- cálculo de custos;
- requisitos do agente simples;
- definição dos quatro casos demonstrados;
- definição da estrutura da entrega.

### 1.3 Exercício 4 — A escolha do case

CRIVELARO, Celso. **Exercício 4 — A escolha do case**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-04-casos-de-uso-e-escolha-do-projeto/exercicios/exercicio_04.md

Acesso em: 22 set. 2026.

Uso no projeto:

- definição do setor;
- formulação do problema em uma frase;
- descrição do processo atual;
- identificação das regras do domínio;
- identificação dos casos difíceis;
- pesquisa dos casos da indústria;
- justificativa de por que utilizar um agente;
- definição dos ganhos esperados.

### 1.4 Exercício 5 — Arquitetura do agente

CRIVELARO, Celso. **A arquitetura do agente do trabalho**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-05-arquitetura-de-agentes/exercicios/exercicio_05-trabalho.md

Acesso em: 22 set. 2026.

Uso no projeto:

- separação da arquitetura em entrada, sistema e processamento;
- definição das ferramentas;
- definição do estado explícito;
- definição dos orçamentos;
- identificação dos padrões utilizados;
- descrição das entradas e saídas de cada etapa;
- marcação dos pontos de escrita;
- construção do fluxo da arquitetura.

### 1.5 Notas da Aula 5 — Arquitetura de agentes

CRIVELARO, Celso. **Notas de aula — Arquitetura de agentes**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/tree/main/aula-05-arquitetura-de-agentes/notas-de-aula

Acesso em: 22 set. 2026.

Uso no projeto:

- escolha do padrão de agente;
- análise do nível de autonomia;
- diferenciação entre workflow, roteador, agente, avaliador e orquestrador;
- aplicação da regra de utilizar a menor autonomia capaz de resolver o problema.

### 1.6 Tabela de decisão de padrões

CRIVELARO, Celso. **Qual padrão usar**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-05-arquitetura-de-agentes/notas-de-aula/01-6-qual-padrao-usar.md

Acesso em: 22 set. 2026.

Uso no projeto:

- justificativa da escolha de um agente com ferramentas;
- análise de por que um workflow fixo não resolve sozinho as ambiguidades;
- definição dos limites de autonomia;
- manutenção da aprovação final com o proprietário.

### 1.7 Exercício 6 — Base de conhecimento

CRIVELARO, Celso. **A base de conhecimento do trabalho**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-06-embeddings-e-rag/exercicios/exercicio_06-trabalho.md

Acesso em: 22 set. 2026.

Uso no projeto:

- identificação do conhecimento privado e específico;
- levantamento das fontes de dados;
- separação entre busca semântica e consulta estruturada;
- estimativa da escala da base;
- definição inicial da estratégia de chunking.

### 1.8 Notas da Aula 6 — Embeddings e RAG

CRIVELARO, Celso. **Notas de aula — Embeddings e RAG**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/tree/main/aula-06-embeddings-e-rag/notas-de-aula

Acesso em: 22 set. 2026.

Uso no projeto:

- entendimento de embeddings;
- avaliação da necessidade de RAG;
- definição das unidades naturais de corte;
- uso de metadados;
- decisão de não utilizar busca vetorial para valores, datas e identificadores.

### 1.9 Chunking e medida da busca

CRIVELARO, Celso. **Chunking e a medida da busca**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-06-embeddings-e-rag/notas-de-aula/02-chunking-e-a-medida-da-busca.md

Acesso em: 22 set. 2026.

Uso no projeto:

- definição de cortes por unidade natural;
- decisão de preservar cabeçalhos;
- avaliação de se cada chunk possui sentido isoladamente;
- rejeição de uma única estratégia de chunking para todos os documentos.

### 1.10 Bancos vetoriais

CRIVELARO, Celso. **Bancos vetoriais**. Repositório da disciplina Agentes de IA com LLMs.

Disponível em:  
https://github.com/celsocrivelaro/senac-agentes-llm/blob/main/aula-06-embeddings-e-rag/notas-de-aula/04-bancos-vetoriais.md

Acesso em: 22 set. 2026.

Uso no projeto:

- separação entre similaridade e filtros estruturados;
- decisão de consultar o MySQL para operações, datas, feiras e quantidades;
- entendimento de que uma base pequena pode ser mantida em memória sem banco vetorial.

## 2. Casos da indústria

### 2.1 C3 AI — previsão de demanda e programação da produção

C3 AI. **Enterprise AI for Demand Planning and Production Scheduling**.

Disponível em:  
https://c3.ai/customers/enterprise-ai-for-demand-planning-and-production-scheduling

Acesso em: 22 set. 2026.

Informações utilizadas:

- aplicação no setor de alimentos e agronegócio;
- operação de oito linhas de produção;
- produção superior a 80 milhões de libras de alimentos por ano;
- mais de 90 códigos de produtos;
- integração de 18 fontes de dados;
- aproximadamente 72 milhões de registros;
- utilização de aprendizado de máquina para previsão diária;
- utilização de otimização para programação da produção;
- aumento declarado de 8% na precisão da previsão;
- redução declarada de 96% no tempo e no esforço para gerar programações;
- identificação de US$ 30 milhões em margem bruta adicional;
- identificação de US$ 1,5 milhão em economia com redução de trocas;
- avaliação e aprovação humana das recomendações.

Relação com o projeto:

O caso demonstra uma arquitetura híbrida, na qual modelos de previsão e algoritmos de otimização realizam os cálculos, enquanto uma interface permite que pessoas avaliem cenários e aprovem recomendações.

Essa separação é semelhante à arquitetura da Pastéis Miyata: o modelo de linguagem coordena ferramentas, mas não inventa a previsão ou a recomendação.

Limitações da fonte:

- o cliente não é identificado;
- os resultados foram publicados pelo fornecedor da solução;
- os valores anteriores das métricas não são detalhados;
- o custo de implantação e manutenção não é informado;
- valores identificados não representam necessariamente ganhos financeiros realizados;
- não existe avaliação independente apresentada na página.

### 2.2 Walmart — Wally

WALMART. **Walmart Develops GenAI-Powered Assistant for Walmart Merchants**. 18 mar. 2025.

Disponível em:  
https://corporate.walmart.com/news/2025/03/18/walmart-develops-genai-powered-assistant-for-walmart-merchants

Acesso em: 22 set. 2026.

Informações utilizadas:

- uso de IA generativa sobre dados proprietários;
- análise de dados em linguagem natural;
- identificação das causas do desempenho de produtos;
- realização de cálculos e previsões;
- resposta a dúvidas operacionais;
- abertura de chamados não resolvidos;
- utilização de uma camada semântica;
- retorno de informações em segundos;
- intenção de aumentar a autonomia dentro de limites configuráveis.

Relação com o projeto:

O Wally demonstra um agente utilizado como interface entre pessoas, dados internos e ferramentas analíticas.

No projeto da Pastéis Miyata, o proprietário conversa em linguagem natural, enquanto o agente decide se deve consultar o MySQL, calcular uma recomendação ou recusar a solicitação.

Limitações da fonte:

- não apresenta uma linha de base numérica;
- não informa a precisão das respostas;
- não informa o custo por interação;
- não quantifica a redução total de trabalho;
- foi publicada pela própria empresa.

### 2.3 Wendy’s — FreshAI

WENDY’S. **Leading Drive-Thru Innovation with Wendy’s FreshAI**. 11 dez. 2023.

Disponível em:  
https://www.wendys.com/blog/drive-thru-innovation-wendys-freshai

Acesso em: 22 set. 2026.

Informações utilizadas:

- agente conversacional aplicado ao drive-thru;
- tratamento de linguagem natural;
- interpretação de pedidos incompletos e personalizados;
- mais de 200 bilhões de possíveis configurações de um produto;
- média declarada de 86% dos pedidos concluídos sem intervenção humana;
- projeto-piloto realizado inicialmente em quatro restaurantes;
- encaminhamento para uma pessoa quando o agente não consegue concluir.

Relação com o projeto:

O caso demonstra por que determinados processos exigem interação em tempo de execução. Assim como o consumidor pode omitir informações de um pedido, o proprietário pode não informar a feira, a data ou uma restrição operacional.

Limitações da fonte:

- não apresenta comparação detalhada com atendentes humanos;
- não informa o custo por pedido;
- não apresenta a gravidade ou frequência dos erros;
- o resultado inicial foi obtido em somente quatro restaurantes;
- foi publicada pela própria empresa.

### 2.4 Wendy’s e Google Cloud — arquitetura do FreshAI

THE WENDY’S COMPANY. **Wendy’s Taps Google Cloud to Revolutionize the Drive-Thru Experience with Artificial Intelligence**. 9 maio 2023.

Disponível em:  
https://www.irwendys.com/news/news-details/2023/Wendys-Taps-Google-Cloud-to-Revolutionize-the-Drive-Thru-Experience-with-Artificial-Intelligence/default.aspx

Acesso em: 22 set. 2026.

Informações utilizadas:

- uso de modelos de linguagem;
- uso de IA generativa;
- conhecimento especializado do cardápio;
- compreensão de pedidos personalizados;
- integração com o sistema de ponto de venda;
- utilização de regras de negócio e proteções na interação.

Limitações da fonte:

- é um comunicado das empresas responsáveis;
- descreve principalmente o início do projeto-piloto;
- não apresenta custo total;
- não apresenta uma avaliação independente.

## 3. Documentação da OpenAI

### 3.1 Catálogo de modelos

OPENAI. **Models — OpenAI API**.

Disponível em:  
https://developers.openai.com/api/docs/models

Acesso em: 22 set. 2026.

Uso no projeto:

- identificação dos modelos disponíveis;
- definição dos candidatos;
- consulta dos identificadores;
- comparação inicial entre Luna, Terra e Sol;
- consulta da janela de contexto e do tamanho máximo da saída.

### 3.2 Comparação de modelos

OPENAI. **Compare models — OpenAI API**.

Disponível em:  
https://developers.openai.com/api/docs/models/compare

Acesso em: 22 set. 2026.

Uso no projeto:

- confirmação do suporte a function calling;
- confirmação do suporte a saídas estruturadas;
- comparação da janela de contexto;
- comparação dos limites de saída;
- comparação de recursos e preços.

### 3.3 GPT-5.6 Luna

OPENAI. **GPT-5.6 Luna Model**.

Disponível em:  
https://developers.openai.com/api/docs/models/gpt-5.6-luna

Acesso em: 22 set. 2026.

Uso no projeto:

- confirmação do identificador `gpt-5.6-luna`;
- confirmação do suporte ao Chat Completions;
- confirmação do suporte a function calling;
- confirmação do suporte a saídas estruturadas;
- consulta da janela de contexto;
- consulta do preço;
- escolha do modelo da primeira versão.

### 3.4 GPT-5.6 Terra

OPENAI. **GPT-5.6 Terra Model**.

Disponível em:  
https://developers.openai.com/api/docs/models/gpt-5.6-terra

Acesso em: 22 set. 2026.

Uso no projeto:

- confirmação do identificador `gpt-5.6-terra`;
- avaliação como modelo intermediário;
- comparação de capacidade e custo;
- execução da verificação mínima.

### 3.5 GPT-5.6 Sol

OPENAI. **GPT-5.6 Sol Model**.

Disponível em:  
https://developers.openai.com/api/docs/models/gpt-5.6-sol

Acesso em: 22 set. 2026.

Uso no projeto:

- confirmação do identificador `gpt-5.6-sol`;
- avaliação como modelo de maior capacidade;
- comparação de capacidade e custo;
- execução da verificação mínima.

### 3.6 Preços da API

OPENAI. **Pricing — OpenAI API**.

Disponível em:  
https://developers.openai.com/api/docs/pricing

Acesso em: 22 set. 2026.

Uso no projeto:

- obtenção dos preços de entrada e saída;
- cálculo de custo por execução;
- cálculo de custo para 100 execuções;
- estimativa de custo para o semestre;
- configuração das variáveis de preço no `.env`.

Observação:

Os valores podem ser alterados pelo provedor. Eles devem ser consultados novamente antes das próximas entregas.

### 3.7 Function calling

OPENAI. **Function calling — OpenAI API**.

Disponível em:  
https://developers.openai.com/api/docs/guides/function-calling

Acesso em: 22 set. 2026.

Uso no projeto:

- definição das ferramentas;
- definição dos parâmetros em JSON Schema;
- implementação do ciclo entre modelo, aplicação e ferramenta;
- envio do resultado da ferramenta novamente ao modelo;
- controle da execução pelo código Python.

### 3.8 Saídas estruturadas

OPENAI. **Structured model outputs — OpenAI API**.

Disponível em:  
https://developers.openai.com/api/docs/guides/structured-outputs

Acesso em: 22 set. 2026.

Uso no projeto:

- entendimento do uso de JSON Schema;
- validação dos argumentos das ferramentas;
- diferenciação entre function calling e formatação da resposta final;
- prevenção de campos ausentes ou valores inválidos.

### 3.9 Biblioteca Python

OPENAI. **OpenAI Python API library**.

Disponível em:  
https://github.com/openai/openai-python

Acesso em: 22 set. 2026.

Uso no projeto:

- instalação da biblioteca `openai`;
- criação do cliente da API;
- envio das mensagens;
- declaração das ferramentas;
- leitura do uso de tokens;
- tratamento dos retornos do modelo.

## 4. Fontes internas do projeto

### 4.1 Banco MySQL da Pastéis Miyata

Fonte privada mantida pelo proprietário.

Banco:

```text
pasteis_miyata