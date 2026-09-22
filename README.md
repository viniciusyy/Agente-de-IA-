# Agente de Planejamento de Produção — Pastéis Miyata

## Integrante

- Vinicius Miyata

## Problema

O proprietário da Pastéis Miyata precisa definir quanto produzir de cada tipo de pastel para cada feira sem depender apenas da experiência e de consultas manuais ao histórico.

## Sobre o projeto

Este projeto apresenta um agente simples desenvolvido para a Parte 1 da disciplina de Agentes de IA com LLMs.

O sistema é utilizado exclusivamente pelo proprietário da Pastéis Miyata. O agente recebe solicitações em linguagem natural, identifica o objetivo do proprietário, decide quais ferramentas utilizar e apresenta os resultados de forma organizada.

Nesta primeira versão, o agente pode:

- consultar operações reais armazenadas no MySQL;
- consultar o histórico de uma feira;
- calcular uma recomendação mock baseada na média das vendas recentes;
- aplicar regras fixas das feiras;
- registrar um plano mock após confirmação explícita;
- informar quando uma solicitação está fora do escopo;
- registrar a trajetória completa de cada execução.

O modelo de linguagem não calcula livremente as quantidades. Consultas, médias, restrições e totais são processados por código Python e pelo banco MySQL.

## Limitações da primeira versão

Este é um agente simples criado para provar que a arquitetura e as ferramentas são implementáveis.

Nesta versão, o sistema:

- ainda não utiliza os modelos definitivos de previsão do TCC;
- ainda não executa a otimização por Simplex;
- não controla estoque de ingredientes;
- não cria listas de compras;
- não inicia nenhuma atividade física de produção;
- não altera os registros históricos do MySQL;
- não substitui a decisão do proprietário;
- não deve ser utilizado por outros perfis de usuário.

A recomendação atual é uma simulação determinística baseada na média das últimas vendas registradas.

## Tecnologias utilizadas

- Python;
- biblioteca `openai`;
- API da OpenAI;
- modelo `gpt-5.6-luna`;
- MySQL;
- `mysql-connector-python`;
- `python-dotenv`;
- Git e GitHub.

Não é necessário utilizar SQLite, pois a integração com software tradicional é realizada diretamente com o banco MySQL da Pastéis Miyata.

## Estrutura do projeto

```text
.
├── dados/
│   └── casos_demonstracao.json
├── docs/
│   ├── case.md
│   ├── fontes.md
│   └── modelos.md
├── exercicios/
│   ├── aula-05-arquitetura.md
│   └── aula-06-base-de-conhecimento.md
├── logs/
│   ├── 01_caso_simples.json
│   ├── 02_caso_divergencia.json
│   ├── 03_registro_inexistente.json
│   └── 04_acao_nao_permitida.json
├── prompts/
│   └── agente_planejamento_v1.md
├── src/
│   ├── agent.py
│   ├── config.py
│   ├── database.py
│   └── main.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

# Como rodar

## 1. Pré-requisitos

Antes de executar o projeto, é necessário ter:

- Python instalado;
- MySQL em execução;
- banco `pasteis_miyata` criado;
- tabelas e registros utilizados pelo projeto;
- uma chave válida da API da OpenAI;
- créditos disponíveis na conta da API.

A assinatura do ChatGPT e os créditos da API são serviços separados.

## 2. Clonar o repositório

```powershell
git clone https://github.com/viniciusyy/Agente-de-IA-.git
cd Agente-de-IA-
```

Caso o projeto já esteja no computador, basta abrir sua pasta no terminal.

## 3. Criar o ambiente virtual

No PowerShell:

```powershell
python -m venv .venv
```

## 4. Instalar as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 5. Criar o arquivo `.env`

Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

Depois, abra o `.env` e informe localmente:

- a chave da API da OpenAI;
- o endereço e a porta do MySQL;
- o nome do banco;
- o usuário e a senha do banco.

Exemplo de estrutura:

```env
LLM_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
LLM_MODEL=gpt-5.6-luna

LLM_INPUT_PRICE_PER_MILLION=0.20
LLM_OUTPUT_PRICE_PER_MILLION=1.20

DB_HOST=localhost
DB_PORT=3306
DB_NAME=pasteis_miyata
DB_USER=
DB_PASSWORD=

AGENT_MAX_STEPS=8
AGENT_MAX_TOOL_CALLS=6
AGENT_MAX_TOKENS=9000
AGENT_MAX_SECONDS=60
AGENT_MAX_COST_USD=0.10
```

A chave da API e a senha do MySQL não devem ser colocadas no `.env.example`, no código ou no GitHub.

## 6. Executar o agente

```powershell
.\.venv\Scripts\python.exe -m src.main
```

Quando a execução funcionar, o sistema exibirá:

```text
AGENTE SIMPLES DE PLANEJAMENTO — PASTÉIS MIYATA
Usuário autorizado: proprietário
```

Também será realizado um teste de conexão com o MySQL.

# Como usar

O proprietário inicia a interação digitando uma solicitação em linguagem natural.

Exemplos:

```text
Consulte as últimas cinco operações da feira QUA.
```

```text
Consulte a operação 101.
```

```text
Calcule uma recomendação para a feira SAB_E.
```

```text
Calcule uma recomendação para a feira SAB_E, mas inclua pastel de frango.
```

Para encerrar:

```text
sair
```

## O que o sistema faz com a solicitação

O agente:

1. interpreta o pedido do proprietário;
2. verifica se a solicitação pertence ao escopo;
3. identifica se alguma informação está ausente;
4. escolhe uma ferramenta quando necessário;
5. executa consultas ou cálculos por código;
6. aplica as regras fixas do negócio;
7. apresenta o resultado;
8. registra a trajetória em um arquivo JSON.

## Como interpretar a saída

Além da resposta principal, cada execução apresenta um resumo:

```text
Motivo da parada
Passos executados
Ferramentas chamadas
Tokens de entrada
Tokens de saída
Custo estimado
Caminho do log
```

Os principais motivos de parada são:

| Motivo | Significado |
|---|---|
| `RESPOSTA_FINAL` | O agente terminou normalmente |
| `LIMITE_DE_PASSOS` | O orçamento máximo de passos foi atingido |
| `LIMITE_DE_TOKENS` | O orçamento máximo de tokens foi atingido |
| `LIMITE_DE_TEMPO` | O tempo máximo da execução foi atingido |
| `LIMITE_DE_CUSTO` | O custo máximo configurado foi atingido |
| `ERRO_DO_MODELO` | O provedor ou o modelo retornou um erro |

# Exemplo real de execução

A entrada e a saída abaixo foram copiadas da execução registrada em `logs/01_caso_simples.json`.

## Entrada

```text
Consulte as últimas cinco operações da feira QUA.
```

## Saída

```text
CONSULTA AO HISTÓRICO

