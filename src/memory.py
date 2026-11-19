from __future__ import annotations

import hashlib
import json
import math
import sqlite3

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings
from src.rag import tokenizar
from src.seguranca import (
    ErroSeguranca,
    validar_preferencia,
    validar_resumo_episodio,
)


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def chave_de_conteudo(conteudo: Any) -> str:
    canonico = json.dumps(
        conteudo,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonico.encode("utf-8")
    ).hexdigest()


class MemoriaLongoPrazo:
    """
    Memórias semântica e episódica.

    Essas memórias ficam separadas dos checkpoints do LangGraph.
    """

    def __init__(
        self,
        caminho: Path | None = None,
    ):
        self.caminho = (
            caminho
            or settings.memory_database
        )

        self.caminho.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._inicializar()

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row

        try:
            yield conexao
            conexao.commit()

        except Exception:
            conexao.rollback()
            raise

        finally:
            conexao.close()

    def _inicializar(self) -> None:
        with self._conectar() as conexao:
            conexao.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                memoria_semantica (
                    id INTEGER PRIMARY KEY
                        AUTOINCREMENT,
                    usuario_id TEXT NOT NULL,
                    chave TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    ativo INTEGER NOT NULL
                        DEFAULT 1,
                    UNIQUE(
                        usuario_id,
                        chave,
                        content_hash
                    )
                );

                CREATE INDEX IF NOT EXISTS
                idx_semantica_usuario_chave
                ON memoria_semantica(
                    usuario_id,
                    chave,
                    id DESC
                );

                CREATE TABLE IF NOT EXISTS
                memoria_episodica (
                    id INTEGER PRIMARY KEY
                        AUTOINCREMENT,
                    usuario_id TEXT NOT NULL,
                    resumo TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    ativo INTEGER NOT NULL
                        DEFAULT 1,
                    UNIQUE(
                        usuario_id,
                        content_hash
                    )
                );

                CREATE TABLE IF NOT EXISTS
                planos_aprovados (
                    id INTEGER PRIMARY KEY
                        AUTOINCREMENT,
                    idempotency_key TEXT NOT NULL
                        UNIQUE,
                    usuario_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    criado_em TEXT NOT NULL
                );
                """
            )

    def salvar_fato_semantico(
        self,
        usuario_id: str,
        chave: str,
        valor: str,
    ) -> dict:
        try:
            dados = validar_preferencia(
                chave,
                valor,
            )

        except ErroSeguranca as erro:
            return erro.como_resultado()

        chave = dados["chave"]
        valor = dados["valor"]

        conteudo = {
            "usuario_id": usuario_id,
            "chave": chave,
            "valor": valor,
        }

        content_hash = chave_de_conteudo(
            conteudo
        )

        with self._conectar() as conexao:
            existente = conexao.execute(
                """
                SELECT id
                FROM memoria_semantica
                WHERE usuario_id = ?
                  AND chave = ?
                  AND content_hash = ?
                """,
                (
                    usuario_id,
                    chave,
                    content_hash,
                ),
            ).fetchone()

            if existente:
                return {
                    "ok": True,
                    "ja_existia": True,
                    "chave": chave,
                    "content_hash": content_hash,
                }

            # Uma contradição cria uma nova versão.
            # A versão anterior não é apagada.
            conexao.execute(
                """
                INSERT INTO memoria_semantica (
                    usuario_id,
                    chave,
                    valor,
                    content_hash,
                    criado_em
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    usuario_id,
                    chave,
                    valor,
                    content_hash,
                    agora_iso(),
                ),
            )

        return {
            "ok": True,
            "ja_existia": False,
            "chave": chave,
            "content_hash": content_hash,
        }

    def ler_fatos_semanticos(
        self,
        usuario_id: str,
    ) -> dict[str, str]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                """
                SELECT chave, valor, content_hash
                FROM memoria_semantica
                WHERE usuario_id = ?
                  AND ativo = 1
                ORDER BY id DESC
                """,
                (usuario_id,),
            ).fetchall()

        fatos = {}

        for linha in linhas:
            try:
                dados = validar_preferencia(
                    linha["chave"],
                    linha["valor"],
                )

            except ErroSeguranca:
                # Não apaga registros antigos.
                # Apenas impede sua entrada no contexto.
                continue

            esperado = chave_de_conteudo(
                {
                    "usuario_id": usuario_id,
                    **dados,
                }
            )

            if esperado == linha["content_hash"]:
                fatos.setdefault(
                    dados["chave"],
                    dados["valor"],
                )

        return fatos

    def salvar_episodio(
        self,
        usuario_id: str,
        resumo: str,
        tags: list[str] | None = None,
    ) -> dict:
        try:
            resumo = validar_resumo_episodio(
                resumo
            )

        except ErroSeguranca as erro:
            return erro.como_resultado()

        # Tags livres não entram na memória.
        # A tag é derivada do esquema permitido.
        tags = ["plano_calculado_v1"]

        conteudo = {
            "usuario_id": usuario_id,
            "resumo": resumo.strip(),
            "tags": tags,
        }

        content_hash = chave_de_conteudo(
            conteudo
        )

        with self._conectar() as conexao:
            cursor = conexao.execute(
                """
                INSERT OR IGNORE INTO
                    memoria_episodica (
                        usuario_id,
                        resumo,
                        tags_json,
                        content_hash,
                        criado_em
                    )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    usuario_id,
                    resumo.strip(),
                    json.dumps(
                        tags,
                        ensure_ascii=False,
                    ),
                    content_hash,
                    agora_iso(),
                ),
            )

        return {
            "ok": True,
            "ja_existia": cursor.rowcount == 0,
            "content_hash": content_hash,
        }

    def buscar_episodios(
        self,
        usuario_id: str,
        consulta: str,
        limite: int = 3,
    ) -> list[dict]:
        termos_consulta = set(
            tokenizar(consulta)
        )

        if not termos_consulta:
            return []

        with self._conectar() as conexao:
            linhas = conexao.execute(
                """
                SELECT
                    resumo,
                    tags_json,
                    content_hash,
                    criado_em
                FROM memoria_episodica
                WHERE usuario_id = ?
                  AND ativo = 1
                """,
                (usuario_id,),
            ).fetchall()

        agora = datetime.now(timezone.utc)
        resultados = []

        for linha in linhas:
            try:
                resumo_seguro = validar_resumo_episodio(
                    linha["resumo"]
                )

                criado = datetime.fromisoformat(
                    linha["criado_em"]
                )

                if criado.tzinfo is None:
                    continue

            except (
                ErroSeguranca,
                ValueError,
                TypeError,
            ):
                continue

            esperado = chave_de_conteudo(
                {
                    "usuario_id": usuario_id,
                    "resumo": resumo_seguro,
                    "tags": ["plano_calculado_v1"],
                }
            )

            if esperado != linha["content_hash"]:
                continue

            termos = set(
                tokenizar(resumo_seguro)
            )

            uniao = (
                termos_consulta
                | termos
            )

            similaridade = (
                len(termos_consulta & termos)
                / len(uniao)
                if uniao
                else 0.0
            )

            idade_dias = max(
                (agora - criado).total_seconds()
                / 86_400,
                0.0,
            )

            # O decaimento rebaixa a relevância,
            # mas não apaga a memória.
            fator_temporal = math.pow(
                0.5,
                idade_dias
                / settings.memory_episode_half_life_days,
            )

            score = (
                similaridade
                * fator_temporal
            )

            if score > 0:
                resultados.append(
                    {
                        "resumo": resumo_seguro,
                        "content_hash": linha["content_hash"],
                        "criado_em": linha["criado_em"],
                        "score": round(score, 6),
                    }
                )

        resultados.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return resultados[:limite]

    def registrar_plano_idempotente(
        self,
        usuario_id: str,
        thread_id: str,
        payload: dict,
    ) -> dict:
        idempotency_key = chave_de_conteudo(
            payload
        )

        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )

        with self._conectar() as conexao:
            existente = conexao.execute(
                """
                SELECT id, criado_em
                FROM planos_aprovados
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if existente:
                return {
                    "ok": True,
                    "ja_existia": True,
                    "registro_id": existente["id"],
                    "idempotency_key": idempotency_key,
                    "criado_em": existente["criado_em"],
                }

            cursor = conexao.execute(
                """
                INSERT INTO planos_aprovados (
                    idempotency_key,
                    usuario_id,
                    thread_id,
                    payload_json,
                    criado_em
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    idempotency_key,
                    usuario_id,
                    thread_id,
                    payload_json,
                    agora_iso(),
                ),
            )

            registro_id = cursor.lastrowid

        return {
            "ok": True,
            "ja_existia": False,
            "registro_id": registro_id,
            "idempotency_key": idempotency_key,
        }

    def contar_planos_por_chave(
        self,
        idempotency_key: str,
    ) -> int:
        with self._conectar() as conexao:
            linha = conexao.execute(
                """
                SELECT COUNT(*) AS total
                FROM planos_aprovados
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

        return int(linha["total"])


_memoria: MemoriaLongoPrazo | None = None


def obter_memoria() -> MemoriaLongoPrazo:
    global _memoria

    if _memoria is None:
        _memoria = MemoriaLongoPrazo()

    return _memoria