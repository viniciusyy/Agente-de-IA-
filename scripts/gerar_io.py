"""
Atualiza os exemplos reais de docs/io.md utilizando somente
saídas copiadas dos logs oficiais.
"""

from __future__ import annotations

import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
DOCUMENTO = RAIZ / "docs" / "io.md"

MARCADOR_INICIO = "<!-- INICIO_EXEMPLOS_REAIS -->"
MARCADOR_FIM = "<!-- FIM_EXEMPLOS_REAIS -->"


CASOS = [
    {
        "arquivo": "01_caso_simples.json",
        "titulo": "Caminho feliz",
        "leitura": (
            "Leia `status=concluido`, "
            "`suficiente=true` e as fontes "
            "provenientes do MySQL."
        ),
    },
    {
        "arquivo": "04_acao_nao_permitida.json",
        "titulo": "Entrada incompleta",
        "leitura": (
            "Leia `status=precisa_informacao`, "
            "`suficiente=false` e a solicitação "
            "da feira ausente."
        ),
    },
    {
        "arquivo": "05_pergunta_fora_corpus.json",
        "titulo": "Recusa fora do corpus",
        "leitura": (
            "Leia `status=recusado`, "
            "`suficiente=false`, o motivo da "
            "recusa e a próxima ação possível."
        ),
    },
]


def carregar_saida(
    arquivo: str,
) -> tuple[dict, dict]:
    """
    Carrega o log oficial e a última saída validada do caso.
    """
    caminho = RAIZ / "logs" / arquivo

    if not caminho.exists():
        raise FileNotFoundError(
            f"Log oficial ausente: {caminho}"
        )

    log = json.loads(
        caminho.read_text(encoding="utf-8")
    )

    execucoes = log.get("execucoes", [])

    if not execucoes:
        raise ValueError(
            f"O log {arquivo} não possui execuções."
        )

    saida = execucoes[-1].get("saida")

    if not saida:
        raise ValueError(
            f"O log {arquivo} não possui "
            "uma saída validada."
        )

    return log, saida


def montar_secao(
    caso: dict,
) -> str:
    """
    Monta um exemplo em Markdown sem inventar entrada ou saída.
    """
    log, saida = carregar_saida(
        caso["arquivo"]
    )

    linhas = [
        f"### {caso['titulo']}",
        "",
        f"- Data: `{log['data_execucao']}`",
        f"- Commit: `{log['commit']}`",
        f"- Log: `logs/{caso['arquivo']}`",
        "",
        "Entrada exata:",
        "",
        "```text",
        log["entrada_exata"],
        "```",
        "",
        "Saída completa:",
        "",
        "```json",
        json.dumps(
            saida,
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
        caso["leitura"],
    ]

    return "\n".join(linhas)


def remover_espacos_finais(
    conteudo: str,
) -> str:
    """
    Remove espaços no final das linhas e mantém uma quebra final.
    """
    linhas = [
        linha.rstrip()
        for linha in conteudo.splitlines()
    ]

    return "\n".join(linhas) + "\n"


def main() -> None:
    if not DOCUMENTO.exists():
        raise FileNotFoundError(
            "docs/io.md ainda não existe. "
            "Crie o documento de contratos antes "
            "de executar este script."
        )

    conteudo_atual = DOCUMENTO.read_text(
        encoding="utf-8"
    )

    if (
        MARCADOR_INICIO not in conteudo_atual
        or MARCADOR_FIM not in conteudo_atual
    ):
        raise ValueError(
            "Os marcadores de exemplos reais "
            "não foram encontrados em docs/io.md."
        )

    secoes = [
        montar_secao(caso)
        for caso in CASOS
    ]

    antes, restante = conteudo_atual.split(
        MARCADOR_INICIO,
        1,
    )

    _, depois = restante.split(
        MARCADOR_FIM,
        1,
    )

    novo_conteudo = (
        antes
        + MARCADOR_INICIO
        + "\n\n"
        + "\n\n".join(secoes)
        + "\n\n"
        + MARCADOR_FIM
        + depois
    )

    novo_conteudo = remover_espacos_finais(
        novo_conteudo
    )

    DOCUMENTO.write_text(
        novo_conteudo,
        encoding="utf-8",
    )

    print(
        f"[atualizado] {DOCUMENTO}"
    )


if __name__ == "__main__":
    main()