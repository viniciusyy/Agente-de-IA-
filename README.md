# Agente de Planejamento de Produção — Pastéis Miyata

## Integrante

- Vinicius Miyata

## Problema em uma frase

O proprietário da Pastéis Miyata precisa definir quanto produzir de cada tipo de pastel para cada feira sem depender apenas da experiência e de consultas manuais ao histórico.

## Sobre o projeto

Este projeto foi desenvolvido para a disciplina de Agentes de IA com LLMs.

O sistema implementa um agente simples utilizado exclusivamente pelo proprietário da Pastéis Miyata. O agente recebe solicitações em linguagem natural, identifica a intenção do proprietário e decide quais ferramentas devem ser utilizadas.

Nesta primeira entrega, o agente pode:

- consultar o histórico de uma feira no MySQL;
- consultar uma operação pelo identificador;
- calcular uma recomendação mock baseada na média das vendas recentes;
- registrar um plano mock depois da confirmação do proprietário;
- tratar erros de ferramentas sem encerrar o programa;
- registrar a trajetória de cada execução em arquivo JSON.

Os cálculos desta versão são uma prova de conceito. O sistema ainda não utiliza os modelos de previsão, a MLP ou a otimização por Simplex previstos no TCC.

## Tecnologias utilizadas

- Python;
- biblioteca `openai`;
- MySQL;
- `mysql-connector-python`;
- `python-dotenv`;
- API de um provedor compatível com a biblioteca `openai`.

## Estrutura do projeto

```text
Agente-de-IA-/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── dados/
│   └── casos_demonstracao.json
├── docs/
│   ├── arquitetura-v1.md
│   ├── base-de-conhecimento-v1.md
│   ├── case.md
│   ├── fontes.md
│   └── modelos.md
├── logs/
├── prompts/
│   └── agente_planejamento_v1.md
└── src/
    ├── agent.py
    ├── config.py
    ├── database.py
    └── main.py
```

## Como rodar

### 1. Clonar o repositório

```powershell
git clone URL_DO_REPOSITORIO
```

Entre na pasta do projeto:

```powershell
cd Agente-de-IA-
```

### 2. Criar o ambiente virtual

No Windows PowerShell:

```powershell
py -m venv .venv
```

Não é obrigatório ativar o ambiente virtual. Os comandos seguintes utilizam diretamente o Python instalado dentro dele.

### 3. Instalar as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Criar o arquivo `.env`

Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

Abra o `.env` e preencha as configurações locais.

Exemplo de configuração com a API da Mistral:

```env
OPENAI_API_KEY=SUA_CHAVE_DA_API
LLM_BASE_URL=https://api.mistral.ai/v1
LLM_MODEL=mistral-small-latest

LLM_INPUT_PRICE_PER_MILLION=PRECO_DE_ENTRADA
LLM_OUTPUT_PRICE_PER_MILLION=PRECO_DE_SAIDA

DB_HOST=localhost
DB_PORT=3306
DB_NAME=pasteis_miyata
DB_USER=SEU_USUARIO
DB_PASSWORD=SUA_SENHA

AGENT_MAX_STEPS=8
AGENT_MAX_TOOL_CALLS=6
AGENT_MAX_TOKENS=9000
AGENT_MAX_TIME_SECONDS=60
AGENT_MAX_COST_USD=0.10

LOG_DIRECTORY=logs
```

Apesar do nome `OPENAI_API_KEY`, essa variável recebe a chave do provedor configurado em `LLM_BASE_URL`. O projeto mantém esse nome porque utiliza a biblioteca Python `openai`.

Os preços de entrada e saída devem ser preenchidos com os valores por um milhão de tokens divulgados pelo provedor para o modelo selecionado.

O arquivo `.env` contém credenciais e não deve ser enviado ao GitHub.

### 5. Preparar o MySQL

O serviço do MySQL deve estar iniciado e o banco configurado no `.env` deve existir.

A primeira versão espera as seguintes tabelas:

- `feiras`;
- `produtos`;
- `operacoes`;
- `registros_producao`.

As consultas utilizam os campos de identificação da feira, datas da operação, produto, quantidade produzida, sobra e quantidade vendida.

