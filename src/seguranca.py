"""Políticas executadas fora do LLM. Não leem credenciais nem acessam rede."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    ValidationError,
)


Feira = Literal["QUA", "QUI", "SAB_C", "SAB_E", "DOM_C", "DOM_E"]

FEIRAS = {
    "QUA",
    "QUI",
    "SAB_C",
    "SAB_E",
    "DOM_C",
    "DOM_E",
}

VALORES_PRIORIDADE = {
    "reduzir sobra",
    "evitar falta",
}

MAX_ARGUMENTOS_BYTES = 8_192


class ErroSeguranca(ValueError):
    """Mensagem fixa: nunca reproduz o valor rejeitado."""

    def __init__(self, codigo: str, mensagem: str):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(f"{codigo}: {mensagem}")

    def como_resultado(self) -> dict:
        return {
            "ok": False,
            "erro": {
                "codigo": self.codigo,
                "mensagem": self.mensagem,
                "orientacao": (
                    "A ação foi bloqueada. Corrija o pedido "
                    "sem incluir credenciais."
                ),
            },
        }


class _Argumentos(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


class _Historico(_Argumentos):
    codigo_feira: Feira

    limite_operacoes: Annotated[
        StrictInt,
        Field(ge=1, le=10),
    ] = 5


class _Operacao(_Argumentos):
    id_operacao: Annotated[
        StrictInt,
        Field(gt=0),
    ]


class _Busca(_Argumentos):
    consulta: Annotated[
        StrictStr,
        Field(min_length=2, max_length=2_000),
    ]


class _Recomendacao(_Argumentos):
    codigo_feira: Feira


class _Preferencia(_Argumentos):
    chave: Literal["prioridade"]

    valor: Literal[
        "reduzir sobra",
        "evitar falta",
    ]


class _Registro(_Argumentos):
    resumo_plano: Annotated[
        StrictStr,
        Field(min_length=1, max_length=600),
    ]


class _EpisodioPlano(_Argumentos):
    tipo: Literal["plano_calculado_v1"]

    feira: Feira

    total_recomendado: Annotated[
        StrictInt,
        Field(ge=0),
    ]

    operacoes_consideradas: Annotated[
        StrictInt,
        Field(ge=1, le=5),
    ] | None = None


_CATALOGO = {
    "consultar_historico": _Historico,
    "consultar_operacao": _Operacao,
    "buscar_conhecimento": _Busca,
    "calcular_recomendacao": _Recomendacao,
    "salvar_preferencia": _Preferencia,
    "registrar_plano": _Registro,
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return " ".join(texto.casefold().split())


_CREDENCIAIS = re.compile(
    r"\bsk-[a-zA-Z0-9_-]{16,}\b"
    r"|\b(?:openai_api_key|mysql_password|eval_mysql_password|db_password|"
    r"password|senha|api[_ -]?key|access[_ -]?token)\s*[:=]\s*\S+"
    r"|\bbearer\s+[a-zA-Z0-9._-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.IGNORECASE,
)


def validar_texto_sem_credenciais(texto: str) -> None:
    """
    Bloqueia formatos reconhecidos.

    Não promete detectar todo dado pessoal ou segredo ofuscado.
    """
    if not isinstance(texto, str) or _CREDENCIAIS.search(texto):
        raise ErroSeguranca(
            "CREDENCIAL_NAO_PERMITIDA",
            "Não envie senhas, chaves ou tokens pelo agente.",
        )


def validar_identidade(
    usuario_id: str,
    autorizado: str,
) -> None:
    """
    Identificação técnica local.

    Não substitui autenticação para HTTP/MCP nem protege contra alguém
    que já pode executar Python ou alterar os arquivos da aplicação.
    """
    if not usuario_id or usuario_id != autorizado:
        raise ErroSeguranca(
            "USUARIO_NAO_AUTORIZADO",
            "Usuário técnico não autorizado.",
        )


def _pares_unicos(pares: list[tuple]) -> dict:
    objeto = {}

    for chave, valor in pares:
        if chave in objeto:
            raise ValueError("chave duplicada")

        objeto[chave] = valor

    return objeto


def _constante_invalida(_: str) -> None:
    raise ValueError("constante JSON não permitida")


def _ler_objeto(bruto: str | dict) -> dict:
    if isinstance(bruto, str):
        if len(bruto.encode("utf-8")) > MAX_ARGUMENTOS_BYTES:
            raise ValueError("argumentos excedem o limite")

        bruto = json.loads(
            bruto,
            object_pairs_hook=_pares_unicos,
            parse_constant=_constante_invalida,
        )

    if type(bruto) is not dict:
        raise ValueError("é necessário um objeto JSON")

    serializado = json.dumps(
        bruto,
        ensure_ascii=False,
        allow_nan=False,
    )

    if len(serializado.encode("utf-8")) > MAX_ARGUMENTOS_BYTES:
        raise ValueError("argumentos excedem o limite")

    return bruto


def validar_argumentos(
    nome: str,
    bruto: str | dict,
) -> dict:
    modelo = (
        _CATALOGO.get(nome)
        if isinstance(nome, str)
        else None
    )

    if modelo is None:
        raise ErroSeguranca(
            "FERRAMENTA_DESCONHECIDA",
            "Ferramenta fora do catálogo permitido.",
        )

    try:
        dados = modelo.model_validate(
            _ler_objeto(bruto)
        ).model_dump()

    except (
        ValueError,
        TypeError,
        RecursionError,
        OverflowError,
    ):
        raise ErroSeguranca(
            "ARGUMENTOS_INVALIDOS",
            "Argumentos fora do contrato da ferramenta.",
        ) from None

    for valor in dados.values():
        if isinstance(valor, str):
            validar_texto_sem_credenciais(valor)

            if not valor.strip():
                raise ErroSeguranca(
                    "ARGUMENTOS_INVALIDOS",
                    "Texto vazio não é permitido.",
                )

    return dados


def contrato_argumentos(nome: str) -> dict:
    """
    O catálogo enviado ao modelo usa o mesmo contrato validado no código.
    """
    return _CATALOGO[nome].model_json_schema()


def validar_lote_chamadas(chamadas: list) -> None:
    if (
        not isinstance(chamadas, list)
        or len(chamadas) != 1
    ):
        raise ErroSeguranca(
            "LOTE_DE_FERRAMENTAS_INVALIDO",
            "É permitida uma ferramenta por decisão do modelo.",
        )

    chamada = chamadas[0]

    if (
        not isinstance(chamada, dict)
        or chamada.get("type") != "function"
        or not isinstance(chamada.get("id"), str)
        or not chamada["id"].strip()
        or not isinstance(chamada.get("function"), dict)
        or not isinstance(
            chamada["function"].get("name"),
            str,
        )
        or chamada["function"]["name"] not in _CATALOGO
    ):
        raise ErroSeguranca(
            "CHAMADA_INVALIDA",
            "Chamada de ferramenta inválida ou não permitida.",
        )


def validar_preferencia(
    chave: str,
    valor: str,
) -> dict:
    if (
        not isinstance(chave, str)
        or not isinstance(valor, str)
    ):
        raise ErroSeguranca(
            "PREFERENCIA_NAO_PERMITIDA",
            "Preferência fora da lista permitida.",
        )

    try:
        return _Preferencia(
            chave=_normalizar(chave),
            valor=_normalizar(valor),
        ).model_dump()

    except ValidationError:
        raise ErroSeguranca(
            "PREFERENCIA_NAO_PERMITIDA",
            (
                "Somente a prioridade operacional prevista "
                "no código pode ser salva."
            ),
        ) from None


def autorizar_preferencia(
    entrada_texto: str,
    argumentos: dict,
) -> None:
    """
    Aceita um comando explícito inteiro.

    Não aceita uma frase encontrada dentro de um documento.
    """
    pedido = _normalizar(entrada_texto)

    padrao = (
        r"(?:por favor[, ]+)?"
        r"(?:guarde|salve|registre|memorize) como preferencia "
        r"(?:permanente|padrao)"
        r"(?: para (?:meus|os meus) planejamentos)? "
        r"a chave prioridade com o valor "
        r"(reduzir sobra|evitar falta)[.!]?"
    )

    declarado = re.fullmatch(
        padrao,
        pedido,
    )

    if (
        declarado is None
        or declarado.group(1) != argumentos["valor"]
    ):
        raise ErroSeguranca(
            "PREFERENCIA_SEM_AUTORIZACAO",
            (
                "Use um pedido explícito: Guarde como preferência "
                "permanente a chave prioridade com o valor reduzir sobra."
            ),
        )


def validar_resumo_episodio(resumo: str) -> str:
    try:
        modelo = _EpisodioPlano.model_validate(
            _ler_objeto(resumo)
        )

    except (
        ValueError,
        TypeError,
        RecursionError,
        OverflowError,
    ):
        raise ErroSeguranca(
            "EPISODIO_NAO_VERIFICADO",
            (
                "Episódios aceitam somente metadados "
                "estruturados de planos calculados."
            ),
        ) from None

    return json.dumps(
        modelo.model_dump(exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
    )


def validar_plano_para_registro(plano: dict) -> None:
    """
    Confere a carga que será apresentada ao humano.

    Não utiliza um texto livre do modelo como plano.
    """
    invalido = ErroSeguranca(
        "PLANO_INVALIDO",
        "Plano inconsistente; nenhum registro foi autorizado.",
    )

    if (
        not isinstance(plano, dict)
        or not isinstance(plano.get("feira"), str)
        or plano["feira"] not in FEIRAS
    ):
        raise invalido

    total = plano.get("total_recomendado")
    itens = plano.get("recomendacoes")

    if (
        type(total) is not int
        or total < 0
        or not isinstance(itens, list)
        or not 1 <= len(itens) <= 100
    ):
        raise invalido

    ids = set()
    soma = 0

    for item in itens:
        if not isinstance(item, dict):
            raise invalido

        codigo = item.get("id_produto")
        quantidade = item.get("quantidade_recomendada")

        if (
            type(codigo) is not int
            or codigo <= 0
            or codigo in ids
        ):
            raise invalido

        if (
            type(quantidade) is not int
            or quantidade < 0
        ):
            raise invalido

        if (
            plano["feira"] in {"SAB_E", "DOM_E"}
            and codigo in {5, 15}
        ):
            raise invalido

        ids.add(codigo)
        soma += quantidade

    if soma != total:
        raise invalido