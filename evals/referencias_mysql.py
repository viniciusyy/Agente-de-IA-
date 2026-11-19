"""Gabaritos independentes, calculados no MySQL de demonstração."""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction

from .verificadores import ReferenciasMySQL

USUARIO = "avaliacao_leitura"
BANCO = "pasteis_miyata"
TABELAS = ("feiras", "operacoes", "produtos", "registros_producao")
_SEM_ASPAS = {39: None, 96: None}


@dataclass(frozen=True)
class Snapshot:
    referencias: ReferenciasMySQL
    sha256: str
    total_operacoes: int
    total_registros: int


class ErroPreflight(ValueError):
    """Erro controlado de configuração ou de compatibilidade do banco."""


def ambiente_demo() -> dict[str, str]:
    env = dict(os.environ)
    modo = env.get("EVAL_MYSQL_MODO", "local").strip().lower()

    if modo == "local":
        host = "127.0.0.1"
        try:
            porta = int(env.get("EVAL_MYSQL_PORT", "3306"))
        except ValueError:
            raise ErroPreflight("EVAL_MYSQL_PORT precisa ser uma porta válida.") from None
        if not 1 <= porta <= 65535:
            raise ErroPreflight("EVAL_MYSQL_PORT precisa ser uma porta válida.")

    elif modo == "docker":
        host, porta = "db", 3306
        destino = (
            env.get("MYSQL_HOST"),
            env.get("MYSQL_PORT"),
            env.get("MYSQL_DATABASE"),
        )
        if destino != (host, str(porta), BANCO):
            raise ErroPreflight("O modo docker precisa do serviço app do Docker Compose.")

    else:
        raise ErroPreflight("EVAL_MYSQL_MODO precisa ser local ou docker.")

    senha = env.pop("EVAL_MYSQL_PASSWORD", "")
    if not senha:
        raise ErroPreflight("Informe EVAL_MYSQL_PASSWORD com a senha da conta de avaliação.")

    for chave in tuple(env):
        if chave.startswith(("DB_", "DEMO_MYSQL_")):
            env.pop(chave)

    env.update(
        EVAL_MYSQL_MODO=modo,
        MYSQL_HOST=host,
        MYSQL_PORT=str(porta),
        MYSQL_DATABASE=BANCO,
        MYSQL_USER=USUARIO,
        MYSQL_PASSWORD=senha,
    )
    return env


def validar_grants(linhas, host_conta: str) -> None:
    """Aceita apenas USAGE e SELECT nas quatro tabelas necessárias."""
    conta = f"{USUARIO}@{host_conta}"
    leituras = {f"GRANT SELECT ON {BANCO}.{tabela} TO {conta}" for tabela in TABELAS}
    encontrados = {
        " ".join(linha[0].translate(_SEM_ASPAS).split())
        for linha in linhas
    }
    permitidos = leituras | {f"GRANT USAGE ON *.* TO {conta}"}
    if not leituras <= encontrados <= permitidos:
        raise ErroPreflight("A conta MySQL não tem o conjunto exclusivo de SELECT esperado.")


def _vendida(registro: dict) -> int:
    valor = registro["quantidade_vendida"]
    if valor is not None:
        return int(valor)
    return int(registro["quantidade_produzida"]) - int(registro["quantidade_sobra"])


