# Agente de Planejamento de Produção — Pastéis Miyata

**Integrante:** Vinicius Miyata  
**Disciplina:** Agentes de IA com LLMs — Partes 1, 2 e 3

O proprietário da Pastéis Miyata precisa definir quanto produzir para cada feira. O agente consulta o histórico, recupera regras do negócio e calcula uma recomendação para apoiar essa decisão.

O modelo de linguagem interpreta os pedidos e escolhe as ferramentas. As consultas e os cálculos são feitos por código. A versão atual usa a média das vendas das cinco operações recentes da feira como baseline. Ela não executa o modelo definitivo de previsão nem o Simplex desenvolvidos no TCC.

- [Executar com Docker em outro computador](#como-executar-o-projeto-com-docker)
- [Executar localmente com Python e MySQL](#como-rodar)
- [Usar o agente](#como-usar)
- [Rodar e comparar avaliações](#avaliação-da-parte-3)
- [Consultar traces](#traces-opentelemetry)

## Sobre o projeto

A Parte 2 implementou o grafo LangGraph, o RAG textual, a memória, os checkpoints, a saída validada e a aprovação humana antes de registrar um plano. A Parte 3 acrescentou uma suíte de avaliação, controles de segurança fora do prompt, documentação de governança e instrumentação OpenTelemetry.

A identidade técnica padrão é `proprietario`, com a conversa `proprietario-principal`. A configuração define o perfil de uso local; não equivale a um sistema de autenticação de rede.

## Arquitetura resumida

| Componente | Responsabilidade |
|---|---|
| `src/main.py` | Interface de terminal, validação inicial e apresentação da resposta |
| `src/agent.py` e `src/graph.py` | Fachada, estado do grafo, seleção de ferramentas, limites e aprovação |
| `src/database.py` e `src/domain.py` | Consultas estruturadas e cálculo determinístico |
| `src/rag.py` e `dados/corpus/` | Recuperação local de regras e definições |
| `src/memory.py` | Preferências, episódios estruturados e planos aprovados em SQLite |
| `src/seguranca.py` | Contratos de ferramentas, filtros e verificações de escrita |
| `src/observabilidade.py` | Spans GenAI e exportação local de traces |
| `evals/` e `tests/` | Dataset, avaliação, comparações e testes automatizados |

O MySQL contém os registros operacionais. O SQLite guarda checkpoints, memória e planos aprovados. O agente não altera o histórico operacional do MySQL.

## Ferramentas

| Ferramenta | Função |
|---|---|
| `consultar_historico` | Lê as operações recentes de uma feira |
| `consultar_operacao` | Lê uma operação pelo identificador |
| `buscar_conhecimento` | Recupera regras e informações do corpus local |
| `calcular_recomendacao` | Usa o histórico para calcular o baseline e aplicar restrições |
| `salvar_preferencia` | Versiona uma preferência permitida e explicitamente autorizada |
| `registrar_plano` | Solicita aprovação humana e registra o plano no SQLite |

## Como executar o projeto com Docker

Este modo permite demonstrar o agente sem acesso ao banco operacional original e sem instalar Python ou MySQL diretamente no computador. É necessário ter Docker com Compose funcionando e, para pedidos que chamam o modelo, uma chave de API própria e acesso ao modelo configurado.

### 1. Preparar o projeto

No PowerShell:

```powershell
git clone https://github.com/viniciusyy/Agente-de-IA-.git
cd Agente-de-IA-

if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Se já tiver o repositório, abra o terminal na raiz, onde está `compose.yaml`.

Coloque o banco de demonstração recebido separadamente em `docker/mysql-init/01-demo.sql` **antes de iniciar o banco pela primeira vez**. O arquivo não faz parte do repositório. O MySQL importa os scripts de inicialização ao criar o banco em um volume vazio; trocar o arquivo não reimporta um volume existente.

### 2. Configurar o `.env`

Preencha estas variáveis no `.env` da sua máquina:

```dotenv
OPENAI_API_KEY=
LLM_MODEL=

DEMO_MYSQL_ROOT_PASSWORD=
DEMO_MYSQL_USER=
DEMO_MYSQL_PASSWORD=
```

Escolha um modelo disponível para sua conta e credenciais próprias para a demonstração. Não reutilize credenciais do banco original. O Compose configura a conexão do agente com o serviço `db`.

### 3. Subir os serviços e executar

```powershell
docker compose version
docker compose config --quiet
docker compose up -d db
docker compose ps
```

Aguarde o serviço `db` ficar saudável. Depois:

```powershell
docker compose build app
docker compose run --rm app python -c "from src.database import testar_conexao; print(testar_conexao())"
docker compose run --rm app
```

Ao abrir o terminal do agente, faça uma pergunta da seção [Como usar](#como-usar). Para conferir a importação, use uma conta do banco de demonstração:

```powershell
docker compose exec db mysql -u NOME_DO_USUARIO_DEMO -p pasteis_miyata
```

No MySQL:

```sql
SHOW TABLES;
SELECT COUNT(*) AS total_registros FROM registros_producao;
```

O snapshot de demonstração usado no projeto tinha 3.634 registros de produção. Confirme se o arquivo recebido corresponde ao snapshot esperado antes de comparar números.

Se a conexão falhar, confira `docker compose ps`, as credenciais e os logs:

```powershell
docker compose logs --tail 100 db
```

Digite `sair` para encerrar o agente. `docker compose down` para os serviços e preserva os volumes. Não use `docker compose down -v` como rotina: ele remove os volumes do banco de demonstração e do estado do agente.

Para rodar a suíte dentro do Docker, consulte o [guia de avaliação](docs/evals.md#avaliação-no-docker-de-demonstração). A suíte usa outra conta, somente de leitura.

## Como rodar

Para a instalação local, são necessários Python 3.11 ou superior, Git, MySQL com o banco e as tabelas do projeto e uma chave de API válida para o modelo selecionado.

```powershell
git clone https://github.com/viniciusyy/Agente-de-IA-.git
cd Agente-de-IA-

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

No `.env`, configure a chave, o modelo e a conexão local. Exemplo de estrutura:

```dotenv
OPENAI_API_KEY=
LLM_MODEL=

DB_HOST=localhost
DB_PORT=3306
DB_NAME=pasteis_miyata
DB_USER=
DB_PASSWORD=
```

O código também aceita `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER` e `MYSQL_PASSWORD`. Deixe as opções comentadas para usar os padrões. Se descomentar uma opção numérica, preencha um valor válido. Configure os preços por milhão de tokens somente se quiser estimar o custo do modelo utilizado.

```powershell
.\.venv\Scripts\python.exe -m src.main
```

## Como usar

| Objetivo | Exemplo de solicitação |
|---|---|
| Consultar histórico | `Consulte as últimas cinco operações da feira QUA.` |
| Consultar uma operação | `Consulte a operação 101.` |
| Consultar uma regra | `Qual regra vale para pastel de frango na SAB_E?` |
| Calcular uma recomendação | `Calcule uma recomendação de produção para a feira QUA.` |
| Solicitar o registro, depois de calcular na mesma conversa | `Registre esse plano como o plano semanal aprovado.` |
| Guardar a preferência permitida | `Guarde como preferência permanente a chave prioridade com o valor reduzir sobra.` |
| Encerrar | `sair` |

Para `prioridade`, os valores cadastráveis são `reduzir sobra` e `evitar falta`. Uma declaração genérica ou instrução recuperada do corpus não autoriza a escrita.

### Aprovação humana

O grafo pausa antes de registrar um plano, mostra a proposta e pede:

```text
[A]provar, [R]ejeitar ou [E]ditar?
```

- `A`: aprova o plano apresentado.
- `R`: rejeita o registro.
- `E`: permite alterar apenas o resumo, não as quantidades calculadas.

O checkpoint permite retomar a aprovação com a mesma identidade e a mesma `thread_id`. Uma decisão inválida, rejeitada ou vencida não grava o plano. O prazo padrão é de 24 horas, e a repetição da mesma escrita não cria dois registros.

### Contrato da saída

A resposta contém `status`, `resultado`, `fontes`, `suficiente`, `motivo` e `proxima_acao`. Os status incluem `concluido`, `precisa_informacao`, `recusado`, `aguardando_aprovacao` e `erro`. O resumo da execução também mostra motivo de término, passos, ferramentas, tokens, custo estimado e log.

### Exemplo real da Parte 2

Do [caso oficial de entrada incompleta](logs/04_acao_nao_permitida.json), executado no commit `00bab35`.

Entrada:

```text
Calcule uma recomendação para a próxima feira.
```

Saída:

```json
{
  "status": "precisa_informacao",
  "resultado": null,
  "fontes": [
    {
      "tipo": "sistema",
      "referencia": "src/prompts/orquestrador_v2.md",
      "detalhe": "Contrato e limites do agente."
    }
  ],
  "suficiente": false,
  "motivo": "É necessário informar o código da feira para calcular a recomendação.",
  "proxima_acao": "Informe o código da feira: QUA, QUI, SAB_C, SAB_E, DOM_C ou DOM_E."
}
```

O agente pede a informação, sem escolher uma feira por conta própria. Os [contratos e exemplos completos](docs/io.md) e os [seis casos oficiais](dados/casos_demonstracao_parte2.json) documentam também o caminho feliz, a regra divergente, o registro inexistente, a recusa por falta de conhecimento e a aprovação humana.

## Verificações locais

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_seguranca*.py" -v
.\.venv\Scripts\python.exe -m scripts.verificar_rag
.\.venv\Scripts\python.exe -m scripts.demonstrar_reducer
.\.venv\Scripts\python.exe conferir_grafo.py
```

Na revisão da Parte 3, **105 testes passaram**, incluindo **39 de segurança e integração**. Os testes dos controles usam modelo simulado e estado temporário, sem consultar o MySQL operacional nem a API. Veja as [evidências de segurança](docs/seguranca.md#6-evidências-executadas).

Para regenerar os logs oficiais da Parte 2, use um checkout sem alterações pendentes e um ambiente de execução autorizado. Os resultados históricos já estão em `logs/`.

```powershell
git status
.\.venv\Scripts\python.exe -m scripts.executar_casos_parte2
.\.venv\Scripts\python.exe -m scripts.gerar_io
```

## Avaliação da Parte 3

A suíte executa os 20 casos do [golden dataset](evals/golden_dataset.json) pela mesma fachada `AgentePlanejamento` utilizada pelo terminal. O MySQL é usado somente para leitura; os checkpoints, preferências e planos dos casos usam SQLite temporário.

### Executar a suíte

Na raiz do projeto, com as dependências instaladas, configure a conta `avaliacao_leitura` conforme o [guia de avaliação](docs/evals.md#preparar-e-rodar-a-suíte). Use somente um banco autorizado e compatível com o dataset.

```powershell
$env:EVAL_MYSQL_MODO = 'local'
$env:EVAL_MYSQL_PASSWORD = [System.Net.NetworkCredential]::new(
    '', (Read-Host 'Senha da conta de avaliação' -AsSecureString)
).Password

.\.venv\Scripts\python.exe -m evals.rodar --conferir
```

O pré-teste não chama o modelo. Se ele passar, configure a chave e o modelo no `.env`. Execute a rodada completa **somente se o envio dos dados ao provedor estiver autorizado**:

```powershell
.\.venv\Scripts\python.exe -m evals.rodar --versao minha-versao --confirmar-dados-autorizados
Remove-Item Env:EVAL_MYSQL_PASSWORD -ErrorAction SilentlyContinue
```

A rodada imprime o placar por classe e grava `resultado.json` em uma nova pasta de `evals/resultados/`. Se parar no pré-teste, feche o terminal ou remova a variável da senha.

### Comparar duas rodadas

Este exemplo reproduz a comparação publicada sem MySQL, API ou chave:

```powershell
$antes = 'evals/resultados/baseline-local-20261114T225713610907Z'
$depois = 'evals/resultados/regressao-final-local-20261117T040153159929Z'

.\.venv\Scripts\python.exe -m evals.comparar "$antes" "$depois"
```

O resultado registrado é **16/20 → 20/20 (+20 pontos percentuais)**. Compare apenas rodadas completas, com o mesmo dataset, modo MySQL e snapshot estável. Os critérios e as outras rodadas estão em [Avaliação do agente](docs/evals.md).

## Traces OpenTelemetry

Para gerar uma demonstração sem conectar ao MySQL nem chamar a API:

```powershell
.\.venv\Scripts\python.exe -m scripts.demonstrar_trace
```

O comando imprime o caminho do JSONL em `logs/traces/`. A demonstração faz parte da coorte de teste e não entra no cálculo dos SLOs. Consulte [como ativar, abrir e interpretar os traces](docs/uso_traces.md), o [plano com os resultados](docs/observabilidade.md) e o [extrato sanitizado de uma aprovação](docs/trace-aprovacao.json).

## Documentação

| Documento | Conteúdo |
|---|---|
| [Case](docs/case.md) | Problema, usuário e regras do domínio |
| [Arquitetura](docs/arquitetura.md) e [grafo](docs/grafo.md) | Componentes, estado, nós, autonomia e reducers |
| [Entrada e saída](docs/io.md) e [prompts](docs/prompts.md) | Contratos, exemplos e instruções do modelo |
| [RAG](docs/rag.md) e [memória](docs/memoria.md) | Recuperação, checkpoints e persistência restrita |
| [Supervisão humana](docs/humano.md) | Pausa, retomada, expiração e idempotência |
| [Modelos](docs/modelos.md) e [fontes](docs/fontes.md) | Escolha de modelo e referências consultadas |
| [Avaliação](docs/evals.md) | Dataset, propriedades, níveis de checagem e rodadas |
| [Histórico de mudanças](docs/mudancas.md) | Correções, commits e evidências |
| [Model card](docs/model-card.md) | Autoridade, limitações e reconstrução de uma decisão |
| [Segurança](docs/seguranca.md) | Riscos, controles, testes e auditoria Git |
| [Observabilidade](docs/observabilidade.md) | Plano, métricas, SLOs e limites da amostra |

## Limites e cuidados

O agente apoia a decisão do proprietário. Não compra, não paga, não inicia a produção e não escreve no MySQL operacional. Sobra zero não prova falta de produto. O baseline usa vendas observadas, não estima sozinho a demanda perdida e não produz um plano ótimo.

Não publique `.env`, chaves, senhas, bancos locais, traces brutos nem o banco de demonstração compartilhado separadamente. Use apenas dados autorizados para o processamento no provedor.