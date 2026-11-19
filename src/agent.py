from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from src import observabilidade as obs
from src.config import settings
from src.graph import grafo
from src.schemas import DecisaoHumana, EntradaAgente, SaidaAgente
from src.seguranca import (
    ErroSeguranca,
    validar_identidade,
    validar_texto_sem_credenciais,
)


class AgentePlanejamento:
    """Fachada do agente utilizada pelo terminal e pelos testes."""

    def _config(self, thread_id: str) -> dict:
        """Configuração da conversa persistente no LangGraph."""
        return {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.graph_recursion_limit,
        }

    def _tamanho_trajetoria(self, thread_id: str) -> int:
        """Identifica onde começa a trajetória do turno atual."""
        try:
            snapshot = grafo.get_state(self._config(thread_id))
            return len(snapshot.values.get("trajetoria", []))
        except Exception:
            return 0

    def _validar_acesso_thread(self, usuario_id: str, thread_id: str) -> bool:
        """Verifica o dono do checkpoint e falha fechado se não puder lê-lo."""
        validar_identidade(usuario_id, settings.default_user_id)
        try:
            snapshot = grafo.get_state(self._config(thread_id))
        except Exception:
            raise ErroSeguranca(
                "CHECKPOINT_INDISPONIVEL",
                "Não foi possível conferir o acesso à conversa.",
            ) from None

        if snapshot.values and snapshot.values.get("usuario_id") != usuario_id:
            raise ErroSeguranca(
                "THREAD_NAO_AUTORIZADA",
                "Conversa de outro usuário técnico.",
            )

        return any(tarefa.interrupts for tarefa in snapshot.tasks)

    def _interrupcao(self, resultado: dict) -> dict | None:
        """Extrai uma interrupção produzida pelo LangGraph."""
        interrupcoes = resultado.get("__interrupt__") or []
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
        """Mantém o log JSON já utilizado pelo terminal e pela avaliação."""
        settings.log_directory.mkdir(parents=True, exist_ok=True)

        nome_arquivo = (
            "execucao_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json"
        )
        caminho = settings.log_directory / nome_arquivo

        interrupcao = self._interrupcao(resultado)
        motivo_termino = (
            "AGUARDANDO_APROVACAO"
            if interrupcao
            else resultado.get("motivo_termino", "SEM_MOTIVO")
        )

        conteudo = {
            "data_hora": datetime.now().isoformat(),
            "tipo": tipo,
            "entrada": entrada,
            "modelo": settings.llm_model,
            "base_url": settings.llm_base_url,
            "prompt_versions": {
                "orquestrador": "orquestrador_v2",
                "procedural": "procedimento_planejamento_v1",
            },
            "parametros": {
                "graph_recursion_limit": settings.graph_recursion_limit,
                "agent_max_steps": settings.agent_max_steps,
                "agent_max_tool_calls": settings.agent_max_tool_calls,
                "agent_max_tokens": settings.agent_max_tokens,
                "agent_max_time_seconds": settings.agent_max_time_seconds,
                "agent_max_cost_usd": settings.agent_max_cost_usd,
            },
            "saida": resultado.get("resposta_validada"),
            "interrupcao": interrupcao,
            "motivo_termino": motivo_termino,
            "passos": resultado.get("passos_turno", 0),
            "chamadas_ferramenta": resultado.get("chamadas_ferramenta_turno", 0),
            "tokens_entrada": resultado.get("tokens_entrada_turno", 0),
            "tokens_saida": resultado.get("tokens_saida_turno", 0),
            "custo_estimado_usd": round(resultado.get("custo_turno_usd", 0.0), 8),
            "trajetoria": resultado.get("trajetoria", [])[inicio_trajetoria:],
        }

        caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(caminho)

    def _formatar_retorno(self, resultado: dict, log: str) -> dict:
        """Converte o estado interno para o contrato usado pelo terminal."""
        interrupcao = self._interrupcao(resultado)

        if interrupcao:
            saida = SaidaAgente(
                status="aguardando_aprovacao",
                resultado=interrupcao,
                fontes=[],
                suficiente=True,
                motivo="O grafo foi pausado antes da operação de escrita.",
                proxima_acao=(
                    "Responda aprovar, rejeitar ou editar. A aprovação expira "
                    "no horário indicado."
                ),
            )
            motivo = "AGUARDANDO_APROVACAO"
        else:
            resposta_validada = resultado.get("resposta_validada") or {
                "status": "erro",
                "resultado": None,
                "fontes": [],
                "suficiente": False,
                "motivo": "O grafo terminou sem produzir o contrato de saída.",
            }
            saida = SaidaAgente.model_validate(resposta_validada)
            motivo = resultado.get("motivo_termino", "SEM_MOTIVO")

        saida_json = saida.model_dump(mode="json")

        return {
            "saida": saida_json,
            # Mantém compatibilidade com consumidores da Parte 1.
            "resposta": json.dumps(saida_json, ensure_ascii=False, indent=2),
            "motivo_termino": motivo,
            "passos": resultado.get("passos_turno", 0),
            "chamadas_ferramenta": resultado.get("chamadas_ferramenta_turno", 0),
            "tokens_entrada": resultado.get("tokens_entrada_turno", 0),
            "tokens_saida": resultado.get("tokens_saida_turno", 0),
            "custo_estimado_usd": round(resultado.get("custo_turno_usd", 0.0), 8),
            "interrupcao": interrupcao,
            "log": log,
        }

    @obs.rastrear_execucao("nova_entrada", lambda: settings)
    def executar(
        self,
        texto: str,
        *,
        usuario_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """Inicia um novo turno no grafo a partir de texto livre."""
        entrada = EntradaAgente(
            texto=texto,
            usuario_id=usuario_id or settings.default_user_id,
            thread_id=thread_id or settings.default_thread_id,
        )

        validar_identidade(entrada.usuario_id, settings.default_user_id)
        validar_texto_sem_credenciais(entrada.texto)

        if self._validar_acesso_thread(entrada.usuario_id, entrada.thread_id):
            raise ErroSeguranca(
                "APROVACAO_PENDENTE",
                "Aprove ou rejeite a ação pendente antes de iniciar outro turno.",
            )

        inicio_trajetoria = self._tamanho_trajetoria(entrada.thread_id)
        turno_id = uuid4().hex

        estado_inicial: dict[str, Any] = {
            "mensagens": [{"role": "user", "content": entrada.texto}],
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
            self._config(entrada.thread_id),
        )

        log = self._salvar_log(
            entrada=entrada.model_dump(),
            resultado=resultado,
            inicio_trajetoria=inicio_trajetoria,
            tipo="nova_entrada",
        )
        return self._formatar_retorno(resultado, log)

    @obs.rastrear_execucao("retomada_humana", lambda: settings)
    def retomar(
        self,
        decisao: dict | DecisaoHumana,
        *,
        usuario_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """Retoma um checkpoint suspenso com a decisão humana."""
        usuario_id = usuario_id or settings.default_user_id
        thread_id = thread_id or settings.default_thread_id

        identificacao = EntradaAgente(
            texto="retomada", usuario_id=usuario_id, thread_id=thread_id
        )
        usuario_id, thread_id = identificacao.usuario_id, identificacao.thread_id
        validar_identidade(usuario_id, settings.default_user_id)

        if isinstance(decisao, DecisaoHumana):
            decisao_validada = decisao
        else:
            decisao_validada = DecisaoHumana.model_validate(decisao)

        if decisao_validada.resumo_plano is not None:
            validar_texto_sem_credenciais(decisao_validada.resumo_plano)

        if not self._validar_acesso_thread(usuario_id, thread_id):
            raise ErroSeguranca(
                "APROVACAO_AUSENTE", "Não existe aprovação pendente nesta conversa."
            )

        inicio_trajetoria = self._tamanho_trajetoria(thread_id)
        comando = Command(resume=decisao_validada.model_dump(exclude_none=True))
        resultado = grafo.invoke(comando, self._config(thread_id))

        log = self._salvar_log(
            entrada={
                "usuario_id": usuario_id,
                "thread_id": thread_id,
                "decisao": decisao_validada.model_dump(exclude_none=True),
            },
            resultado=resultado,
            inicio_trajetoria=inicio_trajetoria,
            tipo="retomada_humana",
        )
        return self._formatar_retorno(resultado, log)

    def obter_aprovacao_pendente(
        self, thread_id: str | None = None
    ) -> dict | None:
        """Verifica se existe uma interrupção aguardando resposta humana."""
        thread_id = thread_id or settings.default_thread_id
        self._validar_acesso_thread(settings.default_user_id, thread_id)

        try:
            snapshot = grafo.get_state(self._config(thread_id))
            for tarefa in snapshot.tasks:
                if tarefa.interrupts:
                    primeira = tarefa.interrupts[0]
                    if hasattr(primeira, "value"):
                        return primeira.value
                    return primeira
        except Exception:
            return None

        return None