def montar_snapshot(
    operacoes: list[dict], registros: list[dict], requisitos: dict
) -> Snapshot:
    por_operacao = defaultdict(list)
    for registro in registros:
        por_operacao[registro["id_operacao"]].append(registro)

    por_feira = defaultdict(list)
    totais = {}
    ids = set()

    for op in operacoes:
        id_ = op["id_operacao"]
        ids.add(id_)
        por_feira[op["feira"]].append(op)
        linhas = por_operacao[id_]
        if linhas:
            totais[id_] = {
                "id_operacao": id_,
                "data_venda": op["data_venda"].isoformat() if op["data_venda"] else None,
                "total_produzido": sum(int(r["quantidade_produzida"]) for r in linhas),
                "total_vendido": sum(_vendida(r) for r in linhas),
                "total_sobra": sum(int(r["quantidade_sobra"]) for r in linhas),
            }

    for id_ in requisitos["operacoes_existentes"]:
        if id_ not in totais:
            raise ErroPreflight(f"Snapshot incompatível: falta a operação {id_} com registros.")
    for id_ in requisitos["operacoes_inexistentes"]:
        if id_ in ids:
            raise ErroPreflight(f"Snapshot incompatível: a operação {id_} deveria estar ausente.")

    historicos = {}
    recomendacoes = {}

    for feira, minimo in requisitos["minimo_operacoes_com_registros"].items():
        ordenadas = sorted(
            por_feira[feira],
            key=lambda op: (
                str(op["data_venda"] or op["data_producao"] or ""),
                op["id_operacao"],
            ),
            reverse=True,
        )
        recentes = [op["id_operacao"] for op in ordenadas[:minimo]]
        if len(recentes) != minimo or any(id_ not in totais for id_ in recentes):
            raise ErroPreflight(
                f"Snapshot incompatível: {feira} precisa de {minimo} operações recentes com registros."
            )

        for limite in range(1, minimo + 1):
            historicos[feira, limite] = [totais[id_] for id_ in recentes[:limite]]

        vendas = defaultdict(list)
        for id_ in recentes[:5]:
            for registro in por_operacao[id_]:
                produto = registro["id_produto"]
                if feira in {"SAB_E", "DOM_E"} and produto in {5, 15}:
                    continue
                if registro["produto"].strip().casefold() in {"banana", "banana simples"}:
                    continue
                vendas[produto].append(_vendida(registro))

        recomendacoes[feira] = {
            produto: round(Fraction(sum(valores), len(valores)))
            for produto, valores in vendas.items()
        }
        if not recomendacoes[feira]:
            raise ErroPreflight(f"Snapshot incompatível: {feira} não tem produtos recomendáveis.")

    serializado = json.dumps(
        [operacoes, registros],
        default=str,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return Snapshot(
        ReferenciasMySQL(historicos, totais, recomendacoes),
        hashlib.sha256(serializado).hexdigest(),
        len(operacoes),
        len(registros),
    )


def ler_snapshot(env: dict[str, str], requisitos: dict) -> Snapshot:
    import mysql.connector

    with closing(mysql.connector.connect(
        host=env["MYSQL_HOST"],
        port=int(env["MYSQL_PORT"]),
        database=env["MYSQL_DATABASE"],
        user=env["MYSQL_USER"],
        password=env["MYSQL_PASSWORD"],
        connection_timeout=10,
    )) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute("SHOW GRANTS")
            host_conta = "%" if env["EVAL_MYSQL_MODO"] == "docker" else "127.0.0.1"
            validar_grants(cursor.fetchall(), host_conta)

        conn.rollback()
        conn.start_transaction(
            consistent_snapshot=True,
            isolation_level="REPEATABLE READ",
            readonly=True,
        )

        with closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("""
                SELECT o.id_operacao, f.codigo AS feira, o.data_producao, o.data_venda,
                       o.eh_feriado, o.nome_feriado, o.observacoes
                FROM operacoes o JOIN feiras f ON f.id_feira = o.id_feira
                ORDER BY o.id_operacao
            """)
            operacoes = cursor.fetchall()

            cursor.execute("""
                SELECT r.id_operacao, p.id_produto, p.nome AS produto,
                       r.quantidade_produzida, r.quantidade_vendida, r.quantidade_sobra
                FROM registros_producao r JOIN produtos p ON p.id_produto = r.id_produto
                ORDER BY r.id_operacao, p.id_produto,
                         r.quantidade_produzida, r.quantidade_vendida, r.quantidade_sobra
            """)
            registros = cursor.fetchall()

    return montar_snapshot(operacoes, registros, requisitos)