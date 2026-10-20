"""
Executa os seis casos oficiais da Parte 2.

Este script utiliza:

- a API configurada no .env;
- o banco MySQL real;
- o corpus em dados/corpus;
- o checkpoint do LangGraph;
- a memória persistente em SQLite.

As execuções geram custo de API. O script deve ser executado
somente depois dos testes automatizados.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agent import AgentePlanejamento
from src.memory import obter_memoria


RAIZ = Path(__file__).resolve().parents[1]

ARQUIVO_CASOS = (
    RAIZ
    / "dados"
    / "casos_demonstracao_parte2.json"
)

PASTA_LOGS = RAIZ / "logs"


def executar_git(
    argumentos: list[str],
) -> str:
    """
    Executa um comando Git na raiz do projeto.
    """
    return subprocess.check_output(
        ["git", *argumentos],
        cwd=RAIZ,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def verificar_repositorio() -> str:
    """
    Exige que o código esteja commitado antes da demonstração.

    Isso garante que o hash registrado no log represente
    exatamente o código executado.
    """
    try:
        commit = executar_git(
            ["rev-parse", "HEAD"]
        )

        alteracoes = executar_git(
            ["status", "--porcelain"]
        )

    except Exception as erro:
        raise RuntimeError(
            "Não foi possível identificar o commit atual. "
            "Execute o script dentro do repositório Git."
        ) from erro

    if alteracoes:
        raise RuntimeError(
            "Existem alterações ainda não commitadas. "
            "Faça o commit do código antes de gerar "
            "os seis logs oficiais.\n\n"
            + alteracoes
        )

    return commit


def carregar_casos() -> list[dict[str, Any]]:
    """
    Carrega os casos declarados no arquivo JSON.
    """
    if not ARQUIVO_CASOS.exists():
        raise FileNotFoundError(
            f"Arquivo de casos não encontrado: "
            f"{ARQUIVO_CASOS}"
        )

    conteudo = json.loads(
        ARQUIVO_CASOS.read_text(
            encoding="utf-8"
        )
    )

    casos = conteudo.get(
        "casos",
        [],
    )

    if len(casos) != 6:
        raise ValueError(
            "O arquivo precisa conter exatamente "
            "seis casos demonstrados."
        )

    return casos


def carregar_log_detalhado(
    resultado: dict,
) -> dict | None:
    """
    Incorpora a trajetória detalhada ao log oficial.

    Os arquivos automáticos execucao_*.json são ignorados pelo Git,
    portanto a trajetória também é copiada para o log oficial.
    """
    caminho_bruto = resultado.get("log")

    if not caminho_bruto:
        return None

    caminho = Path(caminho_bruto)

    if not caminho.is_absolute():
        caminho = RAIZ / caminho

    if not caminho.exists():
        return None

    return json.loads(
        caminho.read_text(
            encoding="utf-8"
        )
    )


def preparar_resultado(
    resultado: dict,
) -> dict:
    """
    Acrescenta o log interno detalhado sem alterar os demais campos.
    """
    preparado = dict(resultado)

    preparado["log_detalhado"] = (
        carregar_log_detalhado(
            resultado
        )
    )

    return preparado


def salvar_log_oficial(
    *,
    arquivo: str,
    caso: dict,
    commit: str,
    thread_id: str,
    execucoes: list[dict],
    extra: dict | None = None,
) -> None:
    """
    Salva um dos seis logs que serão versionados.
    """
    payload = {
        "caso_id": caso["id"],
        "caso_nome": caso["nome"],
        "data_execucao": (
            datetime.now().isoformat()
        ),
        "commit": commit,
        "thread_id": thread_id,
        "entrada_exata": (
            caso.get("entrada")
            or caso.get("entrada_registro")
        ),
        "prova_esperada": caso["prova"],
        "execucoes": execucoes,
        "extra": extra or {},
    }

    caminho = PASTA_LOGS / arquivo

    caminho.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"[salvo] {caminho}"
    )


def executar_casos_simples(
    *,
    agente: AgentePlanejamento,
    casos: list[dict],
    commit: str,
    sufixo_execucao: str,
) -> None:
    """
    Executa os cinco primeiros casos.
    """
    for caso in casos[:5]:
        thread_id = (
            caso["thread_id_base"]
            + "-"
            + sufixo_execucao
        )

        print(
            "\n" + "=" * 72
        )
        print(
            f"Executando: {caso['id']} "
            f"— {caso['nome']}"
        )
        print(
            "=" * 72
        )

        resultado = agente.executar(
            caso["entrada"],
            thread_id=thread_id,
        )

        resultado_preparado = (
            preparar_resultado(
                resultado
            )
        )

        salvar_log_oficial(
            arquivo=caso["arquivo_log"],
            caso=caso,
            commit=commit,
            thread_id=thread_id,
            execucoes=[
                resultado_preparado
            ],
        )


def executar_caso_humano(
    *,
    agente: AgentePlanejamento,
    caso: dict,
    commit: str,
    sufixo_execucao: str,
) -> None:
    """
    Executa o caso de human-in-the-loop e a prova de idempotência.
    """
    thread_id = (
        caso["thread_id_base"]
        + "-"
        + sufixo_execucao
    )

    print(
        "\n" + "=" * 72
    )
    print(
        f"Executando: {caso['id']} "
        f"— {caso['nome']}"
    )
    print(
        "=" * 72
    )

    primeira_bruta = agente.executar(
        caso["entrada_preparacao"],
        thread_id=thread_id,
    )

    primeira = preparar_resultado(
        primeira_bruta
    )

    segunda_bruta = agente.executar(
        caso["entrada_registro"],
        thread_id=thread_id,
    )

    segunda = preparar_resultado(
        segunda_bruta
    )

    interrupcao = segunda.get(
        "interrupcao"
    )

    if not interrupcao:
        raise RuntimeError(
            "O caso 6 não chegou ao interrupt "
            "de aprovação. Confira se o plano "
            "do turno anterior foi preservado."
        )

    decisao = caso[
        "decisao_humana"
    ]

    terceira_bruta = agente.retomar(
        decisao,
        thread_id=thread_id,
    )

    terceira = preparar_resultado(
        terceira_bruta
    )

    # Reconstrói o mesmo payload gravado pelo nó de aprovação.
    payload_repetido = interrupcao[
        "argumentos"
    ].copy()

    if decisao.get("acao") == "editar":
        novo_resumo = decisao.get(
            "resumo_plano"
        )

        if novo_resumo:
            payload_repetido[
                "resumo_plano"
            ] = novo_resumo

    memoria = obter_memoria()

    segunda_tentativa = (
        memoria.registrar_plano_idempotente(
            "proprietario",
            thread_id,
            payload_repetido,
        )
    )

    quantidade_registros = (
        memoria.contar_planos_por_chave(
            segunda_tentativa[
                "idempotency_key"
            ]
        )
    )

    prova_idempotencia = {
        "segunda_tentativa": (
            segunda_tentativa
        ),
        "quantidade_registros_com_mesma_chave": (
            quantidade_registros
        ),
        "resultado_esperado": {
            "ja_existia": True,
            "quantidade_registros": 1,
        },
        "aprovado": (
            segunda_tentativa.get(
                "ja_existia"
            )
            is True
            and quantidade_registros == 1
        ),
    }

    salvar_log_oficial(
        arquivo=caso["arquivo_log"],
        caso=caso,
        commit=commit,
        thread_id=thread_id,
        execucoes=[
            primeira,
            segunda,
            terceira,
        ],
        extra={
            "decisao_humana": decisao,
            "prova_idempotencia": (
                prova_idempotencia
            ),
        },
    )


def main() -> None:
    PASTA_LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    commit = verificar_repositorio()
    casos = carregar_casos()

    sufixo_execucao = (
        datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )
    )

    agente = AgentePlanejamento()

    executar_casos_simples(
        agente=agente,
        casos=casos,
        commit=commit,
        sufixo_execucao=(
            sufixo_execucao
        ),
    )

    executar_caso_humano(
        agente=agente,
        caso=casos[5],
        commit=commit,
        sufixo_execucao=(
            sufixo_execucao
        ),
    )

    print(
        "\nOs seis logs oficiais "
        "foram gerados."
    )

    print(
        "Depois da criação de docs/io.md, "
        "execute: "
        "python -m scripts.gerar_io"
    )


if __name__ == "__main__":
    main()