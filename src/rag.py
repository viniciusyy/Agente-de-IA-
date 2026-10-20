from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.config import RAIZ_PROJETO, settings
from src.schemas import (
    DocumentoRecuperado,
    ResultadoRecuperacao,
)


STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "essa",
    "esse",
    "esta",
    "este",
    "eu",
    "foi",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "qual",
    "que",
    "se",
    "ser",
    "uma",
    "um",
}


EXPANSOES = {
    "quarta": {
        "qua",
    },
    "quinta": {
        "qui",
    },
    "sabado": {
        "sab_c",
        "sab_e",
    },
    "domingo": {
        "dom_c",
        "dom_e",
    },
    "frango": {
        "produto",
        "5",
    },
    "escarola": {
        "produto",
        "15",
    },
    "chuva": {
        "clima",
    },
    "sobras": {
        "sobra",
    },
    "vendas": {
        "vendida",
        "venda",
    },
    "aprovar": {
        "aprovacao",
        "proprietario",
    },

    # Normalização lexical de singular e plural.
    "feira": {
        "feiras",
    },
    "feiras": {
        "feira",
    },
    "codigo": {
        "codigos",
    },
    "codigos": {
        "codigo",
    },
}


def normalizar(texto: str) -> str:
    """
    Converte o texto para letras minúsculas, remove acentos e
    substitui pontuação por espaços.
    """
    sem_acentos = "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            texto.lower(),
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    return re.sub(
        r"[^a-z0-9_]+",
        " ",
        sem_acentos,
    )


def tokenizar(texto: str) -> list[str]:
    """
    Transforma um texto em termos utilizados pelo índice.

    Stopwords são descartadas e alguns termos recebem expansões
    específicas do domínio da Pastéis Miyata.
    """
    tokens = [
        token
        for token in normalizar(
            texto
        ).split()
        if token not in STOPWORDS
    ]

    expandidos = list(tokens)

    for token in tokens:
        expandidos.extend(
            EXPANSOES.get(
                token,
                set(),
            )
        )

    return expandidos


@dataclass(frozen=True)
class Documento:
    """
    Representação interna de um documento do corpus.
    """

    documento_id: str
    titulo: str
    versao: str
    status: str
    caminho: Path
    corpo: str
    tokens: Counter


def _separar_metadados(
    texto: str,
) -> tuple[dict[str, str], str]:
    """
    Separa os metadados localizados entre marcadores ---
    do restante do documento Markdown.
    """
    if not texto.startswith("---\n"):
        return {}, texto

    partes = texto.split(
        "---\n",
        2,
    )

    if len(partes) < 3:
        return {}, texto

    metadados: dict[str, str] = {}

    for linha in partes[1].splitlines():
        if ":" not in linha:
            continue

        chave, valor = linha.split(
            ":",
            1,
        )

        metadados[
            chave.strip()
        ] = valor.strip()

    corpo = partes[2].strip()

    return metadados, corpo