Filtros utilizados:
- Feira: QUA
- Últimas operações: 5

Resultado:

| Operação | Produção | Venda | Produzido | Vendido | Sobra | Feriado |
|---:|---|---|---:|---:|---:|---|
| 101 | 01/09/2026 | 02/09/2026 | 510 | 510 | 0 | Não |
| 94 | 25/08/2026 | 26/08/2026 | 533 | 397 | 136 | Não |
| 88 | 18/08/2026 | 19/08/2026 | 534 | 488 | 46 | Não |
| 81 | 11/08/2026 | 12/08/2026 | 533 | 501 | 32 | Não |
| 75 | 04/08/2026 | 05/08/2026 | 531 | 492 | 39 | Não |

Resumo:
- Total produzido: 2.641 unidades
- Total vendido: 2.388 unidades
- Total de sobras: 253 unidades
- Média produzida por operação: 528,2 unidades
- Média vendida por operação: 477,6 unidades
- Média de sobra por operação: 50,6 unidades
- Maior sobra: 136 unidades, na operação 94

Produtos com maiores sobras registradas:
- Queijo: até 29 unidades
- Carne: até 28 unidades
- Pizza: até 22 unidades
- Carne com queijo: até 18 unidades
- Frango catupiri: até 12 unidades

Alertas:
- A operação 101 não teve sobra.
- A operação 94 apresentou sobra significativamente maior que as demais.
- Os registros detalhados por produto foram consolidados.
```

## Resumo real da execução

```text
Motivo da parada: RESPOSTA_FINAL
Passos executados: 2
Ferramentas chamadas: 1
Tokens de entrada: 7535
Tokens de saída: 476
Custo estimado: US$ 0.00207820
```

# Ferramentas do agente

| Ferramenta | Função | Tipo | Reversível |
|---|---|---|---|
| `consultar_historico` | Consulta operações recentes de determinada feira no MySQL | Leitura | Sim |
| `consultar_operacao` | Consulta uma operação pelo identificador | Leitura | Sim |
| `calcular_recomendacao_mock` | Calcula uma recomendação pela média das vendas recentes | Leitura e cálculo | Sim |
| `registrar_plano_mock` | Registra um plano mock após confirmação explícita | Escrita | Sim |

A ferramenta de escrita não é executada sem confirmação explícita do proprietário.

# Regras do domínio aplicadas

O agente respeita, entre outras, as seguintes regras:

- as feiras válidas são `QUA`, `QUI`, `SAB_C`, `SAB_E`, `DOM_C` e `DOM_E`;
- `SAB_E` e `DOM_E` não comercializam pastel de frango, produto de código `5`;
- `SAB_E` e `DOM_E` não comercializam pastel de escarola sem bacon, produto de código `15`;
- o pastel de banana simples está temporariamente descontinuado;
- quantidade vendida é calculada por `produzida - sobra`;
- uma operação inexistente deve ser tratada como erro de ferramenta, sem derrubar o programa;
- nenhuma quantidade pode ser inventada pelo modelo;
- nenhum plano é registrado sem confirmação explícita do proprietário.

# Casos demonstrados

Os quatro casos obrigatórios estão registrados em `logs/`:

| Caso | Solicitação | Resultado esperado |
|---|---|---|
| Caso simples | Consultar as últimas operações da feira `QUA` | Consulta o MySQL e apresenta o histórico |
| Divergência | Solicitar pastel de frango para `SAB_E` | Aplica a restrição e exclui o produto |
| Registro inexistente | Consultar a operação `999999` | Informa que o registro não existe |
| Ação não permitida | Solicitar lista mensal de ingredientes | Recusa a ação sem chamar ferramentas |

# Segurança

Os seguintes dados não devem ser enviados ao GitHub:

- arquivo `.env`;
- chave da API;
- senha do MySQL;
- credenciais pessoais;
- ambiente virtual `.venv`;
- logs intermediários.

O repositório contém apenas o `.env.example`, sem valores privados.

# Encerramento

Esta versão demonstra que o modelo consegue interpretar solicitações do proprietário, selecionar ferramentas, consultar o MySQL, aplicar regras do negócio, tratar erros e respeitar limites de execução.

A integração com os modelos definitivos de previsão e com a otimização por Simplex pertence às próximas etapas do projeto e não faz parte deste agente simples.