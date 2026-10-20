---
id: glossario_dados_v1
titulo: Glossário e significado dos dados
versao: 1
status: vigente
vigente_desde: 2026-09-01
mantenedor: proprietário
---

# Glossário operacional

`quantidade_produzida` é o número preparado para uma operação.

`quantidade_sobra` é o que retornou sem ser vendido.

`quantidade_vendida` é calculada por:

`quantidade_produzida - quantidade_sobra`

Uma sobra igual a zero não prova falta de produto nem perda de venda.

Ela pode representar:

- venda exata de toda a quantidade;
- produto encerrado antes do final da feira.

Como o banco não registra o horário em que cada sabor termina, o sistema não chama automaticamente esse caso de ruptura e não promete medir vendas perdidas.

Os climas aceitos são:

- Sol;
- Frio;
- Garoa;
- Chuva Moderada;
- Chuva Forte.

Feriado e nome do feriado pertencem à operação, não ao cadastro do produto.