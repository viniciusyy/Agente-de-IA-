# RAG — memória consultável do domínio

## Decisão de recuperação

O agente utiliza duas formas de recuperação, escolhidas conforme a natureza da informação:

| Forma | Fonte | O que responde |
|---|---|---|
| Consulta estruturada | MySQL, pelas ferramentas `consultar_historico` e `consultar_operacao` | Datas, quantidades, produção, sobra, venda, feira e identificadores |
| Busca textual | Índice lexical em memória implementado em `src/rag.py` | Regras das feiras, vocabulário, exceções, aprovação, produtos descontinuados e limites do agente |

Os registros operacionais continuam no MySQL porque possuem estrutura, campos, datas e identificadores exatos. Perguntas como “Consulte a operação 101” não devem ser respondidas por similaridade textual.

Os documentos do domínio são recuperados pelo índice textual porque representam regras e explicações escritas em linguagem natural.

## Por que não utilizar embeddings nesta versão

A busca vetorial não foi escolhida porque o corpus atual possui apenas seis documentos temáticos curtos:

- cinco documentos vigentes;
- um documento revogado utilizado como teste.

Além disso, o vocabulário do domínio é controlado e utiliza termos específicos, como:

- `QUA`;
- `SAB_E`;
- `DOM_E`;
- `Frango`;
- `sobra`;
- `aprovação`;
- `proprietário`.

Nesse cenário, um índice lexical simples é suficiente, verificável e barato. Uma solução com embeddings adicionaria:

- custo de geração dos vetores;
- dependência de um modelo de embedding;
- necessidade de armazenamento vetorial;
- mais parâmetros de recuperação;
- maior dificuldade de inspeção.

A adoção de embeddings poderá ser reconsiderada caso o corpus aumente significativamente ou passe a conter documentos longos com vocabulário menos previsível.

## Classificação das perguntas de avaliação

| # | Pergunta | Forma de recuperação | Resultado esperado |
|---:|---|---|---|
| 1 | Quais são os códigos de feira? | Busca textual | `regras_feiras_v2` |
| 2 | Quando é produzida a feira QUA? | Busca textual | `regras_feiras_v2` |
| 3 | SAB_C e SAB_E são a mesma feira? | Busca textual | `regras_feiras_v2` |
| 4 | Pode vender pastel de Frango na SAB_E? | Busca textual | `regras_feiras_v2` |
| 5 | Escarola sem bacon é permitida na DOM_E? | Busca textual | `regras_feiras_v2` |
| 6 | Como é calculada a quantidade vendida? | Busca textual | `glossario_dados_v1` |
| 7 | Sobra zero prova que faltou produto? | Busca textual | `glossario_dados_v1` |
| 8 | Quem pode aprovar o registro de um plano? | Busca textual | `processo_planejamento_v1` |
| 9 | O pastel de banana simples está ativo? | Busca textual | `produtos_status_v1` |
| 10 | Qual é o fornecedor da massa? | Busca seguida de recusa | Não está no corpus |

A décima pergunta verifica a capacidade de recusa. O resultado correto não é encontrar algum documento semelhante, mas reconhecer que o corpus não sustenta a resposta.

## Corpus do case

| Arquivo | Identificador | Dono | Frequência de mudança | Status |
|---|---|---|---|---|
| `01_regras_feiras.md` | `regras_feiras_v2` | Proprietário | Quando uma feira ou regra muda | Vigente |
| `02_glossario_dados.md` | `glossario_dados_v1` | Proprietário e responsável técnico | Quando o significado de um dado muda | Vigente |
| `03_processo_planejamento.md` | `processo_planejamento_v1` | Proprietário | Quando o processo de aprovação muda | Vigente |
| `04_produtos_status.md` | `produtos_status_v1` | Proprietário | Quando um produto entra, sai ou retorna | Vigente |
| `05_limites_sistema.md` | `limites_sistema_v1` | Responsável técnico | A cada mudança funcional | Vigente |
| `99_regras_feiras_revogado.md` | `regras_feiras_v1_revogado` | Proprietário | Preservado somente como teste | Revogado |

O corpus está armazenado em:

```text
dados/corpus/
```

Ele é privado porque contém regras internas da Pastéis Miyata e específico porque descreve exceções que não fazem parte do conhecimento geral de um modelo de linguagem.

O índice é reconstruído quando o processo é iniciado. Portanto, uma alteração versionada nos documentos entra na próxima execução do agente.

## Estratégia de corte

Não foi aplicado corte por quantidade fixa de caracteres.

Cada arquivo representa uma unidade temática natural:

- regras das feiras;
- glossário dos dados;
- processo de planejamento;
- estado dos produtos;
- limites do sistema;
- regra antiga revogada.

Cada documento faz sentido isoladamente e possui título, identificador, versão e status. Dividir esses arquivos em fragmentos menores reduziria o contexto disponível e poderia separar uma regra de sua exceção.

A unidade recuperada é, portanto, o documento temático completo.

Essa decisão deverá ser revista se os documentos crescerem a ponto de misturar vários assuntos independentes. Nesse caso, o corte deverá acontecer por seção ou regra, preservando o cabeçalho em cada fragmento.

