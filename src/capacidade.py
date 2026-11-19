from __future__ import annotations

import re
import unicodedata


# A ação deve iniciar uma cláusula, para não interpretar uma menção ou
# instrução negada (por exemplo, "não gere um plano") como pedido de plano.
_PEDIDO_PLANO = re.compile(
    r"(?:^|[.!?;,]\s*)"
    r"(?:(?:por favor|so|apenas)[,\s]+)*"
    r"(?:(?:voce\s+)?(?:pode|poderia|consegue)\s+)?"
    r"(?:planeje|planejar|recomende|recomendar|"
    r"(?:gere|gerar|calcule|calcular|monte|montar|crie|criar|faca|fazer|"
    r"prepare|preparar|sugira|sugerir|quero|preciso de)\s+"
    r"(?:(?:um|uma|o|a)\s+)?(?:plano|planejamento|recomendacao))\b"
)

# Só aceita uma declaração de capacidade total, com unidade geral opcional.
# Por exemplo, "0 pastéis de frango" não representa a capacidade total.
_CAPACIDADE_TOTAL = re.compile(
    r"\b(?:capacidade(?:\s+(?:total|maxima|disponivel|global|de producao))*"
    r"|limite(?:\s+(?:total|maximo))?\s+de producao)\b"
    r"\s*(?:(?:e de|igual a|e|de)\s+|[:=]\s*)?"
    r"(?P<valor>zero|\d+(?:[.,]\d+)*)"
    r"(?!\w|[.,]\d)"
    r"(?:\s+(?:pasteis|pastel|unidades?))?"
    r"(?=\s*(?:$|[,.;!?](?!\d)|por favor\b))"
)

_ZERO = re.compile(r"0+(?:[.,]0+)?")


def pedido_plano_com_capacidade_zero(texto: str) -> bool:
    """Reconhece pedidos de plano com limite total zero declarado sem ambiguidade."""
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
    normalizado = " ".join(normalizado.split())

    if not _PEDIDO_PLANO.search(normalizado):
        return False

    valores = [m.group("valor") for m in _CAPACIDADE_TOTAL.finditer(normalizado)]
    # Se também há uma declaração não zero, não inferimos qual limite prevalece.
    return bool(valores) and all(
        valor == "zero" or _ZERO.fullmatch(valor) is not None for valor in valores
    )
