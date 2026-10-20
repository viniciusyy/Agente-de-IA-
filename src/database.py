from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import mysql.connector
from mysql.connector import Error

from src.config import ErroConfiguracao, settings


FEIRAS_VALIDAS = {
    "QUA",
    "QUI",
    "SAB_C",
    "SAB_E",
    "DOM_C",
    "DOM_E",
}


def erro_como_dado(
    codigo: str,
    mensagem: str,
    orientacao: str,
) -> dict:
    return {
        "ok": False,
        "erro": {
            "codigo": codigo,
            "mensagem": mensagem,
            "orientacao": orientacao,
        },
    }


def _serializar(valor: Any) -> Any:
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()

    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def _serializar_linhas(
    linhas: list[dict],
) -> list[dict]:
    return [
        {
            chave: _serializar(valor)
            for chave, valor in linha.items()
        }
        for linha in linhas
    ]


def conectar():
    settings.validar_mysql()

    return mysql.connector.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        user=settings.mysql_user,
        password=settings.mysql_password,
        connection_timeout=10,
    )


def testar_conexao() -> dict:
    conexao = None

    try:
        conexao = conectar()

        if conexao.is_connected():
            return {
                "ok": True,
                "mensagem": (
                    "Conexão com o MySQL realizada "
                    "com sucesso."
                ),
                "banco": settings.mysql_database,
            }

        return erro_como_dado(
            "CONEXAO_INATIVA",
            "A conexão foi criada, mas não está ativa.",
            "Verifique a disponibilidade do MySQL.",
        )

    except (Error, ErroConfiguracao) as erro:
        return erro_como_dado(
            "ERRO_DE_CONEXAO",
            str(erro),
            (
                "Inicie o MySQL e confira as variáveis "
                "DB_* do arquivo .env."
            ),
        )

    finally:
        if (
            conexao is not None
            and conexao.is_connected()
        ):
            conexao.close()


def _validar_feira(
    codigo_feira: str,
) -> str | dict:
    codigo = codigo_feira.strip().upper()

    if codigo not in FEIRAS_VALIDAS:
        return erro_como_dado(
            "FEIRA_INVALIDA",
            f"A feira '{codigo}' não é válida.",
            (
                "Use QUA, QUI, SAB_C, SAB_E, "
                "DOM_C ou DOM_E."
            ),
        )

    return codigo


