"""Traces do grafo real com fontes locais e sem conexões externas."""

import json
import os
import sqlite3
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langgraph.checkpoint.sqlite import SqliteSaver

from src import agent, graph
from src.memory import MemoriaLongoPrazo
from src.observabilidade import PERGUNTA_DEMO


PRIVADO = "DETALHE-PRIVADO-NAO-EXPORTAR"
PLANO = {
    "ok": True,
    "feira": "QUA",
    "total_recomendado": 12,
    "recomendacoes": [
        {"id_produto": 1, "quantidade_recomendada": 12, "observacoes": PRIVADO},
    ],
}


def _modelo(*, uso=True, **mensagem):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=Mock(model_dump=Mock(return_value={
            "role": "assistant", **mensagem,
        })))],
        model="modelo-retornado",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5) if uso else None,
    )


def _chamar(nome, **argumentos):
    return _modelo(tool_calls=[{
        "id": f"call-{nome}-{PRIVADO}",
        "type": "function",
        "function": {"name": nome, "arguments": json.dumps(argumentos)},
    }])


def _final(status="concluido", *, suficiente=True, uso=True):
    return _modelo(uso=uso, content=json.dumps({
        "status": status,
        "resultado": "Resposta do teste " + PRIVADO,
        "suficiente": suficiente,
        "motivo": "Resultado de teste",
    }))


