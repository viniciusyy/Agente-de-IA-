import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from evals.coletar_juiz import (
    _candidata, _fora_do_projeto, _hash, _reduzir_retorno,
    capturar_ferramentas, importar, main,
)
from evals.juiz import nova_amostra, validar_amostra


def _busca():
    return {
        "ok": True,
        "suficiente": True,
        "resultados": [{
            "documento_id": "glossario_dados_v1", "status": "vigente",
            "conteudo": "Sobra zero não prova falta de produto.",
        }],
    }


def _coleta():
    return {
        "tipo": "piloto_local_juiz", "completo": True, "snapshot_inalterado": True,
        "casos": [{
            "caso": id_,
            "candidata": _candidata(id_, "Pergunta fictícia", {"resultado": "Resposta fictícia"}, [
                {"ferramenta": "buscar_conhecimento", "argumentos": {}, "retorno": _busca()},
            ], "coleta-de-teste"),
        } for id_ in ("GD08", "GD11")],
    }


class ColetorJuizTest(unittest.TestCase):
    def test_captura_o_retorno_original_sem_reconsultar_a_fonte(self):
        retorno = {"ok": True, "id_operacao": 101, "total_vendido": 17, "dados": []}
        graph = SimpleNamespace(_executar=Mock(return_value=retorno), buscar_conhecimento=Mock())
        original = graph._executar
        with capturar_ferramentas(graph) as observacoes:
            resultado = graph._executar("consultar_operacao", {"id_operacao": 101}, {})
            self.assertIs(resultado, retorno)
            esperado = _hash(retorno)
            retorno["total_vendido"] = 999
        original.assert_called_once_with("consultar_operacao", {"id_operacao": 101}, {})
        self.assertEqual(observacoes[0]["retorno"]["total_vendido"], 17)
        self.assertEqual(observacoes[0]["retorno_observado_sha256"], esperado)
        self.assertIs(graph._executar, original)

    def test_captura_rag_direto_e_nao_duplica_quando_vem_do_executor(self):
        graph = SimpleNamespace(buscar_conhecimento=Mock(return_value=_busca()))
        graph._executar = lambda nome, argumentos, estado: graph.buscar_conhecimento(argumentos["consulta"])
        original = graph.buscar_conhecimento
        with capturar_ferramentas(graph) as observacoes:
            graph.buscar_conhecimento("consulta direta")
            graph._executar("buscar_conhecimento", {"consulta": "via ferramenta"}, {})
        self.assertEqual(original.call_count, 2)
        self.assertEqual(len(observacoes), 2)
        self.assertEqual(observacoes[0]["retorno"]["resultados"][0]["conteudo"],
                         "Sobra zero não prova falta de produto.")

    def test_pedido_de_escrita_aborta_e_nao_cria_evidencia_artificial(self):
        graph = SimpleNamespace(_executar=Mock(), buscar_conhecimento=Mock())
        original = graph._executar
        with capturar_ferramentas(graph) as observacoes:
            with self.assertRaisesRegex(RuntimeError, "escrita"):
                graph._executar("salvar_preferencia", {"chave": "prioridade"}, {})
        original.assert_not_called()
        self.assertEqual(observacoes, [])

    def test_remove_observacoes_livres_e_nao_calcula_totais_ausentes(self):
        original = {
            "ok": True, "id_operacao": 101, "observacoes": "Texto livre desnecessário",
            "password": "NÃO DEVE SER SALVA",
            "dados": [{"quantidade_produzida": 10, "observacoes": "Texto livre"}],
        }
        reduzido = _reduzir_retorno("consultar_operacao", original)
        self.assertEqual(reduzido, {
            "ok": True, "id_operacao": 101, "dados": [{"quantidade_produzida": 10}],
        })
        self.assertNotIn("total_produzido", reduzido)
        self.assertIn("observacoes", original)

    def test_importa_duas_fichas_sem_rotular_e_sem_mudar_a_amostra_original(self):
        amostra = nova_amostra()
        antes = deepcopy(amostra)
        saida = importar(_coleta(), amostra)
        self.assertEqual(amostra, antes)
        self.assertEqual(len(saida["saidas"]), 30)
        for i in range(2):
            self.assertEqual(saida["saidas"][i]["id"], f"J{i + 1:02d}")
            self.assertTrue(saida["saidas"][i]["evidencias"])
            self.assertEqual(saida["saidas"][i]["consenso"], {"rotulo": None, "nota": ""})
        self.assertEqual(saida["saidas"][2:], antes["saidas"][2:])
        with self.assertRaisesRegex(ValueError, "Amostra incompleta"):
            validar_amostra(saida)

    def test_recusa_coleta_incompleta_repetida_ou_com_rotulo_automatico(self):
        for chave in ("completo", "snapshot_inalterado"):
            with self.subTest(chave=chave), self.assertRaises(ValueError):
                importar({**_coleta(), chave: False}, nova_amostra())
        preenchida = importar(_coleta(), nova_amostra())
        with self.assertRaisesRegex(ValueError, "já foi importada"):
            importar(_coleta(), preenchida)
        rotulada = _coleta()
        rotulada["casos"][0]["candidata"]["consenso"]["rotulo"] = "SIM"
        with self.assertRaisesRegex(ValueError, "rótulos humanos vazios"):
            importar(rotulada, nova_amostra())

    def test_arquivo_de_revisao_nao_pode_ir_para_o_projeto(self):
        from evals.coletar_juiz import RAIZ
        with self.assertRaisesRegex(ValueError, "fora do repositório"):
            _fora_do_projeto(RAIZ / "evals" / "piloto.json")

    def test_cli_sem_autorizacao_nao_inicia_subprocesso(self):
        with patch("evals.coletar_juiz._executar") as executar, redirect_stderr(StringIO()):
            self.assertEqual(main(["piloto", "--versao", "teste"]), 2)
        executar.assert_not_called()

    def test_cli_importa_localmente_e_recusa_sobrescrever_a_saida(self):
        with TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            coleta, amostra, saida = (pasta / nome for nome in ("coleta.json", "amostra.json", "saida.json"))
            coleta.write_text(json.dumps(_coleta()), encoding="utf-8-sig")
            amostra.write_text(json.dumps(nova_amostra()), encoding="utf-8")
            argumentos = ["importar", str(coleta), "--amostra", str(amostra), "--saida", str(saida)]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(argumentos), 0)
                original = saida.read_bytes()
                self.assertEqual(main(argumentos), 2)
            self.assertEqual(original, saida.read_bytes())
