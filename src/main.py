from __future__ import annotations

import json

from src.agent import AgentePlanejamento
from src.config import settings
from src.database import testar_conexao


def mostrar_resultado(resultado: dict) -> None:
    """
    Apresenta a saída validada e os dados da execução no terminal.
    """
    print("\n" + "=" * 72)
    print("SAÍDA VALIDADA")
    print("=" * 72)

    print(
        json.dumps(
            resultado["saida"],
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n" + "-" * 72)
    print("RESUMO DA EXECUÇÃO")
    print("-" * 72)

    print(
        f"Motivo da parada: "
        f"{resultado['motivo_termino']}"
    )

    print(
        f"Passos: "
        f"{resultado['passos']}"
    )

    print(
        f"Ferramentas: "
        f"{resultado['chamadas_ferramenta']}"
    )

    print(
        f"Tokens de entrada: "
        f"{resultado['tokens_entrada']}"
    )

    print(
        f"Tokens de saída: "
        f"{resultado['tokens_saida']}"
    )

    print(
        "Custo estimado: "
        f"US$ {resultado['custo_estimado_usd']:.8f}"
    )

    print(
        f"Log: {resultado['log']}"
    )


def pedir_decisao(
    pendente: dict,
) -> dict:
    """
    Mostra a ação pendente e solicita uma decisão do proprietário.
    """
    print("\n" + "!" * 72)
    print("APROVAÇÃO HUMANA NECESSÁRIA")
    print("!" * 72)

    print(
        json.dumps(
            pendente,
            ensure_ascii=False,
            indent=2,
        )
    )

    escolha = input(
        "\n[A]provar, [R]ejeitar ou [E]ditar? "
    ).strip().lower()

    if escolha in {
        "a",
        "aprovar",
    }:
        return {
            "acao": "aprovar",
        }

    if escolha in {
        "e",
        "editar",
    }:
        resumo = input(
            "Novo resumo do plano "
            "(Enter mantém o atual): "
        ).strip()

        decisao: dict = {
            "acao": "editar",
        }

        if resumo:
            decisao["resumo_plano"] = resumo

        return decisao

    # Qualquer resposta diferente das opções aceitas é tratada
    # como rejeição segura.
    return {
        "acao": "rejeitar",
    }


def resolver_interrupcao(
    agente: AgentePlanejamento,
    resultado: dict,
) -> dict:
    """
    Resolve interrupções sucessivas, caso o grafo tenha mais de
    um ponto de aprovação.
    """
    while resultado.get("interrupcao"):
        decisao = pedir_decisao(
            resultado["interrupcao"]
        )

        resultado = agente.retomar(
            decisao
        )

        mostrar_resultado(
            resultado
        )

    return resultado


def main() -> None:
    """
    Interface de terminal do agente da Parte 2.
    """
    print("=" * 72)
    print(
        "AGENTE DE PLANEJAMENTO — "
        "PASTÉIS MIYATA — PARTE 2"
    )
    print("=" * 72)

    print(
        "Usuário autorizado: proprietário"
    )

    print(
        f"Usuário técnico: "
        f"{settings.default_user_id}"
    )

    print(
        f"Conversa (thread_id): "
        f"{settings.default_thread_id}"
    )

    print(
        "Entrada: texto livre em português. "
        "Digite 'sair' para encerrar."
    )

    print(
        "As quantidades são calculadas por uma ferramenta "
        "determinística; o modelo interpreta, recupera "
        "conhecimento e orquestra as ferramentas."
    )

    resultado_banco = testar_conexao()

    mensagem_banco = resultado_banco.get(
        "mensagem",
        resultado_banco.get(
            "erro",
            {},
        ).get(
            "mensagem",
            "Não foi possível verificar o MySQL.",
        ),
    )

    print(
        "\n" + mensagem_banco
    )

    agente = AgentePlanejamento()

    # Como o LangGraph utiliza checkpoint, uma aprovação pode
    # continuar pendente mesmo depois de fechar o terminal.
    pendente = (
        agente.obter_aprovacao_pendente()
    )

    if pendente:
        print(
            "\nExiste uma aprovação pendente "
            "nesta conversa."
        )

        decisao = pedir_decisao(
            pendente
        )

        resultado = agente.retomar(
            decisao
        )

        mostrar_resultado(
            resultado
        )

        resolver_interrupcao(
            agente,
            resultado,
        )

    while True:
        texto = input(
            "\nProprietário: "
        ).strip()

        if texto.lower() in {
            "sair",
            "encerrar",
            "fechar",
        }:
            print(
                "Agente encerrado pelo proprietário."
            )
            break

        if not texto:
            print(
                "Digite uma solicitação ou utilize "
                "'sair' para encerrar."
            )
            continue

        try:
            resultado = agente.executar(
                texto
            )

            mostrar_resultado(
                resultado
            )

            resolver_interrupcao(
                agente,
                resultado,
            )

        except KeyboardInterrupt:
            print(
                "\nExecução interrompida "
                "pelo proprietário."
            )
            break

        except Exception as erro:
            print(
                "\nErro não recuperado: "
                f"{type(erro).__name__}: {erro}"
            )


if __name__ == "__main__":
    main()