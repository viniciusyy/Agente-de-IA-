import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.comparar import comparar, main


def _rodada(acertos: tuple[bool, bool, bool]) -> dict:
    return {
        "rodada_completa": True,
        "snapshot_inalterado": True,
        "dataset_versao": "1.0.0",
        "dataset_sha256": "d" * 64,
        "snapshot_sha256": "a" * 64,
        "mysql_modo": "local",
        "sistema_versao": "teste",
        "codigo_sha256": "c" * 64,
        "modelo": "modelo-de-teste",
        "casos": [
            {
                "id": f"GD{i:02d}", "classe": "consulta" if i < 3 else "conhecimento",
                "origem": "sintetico" if i < 3 else "desenvolvimento",
                "aprovado_automatico": passou,
            }
            for i, passou in enumerate(acertos, start=1)
        ],
    }


class CompararTest(unittest.TestCase):
    def test_recalcula_acertos_ponderados_e_deltas_sem_confiar_no_resumo(self):
        a = _rodada((False, False, True))
        b = _rodada((True, True, True))
        a["classes"] = {"consulta": {"aprovados": 999, "total": 999}}
        r = comparar(a, b)
        self.assertEqual(r["geral"]["taxa_a_pct"], 33.33)
        self.assertEqual(r["geral"]["taxa_b_pct"], 100.0)
        self.assertEqual(r["geral"]["delta_pp"], 66.67)
        self.assertEqual(r["origens"], {"sintetico": 2, "desenvolvimento": 1})
        self.assertEqual(r["melhoraram"], ["GD01", "GD02"])
        self.assertEqual(r["pioraram"], [])
        self.assertIsNone(r["juiz_calibracao"])

    def test_recusa_snapshot_diferente_mesmo_com_prefixo_igual(self):
        a = _rodada((True, True, True))
        b = deepcopy(a)
        b["snapshot_sha256"] = "a" * 63 + "b"
        with self.assertRaisesRegex(ValueError, "snapshot MySQL"):
            comparar(a, b)

    def test_recusa_rodadas_parciais_ou_com_banco_instavel(self):
        a = _rodada((True, True, True))
        for flag in ("rodada_completa", "snapshot_inalterado"):
            with self.subTest(flag=flag):
                with self.assertRaises(ValueError):
                    comparar(a, {**a, flag: False})

    def test_recusa_casos_com_outra_classe_e_flags_numericas(self):
        a = _rodada((True, True, True))
        b = deepcopy(a)
        b["casos"][0]["classe"] = "outra"
        with self.assertRaisesRegex(ValueError, "classes"):
            comparar(a, b)
        b["casos"][0]["aprovado_automatico"] = 1
        with self.assertRaisesRegex(ValueError, "resultado automático"):
            comparar(a, b)

    def test_cli_aceita_pastas_e_nao_sobrescreve_relatorio(self):
        with TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            antiga, nova = raiz / "antiga", raiz / "nova"
            antiga.mkdir()
            nova.mkdir()
            (antiga / "resultado.json").write_text(
                json.dumps(_rodada((True, False, False))), encoding="utf-8-sig",
            )
            (nova / "resultado.json").write_text(
                json.dumps(_rodada((True, True, True))), encoding="utf-8",
            )
            destino = raiz / "comparacao.json"
            args = [str(antiga), str(nova), "--saida", str(destino)]
            with redirect_stdout(StringIO()) as console, redirect_stderr(StringIO()):
                self.assertEqual(main(args), 0)
                original = destino.read_text(encoding="utf-8")
                self.assertEqual(main(args), 2)
            self.assertIn("não calcula pass^3", console.getvalue())
            self.assertEqual(destino.read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads(original)["tipo"], "comparacao_automatica_de_rodadas")
