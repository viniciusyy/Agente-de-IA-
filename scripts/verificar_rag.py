"""
Avalia as dez perguntas conhecidas do corpus e verifica
o comportamento do filtro de documentos revogados.
"""

import json

from src.rag import obter_indice


CASOS = [
    {
        "pergunta": (
            "Quais são os códigos de feira?"
        ),
        "documento_esperado": (
            "regras_feiras_v2"
        ),
        "tipo": "regra",
    },
    {
        "pergunta": (
            "Quando é produzida a feira QUA?"
        ),
        "documento_esperado": (
            "regras_feiras_v2"
        ),
        "tipo": "regra",
    },
    {
        "pergunta": (
            "SAB_C e SAB_E são a mesma feira?"
        ),
        "documento_esperado": (
            "regras_feiras_v2"
        ),
        "tipo": "excecao",
    },
    {
        "pergunta": (
            "Pode vender pastel de Frango na SAB_E?"
        ),
        "documento_esperado": (
            "regras_feiras_v2"
        ),
        "tipo": "excecao",
    },
    {
        "pergunta": (
            "Escarola sem bacon é permitida na DOM_E?"
        ),
        "documento_esperado": (
            "regras_feiras_v2"
        ),
        "tipo": "excecao",
    },
    {
        "pergunta": (
            "Como é calculada a quantidade vendida?"
        ),
        "documento_esperado": (
            "glossario_dados_v1"
        ),
        "tipo": "glossario",
    },
    {
        "pergunta": (
            "Sobra zero prova que faltou produto?"
        ),
        "documento_esperado": (
            "glossario_dados_v1"
        ),
        "tipo": "interpretacao",
    },
    {
        "pergunta": (
            "Quem pode aprovar o registro de um plano?"
        ),
        "documento_esperado": (
            "processo_planejamento_v1"
        ),
        "tipo": "processo",
    },
    {
        "pergunta": (
            "O pastel de banana simples está ativo?"
        ),
        "documento_esperado": (
            "produtos_status_v1"
        ),
        "tipo": "produto",
    },
    {
        "pergunta": (
            "Qual é o fornecedor da massa?"
        ),
        "documento_esperado": None,
        "tipo": "fora_do_corpus",
    },
]


def executar_casos() -> dict:
    indice = obter_indice(
        recarregar=True
    )

    resultados = []
    acertos = 0

    for caso in CASOS:
        pergunta = caso["pergunta"]
        esperado = caso[
            "documento_esperado"
        ]

        resposta = indice.buscar(
            pergunta
        )

        primeiro_documento = (
            resposta.resultados[0].documento_id
            if resposta.resultados
            else None
        )

        acertou = (
            primeiro_documento == esperado
        )

        if acertou:
            acertos += 1

        resultados.append(
            {
                "pergunta": pergunta,
                "tipo": caso["tipo"],
                "esperado": esperado,
                "recuperado": (
                    primeiro_documento
                ),
                "suficiente": (
                    resposta.suficiente
                ),
                "motivo": resposta.motivo,
                "acertou": acertou,
            }
        )

    return {
        "acertos": acertos,
        "total": len(CASOS),
        "taxa_acerto": round(
            acertos / len(CASOS),
            4,
        ),
        "casos": resultados,
    }


def testar_documento_revogado() -> dict:
    indice = obter_indice(
        recarregar=True
    )

    resposta_normal = indice.buscar(
        "Frango é permitido na SAB_E?"
    )

    resposta_com_revogados = indice.buscar(
        "Frango é permitido na SAB_E?",
        incluir_revogados=True,
    )

    return {
        "busca_normal": [
            {
                "documento_id": (
                    item.documento_id
                ),
                "status": item.status,
                "score": item.score,
            }
            for item in resposta_normal.resultados
        ],
        "busca_incluindo_revogados": [
            {
                "documento_id": (
                    item.documento_id
                ),
                "status": item.status,
                "score": item.score,
            }
            for item in (
                resposta_com_revogados.resultados
            )
        ],
        "conclusao": (
            "A recuperação normal exclui documentos "
            "com status revogado. Quando o filtro é "
            "desativado, a regra antiga volta a disputar "
            "o ranking e pode contradizer a regra vigente."
        ),
    }


def main() -> None:
    resultado = executar_casos()

    resultado[
        "experimento_documento_revogado"
    ] = testar_documento_revogado()

    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()