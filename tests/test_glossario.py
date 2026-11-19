import unittest

from src.glossario import (
    DOCUMENTO_GLOSSARIO,
    detectar_pergunta_sobra_zero,
    responder_sobra_zero,
)


TRECHO = (
    "Uma sobra igual a zero não prova falta de produto nem perda de venda. "
    "Ela pode representar venda exata ou produto encerrado antes do fim da feira. "
    "Como o banco não registra o horário em que cada sabor termina, "
    "o sistema não chama esse caso de ruptura e não promete medir vendas perdidas."
)


def _documento(**campos):
    return {
        "documento_id": DOCUMENTO_GLOSSARIO,
        "status": "vigente",
        "conteudo": "Definição das quantidades.\n\n" + TRECHO + "\n\nClimas aceitos.",
        **campos,
    }


class GlossarioTest(unittest.TestCase):
    def test_reconhece_variacoes_sem_exigir_feira(self):
        for entrada in (
            "Sobra zero prova que faltou produto?",
            "Sem sobras quer dizer que houve ruptura?",
            "Com sobra de 0, posso concluir que houve vendas perdidas?",
            "Como devo interpretar uma sobra igual a 0,00?",
            "Se não sobrou nada, posso afirmar que perdemos vendas?",
        ):
            with self.subTest(entrada=entrada):
                self.assertTrue(detectar_pergunta_sobra_zero(entrada))

    def test_nao_intercepta_outros_pedidos(self):
        for entrada in (
            "Mostre o histórico de operações com sobra zero.",
            "Consulte a operação 101. Sobra zero prova falta?",
            "Calcule uma recomendação para QUA.",
            "Sobra zero significa que vendemos tudo?",
            "Como interpretar uma sobra de 0,5?",
            "Como interpretar sobra elevada?",
            "Qual é o fornecedor da massa?",
        ):
            with self.subTest(entrada=entrada):
                self.assertFalse(detectar_pergunta_sobra_zero(entrada))

    def test_resposta_preserva_trecho_e_documento_usado(self):
        documento = _documento()
        saida, fonte = responder_sobra_zero({
            "ok": True, "suficiente": True, "resultados": [documento],
        })
        self.assertEqual(saida["status"], "concluido")
        self.assertTrue(saida["suficiente"])
        self.assertEqual(saida["resultado"], {"prova_falta": False, "explicacao": TRECHO})
        self.assertIs(fonte, documento)

    def test_recusa_sem_evidencia_vigente_e_suficiente(self):
        for recuperacao in (
            {"suficiente": False, "resultados": [_documento()]},
            {"suficiente": True, "resultados": [_documento(status="revogado")]},
            {"suficiente": True, "resultados": [_documento(documento_id="outro")]},
            {"suficiente": True, "resultados": [_documento(conteudo="Dados sem a regra.")]},
        ):
            with self.subTest(recuperacao=recuperacao):
                saida, fonte = responder_sobra_zero({"ok": True, **recuperacao})
                self.assertEqual(saida["status"], "recusado")
                self.assertFalse(saida["suficiente"])
                self.assertIsNone(saida["resultado"])
                self.assertIsNone(fonte)

    def test_falha_na_busca_nao_afirma_uma_regra(self):
        saida, fonte = responder_sobra_zero({"ok": False})
        self.assertEqual(saida["status"], "erro")
        self.assertIsNone(saida["resultado"])
        self.assertIsNone(fonte)
