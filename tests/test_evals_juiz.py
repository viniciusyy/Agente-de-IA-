import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from evals.juiz import CRITERIOS, avaliar, nova_amostra, validar_amostra


def _amostra() -> dict:
    dados = nova_amostra()
    for indice, saida in enumerate(dados["saidas"], start=1):
        rotulo = "SIM" if indice <= 15 else "NAO"
        saida.update({
            "referencia_execucao": f"execucao-ficticia-{indice}",
            "pergunta": "Pedido fictício, usado somente no teste unitário.",
            "resposta": {"motivo": "Resposta fictícia."},
            "evidencias": [{"referencia": "documento de teste", "trecho": "Trecho de teste."}],
            "revisoes": {
                "tecnica": {"rotulo": rotulo, "nota": "nota-tecnica-nao-enviar"},
                "operacional": {"rotulo": rotulo, "nota": "nota-operacional-nao-enviar"},
            },
            "consenso": {"rotulo": rotulo, "nota": "consenso-nao-enviar"},
        })
    return dados


def _completion(rotulo, *, termino="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=termino,
        message=SimpleNamespace(
            refusal=None,
            content=json.dumps({"rotulo": rotulo, "justificativa": "Justificativa de teste."}),
        ),
    )])


class JuizTest(unittest.TestCase):
    def test_amostra_incompleta_nao_chama_api(self):
        cliente = Mock()
        dados = nova_amostra()
        self.assertEqual(dados["criterios_adocao"], CRITERIOS)
        self.assertEqual(len(dados["saidas"]), 30)
        with self.assertRaisesRegex(ValueError, "Amostra incompleta"):
            avaliar(dados, cliente, modelo="mock")
        cliente.chat.completions.create.assert_not_called()

    def test_matriz_calcula_concordancia_e_nao_envia_rotulos_humanos(self):
        cliente = Mock()
        # 13 VP, 2 FN, 1 FP, 14 VN: 27/30 e revisão ainda pendente.
        rotulos = ["SIM"] * 13 + ["NAO"] * 2 + ["SIM"] + ["NAO"] * 14
        cliente.chat.completions.create.side_effect = [_completion(r) for r in rotulos]
        relatorio = avaliar(_amostra(), cliente, modelo="mock")
        self.assertEqual(relatorio["matriz_humano_por_juiz"], {
            "SIM": {"SIM": 13, "NAO": 2}, "NAO": {"SIM": 1, "NAO": 14},
        })
        self.assertEqual(relatorio["concordancia_pct"], 90.0)
        self.assertTrue(relatorio["atingiu_criterios_numericos"])
        self.assertEqual(relatorio["situacao"], "aguardando_revisao_dos_desacordos")
        self.assertEqual(len(relatorio["desacordos"]), 3)
        self.assertTrue(all(d["classificacao"] is None for d in relatorio["desacordos"]))
        for chamada in cliente.chat.completions.create.call_args_list:
            req = chamada.kwargs
            corpo = json.loads(req["messages"][1]["content"])
            self.assertEqual(set(corpo), {"pergunta", "resposta", "evidencias"})
            self.assertNotIn("nao-enviar", req["messages"][1]["content"])
            self.assertEqual(req["response_format"]["type"], "json_schema")

    def test_limite_de_falsos_positivos_independe_da_concordancia(self):
        cliente = Mock()
        cliente.chat.completions.create.side_effect = (
            [_completion("SIM")] * 17 + [_completion("NAO")] * 13
        )
        relatorio = avaliar(_amostra(), cliente, modelo="mock")
        self.assertGreater(relatorio["concordancia_pct"], 90)
        self.assertEqual(relatorio["falsos_positivos"], 2)
        self.assertFalse(relatorio["atingiu_criterios_numericos"])

    def test_falha_de_contrato_interrompe_sem_contar_como_desacordo(self):
        cliente = Mock()
        cliente.chat.completions.create.return_value = _completion("SIM", termino="length")
        with self.assertRaisesRegex(ValueError, "calibração ficou incompleta"):
            avaliar(_amostra(), cliente, modelo="mock")
        cliente.chat.completions.create.assert_called_once()

    def test_proibe_mudar_limiar_ou_repetir_a_mesma_saida(self):
        dados = _amostra()
        dados["criterios_adocao"]["limiar_pct"] = 50
        with self.assertRaisesRegex(ValueError, "limiar"):
            validar_amostra(dados)
        dados = _amostra()
        dados["saidas"][1]["referencia_execucao"] = dados["saidas"][0]["referencia_execucao"]
        with self.assertRaisesRegex(ValueError, "já foi usada"):
            validar_amostra(dados)