### 6. Executar o agente

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m src.main
```

O programa testará a conexão com o MySQL antes de iniciar o atendimento.

Quando a conexão funcionar, será exibido:

```text
Verificando conexão com o MySQL...
Conexão com o MySQL realizada com sucesso.
Banco selecionado: pasteis_miyata
```

## Como usar

A interação ocorre pelo terminal. O proprietário digita uma solicitação em linguagem natural depois de:

```text
Proprietário:
```

Exemplo:

```text
Proprietário: Consulte as últimas cinco operações da feira QUA.
```

O agente interpreta a solicitação, escolhe uma ferramenta, consulta o sistema necessário e devolve uma resposta em português.

Para encerrar:

```text
sair
```

Também são aceitos:

```text
encerrar
```

```text
fechar
```

## Exemplos de solicitações

### Consultar uma feira

```text
Consulte as últimas cinco operações da feira QUA.
```

### Consultar uma operação

```text
Consulte a operação 25.
```

### Solicitar uma recomendação mock

```text
Calcule uma recomendação simples para a feira SAB_E.
```

### Testar uma divergência com as regras

```text
Calcule uma recomendação para a feira SAB_E, mas inclua pastel de frango.
```

O agente deve informar que o pastel de frango não é comercializado na feira `SAB_E`.

### Testar um registro inexistente

```text
Consulte a operação 999999.
```

A ferramenta deve devolver o erro como dado, permitindo que o agente explique que a operação não foi encontrada.

### Testar uma solicitação fora do escopo

```text
Faça uma lista de compras de ingredientes para o próximo mês.
```

O agente deve explicar que essa ação não pertence ao escopo desta versão e não deve registrar um plano.

## O que o sistema devolve

Ao final de cada solicitação, o terminal apresenta:

- a resposta do agente;
- o motivo da parada;
- a quantidade de passos;
- a quantidade de ferramentas chamadas;
- os tokens de entrada;
- os tokens de saída;
- o custo estimado;
- o caminho do arquivo de log.

Exemplo da estrutura da saída:

```text
RESPOSTA DO AGENTE
======================================================================
[resposta apresentada ao proprietário]

----------------------------------------------------------------------
RESUMO DA EXECUÇÃO
----------------------------------------------------------------------
Motivo da parada: RESPOSTA_FINAL
Passos executados: [quantidade]
Ferramentas chamadas: [quantidade]
Tokens de entrada: [quantidade]
Tokens de saída: [quantidade]
Custo estimado: US$ [valor]
Log salvo em: logs\execucao_[data_e_hora].json
```

## Exemplo completo de uma execução real

> **PENDENTE DE EXECUÇÃO:** esta seção será substituída por uma entrada e uma saída reais depois que a cota da API estiver ativa. O resultado não será inventado, conforme a exigência da disciplina.

A entrada planejada para o exemplo é:

```text
Consulte as últimas cinco operações da feira QUA.
```

Depois da execução bem-sucedida, serão copiados para esta seção:

- o texto exato digitado;
- a resposta exata do agente;
- o motivo da parada;
- a quantidade de ferramentas chamadas;
- o caminho do log correspondente.

## Ferramentas do agente

| Ferramenta | Função | Operação | Reversível |
|---|---|---|---|
| `consultar_historico` | Consulta no MySQL as operações recentes de uma feira | Leitura | Não altera dados |
| `consultar_operacao` | Consulta uma operação pelo identificador | Leitura | Não altera dados |
| `calcular_recomendacao_mock` | Calcula a média das vendas recentes | Leitura e cálculo | Não altera dados |
| `registrar_plano_mock` | Registra um plano aprovado em arquivo JSONL | Escrita | Sim |

## Recomendação mock

A recomendação desta primeira versão é calculada por software tradicional, e não pelo modelo de linguagem.

Para cada produto, o sistema calcula:

```text
média vendida =
soma das quantidades vendidas ÷ quantidade de registros
```

A quantidade recomendada é a média arredondada.

Nas feiras `SAB_E` e `DOM_E`, os seguintes produtos são excluídos:

- pastel de frango, identificado pelo código `5`;
- pastel de escarola sem bacon, identificado pelo código `15`.

Essa recomendação existe somente para demonstrar a integração entre o agente, as ferramentas e o MySQL. Ela não substitui o modelo de previsão do TCC.

## Logs

Cada solicitação gera um arquivo JSON dentro de:

```text
logs/
```

O log contém:

- objetivo informado pelo proprietário;
- ferramentas chamadas;
- argumentos utilizados;
- resultados;
- erros;
- quantidade de passos;
- tokens consumidos;
- custo estimado;
- motivo da terminação.

As quatro execuções exigidas na entrega deverão ser identificadas como:

```text
logs/
├── 01_caso_simples.json
├── 02_caso_divergencia.json
├── 03_registro_inexistente.json
└── 04_acao_nao_permitida.json
```

## O que o sistema não faz

Nesta primeira versão, o agente não:

- inicia fisicamente a produção;
- altera registros oficiais do MySQL;
- executa a MLP do TCC;
- executa otimização por Simplex;
- consulta previsão meteorológica externa;
- compra ingredientes;
- substitui a decisão do proprietário;
- registra um plano sem confirmação;
- garante que a média histórica seja uma previsão definitiva.

Quando não consegue responder, o agente deve explicar a limitação ou apresentar o erro recebido da ferramenta.

## Segurança

As chaves da API e a senha do MySQL ficam somente no arquivo `.env`.

Essas informações não devem ser:

- colocadas diretamente no código;
- incluídas no `.env.example`;
- registradas nos logs;
- enviadas ao GitHub;
- compartilhadas em mensagens ou documentos.

O repositório disponibiliza apenas os nomes das variáveis necessárias.

## Limitações conhecidas

- A recomendação utiliza uma média simples;
- o resultado depende da qualidade dos dados do MySQL;
- o agente depende da disponibilidade da API escolhida;
- limites de requisições podem interromper uma execução;
- os preços do provedor podem mudar;
- a primeira versão funciona somente pelo terminal;
- o sistema foi desenvolvido para uso exclusivo do proprietário.