def consultar_historico(
    codigo_feira: str,
    limite_operacoes: int = 5,
) -> dict:
    codigo_ou_erro = _validar_feira(
        codigo_feira
    )

    if isinstance(codigo_ou_erro, dict):
        return codigo_ou_erro

    codigo = codigo_ou_erro

    if not 1 <= limite_operacoes <= 10:
        return erro_como_dado(
            "LIMITE_INVALIDO",
            (
                "O limite deve estar entre "
                "1 e 10 operações."
            ),
            (
                "Informe um número inteiro "
                "entre 1 e 10."
            ),
        )

    consulta = """
        SELECT
            o.id_operacao,
            f.codigo AS feira,
            o.data_producao,
            o.data_venda,
            o.eh_feriado,
            o.nome_feriado,
            o.observacoes,
            p.id_produto,
            p.nome AS produto,
            rp.quantidade_produzida,
            rp.quantidade_sobra,
            rp.quantidade_vendida
        FROM operacoes AS o
        INNER JOIN feiras AS f
            ON f.id_feira = o.id_feira
        INNER JOIN registros_producao AS rp
            ON rp.id_operacao = o.id_operacao
        INNER JOIN produtos AS p
            ON p.id_produto = rp.id_produto
        WHERE
            f.codigo = %s
            AND o.id_operacao IN (
                SELECT recentes.id_operacao
                FROM (
                    SELECT o2.id_operacao
                    FROM operacoes AS o2
                    INNER JOIN feiras AS f2
                        ON f2.id_feira = o2.id_feira
                    WHERE f2.codigo = %s
                    ORDER BY
                        COALESCE(
                            o2.data_venda,
                            o2.data_producao
                        ) DESC,
                        o2.id_operacao DESC
                    LIMIT %s
                ) AS recentes
            )
        ORDER BY
            COALESCE(
                o.data_venda,
                o.data_producao
            ) DESC,
            o.id_operacao DESC,
            p.nome ASC
    """

    conexao = None
    cursor = None

    try:
        conexao = conectar()
        cursor = conexao.cursor(
            dictionary=True
        )

        cursor.execute(
            consulta,
            (
                codigo,
                codigo,
                limite_operacoes,
            ),
        )

        linhas = cursor.fetchall()

        if not linhas:
            return erro_como_dado(
                "HISTORICO_NAO_ENCONTRADO",
                (
                    "Não foram encontradas operações "
                    f"para a feira {codigo}."
                ),
                (
                    "Confirme o código da feira ou "
                    "consulte outra feira."
                ),
            )

        return {
            "ok": True,
            "fonte": (
                "mysql:"
                f"{settings.mysql_database}"
                f".operacoes/{codigo}"
            ),
            "feira": codigo,
            "quantidade_registros": len(linhas),
            "dados": _serializar_linhas(linhas),
        }

    except (Error, ErroConfiguracao) as erro:
        return erro_como_dado(
            "ERRO_NA_CONSULTA",
            str(erro),
            (
                "Verifique a conexão e a estrutura "
                "das tabelas do MySQL."
            ),
        )

    finally:
        if cursor is not None:
            cursor.close()

        if (
            conexao is not None
            and conexao.is_connected()
        ):
            conexao.close()


def consultar_operacao(
    id_operacao: int,
) -> dict:
    if id_operacao <= 0:
        return erro_como_dado(
            "IDENTIFICADOR_INVALIDO",
            (
                "O identificador deve "
                "ser positivo."
            ),
            (
                "Informe um id_operacao "
                "maior que zero."
            ),
        )

    consulta = """
        SELECT
            o.id_operacao,
            f.codigo AS feira,
            o.data_producao,
            o.data_venda,
            o.eh_feriado,
            o.nome_feriado,
            o.observacoes,
            p.id_produto,
            p.nome AS produto,
            rp.quantidade_produzida,
            rp.quantidade_sobra,
            rp.quantidade_vendida
        FROM operacoes AS o
        INNER JOIN feiras AS f
            ON f.id_feira = o.id_feira
        INNER JOIN registros_producao AS rp
            ON rp.id_operacao = o.id_operacao
        INNER JOIN produtos AS p
            ON p.id_produto = rp.id_produto
        WHERE o.id_operacao = %s
        ORDER BY p.nome ASC
    """

    conexao = None
    cursor = None

    try:
        conexao = conectar()
        cursor = conexao.cursor(
            dictionary=True
        )

        cursor.execute(
            consulta,
            (id_operacao,),
        )

        linhas = cursor.fetchall()

        if not linhas:
            return erro_como_dado(
                "REGISTRO_NAO_ENCONTRADO",
                (
                    f"A operação {id_operacao} "
                    "não existe no banco de dados."
                ),
                (
                    "Confirme o identificador ou "
                    "consulte o histórico de uma feira."
                ),
            )

        return {
            "ok": True,
            "fonte": (
                "mysql:"
                f"{settings.mysql_database}"
                ".operacoes/"
                f"{id_operacao}"
            ),
            "id_operacao": id_operacao,
            "quantidade_registros": len(linhas),
            "dados": _serializar_linhas(linhas),
        }

    except (Error, ErroConfiguracao) as erro:
        return erro_como_dado(
            "ERRO_NA_CONSULTA",
            str(erro),
            (
                "Verifique a conexão e a estrutura "
                "das tabelas do MySQL."
            ),
        )

    finally:
        if cursor is not None:
            cursor.close()

        if (
            conexao is not None
            and conexao.is_connected()
        ):
            conexao.close()