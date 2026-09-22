# Fontes consultadas

## Casos da indústria

### C3 AI — previsão de demanda e programação da produção

C3 AI. **Enterprise AI for Demand Planning and Production Scheduling**.

Disponível em:  
https://c3.ai/customers/enterprise-ai-for-demand-planning-and-production-scheduling

Acesso em: 4 set. 2026.

Informações utilizadas:

- fábrica do setor de alimentos e agronegócio;
- oito linhas de produção;
- mais de 80 milhões de libras produzidas por ano;
- mais de 90 códigos de produtos;
- integração de 18 fontes e aproximadamente 72 milhões de registros;
- aumento de 8% na precisão da previsão;
- redução de 96% no tempo e esforço para gerar programações;
- US$ 30 milhões em margem bruta adicional identificada;
- US$ 1,5 milhão em economia identificada pela redução de trocas;
- participação humana na avaliação e aprovação das recomendações.

Limitações da fonte:

- o cliente não é identificado;
- não apresenta detalhadamente a linha de base;
- os resultados são divulgados pelo fornecedor da solução;
- valores “identificados” não significam necessariamente ganhos financeiros realizados;
- o custo da solução não é apresentado.

### Walmart — Wally

WALMART. **Walmart Develops GenAI-Powered Assistant for Walmart Merchants**. 18 mar. 2025.

Disponível em:  
https://corporate.walmart.com/news/2025/03/18/walmart-develops-genai-powered-assistant-for-walmart-merchants

Acesso em: 4 set. 2026.

Informações utilizadas:

- uso de IA generativa sobre dados proprietários;
- análise de dados e geração de informações;
- identificação da causa do desempenho de produtos;
- realização de cálculos e previsões;
- resposta a perguntas operacionais;
- abertura de chamados não resolvidos;
- retorno de informações em segundos;
- intenção de aumentar a autonomia dentro de limites configuráveis.

Limitações da fonte:

- não informa o tempo anterior das tarefas;
- não apresenta taxa de acerto;
- não informa custo por interação;
- não quantifica a redução de trabalho;
- é uma publicação da própria empresa.

### Wendy’s — FreshAI

WENDY’S. **Leading Drive-Thru Innovation with Wendy’s FreshAI**. 11 dez. 2023.

Disponível em:  
https://www.wendys.com/blog/drive-thru-innovation-wendys-freshai

Acesso em: 4 set. 2026.

Informações utilizadas:

- agente conversacional aplicado ao drive-thru;
- tratamento de linguagem informal e personalizações;
- mais de 200 bilhões de possíveis configurações de um produto;
- média de 86% dos pedidos concluídos sem intervenção de funcionário;
- projeto-piloto realizado inicialmente em quatro restaurantes;
- participação humana quando o agente não consegue concluir o atendimento.

Limitações da fonte:

- não apresenta comparação detalhada com atendentes humanos;
- não informa o custo por pedido;
- não informa a gravidade dos erros;
- o resultado inicial foi obtido em somente quatro restaurantes;
- é uma publicação da própria empresa.

### Wendy’s e Google Cloud — integração e arquitetura

THE WENDY’S COMPANY. **Wendy’s Taps Google Cloud to Revolutionize the Drive-Thru Experience with Artificial Intelligence**. 9 maio 2023.

Disponível em:  
https://www.irwendys.com/news/news-details/2023/Wendys-Taps-Google-Cloud-to-Revolutionize-the-Drive-Thru-Experience-with-Artificial-Intelligence/default.aspx

Acesso em: 4 set. 2026.

Informações utilizadas:

- uso de modelos de linguagem e IA generativa;
- integração com o sistema de ponto de venda;
- conhecimento do cardápio;
- regras de negócio e proteções para a conversa;
- capacidade de compreender pedidos personalizados.

## Modelos e API

### Catálogo de modelos da OpenAI

OPENAI. **All models — OpenAI API**.

Disponível em:

https://developers.openai.com/api/docs/models/all

Acesso em: 21 set. 2026.

Informações utilizadas:

- modelos disponíveis;
- identificadores dos modelos;
- tamanho da janela de contexto;
- limite de saída;
- suporte a ferramentas;
- perfil de utilização de cada modelo.

Modelos analisados:

- `gpt-5.6-luna`;
- `gpt-5.6-terra`;
- `gpt-5.6-sol`.

### Comparação dos modelos

OPENAI. **Compare models — OpenAI API**.

Disponível em:

https://developers.openai.com/api/docs/models/compare

Acesso em: 21 set. 2026.

Informações utilizadas:

- comparação de recursos;
- janela de contexto;
- limite de saída;
- recursos de ferramentas;
- diferenças de posicionamento entre os modelos.

### Preços da API

OPENAI. **Pricing — OpenAI API**.

Disponível em:

https://developers.openai.com/api/docs/pricing

Acesso em: 21 set. 2026.

Informações utilizadas:

- preço por milhão de tokens de entrada;
- preço por milhão de tokens de saída;
- cálculo estimado por execução;
- cálculo estimado para 100 execuções;
- cálculo estimado para 1.000 execuções.

Observação:

Os preços podem ser alterados pelo provedor. Eles deverão ser conferidos novamente antes da entrega e antes da execução dos testes.

### Chamadas de ferramentas

OPENAI. **Function calling — OpenAI API**.

Disponível em:

https://developers.openai.com/api/docs/guides/function-calling

Acesso em: 21 set. 2026.

Informações utilizadas:

- declaração de ferramentas;
- descrição das funções;
- contratos de argumentos;
- geração de chamadas pelo modelo;
- devolução do resultado da ferramenta;
- continuidade da conversa depois da execução.

Relação com o projeto:

O agente utilizará chamadas de ferramentas para consultar o MySQL, executar a previsão, executar a otimização e registrar um plano aprovado.

### Saídas estruturadas

OPENAI. **Structured model outputs — OpenAI API**.

Disponível em:

https://developers.openai.com/api/docs/guides/structured-outputs

Acesso em: 21 set. 2026.

Informações utilizadas:

- geração de respostas estruturadas;
- definição de esquema;
- validação do formato;
- redução de argumentos incompletos ou inesperados.

Relação com o projeto:

Os argumentos enviados às ferramentas deverão seguir contratos estruturados e validados pelo programa.

### Política de privacidade

OPENAI. **Enterprise privacy at OpenAI**.

Disponível em:

https://openai.com/enterprise-privacy/

Acesso em: 21 set. 2026.

Informações utilizadas:

- tratamento de dados enviados pela API;
- não utilização dos dados empresariais para treinamento por padrão;
- necessidade de controle sobre os dados enviados;
- proteção de informações internas.

Aplicação no projeto:

- credenciais não serão enviadas ao modelo;
- chaves de API não serão enviadas no contexto;
- somente os dados necessários serão retornados pelas ferramentas;
- o conteúdo completo do banco MySQL não será enviado ao modelo;
- dados internos não serão publicados no repositório.