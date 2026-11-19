from __future__ import annotations

import re
import unicodedata


DOCUMENTO_GLOSSARIO = "glossario_dados_v1"
CONSULTA_SOBRA_ZERO = (
    "Como interpretar sobra igual a zero, falta de produto e vendas perdidas "
    "no glossário de dados?"
)

_ZERO = r"(?:zero|0+(?:[.,]0+)?)(?!\w|[.,]\d)"
_SOBRA_ZERO = re.compile(
    rf"\b(?:sobras?\s+(?:(?:igual a|iguais a|de|e|sao)\s+)?{_ZERO}"
    rf"|{_ZERO}\s+de\s+sobras?\b|sobrou\s+{_ZERO}"
    r"|sem (?:nenhuma )?sobras?\b|nao sobrou nada\b)"
)
_PERGUNTA_ABERTA = re.compile(
    r"\b(?:o que (?:significa|quer dizer|posso concluir|podemos concluir)|"
    r"como (?:devo )?(?:interpretar|entender)|qual (?:e )?o significado)\b"
)
_INFERENCIA = re.compile(
    r"\b(?:prova|provam|comprova|comprovam|significa|indica|demonstra|"
    r"quer dizer|(?:posso|podemos|permite|da para) (?:concluir|afirmar))\b"
)
_FALTA_OU_PERDA = re.compile(
    r"\b(?:falta|faltou|faltaram|ruptura|esgotou|perdas? de vendas?|"
    r"vendas? perdidas?|(?:perdeu|perdemos) vendas?)\b"
)
_PEDIDO_OPERACIONAL = re.compile(
    r"(?:^|[.!?;]\s*)(?:(?:por favor)[,\s]+)?(?:(?:pode|poderia)\s+)?"
    r"(?:(?:consulte|liste|mostre|traga|busque)\s+(?:(?:a|o|as|os)\s+)?"
    r"(?:operacao|operacoes|historico|ultimas? operacoes)|"
    r"(?:calcule|gere|monte|registre|salve)\s+(?:(?:um|uma|o|a)\s+)?"
    r"(?:plano|recomendacao|preferencia)|planeje)\b"
)
_EVIDENCIA = re.compile(
    rf"{_SOBRA_ZERO.pattern}\s+(?:por si so\s+)?"
    r"nao\s+(?:prova|comprova|permite (?:concluir|afirmar))\s+"
    r"(?:por si so\s+)?(?:que\s+)?"
    r"(?:falta de produtos?|faltou produto|(?:houve\s+)?ruptura)\b"
)


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.replace("`", "").replace("*", "").split())


def detectar_pergunta_sobra_zero(entrada: str) -> bool:
    """Distingue uma pergunta de interpretação de consultas a registros."""
    texto = _normalizar(entrada)
    if not _SOBRA_ZERO.search(texto) or _PEDIDO_OPERACIONAL.search(texto):
        return False

    return bool(
        _PERGUNTA_ABERTA.search(texto)
        or (_INFERENCIA.search(texto) and _FALTA_OU_PERDA.search(texto))
    )


def responder_sobra_zero(recuperacao: dict) -> tuple[dict, dict | None]:
    if recuperacao.get("ok") is not True:
        return {
            "status": "erro",
            "resultado": None,
            "suficiente": False,
            "motivo": "Não foi possível consultar o glossário de dados.",
        }, None

    if recuperacao.get("suficiente") is True:
        for documento in recuperacao.get("resultados") or []:
            if (
                documento.get("documento_id") != DOCUMENTO_GLOSSARIO
                or documento.get("status") != "vigente"
                or not isinstance(documento.get("conteudo"), str)
            ):
                continue

            for bloco in re.split(r"\r?\n[ \t]*\r?\n", documento["conteudo"]):
                trecho = " ".join(bloco.split())
                if _EVIDENCIA.search(_normalizar(trecho)):
                    return {
                        "status": "concluido",
                        "resultado": {"prova_falta": False, "explicacao": trecho},
                        "suficiente": True,
                        "motivo": "Interpretação sustentada pelo glossário vigente.",
                    }, documento

    return {
        "status": "recusado",
        "resultado": None,
        "suficiente": False,
        "motivo": "O glossário recuperado não sustenta uma conclusão sobre sobra zero.",
        "proxima_acao": "Confira se essa interpretação está no glossário vigente.",
    }, None