from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from src.domain import (
    FEIRAS_COM_RESTRICAO,
    FEIRAS_VALIDAS,
    PRODUTOS_PROIBIDOS_FEIRAS_E,
)


DOCUMENTO_REGRAS_FEIRAS = "regras_feiras_v2"

_FEIRA = re.compile(
    r"\b(?:"
    + "|".join(re.escape(feira.lower()) for feira in sorted(FEIRAS_VALIDAS))
    + r")\b"
)

_PEDIDO_PLANO = re.compile(
    r"(?:^|[.!?;,]\s*)(?:(?:por favor|so|apenas)[,\s]+)*"
    r"(?:(?:voce\s+)?(?:pode|poderia|consegue)\s+)?"
    r"(?:planeje|recomende|"
    r"(?:calcule|gere|monte|faca|crie|quero)\s+"
    r"(?:(?:um|uma|o|a)\s+)?(?:plano|recomendacao|planejamento))\b"
)

_INCLUSAO = re.compile(
    r"(?:^|[.!?;,]\s*|\b(?:mas|e)\s+)"
    r"(?:(?:por favor|tambem)\s+)*"
    r"(?:inclua|incluir|adicione|adicionar|coloque|colocar)\s+"
    r"(?:(?:o|a|um|uma)\s+)?"
    r"(?:(?:pastel|pasteis)(?:\s+de)?\s+)?"
    r"(?P<produto>frango|escarola sem bacon)\b"
    r"(?!\s*,?\s*(?:com|catupiri|especial)\b)"
    r"(?=\s*(?:$|[,.;!?]|porque\b|pois\b|por favor\b|no plano\b))"
)

_PERGUNTA_DIA = re.compile(
    r"\b(?:em que dia|que dia|qual (?:e )?o dia|qual dia|quando)\b"
)
_ASSUNTO_CALENDARIO = re.compile(
    r"\b(?:producao|produzid[oa]s?|produzir|venda|vende|vendid[oa]s?)\b"
)
_REFERENCIA_HISTORICA = re.compile(
    r"\b(?:historico|ultima[s]?|ultimo[s]?|operacao|operacoes|ontem|"
    r"ocorreu|foi)\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}\b"
)

_NOMES_DIA = {
    "segunda": "segunda-feira",
    "terca": "terça-feira",
    "quarta": "quarta-feira",
    "quinta": "quinta-feira",
    "sexta": "sexta-feira",
    "sabado": "sábado",
    "domingo": "domingo",
}
_DIA = r"(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b"


@dataclass(frozen=True)
class PedidoRegraFeira:
    tipo: Literal["calendario", "inclusao"]
    feira: str
    produto: str | None = None


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.replace("`", "").split())


def detectar_pedido_regra(entrada: str) -> PedidoRegraFeira | None:
    texto = _normalizar(entrada)
    feiras = {feira.upper() for feira in _FEIRA.findall(texto)}
    if len(feiras) != 1:
        return None

    feira = next(iter(feiras))

    if feira in FEIRAS_COM_RESTRICAO and _PEDIDO_PLANO.search(texto):
        inclusao = _INCLUSAO.search(texto)
        if inclusao:
            return PedidoRegraFeira("inclusao", feira, inclusao.group("produto"))

    if (
        _PERGUNTA_DIA.search(texto)
        and _ASSUNTO_CALENDARIO.search(texto)
        and not _REFERENCIA_HISTORICA.search(texto)
    ):
        return PedidoRegraFeira("calendario", feira)

    return None


def consulta_da_regra(pedido: PedidoRegraFeira) -> str:
    if pedido.tipo == "calendario":
        return f"Em que dia da semana ocorre a produção da feira {pedido.feira}?"
    return f"Pode vender pastel de {pedido.produto} na feira {pedido.feira}?"


def _dias_da_feira(feira: str, corpo: str) -> dict | None:
    codigo = re.escape(feira.lower())
    trecho = re.search(
        rf"\bproducao de {codigo} ocorre (?:na|no) {_DIA}"
        rf" e a venda (?:na|no) {_DIA}",
        corpo,
    )
    if trecho:
        return {
            "feira": feira,
            "dia_producao": _NOMES_DIA[trecho.group(1)],
            "dia_venda": _NOMES_DIA[trecho.group(2)],
        }

    dia_feira = {"SAB": "sabado", "DOM": "domingo"}.get(feira.split("_")[0])
    if dia_feira:
        trecho = re.search(
            rf"\bfeiras de {dia_feira} sao produzidas (?:na|no) {_DIA}",
            corpo,
        )
        if trecho:
            return {
                "feira": feira,
                "dia_producao": _NOMES_DIA[trecho.group(1)],
                "dia_venda": _NOMES_DIA[dia_feira],
            }

    return None


def _codigo_proibido(pedido: PedidoRegraFeira, corpo: str) -> int | None:
    if pedido.produto is None:
        return None

    for trecho in re.finditer(
        r"\bnas feiras (?P<feiras>[^.]+?) nao sao comercializados:?\s+"
        r"(?P<itens>[^.]+)",
        corpo,
    ):
        feiras = {feira.upper() for feira in _FEIRA.findall(trecho.group("feiras"))}
        if pedido.feira not in feiras:
            continue

        produto = re.escape(pedido.produto)
        item = re.search(
            rf"\bpastel de {produto},?\s+produto de codigo (\d+)\b",
            trecho.group("itens"),
        )
        if item:
            codigo = int(item.group(1))
            if codigo in PRODUTOS_PROIBIDOS_FEIRAS_E:
                return codigo

    return None


def responder_regra_feira(
    pedido: PedidoRegraFeira, recuperacao: dict
) -> tuple[dict, dict | None]:
    if recuperacao.get("ok") is not True:
        return {
            "status": "erro",
            "resultado": None,
            "suficiente": False,
            "motivo": "Não foi possível consultar o corpus de regras das feiras.",
        }, None

    if recuperacao.get("suficiente") is True:
        for documento in recuperacao.get("resultados") or []:
            if (
                documento.get("documento_id") != DOCUMENTO_REGRAS_FEIRAS
                or documento.get("status") != "vigente"
                or not isinstance(documento.get("conteudo"), str)
            ):
                continue

            corpo = _normalizar(documento["conteudo"])

            if pedido.tipo == "calendario":
                dias = _dias_da_feira(pedido.feira, corpo)
                if dias is not None:
                    return {
                        "status": "concluido",
                        "resultado": dias,
                        "suficiente": True,
                        "motivo": "Calendário extraído da regra vigente da feira.",
                    }, documento
            else:
                codigo = _codigo_proibido(pedido, corpo)
                if codigo is not None:
                    return {
                        "status": "recusado",
                        "resultado": None,
                        "suficiente": False,
                        "motivo": (
                            f"A feira {pedido.feira} não comercializa o pastel "
                            f"de {pedido.produto} (código {codigo}). Como o pedido "
                            "exige esse produto, nenhum plano foi calculado."
                        ),
                        "proxima_acao": (
                            f"Peça uma recomendação para {pedido.feira} "
                            "sem incluir esse produto."
                        ),
                    }, documento

    return {
        "status": "recusado",
        "resultado": None,
        "suficiente": False,
        "motivo": "A busca não confirmou a regra vigente necessária para atender ao pedido.",
        "proxima_acao": "Confira a regra da feira cadastrada no corpus.",
    }, None