class ObservabilidadeTest(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(self.enterContext(TemporaryDirectory()))
        self.traces = self.pasta / "traces"
        self.enterContext(patch.dict(os.environ, {
            "PASTEIS_TRACE_DIR": str(self.traces),
            "PASTEIS_TRACE_VERSAO": "codigo-teste",
            "PASTEIS_TRACE_COORTE": "teste",
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "OTEL_SDK_DISABLED": "false",
        }))
        self.config = replace(
            graph.settings,
            openai_api_key=PRIVADO,
            llm_model="modelo-teste",
            llm_base_url="https://api.openai.com/v1",
            log_directory=self.pasta / "logs",
            default_user_id="proprietario",
            default_thread_id="thread-" + PRIVADO,
            llm_input_price_per_million=2.0,
            llm_output_price_per_million=4.0,
            agent_max_steps=10,
            agent_max_tool_calls=8,
            agent_max_tokens=10_000,
            agent_max_cost_usd=1,
            agent_max_time_seconds=90,
            graph_recursion_limit=24,
        )
        for modulo in (agent, graph):
            self.enterContext(patch.object(modulo, "settings", self.config))

        self.memoria = MemoriaLongoPrazo(self.pasta / "memoria.sqlite3")
        self.enterContext(patch.object(graph, "obter_memoria", return_value=self.memoria))
        self.checkpoint = self.pasta / "checkpoint.sqlite3"
        self.conn = self._conexao()
        self.enterContext(patch.object(agent, "grafo", self._grafo(self.conn)))

        openai = self.enterContext(patch.object(graph, "OpenAI"))
        self.modelo = openai.return_value.chat.completions.create
        self.modelo.side_effect = AssertionError("Nenhuma chamada ao modelo foi planejada neste teste")
        self.enterContext(patch(
            "mysql.connector.connect", side_effect=AssertionError("Não consulte o MySQL"),
        ))
        self.agente = agent.AgentePlanejamento()

    def _conexao(self):
        return self.enterContext(closing(sqlite3.connect(self.checkpoint, check_same_thread=False)))

    def _grafo(self, conexao):
        return graph.construtor.compile(checkpointer=SqliteSaver(conexao))

    def _spans(self):
        linhas = [
            linha
            for arquivo in self.traces.glob("otel-*.jsonl")
            for linha in arquivo.read_text(encoding="utf-8").splitlines()
        ]
        self.assertNotIn(PRIVADO, "\n".join(linhas))
        return [json.loads(linha) for linha in linhas]

    def _raizes(self):
        return [span for span in self._spans() if span["parent_id"] is None]

    @staticmethod
    def _evento(raiz, nome):
        return next(evento for evento in raiz["events"] if evento["name"] == nome)

    def test_off_por_padrao_preserva_retorno_e_log(self):
        with patch.dict(os.environ, {"PASTEIS_TRACE_DIR": ""}):
            retorno = self.agente.executar(PERGUNTA_DEMO)

        self.assertEqual(retorno["motivo_termino"], "CONCLUIDO")
        self.assertTrue(Path(retorno["log"]).is_file())
        self.assertFalse(self.traces.exists())
        self.modelo.assert_not_called()

    def test_rota_direta_cita_corpus_com_um_span_filho_sem_chat(self):
        retorno = self.agente.executar(PERGUNTA_DEMO)
        raiz, = self._raizes()
        ferramenta, = [span for span in self._spans() if span["parent_id"] is not None]

        self.assertEqual(raiz["name"], "invoke_agent pasteis-miyata")
        self.assertEqual(raiz["resource"]["attributes"]["service.version"], "codigo-teste")
        self.assertEqual(raiz["attributes"]["pasteis.entrada.pergunta_demo"], PERGUNTA_DEMO)
        self.assertEqual(raiz["attributes"]["pasteis.execucao.custo_estimado_usd"], 0)
        self.assertEqual(raiz["attributes"]["pasteis.execucao.chamadas_modelo"], 0)
        self.assertFalse(raiz["attributes"]["pasteis.saida.normalizada"])
        self.assertEqual(ferramenta["name"], "execute_tool buscar_conhecimento")
        self.assertEqual(ferramenta["parent_id"], raiz["context"]["span_id"])
        self.assertEqual(ferramenta["context"]["trace_id"], raiz["context"]["trace_id"])

        atributos = self._evento(raiz, "rag.decisao")["attributes"]
        documento = json.loads(atributos["pasteis.rag.documento_usado"])
        self.assertEqual(documento["documento_id"], "glossario_dados_v1")
        self.assertEqual(json.loads(atributos["pasteis.rag.resultado"]), {"prova_falta": False})
        self.assertFalse(retorno["saida"]["resultado"]["prova_falta"])
        self.modelo.assert_not_called()
        self.assertNotIn("conteudo", json.dumps(self._spans()))

    def test_recusa_de_regra_registra_ref_e_nao_chama_calculo(self):
        retorno = self.agente.executar(
            "Calcule uma recomendação para SAB_E, mas inclua pastel de frango."
        )
        raiz, = self._raizes()
        self.assertEqual(retorno["saida"]["status"], "recusado")

        evento = self._evento(raiz, "rag.decisao")["attributes"]
        self.assertEqual(evento["pasteis.rag.produto"], "frango")
        documento = json.loads(evento["pasteis.rag.documento_usado"])
        self.assertEqual(documento["documento_id"], "regras_feiras_v2")
        self.assertEqual(len(self._spans()), 2)
        self.modelo.assert_not_called()

    def test_modelo_e_ferramenta_com_uso_resumo_e_custo_da_raiz(self):
        self.modelo.side_effect = [_chamar("calcular_recomendacao", codigo_feira="QUA"), _final()]
        with patch.object(graph, "calcular_recomendacao", return_value=PLANO) as calcular:
            retorno = self.agente.executar(f"Calcule uma recomendação para QUA. {PRIVADO}")
        calcular.assert_called_once_with("QUA")

        raiz, = self._raizes()
        attrs = raiz["attributes"]
        self.assertEqual(attrs["pasteis.execucao.categoria_termino"], "respondeu")
        self.assertEqual(attrs["pasteis.execucao.chamadas_modelo"], 2)
        self.assertAlmostEqual(attrs["pasteis.execucao.custo_estimado_usd"], 0.00008)
        self.assertGreater(attrs["pasteis.execucao.latencia_ms"], 0)
        self.assertEqual(len(attrs["pasteis.prompt.orquestrador.sha256"]), 64)

        chats = [s for s in self._spans() if s["name"].startswith("chat ")]
        self.assertEqual(len(chats), 2)
        for span in chats:
            self.assertEqual(span["parent_id"], raiz["context"]["span_id"])
            self.assertEqual(span["attributes"]["gen_ai.provider.name"], "openai")
            self.assertEqual(span["attributes"]["gen_ai.response.model"], "modelo-retornado")
            self.assertEqual(span["attributes"]["gen_ai.usage.input_tokens"], 10)
            self.assertEqual(span["attributes"]["gen_ai.usage.output_tokens"], 5)

        span, = [s for s in self._spans() if s["name"].startswith("execute_tool")]
        campos = json.loads(span["attributes"]["pasteis.ferramenta.resultado"])
        self.assertEqual(
            campos["recomendacoes"], [{"id_produto": 1, "quantidade_recomendada": 12}],
        )
        self.assertEqual(span["attributes"]["pasteis.ferramenta.desfecho"], "ok")
        self.assertEqual(retorno["saida"]["resultado"]["total_recomendado"], 12)

    def test_normalizacao_e_uso_ausente_nao_parecem_saudaveis(self):
        self.modelo.side_effect = [_modelo(uso=False, content=PRIVADO)]
        retorno = self.agente.executar("Pedido que usa o modelo")
        raiz, = self._raizes()
        attrs = raiz["attributes"]

        self.assertEqual(retorno["motivo_termino"], "CONCLUIDO")
        self.assertTrue(attrs["pasteis.saida.normalizada"])
        self.assertFalse(attrs["pasteis.execucao.custo_completo"])
        self.assertNotIn("pasteis.execucao.custo_estimado_usd", attrs)

    def test_limite_de_passos_nao_aparece_como_erro_tecnico(self):
        self.modelo.side_effect = [_chamar("calcular_recomendacao", codigo_feira="QUA")]
        with (
            patch.object(graph, "settings", replace(self.config, agent_max_steps=1)),
            patch.object(graph, "calcular_recomendacao", return_value=PLANO),
        ):
            retorno = self.agente.executar("Calcule recomendação para QUA.")

        raiz, = self._raizes()
        self.assertEqual(retorno["motivo_termino"], "LIMITE_DE_PASSOS")
        attrs = raiz["attributes"]
        self.assertEqual(attrs["pasteis.execucao.categoria_termino"], "orcamento_esgotado")
        self.assertEqual(attrs["pasteis.execucao.chamadas_modelo"], 1)
        self.assertEqual(attrs["pasteis.execucao.erros_tecnicos"], 0)

    def test_modelo_com_erro_nao_exporta_mensagem_nem_stacktrace(self):
        self.modelo.side_effect = TimeoutError(PRIVADO)
        retorno = self.agente.executar("Preciso de ajuda")
        self.assertEqual(retorno["motivo_termino"], "ERRO_DO_MODELO")

        raiz, = self._raizes()
        chat, = [s for s in self._spans() if s["name"].startswith("chat ")]
        self.assertEqual(chat["attributes"]["error.type"], "TimeoutError")
        self.assertEqual(chat["events"], [])
        self.assertEqual(raiz["attributes"]["pasteis.execucao.erros_tecnicos"], 1)

    def test_operacao_inexistente_e_erro_mysql_sao_distintos(self):
        for codigo, tipo in (
            ("REGISTRO_NAO_ENCONTRADO", "sem_dados"),
            ("ERRO_NA_CONSULTA", "erro_tecnico"),
        ):
            with self.subTest(codigo=codigo):
                self.modelo.side_effect = [
                    _chamar("consultar_operacao", id_operacao=999999),
                    _final("recusado", suficiente=False),
                ]
                with patch.object(graph, "consultar_operacao", return_value={
                    "ok": False,
                    "erro": {"codigo": codigo, "mensagem": PRIVADO},
                }):
                    self.agente.executar("Consulte a operação 999999.")

                ferramenta = [
                    s for s in self._spans() if s["name"] == "execute_tool consultar_operacao"
                ][-1]
                self.assertEqual(ferramenta["attributes"]["pasteis.ferramenta.desfecho"], tipo)
                self.assertEqual(
                    self._raizes()[-1]["attributes"]["pasteis.execucao.erros_tecnicos"],
                    int(tipo == "erro_tecnico"),
                )

    def test_rejeicao_de_preferencia_e_evento_sem_span_de_escrita(self):
        self.modelo.side_effect = [
            _chamar("salvar_preferencia", chave="prioridade", valor="evitar falta"),
            _final("recusado", suficiente=False),
        ]
        self.agente.executar("Só para este pedido, quero evitar falta.")
        raiz, = self._raizes()

        dados = self._evento(raiz, "ferramenta.nao_executada")["attributes"]
        self.assertEqual(dados["pasteis.ferramenta.erro_codigo"], "PREFERENCIA_SEM_AUTORIZACAO")
        self.assertFalse(any(s["name"].startswith("execute_tool") for s in self._spans()))
        self.assertEqual(self.memoria.ler_fatos_semanticos("proprietario"), {})

    def test_falha_de_exportacao_nao_repete_execucao(self):
        abrir = Path.open

        def abrir_com_falha(caminho, *args, **kwargs):
            if caminho.suffix == ".jsonl":
                raise PermissionError(PRIVADO)
            return abrir(caminho, *args, **kwargs)

        buscar = graph.buscar_conhecimento
        with (
            patch.object(Path, "open", abrir_com_falha),
            patch.object(graph, "buscar_conhecimento", wraps=buscar) as busca,
            self.assertLogs("src.observabilidade", level="WARNING") as avisos,
        ):
            retorno = self.agente.executar(PERGUNTA_DEMO)

        busca.assert_called_once()
        self.assertEqual(retorno["saida"]["status"], "concluido")
        self.assertNotIn(PRIVADO, "\n".join(avisos.output))
        self.assertEqual(self._spans(), [])

    def _pausar(self):
        self.modelo.side_effect = [
            _chamar("calcular_recomendacao", codigo_feira="QUA"),
            _final(),
            _chamar("registrar_plano", resumo_plano=PRIVADO),
        ]
        with patch.object(graph, "calcular_recomendacao", return_value=PLANO):
            self.agente.executar("Calcule uma recomendação para QUA.")

        retorno = self.agente.executar("Registre esse plano.")
        self.assertEqual(retorno["saida"]["status"], "aguardando_aprovacao")
        pausa = self._raizes()[-1]
        evt = self._evento(pausa, "aprovacao.solicitada")["attributes"]

        self.assertEqual(json.loads(evt["pasteis.aprovacao.plano"]), {
            "feira": "QUA",
            "total_recomendado": 12,
            "produtos": [{"id_produto": 1, "quantidade_recomendada": 12}],
        })
        self.assertIn("pasteis.aprovacao.expira_em", evt)
        self.assertFalse(any(s["name"] == "execute_tool registrar_plano" for s in self._spans()))
        return pausa

    def test_retomada_apos_reabrir_checkpoint_liga_raizes_e_custo_nao_duplica(self):
        pausa = self._pausar()
        self.conn.close()
        self.modelo.side_effect = [_final()]
        with patch.object(agent, "grafo", self._grafo(self._conexao())):
            retorno = agent.AgentePlanejamento().retomar({
                "acao": "editar", "resumo_plano": PRIVADO,
            })

        retomada = self._raizes()[-1]
        self.assertEqual(retorno["saida"]["status"], "concluido")
        self.assertNotEqual(pausa["context"]["trace_id"], retomada["context"]["trace_id"])
        self.assertEqual(
            pausa["attributes"]["pasteis.aprovacao.id"],
            retomada["attributes"]["pasteis.aprovacao.id"],
        )
        self.assertEqual(retomada["attributes"]["pasteis.execucao.tipo"], "retomada_humana")
        self.assertEqual(retomada["attributes"]["pasteis.execucao.chamadas_modelo"], 1)
        self.assertAlmostEqual(retomada["attributes"]["pasteis.execucao.custo_estimado_usd"], 0.00004)

        decisao = self._evento(retomada, "aprovacao.decidida")
        escrita = self._evento(retomada, "aprovacao.escrita")
        self.assertEqual(decisao["attributes"]["pasteis.aprovacao.decisao"], "editar")
        self.assertEqual(escrita["attributes"]["pasteis.aprovacao.desfecho"], "ok")
        self.assertFalse(escrita["attributes"]["pasteis.aprovacao.ja_existia"])

        registro, = [s for s in self._spans() if s["name"] == "execute_tool registrar_plano"]
        self.assertEqual(registro["parent_id"], retomada["context"]["span_id"])

    def test_rejeicao_humana_nao_registra_erro_nem_span_de_escrita(self):
        self._pausar()
        retorno = self.agente.retomar({"acao": "rejeitar"})
        raiz = self._raizes()[-1]

        self.assertEqual(retorno["motivo_termino"], "RECUSADO")
        self.assertEqual(raiz["attributes"]["pasteis.execucao.erros_tecnicos"], 0)
        self.assertEqual(raiz["attributes"]["pasteis.execucao.chamadas_modelo"], 0)
        self.assertEqual([e["name"] for e in raiz["events"]], ["aprovacao.decidida"])
        self.assertFalse(any(s["name"] == "execute_tool registrar_plano" for s in self._spans()))

    def test_usuario_invalido_ainda_tem_raiz_sem_thread_bruta(self):
        with self.assertRaises(ValueError):
            self.agente.executar("Pedido " + PRIVADO, usuario_id=PRIVADO)

        raiz, = self._raizes()
        self.assertEqual(len(self._spans()), 1)
        self.assertEqual(
            raiz["attributes"]["pasteis.execucao.categoria_termino"], "bloqueado_politica",
        )
        self.assertEqual(
            raiz["attributes"]["pasteis.execucao.motivo_termino"], "USUARIO_NAO_AUTORIZADO",
        )


if __name__ == "__main__":
    unittest.main()