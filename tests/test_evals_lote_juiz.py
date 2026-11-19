import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from evals.coletar_juiz import _candidata
from evals.coletar_lote_juiz import (
    _campos_candidata, conferir_base, main, montar_amostra, plano_lote,
)
from evals.juiz import nova_amostra, validar_amostra


def _origem():
    amostra = nova_amostra()
    piloto = {
        "tipo": "piloto_local_juiz", "completo": True, "snapshot_inalterado": True,
        "snapshot_sha256": "a" * 64, "casos": [],
    }
    obs = [{"ferramenta": "buscar_conhecimento", "argumentos": {}, "retorno": {"ok": True}}]
    for indice, id_ in enumerate(("GD08", "GD11")):
        c = _candidata(id_, "Pergunta fictícia.", {"resultado": "Resposta fictícia."}, obs, "base")
        amostra["saidas"][indice].update(c)
        amostra["saidas"][indice]["revisoes"]["tecnica"] = {
            "rotulo": "SIM", "nota": "Nota da revisão técnica já realizada.",
        }
        piloto["casos"].append({"caso": id_, "candidata": c})
    return amostra, piloto


def _casos_lote():
    return [{
        "caso": pedido["id"],
        "candidata": _campos_candidata(
            pedido["id"], pedido["pergunta"],
            {"saida": {"resultado": "Resposta fictícia de teste."}, "motivo_termino": "CONCLUIDO"},
            [], "lote-teste",
        ),
    } for pedido in plano_lote()]


class LoteJuizTest(unittest.TestCase):
    def test_plano_tem_28_perguntas_sinteticas_distintas(self):
        plano = plano_lote()
        self.assertEqual([p["id"] for p in plano], [f"L{i:02d}" for i in range(1, 29)])
        self.assertEqual(len({p["pergunta"] for p in plano}), 28)
        self.assertTrue(all(p["origem_entrada"] == "sintetico" for p in plano))

    def test_preserva_primeiras_duas_fichas_e_deixa_novas_sem_rotulo(self):
        amostra, piloto = _origem()
        copia = deepcopy(amostra)
        conferir_base(amostra, piloto)
        completa = montar_amostra(amostra, _casos_lote())
        self.assertEqual(completa["saidas"][:2], amostra["saidas"][:2])
        self.assertEqual(amostra, copia)
        self.assertEqual(len(completa["saidas"]), 30)
        for ficha in completa["saidas"][2:]:
            self.assertTrue(ficha["pergunta"])
            self.assertTrue(ficha["resposta"])
            self.assertTrue(ficha["evidencias"])
            self.assertEqual(ficha["consenso"], {"rotulo": None, "nota": ""})
            self.assertIsNone(ficha["revisoes"]["tecnica"]["rotulo"])
        with self.assertRaisesRegex(ValueError, "Amostra incompleta"):
            validar_amostra(completa)

    def test_proibe_alteracao_da_evidencia_ou_de_uma_ficha_preenchida(self):
        amostra, piloto = _origem()
        amostra["saidas"][0]["resposta"] = {"resultado": "Resposta adulterada."}
        with self.assertRaisesRegex(ValueError, "mudou"):
            conferir_base(amostra, piloto)
        amostra, piloto = _origem()
        amostra["saidas"][2]["revisoes"]["tecnica"]["nota"] = "Revisão iniciada."
        with self.assertRaisesRegex(ValueError, "não apaga revisões"):
            conferir_base(amostra, piloto)

    def test_recusa_lote_parcial_referencia_duplicada_ou_rotulo_novo(self):
        amostra, _ = _origem()
        with self.assertRaisesRegex(ValueError, "28 saídas"):
            montar_amostra(amostra, _casos_lote()[:-1])
        casos = _casos_lote()
        casos[1]["candidata"]["referencia_execucao"] = casos[0]["candidata"]["referencia_execucao"]
        with self.assertRaisesRegex(ValueError, "repetida"):
            montar_amostra(amostra, casos)
        casos = _casos_lote()
        casos[0]["candidata"]["consenso"]["rotulo"] = "SIM"
        with self.assertRaisesRegex(ValueError, "rótulo automático"):
            montar_amostra(amostra, casos)

    def test_sem_tool_preserva_a_resposta_e_registra_ausencia_sem_inventar_fonte(self):
        retorno = {
            "saida": {"status": "concluido", "resultado": "Uma afirmação sem consulta."},
            "motivo_termino": "CONCLUIDO",
        }
        candidata = _campos_candidata("L01", "Pergunta.", retorno, [], "lote-teste")
        self.assertEqual(candidata["resposta"], retorno["saida"])
        evidencia, = candidata["evidencias"]
        self.assertTrue(evidencia["referencia"].endswith("/rastro"))
        self.assertEqual(json.loads(evidencia["trecho"])["ferramentas_com_retorno_observado"], [])

    def test_conferir_plano_e_executar_sem_autorizacao_nao_chamam_api(self):
        with patch("evals.coletar_lote_juiz._executar") as executar:
            with redirect_stdout(StringIO()) as saida:
                self.assertEqual(main(["--conferir"]), 0)
            self.assertIn("28 entradas", saida.getvalue())
            with redirect_stderr(StringIO()):
                self.assertEqual(main(["--versao", "teste"]), 2)
        executar.assert_not_called()

    def test_base_com_snapshot_instavel_e_recusada(self):
        amostra, piloto = _origem()
        piloto["snapshot_inalterado"] = False
        with self.assertRaisesRegex(ValueError, "snapshot inalterado"):
            conferir_base(amostra, piloto)

    def test_fluxo_cli_mockado_completa_arquivo_sem_modificar_base(self):
        # Não inicializa o agente nem usa MySQL. As 28 execuções são simuladas.
        amostra, piloto = _origem()
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            origem, fonte, destino = pasta / "amostra.json", pasta / "piloto.json", pasta / "lote"
            origem.write_text(json.dumps(amostra), encoding="utf-8-sig")
            fonte.write_text(json.dumps(piloto), encoding="utf-8")
            original = origem.read_bytes()
            casos = _casos_lote()
            for caso in casos:
                caso.update(status="concluido", requer_revisao_de_tamanho=False)
            from types import ModuleType, SimpleNamespace
            referencias = ModuleType("evals.referencias_mysql")
            referencias.ambiente_demo = Mock(return_value={"EVAL_MYSQL_MODO": "local"})
            referencias.ler_snapshot = Mock(return_value=SimpleNamespace(sha256="a" * 64))
            rodar = ModuleType("evals.rodar")
            rodar.carregar_dataset = Mock(return_value={"ambiente": {}})
            rodar._checar_modelo = Mock(return_value="mock")
            rodar._hash_dataset = Mock(return_value="dataset-mock")
            rodar._marcar_codigo = Mock(return_value="codigo-mock")
            with patch.dict("sys.modules", {
                "evals.referencias_mysql": referencias, "evals.rodar": rodar,
            }), patch("evals.coletar_lote_juiz._executar", side_effect=casos) as executar:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    codigo = main([
                        "--amostra", str(origem), "--coleta-base", str(fonte),
                        "--saida", str(destino), "--versao", "teste",
                        "--confirmar-dados-autorizados",
                    ])
            self.assertEqual(codigo, 0)
            self.assertEqual(executar.call_count, 28)
            completa = json.loads((destino / "amostra-30.json").read_text(encoding="utf-8"))
            self.assertEqual(completa["saidas"][:2], amostra["saidas"][:2])
            self.assertEqual(origem.read_bytes(), original)
            self.assertTrue(json.loads((destino / "lote.json").read_text())["completo"])
