---
id: processo_planejamento_v1
titulo: Processo de planejamento e aprovação
versao: 1
status: vigente
vigente_desde: 2026-09-01
mantenedor: proprietário
---

# Processo de planejamento

O proprietário inicia a conversa em texto livre.

Para calcular uma recomendação, o sistema precisa identificar a feira.

As seguintes informações refinam o cenário:

- data da venda;
- clima;
- feriado;
- evento;
- capacidade;
- limitações de ingredientes.

A versão atual pode produzir um baseline quando somente a feira está disponível, desde que declare as limitações.

O LLM interpreta a solicitação e escolhe ferramentas.

O MySQL fornece os registros.

Uma ferramenta determinística calcula as quantidades.

O LLM não pode alterar os números retornados nem considerar um plano aprovado por conta própria.

## Aprovação

Somente o proprietário pode aprovar o registro de um plano.

A pausa deve mostrar:

- feira;
- total recomendado;
- resumo;
- quantidades;
- consequência da escrita.

O proprietário pode:

- aprovar;
- rejeitar;
- aprovar editando o resumo.

Sem resposta em 24 horas, a aprovação expira e nenhuma escrita deve ocorrer.