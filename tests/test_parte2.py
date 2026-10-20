import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.domain import calcular_recomendacao
from src.graph import grafo
from src.memory import MemoriaLongoPrazo
from src.rag import IndiceTextual
from src.schemas import EntradaAgente, SaidaAgente


class ContratosTest(unittest.TestCase):
    def test_entrada_remove_espacos_externos(self):
        entrada = EntradaAgente(
            texto="  Planeje a feira QUA.  ",
            usuario_id="proprietario",
            thread_id="teste",
        )

        self.assertEqual(
            entrada.texto,
            "Planeje a feira QUA.",
        )

    def test_recusa_tambem_respeita_contrato_de_saida(self):
        saida = SaidaAgente(
            status="recusado",
            resultado=None,
            fontes=[],
            suficiente=False,
            motivo="Informação fora do corpus.",
        )

        self.assertEqual(saida.status, "recusado")
        self.assertFalse(saida.suficiente)
        self.assertEqual(
            saida.motivo,
            "Informação fora do corpus.",
        )


class RagTest(unittest.TestCase):
    def setUp(self):
        self.indice = IndiceTextual()

    def test_dez_perguntas_do_conjunto_de_verificacao(self):
        casos = [
            (
                "Quais são os códigos de feira?",
                "regras_feiras_v2",
            ),
            (
                "Quando é produzida a feira QUA?",
                "regras_feiras_v2",
            ),
            (
                "SAB_C e SAB_E são a mesma feira?",
                "regras_feiras_v2",
            ),
            (
                "Pode vender pastel de Frango na SAB_E?",
                "regras_feiras_v2",
            ),
            (
                "Escarola sem bacon é permitida na DOM_E?",
                "regras_feiras_v2",
            ),
            (
                "Como é calculada a quantidade vendida?",
                "glossario_dados_v1",
            ),
            (
                "Sobra zero prova que faltou produto?",
                "glossario_dados_v1",
            ),
            (
                "Quem pode aprovar o registro de um plano?",
                "processo_planejamento_v1",
            ),
            (
                "O pastel de banana simples está ativo?",
                "produtos_status_v1",
            ),
            (
                "Qual é o fornecedor da massa?",
                None,
            ),
        ]

        for pergunta, documento_esperado in casos:
            with self.subTest(pergunta=pergunta):
                resultado = self.indice.buscar(pergunta)

                if documento_esperado is None:
                    self.assertFalse(resultado.suficiente)
                    self.assertEqual(resultado.resultados, [])
                    continue

                self.assertTrue(resultado.suficiente)
                self.assertGreater(
                    len(resultado.resultados),
                    0,
                )
                self.assertEqual(
                    resultado.resultados[0].documento_id,
                    documento_esperado,
                )

    def test_documento_revogado_nao_participa_da_busca_normal(self):
        resultado = self.indice.buscar(
            "Frango pode ser vendido na SAB_E?"
        )

        ids_recuperados = [
            item.documento_id
            for item in resultado.resultados
        ]

        self.assertIn(
            "regras_feiras_v2",
            ids_recuperados,
        )
        self.assertNotIn(
            "regras_feiras_v1_revogado",
            ids_recuperados,
        )

        resultado_com_revogados = self.indice.buscar(
            "Frango pode ser vendido na SAB_E?",
            incluir_revogados=True,
        )

        ids_com_revogados = [
            item.documento_id
            for item in resultado_com_revogados.resultados
        ]

        self.assertIn(
            "regras_feiras_v1_revogado",
            ids_com_revogados,
        )


