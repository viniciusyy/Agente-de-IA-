"""
Imprime a topologia do mesmo grafo utilizado pelo agente.

Este arquivo permite conferir os nós e as arestas sem fazer
uma chamada ao modelo de linguagem.
"""

from src.graph import grafo


def main() -> None:
    desenho = grafo.get_graph()

    print("=" * 72)
    print("NÓS DO GRAFO")
    print("=" * 72)

    for nome in sorted(desenho.nodes):
        print(f"- {nome}")

    print("\n" + "=" * 72)
    print("ARESTAS DO GRAFO")
    print("=" * 72)

    for aresta in desenho.edges:
        tipo = (
            "condicional"
            if getattr(
                aresta,
                "conditional",
                False,
            )
            else "direta"
        )

        print(
            f"- {aresta.source} "
            f"-> {aresta.target} "
            f"[{tipo}]"
        )


if __name__ == "__main__":
    main()