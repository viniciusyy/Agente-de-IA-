# Avaliação do agente 

A suíte verifica o agente de planejamento da Pastéis Miyata.

## Dataset e execução

O [golden dataset v1.0.0](../evals/golden_dataset.json) contém 20 casos com entrada, critérios esperados, origem, classe e motivo da escolha (`por_que_existe`). São 8 casos de desenvolvimento e 12 sintéticos, cuja revisão pelo propietário está registrada no dataset. Os seis casos da Parte 2 correspondem a GD01–GD06. Pedidos fora do corpus ou da autoridade do agente também são avaliados, como GD05 e GD20.

O terminal (`src.main`) e a suíte (`evals.rodar`) chamam a mesma fachada `AgentePlanejamento`, sem substituir o grafo por um simulador. Cada caso recebe thread, checkpoint e memória SQLite temporários. Etapas do mesmo caso compartilham esse estado. A referência numérica é calculada separadamente com consultas de leitura ao MySQL, e a assinatura dos dados é conferida antes e depois da rodada.

## Propriedades e níveis de checagem

| Propriedade | Nível | Como se confere | Por que um nível mais barato não resolve |
|---|---|---|---|
| Contrato de saída, conclusão ou recusa esperada | Determinístico | Validação de `SaidaAgente` e dos campos esperados por etapa | Os tipos e campos já são verificáveis diretamente. |
| Totais, histórico, quantidades e restrições | Determinístico | Comparação com referências de `referencias_mysql.py` e critérios do caso | A redação da resposta não comprova a correção numérica. |
| Ferramenta, argumentos, ordem e fonte recuperada | Trajetória | Verificação das chamadas registradas; GD02 verifica a consulta da regra antes de eventual recomendação | A saída final não prova que a fonte foi consultada nem que uma ação foi evitada. |
| Aprovação, rejeição e repetição sem duplicidade | Resultado | GD06, GD18 e GD19 conferem pausa, estado antes/depois, conteúdo registrado e idempotência, conforme o caso | A resposta ou tentativa de escrita não comprova seu efeito no SQLite. |
| Preferência autorizada persistida e preferência temporária não persistida | Resultado | GD12 e GD17 comparam o estado; GD12 verifica também chave e valor | A trajetória não comprova o conteúdo efetivamente guardado. |
| Justificativa sustentada pela evidência | Juiz LLM, separado da suíte automática | [Rubrica binária v1.0.0](../evals/rubrica_justificativa_v1.md), saída estruturada e exemplos SIM/NAO | Uma referência válida ou um estado correto não comprovam que a interpretação em texto livre decorre da evidência. |

As checagens automáticas estão em [`evals/verificadores.py`](../evals/verificadores.py). Um caso só é aprovado quando suas etapas passam. Os resultados desta página são do verificador automático. A rubrica separada estabelece pelo menos 90% de concordância e no máximo um falso positivo em relação à revisão humana; esses critérios não são taxas medidas nas rodadas abaixo.

## Preparar e rodar a suíte

