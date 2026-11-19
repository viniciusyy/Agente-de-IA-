# Traces locais — Pastéis Miyata

Consulte o [plano de observabilidade](observabilidade.md) para objetivos,
coortes e critérios de medição. O tracing é opcional e usa o SDK OpenTelemetry
para salvar spans em JSONL. Não há coletor remoto. Os logs já utilizados pela
suíte de avaliação continuam funcionando.

## Primeiro teste, sem MySQL nem API

Na raiz do repositório, com o ambiente virtual ativo:

```powershell
python.exe -m pip install -r requirements.txt
python.exe -m unittest discover -s tests -p test_observabilidade.py -v
python.exe -m scripts.demonstrar_trace
```

A demonstração usa a pergunta **“Sobra zero prova que faltou produto?”**,
o corpus versionado e SQLite temporário. O trace contém uma raiz `invoke_agent`
e um span filho `execute_tool buscar_conhecimento`. A resposta usa o documento
`glossario_dados_v1` e retorna `prova_falta=false`, sem chamar o modelo.

O terminal informa o caminho do JSONL em `logs/traces/`. Como a execução
pertence à coorte `teste`, ela não entra nos indicadores do SLO.

## Ativação no PowerShell

Por padrão, o agente não gera traces. Para ativar a exportação no terminal
atual, defina as variáveis abaixo. Use o hash do commit como versão somente
se ele identificar o código que está sendo executado.

```powershell
$env:PASTEIS_TRACE_DIR = Join-Path (Get-Location) 'logs\traces\operacional'
$env:PASTEIS_TRACE_VERSAO = git rev-parse --short HEAD
$env:PASTEIS_TRACE_COORTE = 'operacional'
```

Para a suíte de avaliação, use uma pasta separada dentro de `logs/traces/`
e a coorte `avaliacao`. As variáveis são herdadas pelos subprocessos da
suíte. Elas não alteram o `.env`, o banco MySQL nem as permissões da conta.
Use apenas dados cuja consulta e cujo processamento pelo provedor já foram
autorizados.

Para desativar no terminal atual: `Remove-Item Env:PASTEIS_TRACE_DIR`.
Isso não apaga arquivos existentes. O Git ignora `logs/traces/`; não faça
commit dos JSONLs brutos nem de uma pasta alternativa de exportação.
O acesso e a retenção local são administrados pelo proprietário. A meta
de 30 dias do plano não implica limpeza automática.

## Como ler um trace

```powershell
$arquivo = Get-ChildItem logs\traces -Recurse -Filter 'otel-*.jsonl' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

Get-Content -LiteralPath $arquivo.FullName -Encoding UTF8 |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Select-Object name, parent_id, attributes, events |
    ConvertTo-Json -Depth 10
```

Cada linha do JSONL é um span finalizado. Os filhos podem aparecer antes
da raiz. Use `context.trace_id` para agrupá-los e `parent_id` para conferir
a hierarquia. Um `chat` representa uma chamada lógica ao modelo feita pelo
agente. Tentativas internas do cliente não são contadas como chamadas
adicionais do grafo. Alguns atributos estruturados são strings JSON.

A pausa gera `aprovacao.solicitada`, com prazo e quantidades exibidas.
A retomada abre outro trace e gera `aprovacao.decidida`. Ambos usam o
mesmo identificador, `pasteis.aprovacao.id`, derivado de campos do checkpoint.
A espera pela decisão fica fora da latência do agente. A tentativa de escrita
gera seu próprio span; rejeição humana não é falha do banco.

O trace guarda campos permitidos, identificadores opacos e referências
ao corpus. Não copia prompts, mensagens livres, credenciais, observações
do banco nem linhas completas do MySQL. Custo desconhecido não é registrado
como zero. Chamadas bloqueadas antes da execução não têm span de ferramenta.
Falhas de exportação são sinalizadas sem repetir a operação. Essas lacunas
devem ser consideradas ao conferir a cobertura da coleta.