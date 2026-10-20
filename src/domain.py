from __future__ import annotations

from typing import Any

from src.database import consultar_historico


FEIRAS_VALIDAS = {
    "QUA",
    "QUI",
    "SAB_C",
    "SAB_E",
    "DOM_C",
    "DOM_E",
}

FEIRAS_COM_RESTRICAO = {
    "SAB_E",
    "DOM_E",
}

PRODUTOS_PROIBIDOS_FEIRAS_E = {
    5,
    15,
}


def resumir_historico(
    resultado: dict,
) -> dict:
    if not resultado.get("ok"):
        return resultado

    operacoes: dict[int, dict[str, Any]] = {}

    for registro in resultado["dados"]:
        id_operacao = int(
            registro["id_operacao"]
        )

        operacao = operacoes.setdefault(
            id_operacao,
            {
                "id_operacao": id_operacao,
                "feira": registro["feira"],
                "data_producao": (
                    registro["data_producao"]
                ),
                "data_venda": (
                    registro["data_venda"]
                ),
                "eh_feriado": bool(
                    registro.get(
                        "eh_feriado",
                        False,
                    )
                ),
                "nome_feriado": registro.get(
                    "nome_feriado"
                ),
                "total_produzido": 0,
                "total_vendido": 0,
                "total_sobra": 0,
                "produtos_com_sobra": [],
            },
        )

        produzida = int(
            registro["quantidade_produzida"]
        )

        sobra = int(
            registro["quantidade_sobra"]
        )

        vendida = registro.get(
            "quantidade_vendida"
        )

        if vendida is None:
            vendida = produzida - sobra
        else:
            vendida = int(vendida)

        operacao["total_produzido"] += produzida
        operacao["total_vendido"] += vendida
        operacao["total_sobra"] += sobra

        if sobra > 0:
            operacao[
                "produtos_com_sobra"
            ].append(
                {
                    "produto": registro["produto"],
                    "quantidade_sobra": sobra,
                }
            )

    consolidadas = []

    for operacao in operacoes.values():
        maiores = sorted(
            operacao.pop(
                "produtos_com_sobra"
            ),
            key=lambda item: (
                item["quantidade_sobra"]
            ),
            reverse=True,
        )[:5]

        operacao[
            "produtos_com_maior_sobra"
        ] = maiores

        consolidadas.append(operacao)

    consolidadas.sort(
        key=lambda item: (
            item["data_venda"] or "",
            item["id_operacao"],
        ),
        reverse=True,
    )

    return {
        "ok": True,
        "fonte": resultado["fonte"],
        "feira": resultado["feira"],
        "quantidade_operacoes": len(
            consolidadas
        ),
        "operacoes": consolidadas,
        "observacao": (
            "Dados por produto consolidados; "
            "foram mantidos os totais e os "
            "cinco produtos com maior sobra "
            "por operação."
        ),
    }


def calcular_recomendacao(
    codigo_feira: str,
) -> dict:
    """
    Baseline operacional determinístico.

    A recomendação utiliza a média das vendas
    das cinco operações mais recentes.
    """

    codigo = codigo_feira.strip().upper()

    historico = consultar_historico(
        codigo,
        limite_operacoes=5,
    )

    if not historico.get("ok"):
        return historico

    produtos: dict[int, dict[str, Any]] = {}
    ids_operacoes: set[int] = set()

    for registro in historico["dados"]:
        id_operacao = int(
            registro["id_operacao"]
        )

        id_produto = int(
            registro["id_produto"]
        )

        nome_produto = str(
            registro["produto"]
        ).strip()

        ids_operacoes.add(id_operacao)

        if (
            codigo in FEIRAS_COM_RESTRICAO
            and id_produto
            in PRODUTOS_PROIBIDOS_FEIRAS_E
        ):
            continue

        # Produto descontinuado.
        # A validação fica em código, não no LLM.
        if nome_produto.casefold() in {
            "banana",
            "banana simples",
        }:
            continue

        item = produtos.setdefault(
            id_produto,
            {
                "id_produto": id_produto,
                "produto": nome_produto,
                "total_vendido": 0.0,
                "quantidade_registros": 0,
            },
        )

        vendida = registro.get(
            "quantidade_vendida"
        )

        if vendida is None:
            vendida = (
                int(
                    registro[
                        "quantidade_produzida"
                    ]
                )
                - int(
                    registro[
                        "quantidade_sobra"
                    ]
                )
            )

        item["total_vendido"] += float(
            vendida
        )

        item[
            "quantidade_registros"
        ] += 1

    recomendacoes = []

    for produto in produtos.values():
        media = (
            produto["total_vendido"]
            / produto["quantidade_registros"]
        )

        recomendacoes.append(
            {
                "id_produto": (
                    produto["id_produto"]
                ),
                "produto": produto["produto"],
                "demanda_media": round(
                    media,
                    2,
                ),
                "quantidade_recomendada": round(
                    media
                ),
            }
        )

    recomendacoes.sort(
        key=lambda item: item["id_produto"]
    )

    total = sum(
        item["quantidade_recomendada"]
        for item in recomendacoes
    )

    return {
        "ok": True,
        "fonte": historico["fonte"],
        "metodo": (
            "baseline_media_vendas_5_operacoes"
        ),
        "feira": codigo,
        "operacoes_consideradas": len(
            ids_operacoes
        ),
        "recomendacoes": recomendacoes,
        "total_recomendado": total,
        "regras_aplicadas": {
            "produtos_excluidos": (
                sorted(
                    PRODUTOS_PROIBIDOS_FEIRAS_E
                )
                if codigo
                in FEIRAS_COM_RESTRICAO
                else []
            ),
            "produtos_descontinuados_excluidos": [
                "Banana simples"
            ],
        },
        "aviso": (
            "Este baseline é verificável e não "
            "é a previsão definitiva do TCC. "
            "O LLM não calculou as quantidades."
        ),
    }