Use os [comandos do README](../README.md#avaliação-da-parte-3). O pré-teste `--conferir` verifica a conta e a compatibilidade do banco, sem chamar o modelo. A rodada completa também requer modelo e API configurados. Confirme o envio somente se os dados estiverem autorizados para processamento no provedor.

A suíte espera a conta MySQL dedicada `avaliacao_leitura` no banco `pasteis_miyata`: `@127.0.0.1` no modo local e `@%` no modo Docker. O administrador deve conceder somente `SELECT`, individualmente, sobre `feiras`, `operacoes`, `produtos` e `registros_producao`. A conferência aceita `USAGE` e esses quatro `SELECT`, sem outros privilégios. A conta padrão do agente não substitui a conta de avaliação.

As rodadas versionadas usaram o modo local. A comparação de arquivos já gerados não precisa de MySQL nem de API.

### Avaliação no Docker de demonstração

No [ambiente Docker](../README.md#como-executar-o-projeto-com-docker), a conta de leitura precisa ser provisionada separadamente no banco de demonstração. O Compose não a cria. Não use a conta operacional nem a conta root para rodar a suíte.

No PowerShell, na raiz:

```powershell
$env:EVAL_MYSQL_PASSWORD = [System.Net.NetworkCredential]::new(
    '', (Read-Host 'Senha da conta de avaliação no Docker' -AsSecureString)
).Password

$pastaResultados = (Resolve-Path -LiteralPath 'evals/resultados').Path

docker compose run --rm -e EVAL_MYSQL_MODO=docker -e EVAL_MYSQL_PASSWORD --volume "${pastaResultados}:/app/evals/resultados" app python -m evals.rodar --conferir
```

Se o pré-teste passar e o processamento dos dados estiver autorizado:

```powershell
docker compose run --rm -e EVAL_MYSQL_MODO=docker -e EVAL_MYSQL_PASSWORD --volume "${pastaResultados}:/app/evals/resultados" app python -m evals.rodar --versao minha-versao-docker --confirmar-dados-autorizados

Remove-Item Env:EVAL_MYSQL_PASSWORD -ErrorAction SilentlyContinue
```

A montagem preserva os resultados no computador mesmo após remover o contêiner. O comparador não mistura os modos local e Docker. Se encerrar após a conferência, feche o terminal ou remova a variável de senha.

## Rodadas e comparação

As rodadas abaixo usaram o dataset `1.0.0`, o modelo registrado `gpt-5.6-luna` e o snapshot de prefixo `c7f695afd8f7` (138 operações e 3.634 registros). A coluna Código é o prefixo do SHA-256 da versão executada, não um hash de commit Git.

| Rodada publicada | Código | Aprovados |
|---|---|---:|
| [Baseline](../evals/resultados/baseline-local-20261114T225713610907Z/resultado.json) | `4272072f85e6` | 16/20 (80%) |
| [Regressão após correções](../evals/resultados/regressao-final-local-20261117T040153159929Z/resultado.json) | `86f313e4cae4` | 20/20 (100%) |
| [Segurança v1](../evals/resultados/seguranca-v1-local-20261118T165538902292Z/resultado.json) | `a5a28b0960cf` | 20/20 (100%) |
| [Observabilidade — rodada 1](../evals/resultados/obs-v1-9393b1db60fb-20261119T005315581767Z/resultado.json) | `9393b1db60fb` | 20/20 (100%) |
| [Observabilidade — rodada 2](../evals/resultados/obs-v1-9393b1db60fb-20261119T005640561234Z/resultado.json) | `9393b1db60fb` | 20/20 (100%) |

O [relatório baseline × regressão](../evals/resultados/comparacao-baseline-final.json) compara as duas versões e registra a melhora em [GD02, GD10, GD14 e GD19](mudancas.md#correções-verificadas).

| Classe | Baseline | Regressão | Diferença |
|---|---:|---:|---:|
| Conhecimento | 2/3 | 3/3 | +33,33 p.p. |
| Esclarecimento | 3/3 | 3/3 | 0 p.p. |
| Governança | 3/4 | 4/4 | +25 p.p. |
| Histórico | 4/4 | 4/4 | 0 p.p. |
| Memória | 2/2 | 2/2 | 0 p.p. |
| Planejamento | 2/4 | 4/4 | +50 p.p. |
| **Total** | **16/20** | **20/20** | **+20 p.p.** |

O [relatório regressão × segurança](../evals/resultados/comparacao-regressao-seguranca-v1.json) compara o agente antes e depois do catálogo restrito, da memória mínima e da aprovação reforçada. Ambas as versões obtiveram 20/20, sem regressão observada nesses casos.

As duas rodadas de observabilidade repetiram os mesmos 20 casos na mesma versão. Não são 40 cenários distintos. `evals.comparar` rejeita rodadas parciais, snapshots instáveis e diferenças de dataset, modo MySQL ou snapshot. Os resultados descrevem essas execuções; não garantem desempenho em produção nem medem toda a variabilidade do modelo.