class MemoriaTest(unittest.TestCase):
    def test_memoria_semantica_mantem_versoes_e_le_a_mais_recente(self):
        with tempfile.TemporaryDirectory() as pasta:
            memoria = MemoriaLongoPrazo(
                Path(pasta) / "memoria.sqlite3"
            )

            primeira = memoria.salvar_fato_semantico(
                usuario_id="proprietario",
                chave="prioridade",
                valor="reduzir sobra",
            )

            segunda = memoria.salvar_fato_semantico(
                usuario_id="proprietario",
                chave="prioridade",
                valor="evitar falta",
            )

            fatos = memoria.ler_fatos_semanticos(
                "proprietario"
            )

            self.assertFalse(primeira["ja_existia"])
            self.assertFalse(segunda["ja_existia"])
            self.assertEqual(
                fatos["prioridade"],
                "evitar falta",
            )

    def test_registro_de_plano_e_idempotente(self):
        with tempfile.TemporaryDirectory() as pasta:
            memoria = MemoriaLongoPrazo(
                Path(pasta) / "memoria.sqlite3"
            )

            payload = {
                "feira": "QUA",
                "total_recomendado": 500,
                "resumo_plano": "Plano aprovado.",
            }

            primeira = memoria.registrar_plano_idempotente(
                usuario_id="proprietario",
                thread_id="teste-idempotencia",
                payload=payload,
            )

            segunda = memoria.registrar_plano_idempotente(
                usuario_id="proprietario",
                thread_id="teste-idempotencia",
                payload=payload,
            )

            quantidade = memoria.contar_planos_por_chave(
                primeira["idempotency_key"]
            )

            self.assertFalse(primeira["ja_existia"])
            self.assertTrue(segunda["ja_existia"])
            self.assertEqual(
                primeira["idempotency_key"],
                segunda["idempotency_key"],
            )
            self.assertEqual(quantidade, 1)


class DominioTest(unittest.TestCase):
    @patch("src.domain.consultar_historico")
    def test_feira_e_exclui_produtos_proibidos_e_descontinuados(
        self,
        consultar_historico_mock,
    ):
        consultar_historico_mock.return_value = {
            "ok": True,
            "fonte": "mysql:teste",
            "dados": [
                {
                    "id_operacao": 1,
                    "id_produto": 5,
                    "produto": "Frango",
                    "quantidade_produzida": 10,
                    "quantidade_sobra": 0,
                    "quantidade_vendida": 10,
                },
                {
                    "id_operacao": 1,
                    "id_produto": 15,
                    "produto": "Escarola sem bacon",
                    "quantidade_produzida": 10,
                    "quantidade_sobra": 0,
                    "quantidade_vendida": 10,
                },
                {
                    "id_operacao": 1,
                    "id_produto": 6,
                    "produto": "Frango com catupiri",
                    "quantidade_produzida": 20,
                    "quantidade_sobra": 2,
                    "quantidade_vendida": 18,
                },
                {
                    "id_operacao": 1,
                    "id_produto": 28,
                    "produto": "Banana simples",
                    "quantidade_produzida": 10,
                    "quantidade_sobra": 1,
                    "quantidade_vendida": 9,
                },
            ],
        }

        resultado = calcular_recomendacao("SAB_E")

        ids_recomendados = [
            item["id_produto"]
            for item in resultado["recomendacoes"]
        ]

        self.assertTrue(resultado["ok"])
        self.assertEqual(ids_recomendados, [6])
        self.assertEqual(
            resultado["regras_aplicadas"]["produtos_excluidos"],
            [5, 15],
        )
        self.assertEqual(
            resultado["regras_aplicadas"][
                "produtos_descontinuados_excluidos"
            ],
            ["Banana simples"],
        )


class GrafoTest(unittest.TestCase):
    def test_grafo_contem_os_nos_obrigatorios(self):
        nomes = set(grafo.get_graph().nodes)

        nos_esperados = {
            "preparar_contexto",
            "chamar_modelo",
            "executar_ferramentas",
            "aprovar_plano",
            "validar_saida",
            "memorizar_episodio",
        }

        self.assertTrue(
            nos_esperados.issubset(nomes)
        )


if __name__ == "__main__":
    unittest.main()