## Metadados

Cada documento contém metadados no cabeçalho:

```yaml
---
id: regras_feiras_v2
titulo: Regras vigentes das feiras
versao: 2
status: vigente
vigente_desde: 2026-09-01
mantenedor: proprietário
---
```

Os principais campos são:

| Metadado | Função |
|---|---|
| `id` | Identifica o documento de forma estável |
| `titulo` | Ajuda na busca e na apresentação da fonte |
| `versao` | Permite rastrear mudanças |
| `status` | Separa documentos vigentes de documentos revogados |
| `vigente_desde` | Informa quando a regra passou a valer |
| `mantenedor` | Identifica quem responde pela informação |

A busca normal remove documentos com `status=revogado` antes do ranqueamento.

## Funcionamento do índice

O índice executa as seguintes etapas:

1. carrega os documentos Markdown;
2. separa os metadados do corpo;
3. normaliza letras maiúsculas, minúsculas e acentos;
4. remove sinais e palavras muito comuns;
5. aplica expansões controladas do vocabulário;
6. calcula a relevância lexical;
7. ordena os documentos;
8. remove revogados;
9. devolve até `RAG_MAX_RESULTS` documentos;
10. aplica o portão de suficiência.

O título também é incluído no conteúdo indexado. Isso permite que termos importantes presentes no título participem da recuperação.

## Expansões controladas

O vocabulário contém expansões explícitas para termos conhecidos do domínio.

Exemplos:

```python
"quarta": {"qua"}
"quinta": {"qui"}
"sabado": {"sab_c", "sab_e"}
"domingo": {"dom_c", "dom_e"}
"feira": {"feiras"}
"feiras": {"feira"}
"codigo": {"codigos"}
"codigos": {"codigo"}
```

As expansões não substituem a regra original. Elas somente melhoram o encontro entre formas equivalentes utilizadas na pergunta e no documento.

## Limite e portão de suficiência

A busca devolve no máximo:

```text
RAG_MAX_RESULTS=3
```

Esse valor limita o contexto enviado ao modelo. Ele não representa quantidade de vizinhos de um banco vetorial, pois esta versão não utiliza embeddings.

O limiar mínimo é:

```text
RAG_MIN_SCORE=0.001
```

Quando nenhum documento atinge o limiar, o resultado possui:

```json
{
  "suficiente": false,
  "resultados": [],
  "motivo": "Nenhum documento vigente sustenta a resposta."
}
```

O modelo deve recusar a resposta ou explicar qual informação está faltando.

## Documento revogado

O arquivo `99_regras_feiras_revogado.md` contém uma regra antiga segundo a qual todas as feiras vendiam todos os sabores.

Essa regra está incorreta e foi preservada apenas para provar que o filtro de vigência funciona.

Na busca normal, o resultado foi:

```text
regras_feiras_v2      vigente      score 0.303798
glossario_dados_v1    vigente      score 0.062709
```

Com a inclusão proposital de documentos revogados, o resultado foi:

```text
regras_feiras_v2             vigente    score 0.271631
regras_feiras_v1_revogado    revogado   score 0.176758
glossario_dados_v1           vigente    score 0.057764
```

Isso demonstra que o documento antigo ainda possui similaridade com a pergunta. A proteção correta é a curadoria pelo campo `status`, não uma tentativa de corrigir o resultado apenas pelo prompt.

## Medição e evolução

A primeira execução do conjunto de avaliação obteve:

```text
9 acertos em 10 perguntas
Taxa de acerto: 90%
```

A pergunta com falha foi:

```text
Quais são os códigos de feira?
```

O índice recuperou incorretamente `produtos_status_v1`. A análise mostrou dois problemas:

1. formas no singular e no plural não estavam sendo aproximadas;
2. o título do documento não participava da indexação.

Foram realizadas duas correções:

- normalização controlada entre `feira` e `feiras`, e entre `codigo` e `codigos`;
- inclusão do título no texto indexado.

Depois da correção, uma nova execução obteve:

```text
10 acertos em 10 perguntas
Taxa de acerto: 100%
```

O comando utilizado foi:

```powershell
python.exe -m scripts.verificar_rag
```

O resultado inclui:

- recuperação correta das nove perguntas respondíveis;
- recusa correta da pergunta fora do corpus;
- exclusão do documento revogado na recuperação normal.

A medição representa apenas o conjunto controlado atual. Ela não prova desempenho perfeito diante de qualquer pergunta futura.

## Integração ao laço do agente

`buscar_conhecimento` é uma ferramenta disponível dentro do grafo. A recuperação não acontece como um pipeline separado.

O modelo chama essa ferramenta quando a decisão depende de:

- regra;
- vocabulário;
- exceção;
- processo de aprovação;
- status de produto;
- limite do sistema.

Consultas estruturadas ao MySQL e entradas claramente incompletas podem terminar sem chamada ao RAG.

A trajetória registra:

- nome da ferramenta;
- argumentos;
- resultado;
- erro;
- fontes recuperadas.

Dessa forma, é possível verificar por que um documento participou de uma resposta.