import json

from src.agent import AgentePlanejamento
from src.database import testar_conexao


def mostrar_resultado(resultado: dict) -> None:
    """
    Mostra a resposta do agente e um resumo técnico da execução.
    """
    print("\n" + "=" * 70)
    print("RESPOSTA DO AGENTE")
    print("=" * 70)
    print(resultado["resposta"])

    print("\n" + "-" * 70)
    print("RESUMO DA EXECUÇÃO")
    print("-" * 70)
    print(f"Motivo da parada: {resultado['motivo_termino']}")
    print(f"Passos executados: {resultado['passos']}")
    print(
        "Ferramentas chamadas: "
        f"{resultado['chamadas_ferramenta']}"
    )
    print(f"Tokens de entrada: {resultado['tokens_entrada']}")
    print(f"Tokens de saída: {resultado['tokens_saida']}")
    print(
        "Custo estimado: US$ "
        f"{resultado['custo_estimado_usd']:.8f}"
    )
    print(f"Log salvo em: {resultado['log']}")
    print("=" * 70)


def verificar_banco() -> bool:
    """
    Testa a conexão antes de iniciar o atendimento.

    Uma falha não encerra obrigatoriamente o programa porque o erro
    do banco também precisa poder ser observado durante os testes.
    """
    print("\nVerificando conexão com o MySQL...")

    resultado = testar_conexao()

    if resultado.get("ok"):
        print(resultado["mensagem"])
        print(f"Banco selecionado: {resultado['banco']}")
        return True

    print("Não foi possível conectar ao MySQL.")
    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
        )
    )

    return False


def main() -> None:
    print("=" * 70)
    print("AGENTE SIMPLES DE PLANEJAMENTO — PASTÉIS MIYATA")
    print("=" * 70)
    print("Usuário autorizado: proprietário")
    print("Digite uma solicitação em linguagem natural.")
    print("Digite 'sair' para encerrar.")
    print()
    print(
        "Aviso: esta versão utiliza uma recomendação mock baseada "
        "na média das vendas recentes."
    )
    print(
        "Ela ainda não executa os modelos de previsão e o Simplex "
        "do TCC."
    )

    verificar_banco()

    try:
        agente = AgentePlanejamento()

    except Exception as erro:
        print("\nNão foi possível iniciar o agente.")
        print(f"Motivo: {erro}")
        return

    while True:
        print()
        solicitacao = input("Proprietário: ").strip()

        if solicitacao.lower() in {
            "sair",
            "encerrar",
            "fechar",
        }:
            print("\nAgente encerrado pelo proprietário.")
            break

        if not solicitacao:
            print(
                "Digite uma solicitação ou utilize 'sair' "
                "para encerrar."
            )
            continue

        try:
            resultado = agente.executar(solicitacao)
            mostrar_resultado(resultado)

        except KeyboardInterrupt:
            print("\n\nExecução interrompida pelo proprietário.")
            break

        except Exception as erro:
            print("\nOcorreu um erro inesperado.")
            print(f"Tipo: {type(erro).__name__}")
            print(f"Detalhes: {erro}")
            print(
                "A solicitação não foi concluída. "
                "Verifique a configuração e tente novamente."
            )


if __name__ == "__main__":
    main()