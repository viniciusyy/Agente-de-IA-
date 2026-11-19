"""Verifica uma etapa da suíte, sem chamar o agente nem escrever no banco."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from src.schemas import SaidaAgente


@dataclass(frozen=True)
class EstadoSQLite:
    planos: dict[int, dict]
    preferencias: dict[int, dict]


@dataclass(frozen=True)
class ReferenciasMySQL:
    """Gabaritos calculados separadamente do agente, em tipos JSON."""

    historicos: dict[tuple[str, int], list[dict]] = field(default_factory=dict)
    operacoes: dict[int, dict] = field(default_factory=dict)
    recomendacoes: dict[str, dict[int, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenciasEtapa:
    execucao: dict
    trajetoria: list[dict] | None
    antes: EstadoSQLite
    depois: EstadoSQLite
    entrada: dict
    usuario_id: str
    thread_id: str
    anterior: dict | None = None
    mysql: ReferenciasMySQL | None = None


def ler_estado_sqlite(caminho: str | Path) -> EstadoSQLite:
    """Lê o SQLite isolado do caso, já inicializado pelo sistema."""
    uri = Path(caminho).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conexao:
        conexao.row_factory = sqlite3.Row
        conexao.execute("BEGIN")
        planos = {
            linha["id"]: dict(linha)
            for linha in conexao.execute("SELECT * FROM planos_aprovados")
        }
        preferencias = {
            linha["id"]: dict(linha)
            for linha in conexao.execute("SELECT * FROM memoria_semantica")
        }
    return EstadoSQLite(planos=planos, preferencias=preferencias)


_AUSENTE = object()
_TOTAIS = ("total_produzido", "total_vendido", "total_sobra")


def _campo(objeto, caminho: str):
    for chave in caminho.split("."):
        if not isinstance(objeto, dict) or chave not in objeto:
            return _AUSENTE
        objeto = objeto[chave]
    return objeto


def _igual(real, esperado) -> bool:
    # Evita, inclusive em listas, aceitar True como se fosse o inteiro 1.
    if type(real) is not type(esperado):
        return False
    if isinstance(real, dict):
        return real.keys() == esperado.keys() and all(
            _igual(real[k], esperado[k]) for k in esperado
        )
    if isinstance(real, list):
        return len(real) == len(esperado) and all(
            _igual(a, b) for a, b in zip(real, esperado)
        )
    return real == esperado


def _corresponde(chamada: dict, regra: dict) -> bool:
    argumentos = chamada.get("argumentos")
    erro = chamada.get("erro")
    return (
        chamada.get("ferramenta") == regra["nome"]
        and all(
            _igual(_campo(chamada, chave), regra[chave])
            for chave in ("ok", "ja_existia")
            if chave in regra
        )
        and (
            "erro_codigo" not in regra
            or isinstance(erro, dict) and erro.get("codigo") == regra["erro_codigo"]
        )
        and all(
            isinstance(argumentos, dict)
            and _igual(argumentos.get(chave, _AUSENTE), valor)
            for chave, valor in regra.get("argumentos", {}).items()
        )
    )


def _data_iso(valor):
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, "%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    return valor


def _projetar(linha: dict, campos: list | tuple) -> dict:
    return {
        chave: _data_iso(linha[chave]) if chave == "data_venda" else linha[chave]
        for chave in campos
        if chave in linha
    }


def _quantidades_plano(resultado: dict) -> dict[int, int] | None:
    itens = resultado.get("recomendacoes")
    if not isinstance(itens, list) or not itens:
        return None

    quantidades = {}
    for item in itens:
        if not isinstance(item, dict):
            return None
        produto = item.get("id_produto")
        quantidade = item.get("quantidade_recomendada")
        nome = item.get("produto")
        if (
            type(produto) is not int
            or produto <= 0
            or produto in quantidades
            or type(quantidade) is not int
            or quantidade < 0
            or not isinstance(nome, str)
            or not nome.strip()
            or nome.strip().casefold() in {"banana", "banana simples"}
        ):
            return None
        quantidades[produto] = quantidade
    return quantidades


def _pausa_valida(interrupcao) -> bool:
    if not isinstance(interrupcao, dict):
        return False
    argumentos = interrupcao.get("argumentos")
    if not isinstance(argumentos, dict):
        return False
    quantidades = _quantidades_plano({"recomendacoes": argumentos.get("plano")})
    return (
        interrupcao.get("acao") == "registrar_plano"
        and isinstance(argumentos.get("feira"), str)
        and bool(argumentos["feira"].strip())
        and quantidades is not None
        and _igual(argumentos.get("total_recomendado"), sum(quantidades.values()))
        and isinstance(argumentos.get("resumo_plano"), str)
        and isinstance(interrupcao.get("consequencia"), str)
        and bool(interrupcao["consequencia"].strip())
    )


def _payload_aprovado(e: EvidenciasEtapa) -> dict | None:
    pausa = (e.anterior or {}).get("interrupcao")
    decisao = e.entrada.get("decisao")
    if (
        not _pausa_valida(pausa)
        or e.entrada.get("tipo") != "decisao_humana"
        or not isinstance(decisao, dict)
        or decisao.get("acao") not in {"aprovar", "editar"}
    ):
        return None
    payload = dict(pausa["argumentos"])
    if decisao["acao"] == "editar" and decisao.get("resumo_plano") is not None:
        payload["resumo_plano"] = decisao["resumo_plano"]
    return payload


def _registro_igual_ao_aprovado(registro: dict, e: EvidenciasEtapa) -> bool:
    payload = _payload_aprovado(e)
    try:
        gravado = json.loads(registro["payload_json"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        payload is not None
        and registro.get("usuario_id") == e.usuario_id
        and registro.get("thread_id") == e.thread_id
        and isinstance(registro.get("idempotency_key"), str)
        and bool(registro["idempotency_key"])
        and _igual(gravado, payload)
    )


def _verificacao_extra(
    v: dict, e: EvidenciasEtapa, saida: dict, chamadas: list[dict]
) -> tuple[str, bool]:
    tipo = v["tipo"]
    resultado = saida.get("resultado")

    if tipo == "ordem_ferramentas":
        nomes = iter(c["ferramenta"] for c in chamadas if c.get("ok") is True)
        return "trajetoria", all(nome in nomes for nome in v["nomes"])

    if tipo == "preferencia_sqlite":
        novas = [
            linha
            for chave, linha in e.depois.preferencias.items()
            if chave not in e.antes.preferencias
        ]
        return "resultado", len(novas) == 1 and all(
            _igual(novas[0].get(k), valor)
            for k, valor in {
                "usuario_id": e.usuario_id,
                "chave": v["chave"],
                "valor": v["valor"],
                "ativo": 1,
            }.items()
        )

    if tipo in {"plano_sqlite", "registro_idempotente"}:
        planos = e.depois.planos
        if len(planos) != v["total_registros"] or len(planos) != 1:
            return "resultado", False
        chave, registro = next(iter(planos.items()))
        if not _registro_igual_ao_aprovado(registro, e):
            return "resultado", False
        if tipo == "registro_idempotente":
            return "resultado", _igual(e.antes.planos, planos)
        payload = _payload_aprovado(e)
        return "resultado", (
            chave not in e.antes.planos
            and payload is not None
            and payload.get("resumo_plano") == v["resumo_plano"]
        )

    mysql = e.mysql

    if tipo == "historico_snapshot":
        limite = v["limite"]
        referencia = mysql.historicos.get((v["feira"], limite)) if mysql else None
        campos = v.get("campos", ("id_operacao", *_TOTAIS))
        if (
            not isinstance(referencia, list)
            or len(referencia) != limite
            or not all(
                isinstance(linha, dict) and all(k in linha for k in campos)
                for linha in referencia
            )
        ):
            return "evidencia", False
        linhas = resultado.get("operacoes") if isinstance(resultado, dict) else resultado
        if not isinstance(linhas, list) or not all(isinstance(l, dict) for l in linhas):
            return "deterministico", False
        if "campos" in v and any(set(linha) != set(campos) for linha in linhas):
            return "deterministico", False
        return "deterministico", _igual(
            [_projetar(l, campos) for l in linhas],
            [_projetar(l, campos) for l in referencia],
        )

    if tipo == "operacao_totais_snapshot":
        referencia = mysql.operacoes.get(v["id_operacao"]) if mysql else None
        campos = ("id_operacao", *_TOTAIS)
        if not isinstance(referencia, dict) or not all(k in referencia for k in campos):
            return "evidencia", False
        return "deterministico", isinstance(resultado, dict) and _igual(
            _projetar(resultado, campos), _projetar(referencia, campos)
        )

    if tipo == "recomendacao_snapshot":
        referencia = mysql.recomendacoes.get(v["feira"]) if mysql else None
        if not referencia:
            return "evidencia", False
        if not isinstance(resultado, dict):
            return "deterministico", False
        reais = _quantidades_plano(resultado)
        if reais is None:
            return "deterministico", False
        excluidos = v.get("ids_excluidos", [])
        return "deterministico", (
            resultado.get("feira") == v["feira"]
            and _igual(reais, referencia)
            and _igual(resultado.get("total_recomendado"), sum(reais.values()))
            and not any(produto in reais for produto in excluidos)
            and (
                not excluidos
                or _igual(
                    _campo(resultado, "regras_aplicadas.produtos_excluidos"),
                    excluidos,
                )
            )
        )

    return "evidencia", False


def _conferir(
    regras: dict, e: EvidenciasEtapa, saida: dict, chamadas: list[dict]
) -> list[dict]:
    falhas = []

    def exigir(ok: bool, nivel: str, checagem: str) -> None:
        if not ok:
            falhas.append({"nivel": nivel, "checagem": checagem})

    if "status" in regras:
        exigir(saida.get("status") in regras["status"], "deterministico", "status")

    if "suficiente" in regras:
        exigir(
            _igual(saida.get("suficiente"), regras["suficiente"]),
            "deterministico",
            "suficiente",
        )

    if "interrupcao" in regras:
        pausa = e.execucao.get("interrupcao")
        ok = (
            _pausa_valida(pausa) and _igual(saida.get("resultado"), pausa)
            if regras["interrupcao"]
            else pausa is None
        )
        if ok and regras["interrupcao"]:
            plano_anterior = _campo(e.anterior or {}, "saida.resultado")
            if isinstance(plano_anterior, dict) and "recomendacoes" in plano_anterior:
                argumentos = pausa["argumentos"]
                ok = all(
                    _igual(argumentos.get(k), plano_anterior.get(k))
                    for k in ("feira", "total_recomendado")
                ) and _igual(argumentos["plano"], plano_anterior["recomendacoes"])
        exigir(ok, "trajetoria", "interrupcao")

    for campo, valor in regras.get("campos_iguais", {}).items():
        exigir(_igual(_campo(saida, campo), valor), "deterministico", campo)

    fontes = saida.get("fontes")
    fontes = [f for f in fontes if isinstance(f, dict)] if isinstance(fontes, list) else []

    for tipo in regras.get("fontes_tipos", []):
        exigir(
            any(f.get("tipo") == tipo for f in fontes),
            "trajetoria",
            f"fonte:{tipo}",
        )

    for documento in regras.get("documentos_requeridos", []):
        exigir(
            any(
                f.get("tipo") == "corpus"
                and str(f.get("referencia", "")).endswith(f"#{documento}")
                for f in fontes
            ),
            "trajetoria",
            f"documento:{documento}",
        )

    for chave, presente in (
        ("ferramentas_requeridas", True),
        ("ferramentas_proibidas", False),
    ):
        for regra in regras.get(chave, []):
            achou = any(_corresponde(c, regra) for c in chamadas)
            exigir(achou == presente, "trajetoria", f"{chave}:{regra['nome']}")

    estados = {
        "delta_planos": (e.antes.planos, e.depois.planos),
        "delta_preferencias": (e.antes.preferencias, e.depois.preferencias),
    }
    for chave, (antes, depois) in estados.items():
        if chave in regras:
            novas = len(depois.keys() - antes.keys())
            exigir(
                novas == regras[chave]
                and all(_igual(linha, depois.get(id_)) for id_, linha in antes.items()),
                "resultado",
                chave,
            )

    for v in regras.get("verificacoes", []):
        nivel, ok = _verificacao_extra(v, e, saida, chamadas)
        exigir(ok, nivel, v["tipo"])

    return falhas


def verificar_etapa(esperado: dict, padroes: dict, e: EvidenciasEtapa) -> dict:
    """Aplica as regras comuns e, se houver, exige que uma alternativa passe."""
    regras = {**padroes, **esperado}
    saida = e.execucao.get("saida")
    falhas = []

    if regras.get("validar_schema_saida", True):
        try:
            SaidaAgente.model_validate(saida, strict=True)
        except ValidationError:
            falhas.append({"nivel": "deterministico", "checagem": "schema_saida"})

    if not isinstance(saida, dict):
        saida = {}

    if not isinstance(e.trajetoria, list) or not all(
        isinstance(item, dict) for item in e.trajetoria
    ):
        falhas.append({
            "nivel": "evidencia",
            "checagem": "trajetoria_ausente_ou_invalida",
        })
        chamadas = []
    else:
        chamadas = [
            item for item in e.trajetoria
            if isinstance(item.get("ferramenta"), str)
        ]

    falhas.extend(_conferir(regras, e, saida, chamadas))
    criterios = [regras["criterio"]] if regras.get("criterio") else []
    alternativa_escolhida = None
    falhas_alternativas = []

    for indice, alternativa in enumerate(regras.get("alternativas", []), start=1):
        erros = _conferir(alternativa, e, saida, chamadas)
        if not erros:
            alternativa_escolhida = indice
            if alternativa.get("criterio"):
                criterios.append(alternativa["criterio"])
            break
        falhas_alternativas.append({"alternativa": indice, "falhas": erros})

    if regras.get("alternativas") and alternativa_escolhida is None:
        falhas.append({
            "nivel": "regra_composta",
            "checagem": "nenhuma_alternativa_passou",
        })

    return {
        "aprovado_automatico": not falhas,
        "falhas": falhas,
        "alternativa": alternativa_escolhida,
        "falhas_alternativas": (
            falhas_alternativas if alternativa_escolhida is None else []
        ),
        "criterios_para_revisao": criterios,
    }