from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class EntradaAgente(BaseModel):
    """
    Contrato externo.

    O conteúdo é texto livre. Os identificadores são metadados.
    """

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(
        min_length=1,
        max_length=4_000,
    )
    usuario_id: str = Field(
        min_length=1,
        max_length=80,
    )
    thread_id: str = Field(
        min_length=1,
        max_length=120,
    )

    @model_validator(mode="after")
    def limpar(self) -> "EntradaAgente":
        self.texto = self.texto.strip()
        self.usuario_id = self.usuario_id.strip()
        self.thread_id = self.thread_id.strip()

        if not self.texto:
            raise ValueError(
                "O texto da solicitação não pode estar vazio."
            )

        return self


class FonteResposta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal[
        "mysql",
        "corpus",
        "memoria",
        "ferramenta",
        "usuario",
        "sistema",
    ]
    referencia: str
    detalhe: str = ""


class SaidaAgente(BaseModel):
    """
    Objeto devolvido ao chamador.

    Recusas, erros e pedidos de informação também seguem
    este contrato.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "concluido",
        "precisa_informacao",
        "recusado",
        "aguardando_aprovacao",
        "erro",
    ]

    resultado: (
        str
        | dict[str, Any]
        | list[Any]
        | None
    )

    fontes: list[FonteResposta] = Field(
        default_factory=list
    )

    suficiente: bool
    motivo: str
    proxima_acao: str | None = None

    @model_validator(mode="after")
    def conferir_suficiencia(self) -> "SaidaAgente":
        if (
            not self.suficiente
            and not self.motivo.strip()
        ):
            raise ValueError(
                "Uma saída insuficiente precisa declarar "
                "o motivo."
            )

        if (
            self.status == "aguardando_aprovacao"
            and self.proxima_acao is None
        ):
            raise ValueError(
                "A pausa precisa explicar como o humano "
                "responde."
            )

        return self


class DecisaoHumana(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acao: Literal[
        "aprovar",
        "rejeitar",
        "editar",
        "expirar",
    ]

    resumo_plano: str | None = None


class DocumentoRecuperado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento_id: str
    titulo: str
    caminho: str

    status: Literal[
        "vigente",
        "revogado",
    ]

    versao: str
    score: float
    conteudo: str


class ResultadoRecuperacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    suficiente: bool
    consulta: str

    forma: Literal[
        "busca_textual"
    ] = "busca_textual"

    resultados: list[DocumentoRecuperado] = Field(
        default_factory=list
    )

    motivo: str