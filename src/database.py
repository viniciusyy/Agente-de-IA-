from datetime import date, datetime
from decimal import Decimal
from typing import Any

import mysql.connector
from mysql.connector import Error

from src.config import settings


FEIRAS_VALIDAS = {
    "QUA",
    "QUI",
    "SAB_C",
    "SAB_E",
    "DOM_C",
    "DOM_E",
}


def conectar():
    """
    Abre uma conexão com o banco MySQL da Pastéis Miyata.

    Esta função não é uma ferramenta do agente. Ela é utilizada
    internamente pelas funções de consulta.
    """
    return mysql.connector.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
        user=settings.mysql_user,
        password=settings.mysql_password,
        connection_timeout=10,
    )


def serializar_valor(valor: Any) -> Any:
    """
    Converte valores do MySQL para formatos que podem ser
    transformados em JSON e enviados ao modelo.
    """
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()

    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def serializar_linhas(linhas: list[dict]) -> list[dict]:
    return [
        {
            chave: serializar_valor(valor)
            for chave, valor in linha.items()
        }
        for linha in linhas
    ]


def erro_como_dado(
    codigo: str,
    mensagem: str,
    orientacao: str,
) -> dict:
    """
    Retorna o erro como dado estruturado.

    Isso permite que o modelo compreenda o problema e tente
    corrigir a solicitação sem derrubar o programa.
    """
    return {
        "ok": False,
        "erro": {
            "codigo": codigo,
            "mensagem": mensagem,
            "orientacao": orientacao,
        },
    }


def testar_conexao() -> dict:
    """
    Verifica se o banco está acessível.
    """
    conexao = None

    try:
        conexao = conectar()

        if conexao.is_connected():
            return {
                "ok": True,
                "mensagem": "Conexão com o MySQL realizada com sucesso.",
                "banco": settings.mysql_database,
            }

        return erro_como_dado(
            codigo="CONEXAO_INATIVA",
            mensagem="A conexão foi criada, mas não está ativa.",
            orientacao="Verifique a disponibilidade do MySQL.",
        )

    except Error as erro:
        return erro_como_dado(
            codigo="ERRO_DE_CONEXAO",
            mensagem=str(erro),
            orientacao=(
                "Verifique se o MySQL está iniciado e confira "
                "as variáveis MYSQL_HOST, MYSQL_PORT, "
                "MYSQL_DATABASE, MYSQL_USER e MYSQL_PASSWORD."
            ),
        )

    finally:
        if conexao is not None and conexao.is_connected():
            conexao.close()


def consultar_historico(
    codigo_feira: str,
    limite_operacoes: int = 5,
) -> dict:
    """
    Ferramenta de leitura.

    Consulta os produtos registrados nas operações mais recentes
    de uma feira. Não altera nenhuma informação do banco.
    """
    codigo_feira = codigo_feira.strip().upper()

    if codigo_feira not in FEIRAS_VALIDAS:
        return erro_como_dado(
            codigo="FEIRA_INVALIDA",
            mensagem=f"A feira '{codigo_feira}' não é válida.",
            orientacao=(
                "Utilize um destes códigos: "
                + ", ".join(sorted(FEIRAS_VALIDAS))
            ),
        )

    if limite_operacoes < 1 or limite_operacoes > 10:
        return erro_como_dado(
            codigo="LIMITE_INVALIDO",
            mensagem="O limite deve estar entre 1 e 10 operações.",
            orientacao="Informe um número inteiro entre 1 e 10.",
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
        cursor = conexao.cursor(dictionary=True)

        cursor.execute(
            consulta,
            (
                codigo_feira,
                codigo_feira,
                limite_operacoes,
            ),
        )

        linhas = cursor.fetchall()

        if not linhas:
            return erro_como_dado(
                codigo="HISTORICO_NAO_ENCONTRADO",
                mensagem=(
                    f"Não foram encontradas operações para "
                    f"a feira {codigo_feira}."
                ),
                orientacao=(
                    "Confirme o código da feira ou consulte "
                    "outra feira."
                ),
            )

        return {
            "ok": True,
            "feira": codigo_feira,
            "quantidade_registros": len(linhas),
            "dados": serializar_linhas(linhas),
        }

    except Error as erro:
        return erro_como_dado(
            codigo="ERRO_NA_CONSULTA",
            mensagem=str(erro),
            orientacao=(
                "Verifique a conexão e confirme se as tabelas "
                "feiras, operacoes, produtos e "
                "registros_producao possuem as colunas esperadas."
            ),
        )

    finally:
        if cursor is not None:
            cursor.close()

        if conexao is not None and conexao.is_connected():
            conexao.close()


def consultar_operacao(id_operacao: int) -> dict:
    """
    Ferramenta de leitura.

    Consulta uma operação específica pelo identificador.
    Também será utilizada para demonstrar o caso de registro
    inexistente exigido no trabalho.
    """
    if id_operacao <= 0:
        return erro_como_dado(
            codigo="IDENTIFICADOR_INVALIDO",
            mensagem="O identificador da operação deve ser positivo.",
            orientacao="Informe um id_operacao maior que zero.",
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
        cursor = conexao.cursor(dictionary=True)

        cursor.execute(consulta, (id_operacao,))
        linhas = cursor.fetchall()

        if not linhas:
            return erro_como_dado(
                codigo="REGISTRO_NAO_ENCONTRADO",
                mensagem=(
                    f"A operação {id_operacao} não existe "
                    "no banco de dados."
                ),
                orientacao=(
                    "Peça ao proprietário para confirmar o "
                    "identificador ou consultar uma feira."
                ),
            )

        return {
            "ok": True,
            "id_operacao": id_operacao,
            "quantidade_registros": len(linhas),
            "dados": serializar_linhas(linhas),
        }

    except Error as erro:
        return erro_como_dado(
            codigo="ERRO_NA_CONSULTA",
            mensagem=str(erro),
            orientacao=(
                "Verifique a conexão e a estrutura das tabelas "
                "do banco MySQL."
            ),
        )

    finally:
        if cursor is not None:
            cursor.close()

        if conexao is not None and conexao.is_connected():
            conexao.close()