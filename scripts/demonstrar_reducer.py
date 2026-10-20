"""
Demonstra por que campos acumulados do estado precisam
de um reducer quando dois nós escrevem simultaneamente.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)


class EstadoSemReducer(TypedDict):
    resultados: list[str]


class EstadoComReducer(TypedDict):
    resultados: Annotated[
        list[str],
        operator.add,
    ]


def ramo_a(_: dict) -> dict:
    return {
        "resultados": ["A"],
    }


def ramo_b(_: dict) -> dict:
    return {
        "resultados": ["B"],
    }


def montar_grafo(schema):
    construtor = StateGraph(schema)

    construtor.add_node(
        "ramo_a",
        ramo_a,
    )

    construtor.add_node(
        "ramo_b",
        ramo_b,
    )

    construtor.add_edge(
        START,
        "ramo_a",
    )

    construtor.add_edge(
        START,
        "ramo_b",
    )

    construtor.add_edge(
        "ramo_a",
        END,
    )

    construtor.add_edge(
        "ramo_b",
        END,
    )

    return construtor.compile()


def main() -> None:
    print("=" * 72)
    print("EXECUÇÃO SEM REDUCER")
    print("=" * 72)

    try:
        grafo_sem_reducer = montar_grafo(
            EstadoSemReducer
        )

        resultado = grafo_sem_reducer.invoke(
            {
                "resultados": [],
            }
        )

        print(resultado)

    except Exception as erro:
        print(
            f"{type(erro).__name__}: {erro}"
        )

    print("\n" + "=" * 72)
    print("EXECUÇÃO COM REDUCER")
    print("=" * 72)

    grafo_com_reducer = montar_grafo(
        EstadoComReducer
    )

    resultado = grafo_com_reducer.invoke(
        {
            "resultados": [],
        }
    )

    print(resultado)


if __name__ == "__main__":
    main()