class IndiceTextual:
    """
    Índice lexical em memória para o corpus pequeno do case.

    Não utiliza embeddings nem banco vetorial. A unidade recuperada
    é o documento temático inteiro. Portanto, não existe chunking
    vetorial nem quantidade k de vizinhos.

    O parâmetro limite representa somente a quantidade máxima de
    documentos textuais devolvidos para o agente.
    """

    def __init__(
        self,
        diretorio: Path | None = None,
    ):
        self.diretorio = (
            diretorio
            or settings.corpus_directory
        )

        self.documentos = self._carregar()

    def _carregar(
        self,
    ) -> list[Documento]:
        """
        Carrega os documentos Markdown e constrói o índice lexical.
        """
        documentos: list[Documento] = []

        if not self.diretorio.exists():
            return documentos

        for caminho in sorted(
            self.diretorio.glob("*.md")
        ):
            texto = caminho.read_text(
                encoding="utf-8"
            )

            metadados, corpo = (
                _separar_metadados(texto)
            )

            titulo = metadados.get(
                "titulo",
                caminho.stem,
            )

            # O título também faz parte do índice porque apresenta
            # de forma resumida o assunto principal do documento.
            texto_indexado = (
                titulo
                + " "
                + corpo
                + " "
                + caminho.stem
            )

            documentos.append(
                Documento(
                    documento_id=(
                        metadados.get(
                            "id",
                            caminho.stem,
                        )
                    ),
                    titulo=titulo,
                    versao=(
                        metadados.get(
                            "versao",
                            "1",
                        )
                    ),
                    status=(
                        metadados.get(
                            "status",
                            "vigente",
                        ).lower()
                    ),
                    caminho=caminho,
                    corpo=corpo,
                    tokens=Counter(
                        tokenizar(
                            texto_indexado
                        )
                    ),
                )
            )

        return documentos

    def buscar(
        self,
        consulta: str,
        limite: int | None = None,
        incluir_revogados: bool = False,
    ) -> ResultadoRecuperacao:
        """
        Pesquisa documentos por correspondência lexical ponderada.

        Por padrão, documentos revogados são eliminados antes do
        cálculo do ranking.
        """
        limite = (
            limite
            or settings.rag_max_results
        )

        candidatos = [
            documento
            for documento in self.documentos
            if (
                incluir_revogados
                or documento.status == "vigente"
            )
        ]

        termos = Counter(
            tokenizar(consulta)
        )

        if not candidatos or not termos:
            return ResultadoRecuperacao(
                ok=True,
                suficiente=False,
                consulta=consulta,
                motivo=(
                    "A consulta não produziu "
                    "termos recuperáveis."
                ),
            )

        quantidade_documentos = len(
            candidatos
        )

        frequencia_documental = Counter()

        for termo in termos:
            frequencia_documental[
                termo
            ] = sum(
                1
                for documento in candidatos
                if termo in documento.tokens
            )

        ranqueados: list[
            tuple[float, Documento]
        ] = []

        for documento in candidatos:
            score = 0.0

            tamanho = max(
                sum(
                    documento.tokens.values()
                ),
                1,
            )

            for (
                termo,
                peso_consulta,
            ) in termos.items():
                frequencia_termo = (
                    documento.tokens.get(
                        termo,
                        0,
                    )
                    / tamanho
                )

                quantidade_com_termo = (
                    frequencia_documental.get(
                        termo,
                        0,
                    )
                )

                frequencia_inversa = (
                    math.log(
                        (
                            quantidade_documentos
                            + 1
                        )
                        / (
                            quantidade_com_termo
                            + 1
                        )
                    )
                    + 1
                )

                score += (
                    peso_consulta
                    * frequencia_termo
                    * frequencia_inversa
                )

            if score > 0:
                ranqueados.append(
                    (
                        score,
                        documento,
                    )
                )

        ranqueados.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        selecionados = ranqueados[
            :limite
        ]

        def caminho_publico(
            documento: Documento,
        ) -> str:
            """
            Devolve um caminho relativo ao projeto quando possível.
            """
            try:
                return (
                    documento
                    .caminho
                    .resolve()
                    .relative_to(
                        RAIZ_PROJETO.resolve()
                    )
                    .as_posix()
                )

            except ValueError:
                return (
                    documento
                    .caminho
                    .as_posix()
                )

        resultados = [
            DocumentoRecuperado(
                documento_id=(
                    documento.documento_id
                ),
                titulo=documento.titulo,
                caminho=caminho_publico(
                    documento
                ),
                status=(
                    "revogado"
                    if documento.status
                    == "revogado"
                    else "vigente"
                ),
                versao=documento.versao,
                score=round(
                    score,
                    6,
                ),
                conteudo=(
                    documento.corpo[:2_500]
                ),
            )
            for (
                score,
                documento,
            ) in selecionados
        ]

        suficiente = (
            bool(resultados)
            and resultados[0].score
            >= settings.rag_min_score
        )

        if suficiente:
            motivo = (
                "Foram encontrados documentos "
                "vigentes com termos da consulta."
            )
        else:
            motivo = (
                "Nenhum documento vigente "
                "sustenta a resposta."
            )

        return ResultadoRecuperacao(
            ok=True,
            suficiente=suficiente,
            consulta=consulta,
            resultados=resultados,
            motivo=motivo,
        )


_indice: IndiceTextual | None = None


def obter_indice(
    recarregar: bool = False,
) -> IndiceTextual:
    """
    Devolve uma instância compartilhada do índice.

    O parâmetro recarregar força a reconstrução depois de uma
    alteração realizada nos documentos do corpus.
    """
    global _indice

    if _indice is None or recarregar:
        _indice = IndiceTextual()

    return _indice


def buscar_conhecimento(
    consulta: str,
) -> dict:
    """
    Ferramenta exposta ao agente para consultar o corpus.
    """
    resultado = obter_indice().buscar(
        consulta
    )

    return resultado.model_dump(
        mode="json"
    )