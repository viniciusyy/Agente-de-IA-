import json
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


PLANO = {
    "feira": "QUA",
    "total_recomendado": 12,
    "recomendacoes": [{"id_produto": 1, "quantidade_recomendada": 12}],
}


def _resposta_modelo(**mensagem):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=Mock(model_dump=Mock(return_value={
            "role": "assistant", **mensagem,
        })))],
        usage=None,
    )


def _chamada(id_, nome, **argumentos):
    return _resposta_modelo(tool_calls=[{
        "id": id_,
        "type": "function",
        "function": {"name": nome, "arguments": json.dumps(argumentos)},
    }])


def _resposta_final(resultado):
    return _resposta_modelo(content=json.dumps({
        "status": "concluido",
        "resultado": resultado,
        "suficiente": True,
        "motivo": "Concluído no teste.",
    }))


class AprovacaoGrafoTest(unittest.TestCase):
    def setUp(self):
        pasta = Path(self.enterContext(TemporaryDirectory()))
        self.memoria = self.enterContext(closing(sqlite3.connect(":memory:", check_same_thread=False)))
        self.memoria.row_factory = sqlite3.Row
        self.enterContext(patch.object(MemoriaLongoPrazo, "_conectar", return_value=self.memoria))
        memoria = MemoriaLongoPrazo(pasta / "memoria.sqlite3")
        self.enterContext(patch.object(graph, "obter_memoria", return_value=memoria))

        checkpoint = self.enterContext(closing(sqlite3.connect(":memory:", check_same_thread=False)))
        self.grafo = graph.construtor.compile(checkpointer=SqliteSaver(checkpoint))
        self.enterContext(patch.object(agent, "grafo", self.grafo))
        config = replace(
            graph.settings, openai_api_key="teste", llm_model="teste",
            log_directory=pasta, default_user_id="teste", default_thread_id="teste-aprovacao",
            agent_max_steps=10, agent_max_tool_calls=8, graph_recursion_limit=24,
        )
        self.enterContext(patch.object(graph, "settings", config))
        self.enterContext(patch.object(agent, "settings", config))
        self.calcular = self.enterContext(patch.object(
            graph, "calcular_recomendacao", return_value={"ok": True, **PLANO},
        ))
        openai = self.enterContext(patch.object(graph, "OpenAI"))
        self.modelo = openai.return_value.chat.completions.create
        self.agente = agent.AgentePlanejamento()

    def _preparar_e_pausar(self, *respostas_seguintes):
        self.modelo.side_effect = [
            _chamada("calc-1", "calcular_recomendacao", codigo_feira="QUA"),
            _resposta_final("Recomendação pronta."),
            _chamada("reg-1", "registrar_plano", resumo_plano="Original"),
            *respostas_seguintes,
        ]
        recomendacao = self.agente.executar("Calcule uma recomendação para QUA.")
        self.assertEqual(recomendacao["saida"]["status"], "concluido")
        self.assertEqual(recomendacao["saida"]["resultado"], PLANO)
        pausa = self.agente.executar("Registre o plano anterior.")
        self.assertEqual(pausa["saida"]["status"], "aguardando_aprovacao")
        self.assertEqual(self._planos(), [])

    def _planos(self):
        return self.memoria.execute(
            "SELECT idempotency_key, payload_json FROM planos_aprovados"
        ).fetchall()

    def _evento_registro(self, retorno):
        log = json.loads(Path(retorno["log"]).read_text(encoding="utf-8"))
        eventos = [e for e in log["trajetoria"] if e.get("ferramenta") == "registrar_plano"]
        self.assertEqual(len(eventos), 1)
        return eventos[0], [e["no"] for e in log["trajetoria"]]

    def test_rejeicao_encerra_sem_modelo_e_sem_gravar(self):
        self._preparar_e_pausar()
        chamadas_antes = self.modelo.call_count

        resposta = self.agente.retomar({"acao": "rejeitar"})

        self.assertEqual(resposta["saida"]["status"], "recusado")
        self.assertEqual(resposta["motivo_termino"], "RECUSADO")
        self.assertFalse(resposta["saida"]["suficiente"])
        self.assertIsNone(resposta["interrupcao"])
        self.assertEqual(self.modelo.call_count, chamadas_antes)
        self.assertEqual(self._planos(), [])
        evento, nos = self._evento_registro(resposta)
        self.assertIs(evento["ok"], False)
        self.assertEqual(evento["erro"]["codigo"], "APROVACAO_REJEITADA")
        self.assertNotIn("chamar_modelo", nos)
        self.assertIn("validar_saida", nos)

        estado = self.grafo.get_state({"configurable": {"thread_id": "teste-aprovacao"}})
        ferramenta, final = estado.values["mensagens"][-2:]
        self.assertEqual((ferramenta["role"], ferramenta["tool_call_id"]), ("tool", "reg-1"))
        self.assertEqual(final["role"], "assistant")
        self.assertEqual(json.loads(final["content"])["status"], "recusado")

    def test_editar_e_repetir_registro_mantem_idempotencia(self):
        self._preparar_e_pausar(
            _resposta_final("Plano registrado."),
            _chamada("reg-2", "registrar_plano", resumo_plano="Original"),
            _resposta_final("Plano já registrado."),
        )
        decisao = {"acao": "editar", "resumo_plano": "Revisado pelo proprietário"}
        resposta = self.agente.retomar(decisao)
        self.assertEqual(resposta["saida"]["status"], "concluido")
        evento, _ = self._evento_registro(resposta)
        self.assertIs(evento["ja_existia"], False)
        primeiro, = self._planos()
        payload = json.loads(primeiro["payload_json"])
        self.assertEqual(payload["resumo_plano"], decisao["resumo_plano"])
        self.assertEqual(payload["plano"], PLANO["recomendacoes"])

        pausa = self.agente.executar("Tente registrar o mesmo plano novamente.")
        self.assertEqual(pausa["saida"]["status"], "aguardando_aprovacao")
        resposta = self.agente.retomar(decisao)
        self.assertEqual(resposta["saida"]["status"], "concluido")
        evento, _ = self._evento_registro(resposta)
        self.assertIs(evento["ja_existia"], True)
        self.assertEqual(self._planos(), [primeiro])
        self.calcular.assert_called_once_with("QUA")

    def test_texto_do_modelo_nao_perde_plano_nem_contamina_outro_turno(self):
        self.modelo.side_effect = [
            _chamada("calc-1", "calcular_recomendacao", codigo_feira="QUA"),
            _resposta_modelo(content="A recomendação está pronta."),
            _resposta_final("Resposta sem novo cálculo."),
        ]
        recomendacao = self.agente.executar("Calcule uma recomendação para QUA.")
        self.assertEqual(recomendacao["saida"]["resultado"], PLANO)

        resposta = self.agente.executar("Só confirme que entendeu.")
        self.assertEqual(resposta["saida"]["resultado"], "Resposta sem novo cálculo.")
        self.calcular.assert_called_once_with("QUA")

    def test_calculo_bem_sucedido_nao_substitui_recusa(self):
        self.modelo.side_effect = [
            _chamada("calc-1", "calcular_recomendacao", codigo_feira="QUA"),
            _resposta_modelo(content=json.dumps({
                "status": "recusado",
                "resultado": None,
                "suficiente": False,
                "motivo": "Não posso recomendar nessa condição.",
            })),
        ]
        resposta = self.agente.executar("Calcule uma recomendação para QUA.")
        self.assertEqual(resposta["saida"]["status"], "recusado")
        self.assertIsNone(resposta["saida"]["resultado"])

    def test_registro_no_mesmo_turno_preserva_confirmacao_do_registro(self):
        self.modelo.side_effect = [
            _chamada("calc-1", "calcular_recomendacao", codigo_feira="QUA"),
            _chamada("reg-1", "registrar_plano", resumo_plano="Original"),
            _resposta_final("Plano registrado."),
        ]
        pausa = self.agente.executar("Calcule e registre uma recomendação para QUA.")
        self.assertEqual(pausa["saida"]["status"], "aguardando_aprovacao")
        self.assertEqual(self._planos(), [])

        resposta = self.agente.retomar({"acao": "aprovar"})
        self.assertEqual(resposta["saida"]["resultado"], "Plano registrado.")
        self.assertEqual(len(self._planos()), 1)

    def test_capacidade_zero_recusa_antes_do_modelo_e_do_calculo(self):
        resposta = self.agente.executar(
            "Para a feira DOM_C, minha capacidade é zero. "
            "Só gere um plano se for possível respeitar esse limite."
        )

        self.assertEqual(resposta["saida"]["status"], "recusado")
        self.assertEqual(resposta["motivo_termino"], "RECUSADO")
        self.assertFalse(resposta["saida"]["suficiente"])
        self.assertIsNone(resposta["saida"]["resultado"])
        self.assertIsNone(resposta["interrupcao"])
        self.assertEqual(resposta["chamadas_ferramenta"], 0)
        self.modelo.assert_not_called()
        self.calcular.assert_not_called()
        self.assertEqual(self._planos(), [])

        log = json.loads(Path(resposta["log"]).read_text(encoding="utf-8"))
        self.assertIn(
            {"no": "recusar_capacidade_zero", "codigo": "CAPACIDADE_TOTAL_ZERO"},
            log["trajetoria"],
        )

    def test_totais_da_operacao_vem_da_ferramenta_e_nao_do_modelo(self):
            consulta = {
                "ok": True,
                "id_operacao": 101,
                "fonte": "mysql:teste.operacoes/101",
                "dados": [
                    {
                        "quantidade_produzida": 12,
                        "quantidade_vendida": 7,
                        "quantidade_sobra": 2,
                    },
                    {
                        "quantidade_produzida": 8,
                        "quantidade_vendida": None,
                        "quantidade_sobra": 1,
                    },
                    {
                        "quantidade_produzida": 6,
                        "quantidade_vendida": 0,
                        "quantidade_sobra": 4,
                    },
                ],
            }
            self.modelo.side_effect = [
                _chamada("op-1", "consultar_operacao", id_operacao=101),
                _resposta_final({
                    "id_operacao": 101,
                    "total_produzido": 999,
                    "total_vendido": "999",
                    "total_sobra": 999,
                }),
                _resposta_final("Sem nova consulta."),
            ]

            with patch.object(graph, "consultar_operacao", return_value=consulta) as consultar:
                resposta = self.agente.executar("Consulte os totais da operação 101.")
                seguinte = self.agente.executar("Apenas confirme que entendeu.")

            consultar.assert_called_once_with(101)
            self.assertEqual(resposta["saida"]["status"], "concluido")
            self.assertEqual(resposta["saida"]["resultado"], {
                "id_operacao": 101,
                "total_produzido": 26,
                "total_vendido": 14,
                "total_sobra": 7,
            })
            self.assertEqual(seguinte["saida"]["resultado"], "Sem nova consulta.")

    def test_calendario_extrai_dia_e_cita_regra_vigente(self):
        with patch.object(
            graph, "buscar_conhecimento", wraps=graph.buscar_conhecimento
        ) as buscar:
            resposta = self.agente.executar(
                "Em que dia da semana ocorre a produção da feira QUA?"
            )

        buscar.assert_called_once()
        self.modelo.assert_not_called()
        saida = resposta["saida"]
        self.assertEqual(saida["status"], "concluido")
        self.assertEqual(saida["resultado"]["dia_producao"], "terça-feira")
        self.assertEqual(saida["resultado"]["dia_venda"], "quarta-feira")
        self.assertTrue(
            any(f["referencia"].endswith("#regras_feiras_v2") for f in saida["fontes"])
        )

    def test_produto_restrito_consulta_regra_e_recusa_sem_calcular(self):
        with patch.object(
            graph, "buscar_conhecimento", wraps=graph.buscar_conhecimento
        ) as buscar:
            resposta = self.agente.executar(
                "Calcule uma recomendação para a feira SAB_E, mas inclua "
                "pastel de frango porque eu quero produzir esse produto."
            )

        buscar.assert_called_once()
        self.modelo.assert_not_called()
        self.calcular.assert_not_called()
        saida = resposta["saida"]
        self.assertEqual(saida["status"], "recusado")
        self.assertFalse(saida["suficiente"])
        self.assertIn("código 5", saida["motivo"])
        self.assertTrue(
            any(f["referencia"].endswith("#regras_feiras_v2") for f in saida["fontes"])
        )
        log = json.loads(Path(resposta["log"]).read_text(encoding="utf-8"))
        ferramentas = [evento["ferramenta"] for evento in log["trajetoria"]
                       if "ferramenta" in evento]
        self.assertEqual(ferramentas, ["buscar_conhecimento"])

    def test_busca_insuficiente_nao_inventa_regra_nem_citacao(self):
        with patch.object(
            graph,
            "buscar_conhecimento",
            return_value={"ok": True, "suficiente": False, "resultados": []},
        ):
            resposta = self.agente.executar(
                "Em que dia da semana ocorre a produção da feira QUA?"
            )

        saida = resposta["saida"]
        self.assertEqual(saida["status"], "recusado")
        self.assertIsNone(saida["resultado"])
        self.assertFalse(any(f["tipo"] == "corpus" for f in saida["fontes"]))
        self.modelo.assert_not_called()

    def test_frango_com_catupiri_nao_e_confundido_com_frango_simples(self):
        pedido = graph.detectar_pedido_regra(
            "Calcule uma recomendação para SAB_E, mas inclua pastel de frango com catupiri."
        )
        self.assertIsNone(pedido)