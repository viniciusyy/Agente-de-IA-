import unittest

from src.capacidade import pedido_plano_com_capacidade_zero


class CapacidadeZeroTest(unittest.TestCase):
    def test_reconhece_pedidos_de_plano_com_limite_total_zero(self):
        entradas = (
            "Para a feira DOM_C, minha capacidade é zero. "
            "Só gere um plano se for possível respeitar esse limite.",
            "Planeje DOM_C com capacidade disponível igual a zero.",
            "Calcule uma recomendação para QUI. Capacidade total de produção: 0,00 pastéis.",
            "Com limite total de produção de 0 unidades, monte um plano para QUA.",
            "Por favor, pode gerar uma recomendação? Capacidade máxima: 0.",
        )
        for entrada in entradas:
            with self.subTest(entrada=entrada):
                self.assertTrue(pedido_plano_com_capacidade_zero(entrada))

    def test_nao_bloqueia_declaracoes_que_nao_sao_um_limite_total_zero(self):
        entradas = (
            "Consulte o histórico da DOM_C. Minha capacidade é zero.",
            "O que significa capacidade total zero?",
            "Não gere um plano. Minha capacidade é zero.",
            "Planeje DOM_C. Minha capacidade não é zero.",
            "Planeje DOM_C. A capacidade era zero.",
            "Planeje DOM_C. A capacidade é zero para frango.",
            "Planeje DOM_C. A capacidade de frango é zero.",
            "Planeje DOM_C com capacidade máxima de 0 pastéis de frango.",
            "Planeje DOM_C com capacidade máxima de 1200 pastéis.",
            "Planeje DOM_C com capacidade máxima de 0,5 unidade.",
            "Planeje DOM_C com capacidade máxima de 0.5 unidade.",
            "Planeje DOM_C com capacidade de 0 a 20 pastéis.",
            "Planeje DOM_C. Minha capacidade é zero. Corrigindo: capacidade total de 100 pastéis.",
        )
        for entrada in entradas:
            with self.subTest(entrada=entrada):
                self.assertFalse(pedido_plano_com_capacidade_zero(entrada))
