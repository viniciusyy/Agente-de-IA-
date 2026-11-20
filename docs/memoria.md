# Memória do agente

## Curto e longo prazo

| Componente | Conteúdo | Persistência |
|---|---|---|
| Curto prazo | Mensagens, estado do grafo, fontes, contadores, ferramentas e aprovação pendente da conversa | Checkpoint em `dados/checkpoints.sqlite3`, pelo `SqliteSaver` |
| Memória semântica | Preferência autorizada na chave `prioridade` | Versões em `dados/memoria.sqlite3` |
| Memória episódica | Metadados estruturados de planos verificáveis calculados no turno | Episódios em `dados/memoria.sqlite3` |
| Memória procedural | Procedimento versionado de consulta, cálculo e aprovação | [`src/prompts/procedimento_planejamento_v1.md`](../src/prompts/procedimento_planejamento_v1.md) |
| RAG | Regras e definições curadas, recuperadas como fonte, não como autorização | [`dados/corpus/`](../dados/corpus/) |

O MySQL é fonte dos dados operacionais. Não é memória conversacional e não recebe registros de aprovação, preferências ou episódios.

## Política de escrita

### Preferência semântica

[`salvar_fato_semantico`](../src/memory.py#L140) aceita apenas a chave `prioridade` com valor `reduzir sobra` ou `evitar falta`. A [autorização](../src/seguranca.py#L342) exige que a solicitação do próprio usuário no turno autorize explicitamente o valor. Uma instrução de documento recuperado não é autorização.

Exemplo:

```text
Guarde como preferência permanente a chave prioridade com o valor reduzir sobra.
```

Uma mudança autorizada de valor cria nova versão. A [leitura](../src/memory.py#L221) usa a versão válida mais recente sem apagar a anterior. A escrita repetida pode informar `ja_existia`. O hash de conteúdo serve à consistência e à idempotência, não à autenticação do autor.

### Episódio

[`memorizar_episodio`](../src/graph.py#L1019) grava no máximo um episódio se a saída for conclusiva e suficiente e houver um plano verificável calculado naquele turno. O episódio contém:

- tipo;
- feira;
- total recomendado;
- quantidade de operações consideradas, quando disponível.

Consultas, recusas e confirmações sem novo cálculo não geram episódio. [`salvar_episodio`](../src/memory.py#L266) valida o conteúdo antes da escrita. Registros legados incompatíveis são excluídos da recuperação, sem remoção automática dos arquivos.

## Recuperação e esquecimento

A memória episódica recupera até três episódios válidos por relevância. A pontuação usa decaimento com meia-vida padrão de 90 dias. Reduzir a relevância não apaga registros.

A janela de conversa usa, por padrão, até seis turnos completos. O grafo prioriza o procedimento, o objetivo atual e os retornos do turno. Quando precisa reduzir o contexto, descarta mensagens e retornos antigos e episódios de menor relevância. O que sai da janela enviada ao modelo não é necessariamente removido do checkpoint.

As conversas usam `thread_id`. O padrão é `proprietario-principal`; para abrir uma conversa distinta, configure `AGENT_THREAD_ID`. Conversas diferentes não reutilizam o checkpoint, mas podem recuperar memória de longo prazo da mesma identidade técnica autorizada.

## Aprovação humana e idempotência

O checkpoint preserva a proposta, os argumentos e o ponto de interrupção. Ao reiniciar com a mesma identidade e a mesma thread, o agente consegue apresentar a aprovação pendente. A pausa não grava o plano. Somente uma aprovação ou edição válida, dentro do prazo, permite gravá-lo na tabela de planos aprovados. Essa tabela é distinta da memória episódica.

A chave de idempotência deriva do SHA-256 do conteúdo canônico do plano. Repetir o mesmo registro retorna `ja_existia=true` em vez de inserir outro plano. Veja [a supervisão humana](humano.md) e [a decisão reconstruída](model-card.md#11-registro-e-retenção).

## O que não entra na memória

A memória semântica e a episódica não aceitam mensagens livres, respostas livres, nomes de produtos, tags arbitrárias, instruções externas nem credenciais como campos de memória. As escritas e as leituras aplicam os contratos previstos no código.

Logs, checkpoints e resumos de planos são armazenamentos distintos e podem conter campos livres. O agente não exige cadastro de clientes, mas o texto livre pode conter dados pessoais. Não há rotina de eliminação por titular nem prazo automático para esses armazenamentos. Consulte os [fluxos e prazos em Segurança](seguranca.md#fluxos-e-retenção).

## Evidência de teste

Os testes verificam versionamento, preferência não autorizada, episódios incompatíveis na gravação e na leitura, retomada e idempotência do plano. Eles usam SQLite temporário e não alteram o MySQL operacional.

```powershell
python.exe -m unittest discover -s tests -p "test_seguranca*.py" -v
python.exe -m unittest discover -s tests -p "test_aprovacao_grafo.py" -v
```

Veja os [resultados dos testes](seguranca.md#6-evidências-executadas).