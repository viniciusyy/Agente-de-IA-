from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from src.config import settings
from src.graph import grafo
from src.schemas import (
    DecisaoHumana,
    EntradaAgente,
    SaidaAgente,
)


class AgentePlanejamento:
    """
    Fachada do agente utilizada pelo terminal, pelos testes e por
    futuros consumidores HTTP ou MCP.

    A classe esconde os detalhes do LangGraph e sempre devolve
    uma estrutura padronizada para quem utiliza o sistema.
    """

    def _config(
        self,
        thread_id: str,
    ) -> dict:
        """
        Produz a configuração de uma conversa persistente.

        O thread_id identifica qual checkpoint deve ser carregado.
        """
        return {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": (
                settings.graph_recursion_limit
            ),
        }

    def _tamanho_trajetoria(
        self,
        thread_id: str,
    ) -> int:
        """
        Consulta o checkpoint para identificar onde começa a
        trajetória da execução atual.
        """
        try:
            snapshot = grafo.get_state(
                self._config(thread_id)
            )

            return len(
                snapshot.values.get(
                    "trajetoria",
                    [],
                )
            )

        except Exception:
            return 0

    def _interrupcao(
        self,
        resultado: dict,
    ) -> dict | None:
        """
        Extrai uma interrupção produzida pelo LangGraph.
        """
        interrupcoes = (
            resultado.get("__interrupt__")
            or []
        )

        if not interrupcoes:
            return None

        primeira = interrupcoes[0]

        if hasattr(primeira, "value"):
            return primeira.value

        return primeira

    def _salvar_log(
        self,
        *,
        entrada: dict,
        resultado: dict,
        inicio_trajetoria: int,
        tipo: str,
    ) -> str:
        """
        Registra entrada, saída, trajetória, custos, modelo,
        prompts e motivo de término.
        """
        settings.log_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        nome_arquivo = (
            "execucao_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )
            + ".json"
        )

        caminho = (
            settings.log_directory
            / nome_arquivo
        )

        interrupcao = self._interrupcao(
            resultado
        )

        motivo_termino = (
            "AGUARDANDO_APROVACAO"
            if interrupcao
            else resultado.get(
                "motivo_termino",
                "SEM_MOTIVO",
            )
        )

        conteudo = {
            "data_hora": (
                datetime.now().isoformat()
            ),
            "tipo": tipo,
            "entrada": entrada,
            "modelo": settings.llm_model,
            "base_url": settings.llm_base_url,
            "prompt_versions": {
                "orquestrador": (
                    "orquestrador_v2"
                ),
                "procedural": (
                    "procedimento_planejamento_v1"
                ),
            },
            "parametros": {
                "graph_recursion_limit": (
                    settings.graph_recursion_limit
                ),
                "agent_max_steps": (
                    settings.agent_max_steps
                ),
                "agent_max_tool_calls": (
                    settings.agent_max_tool_calls
                ),
                "agent_max_tokens": (
                    settings.agent_max_tokens
                ),
                "agent_max_time_seconds": (
                    settings.agent_max_time_seconds
                ),
                "agent_max_cost_usd": (
                    settings.agent_max_cost_usd
                ),
            },
            "saida": resultado.get(
                "resposta_validada"
            ),
            "interrupcao": interrupcao,
            "motivo_termino": motivo_termino,
            "passos": resultado.get(
                "passos_turno",
                0,
            ),
            "chamadas_ferramenta": (
                resultado.get(
                    "chamadas_ferramenta_turno",
                    0,
                )
            ),
            "tokens_entrada": resultado.get(
                "tokens_entrada_turno",
                0,
            ),
            "tokens_saida": resultado.get(
                "tokens_saida_turno",
                0,
            ),
            "custo_estimado_usd": round(
                resultado.get(
                    "custo_turno_usd",
                    0.0,
                ),
                8,
            ),
            "trajetoria": resultado.get(
                "trajetoria",
                [],
            )[inicio_trajetoria:],
        }

        caminho.write_text(
            json.dumps(
                conteudo,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return str(caminho)

    def _formatar_retorno(
        self,
        resultado: dict,
        log: str,
    ) -> dict:
        """
        Converte o estado interno do grafo para o contrato utilizado
        pelo terminal e pelos testes.
        """
        interrupcao = self._interrupcao(
            resultado
        )

        if interrupcao:
            saida = SaidaAgente(
                status="aguardando_aprovacao",
                resultado=interrupcao,
                fontes=[],
                suficiente=True,
                motivo=(
                    "O grafo foi pausado antes "
                    "da operação de escrita."
                ),
                proxima_acao=(
                    "Responda aprovar, rejeitar "
                    "ou editar. A aprovação expira "
                    "no horário indicado."
                ),
            )

            motivo = "AGUARDANDO_APROVACAO"

        else:
            resposta_validada = (
                resultado.get(
                    "resposta_validada"
                )
                or {
                    "status": "erro",
                    "resultado": None,
                    "fontes": [],
                    "suficiente": False,
                    "motivo": (
                        "O grafo terminou sem produzir "
                        "o contrato de saída."
                    ),
                }
            )

            saida = SaidaAgente.model_validate(
                resposta_validada
            )

            motivo = resultado.get(
                "motivo_termino",
                "SEM_MOTIVO",
            )

        saida_json = saida.model_dump(
            mode="json"
        )

        return {
            "saida": saida_json,

            # Mantém compatibilidade temporária com consumidores
            # desenvolvidos durante a Parte 1.
            "resposta": json.dumps(
                saida_json,
                ensure_ascii=False,
                indent=2,
            ),

            "motivo_termino": motivo,
            "passos": resultado.get(
                "passos_turno",
                0,
            ),
            "chamadas_ferramenta": (
                resultado.get(
                    "chamadas_ferramenta_turno",
                    0,
                )
            ),
            "tokens_entrada": resultado.get(
                "tokens_entrada_turno",
                0,
            ),
            "tokens_saida": resultado.get(
                "tokens_saida_turno",
                0,
            ),
            "custo_estimado_usd": round(
                resultado.get(
                    "custo_turno_usd",
                    0.0,
                ),
                8,
            ),
            "interrupcao": interrupcao,
            "log": log,
        }

    def executar(
        self,
        texto: str,
        *,
        usuario_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """
        Inicia um novo turno no grafo a partir de texto livre.
        """
        entrada = EntradaAgente(
            texto=texto,
            usuario_id=(
                usuario_id
                or settings.default_user_id
            ),
            thread_id=(
                thread_id
                or settings.default_thread_id
            ),
        )

        inicio_trajetoria = (
            self._tamanho_trajetoria(
                entrada.thread_id
            )
        )

        turno_id = uuid4().hex

        estado_inicial: dict[str, Any] = {
            "mensagens": [
                {
                    "role": "user",
                    "content": entrada.texto,
                }
            ],
            "entrada_texto": entrada.texto,
            "usuario_id": entrada.usuario_id,
            "thread_id": entrada.thread_id,
            "turno_id": turno_id,
            "fontes": [],
            "trajetoria": [],
            "assinaturas_passos": [],
            "passos_turno": 0,
            "chamadas_ferramenta_turno": 0,
            "tokens_entrada_turno": 0,
            "tokens_saida_turno": 0,
            "custo_turno_usd": 0.0,
            "inicio_turno_epoch": time.time(),
            "resposta_validada": None,
            "erro_fatal": None,
            "motivo_termino": "",
        }

        resultado = grafo.invoke(
            estado_inicial,
            self._config(
                entrada.thread_id
            ),
        )

        log = self._salvar_log(
            entrada=entrada.model_dump(),
            resultado=resultado,
            inicio_trajetoria=(
                inicio_trajetoria
            ),
            tipo="nova_entrada",
        )

        return self._formatar_retorno(
            resultado,
            log,
        )

    def retomar(
        self,
        decisao: dict | DecisaoHumana,
        *,
        usuario_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """
        Retoma um checkpoint suspenso com a decisão humana.
        """
        usuario_id = (
            usuario_id
            or settings.default_user_id
        )

        thread_id = (
            thread_id
            or settings.default_thread_id
        )

        if isinstance(
            decisao,
            DecisaoHumana,
        ):
            decisao_validada = decisao

        else:
            decisao_validada = (
                DecisaoHumana.model_validate(
                    decisao
                )
            )

        inicio_trajetoria = (
            self._tamanho_trajetoria(
                thread_id
            )
        )

        comando = Command(
            resume=decisao_validada.model_dump(
                exclude_none=True
            )
        )

        resultado = grafo.invoke(
            comando,
            self._config(thread_id),
        )

        log = self._salvar_log(
            entrada={
                "usuario_id": usuario_id,
                "thread_id": thread_id,
                "decisao": (
                    decisao_validada.model_dump(
                        exclude_none=True
                    )
                ),
            },
            resultado=resultado,
            inicio_trajetoria=(
                inicio_trajetoria
            ),
            tipo="retomada_humana",
        )

        return self._formatar_retorno(
            resultado,
            log,
        )

    def obter_aprovacao_pendente(
        self,
        thread_id: str | None = None,
    ) -> dict | None:
        """
        Verifica se existe uma interrupção aguardando resposta humana.
        """
        thread_id = (
            thread_id
            or settings.default_thread_id
        )

        try:
            snapshot = grafo.get_state(
                self._config(thread_id)
            )

            for tarefa in snapshot.tasks:
                if tarefa.interrupts:
                    primeira = (
                        tarefa.interrupts[0]
                    )

                    if hasattr(
                        primeira,
                        "value",
                    ):
                        return primeira.value

                    return primeira

        except Exception:
            return None

        return None