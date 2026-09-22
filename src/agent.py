import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.config import settings
from src.database import consultar_historico, consultar_operacao


# ============================================================
# REGRAS FIXAS DO DOMÍNIO
# ============================================================

FEIRAS_COM_RESTRICAO = {"SAB_E", "DOM_E"}

# Produtos que não são comercializados nas feiras E:
# 5 = Frango
# 15 = Escarola sem bacon
PRODUTOS_PROIBIDOS_FEIRAS_E = {5, 15}

FRASES_DE_CONFIRMACAO = {
    "aprovo",
    "confirmo",
    "pode registrar",
    "pode salvar",
    "registre o plano",
    "registrar o plano",
}

FRASES_DE_NEGACAO = {
    "não aprovo",
    "nao aprovo",
    "não confirmo",
    "nao confirmo",
    "não registre",
    "nao registre",
    "não salve",
    "nao salve",
}


# ============================================================
# FERRAMENTAS DISPONÍVEIS PARA O MODELO
# ============================================================

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_historico",
            "description": (
                "Consulta no MySQL o histórico recente de produção, "
                "venda e sobra de uma feira."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_feira": {
                        "type": "string",
                        "description": "Código da feira.",
                        "enum": [
                            "QUA",
                            "QUI",
                            "SAB_C",
                            "SAB_E",
                            "DOM_C",
                            "DOM_E",
                        ],
                    },
                    "limite_operacoes": {
                        "type": "integer",
                        "description": (
                            "Quantidade de operações recentes, "
                            "entre 1 e 10."
                        ),
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["codigo_feira"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_operacao",
            "description": (
                "Consulta no MySQL uma operação específica pelo "
                "seu identificador."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id_operacao": {
                        "type": "integer",
                        "description": (
                            "Identificador numérico da operação."
                        ),
                        "minimum": 1,
                    }
                },
                "required": ["id_operacao"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_recomendacao_mock",
            "description": (
                "Calcula uma recomendação simplificada e "
                "determinística pela média das vendas recentes. "
                "Não utiliza o LLM para calcular quantidades."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_feira": {
                        "type": "string",
                        "description": (
                            "Código da feira para a recomendação."
                        ),
                        "enum": [
                            "QUA",
                            "QUI",
                            "SAB_C",
                            "SAB_E",
                            "DOM_C",
                            "DOM_E",
                        ],
                    }
                },
                "required": ["codigo_feira"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_plano_mock",
            "description": (
                "Registra um plano mock aprovado pelo proprietário "
                "em um arquivo JSONL. A escrita é reversível e "
                "depende de confirmação explícita."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_feira": {
                        "type": "string",
                        "description": "Código da feira.",
                        "enum": [
                            "QUA",
                            "QUI",
                            "SAB_C",
                            "SAB_E",
                            "DOM_C",
                            "DOM_E",
                        ],
                    },
                    "resumo_plano": {
                        "type": "string",
                        "description": (
                            "Resumo do plano que será registrado."
                        ),
                    },
                    "confirmado": {
                        "type": "boolean",
                        "description": (
                            "Verdadeiro somente quando o proprietário "
                            "confirmar explicitamente o registro."
                        ),
                    },
                },
                "required": [
                    "codigo_feira",
                    "resumo_plano",
                    "confirmado",
                ],
                "additionalProperties": False,
            },
        },
    },
]


# ============================================================
# ESTADO EXPLÍCITO DO AGENTE
# ============================================================

@dataclass
class EstadoAgente:
    """
    Estado explícito de uma execução.

    O estado não fica armazenado somente na lista de mensagens
    enviada ao modelo.
    """

    objetivo: str
    data_hora_inicio: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    inicio_monotonico: float = field(
        default_factory=time.monotonic,
        repr=False,
    )
    passos: int = 0
    chamadas_ferramenta: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_estimado_usd: float = 0.0
    trajetoria: list[dict[str, Any]] = field(default_factory=list)
    motivo_termino: str = ""
    resposta_final: str = ""


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def ler_preco_variavel(nome: str) -> float:
    """
    Lê um preço definido no .env.

    Valores vazios são tratados como zero para que o programa
    não encerre durante os testes iniciais.
    """
    valor = os.getenv(nome, "").strip()

    if not valor:
        return 0.0

    try:
        preco = float(valor)
    except ValueError as erro:
        raise ValueError(
            f"A variável {nome} deve conter um número decimal."
        ) from erro

    if preco < 0:
        raise ValueError(
            f"A variável {nome} não pode ser negativa."
        )

    return preco


# ============================================================
# AGENTE
# ============================================================

class AgentePlanejamento:
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.openai_api_key,
        )

        self.prompt_sistema = self._carregar_prompt()

        self.preco_entrada = ler_preco_variavel(
            "LLM_INPUT_PRICE_PER_MILLION"
        )

        self.preco_saida = ler_preco_variavel(
            "LLM_OUTPUT_PRICE_PER_MILLION"
        )

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------

    def _carregar_prompt(self) -> str:
        caminho = (
            Path(__file__).resolve().parents[1]
            / "prompts"
            / "agente_planejamento_v1.md"
        )

        if not caminho.exists():
            raise FileNotFoundError(
                f"Prompt não encontrado: {caminho}"
            )

        return caminho.read_text(encoding="utf-8")

    # --------------------------------------------------------
    # CUSTO
    # --------------------------------------------------------

    def _calcular_custo(
        self,
        tokens_entrada: int,
        tokens_saida: int,
    ) -> float:
        custo_entrada = (
            tokens_entrada
            / 1_000_000
            * self.preco_entrada
        )

        custo_saida = (
            tokens_saida
            / 1_000_000
            * self.preco_saida
        )

        return custo_entrada + custo_saida

    # --------------------------------------------------------
    # ORÇAMENTO
    # --------------------------------------------------------

    def _verificar_orcamento(
        self,
        estado: EstadoAgente,
    ) -> tuple[bool, str]:
        tempo_decorrido = (
            time.monotonic() - estado.inicio_monotonico
        )

        total_tokens = (
            estado.tokens_entrada + estado.tokens_saida
        )

        if estado.passos >= settings.agent_max_steps:
            return False, "LIMITE_DE_PASSOS"

        if (
            estado.chamadas_ferramenta
            >= settings.agent_max_tool_calls
        ):
            return False, "LIMITE_DE_FERRAMENTAS"

        if total_tokens >= settings.agent_max_tokens:
            return False, "LIMITE_DE_TOKENS"

        if tempo_decorrido >= settings.agent_max_time_seconds:
            return False, "LIMITE_DE_TEMPO"

        if (
            estado.custo_estimado_usd
            >= settings.agent_max_cost_usd
        ):
            return False, "LIMITE_DE_CUSTO"

        return True, ""

    # --------------------------------------------------------
    # TRAJETÓRIA
    # --------------------------------------------------------

    def _registrar_trajetoria(
        self,
        estado: EstadoAgente,
        ferramenta: str,
        argumentos: dict,
        resultado: dict,
    ) -> None:
        estado.trajetoria.append(
            {
                "passo": estado.passos,
                "ferramenta": ferramenta,
                "argumentos": argumentos,
                "resultado": resultado,
                "erro": not resultado.get("ok", False),
            }
        )

    # --------------------------------------------------------
    # CONFIRMAÇÃO HUMANA
    # --------------------------------------------------------

    def _possui_confirmacao_explicita(
        self,
        solicitacao: str,
    ) -> bool:
        texto = solicitacao.lower().strip()

        if any(
            frase in texto
            for frase in FRASES_DE_NEGACAO
        ):
            return False

        return any(
            frase in texto
            for frase in FRASES_DE_CONFIRMACAO
        )

    # --------------------------------------------------------
    # RESUMO DO HISTÓRICO PARA O MODELO
    # --------------------------------------------------------

    def _resumir_historico_para_modelo(
        self,
        resultado: dict,
    ) -> dict:
        """
        Consolida os registros por operação antes de enviá-los ao LLM.

        O banco continua devolvendo os dados detalhados, mas o modelo
        recebe somente totais e os produtos com maior sobra. Isso
        reduz tokens sem alterar os dados armazenados no MySQL.
        """
        if not resultado.get("ok"):
            return resultado

        operacoes: dict[int, dict[str, Any]] = {}

        for registro in resultado["dados"]:
            id_operacao = int(registro["id_operacao"])

            if id_operacao not in operacoes:
                operacoes[id_operacao] = {
                    "id_operacao": id_operacao,
                    "feira": registro["feira"],
                    "data_producao": registro["data_producao"],
                    "data_venda": registro["data_venda"],
                    "eh_feriado": bool(
                        registro.get("eh_feriado", False)
                    ),
                    "nome_feriado": registro.get(
                        "nome_feriado"
                    ),
                    "total_produzido": 0,
                    "total_vendido": 0,
                    "total_sobra": 0,
                    "produtos_com_sobra": [],
                }

            quantidade_produzida = int(
                registro["quantidade_produzida"]
            )

            quantidade_sobra = int(
                registro["quantidade_sobra"]
            )

            quantidade_vendida = registro.get(
                "quantidade_vendida"
            )

            if quantidade_vendida is None:
                quantidade_vendida = (
                    quantidade_produzida
                    - quantidade_sobra
                )

            quantidade_vendida = int(
                quantidade_vendida
            )

            operacao = operacoes[id_operacao]

            operacao["total_produzido"] += (
                quantidade_produzida
            )

            operacao["total_vendido"] += (
                quantidade_vendida
            )

            operacao["total_sobra"] += (
                quantidade_sobra
            )

            if quantidade_sobra > 0:
                operacao["produtos_com_sobra"].append(
                    {
                        "produto": registro["produto"],
                        "quantidade_sobra": quantidade_sobra,
                    }
                )

        resumo_operacoes = []

        for operacao in operacoes.values():
            produtos_ordenados = sorted(
                operacao["produtos_com_sobra"],
                key=lambda item: item["quantidade_sobra"],
                reverse=True,
            )

            operacao["produtos_com_maior_sobra"] = (
                produtos_ordenados[:5]
            )

            operacao["quantidade_produtos_com_sobra"] = len(
                operacao["produtos_com_sobra"]
            )

            del operacao["produtos_com_sobra"]

            resumo_operacoes.append(operacao)

        resumo_operacoes.sort(
            key=lambda item: (
                item["data_venda"],
                item["id_operacao"],
            ),
            reverse=True,
        )

        return {
            "ok": True,
            "feira": resultado["feira"],
            "quantidade_operacoes": len(
                resumo_operacoes
            ),
            "quantidade_registros_originais": resultado[
                "quantidade_registros"
            ],
            "operacoes": resumo_operacoes,
            "observacao": (
                "Os registros por produto foram consolidados antes "
                "do envio ao modelo. Para cada operação foram "
                "mantidos os totais e os cinco produtos com maior "
                "sobra."
            ),
        }

    # --------------------------------------------------------
    # RECOMENDAÇÃO MOCK
    # --------------------------------------------------------

    def _calcular_recomendacao_mock(
        self,
        codigo_feira: str,
    ) -> dict:
        """
        Calcula uma média simples das vendas registradas nas
        cinco operações mais recentes.

        O cálculo é determinístico e ocorre fora do LLM.
        """
        codigo_feira = codigo_feira.strip().upper()

        historico = consultar_historico(
            codigo_feira=codigo_feira,
            limite_operacoes=5,
        )

        if not historico.get("ok"):
            return historico

        produtos: dict[int, dict[str, Any]] = {}
        ids_operacoes: set[int] = set()

        for registro in historico["dados"]:
            id_operacao = int(registro["id_operacao"])
            id_produto = int(registro["id_produto"])

            ids_operacoes.add(id_operacao)

            if (
                codigo_feira in FEIRAS_COM_RESTRICAO
                and id_produto in PRODUTOS_PROIBIDOS_FEIRAS_E
            ):
                continue

            if id_produto not in produtos:
                produtos[id_produto] = {
                    "id_produto": id_produto,
                    "produto": registro["produto"],
                    "total_vendido": 0,
                    "quantidade_registros": 0,
                }

            quantidade_vendida = registro.get(
                "quantidade_vendida"
            )

            if quantidade_vendida is None:
                quantidade_vendida = (
                    registro["quantidade_produzida"]
                    - registro["quantidade_sobra"]
                )

            produtos[id_produto]["total_vendido"] += float(
                quantidade_vendida
            )

            produtos[id_produto][
                "quantidade_registros"
            ] += 1

        recomendacoes = []

        for produto in produtos.values():
            media_vendida = (
                produto["total_vendido"]
                / produto["quantidade_registros"]
            )

            recomendacoes.append(
                {
                    "id_produto": produto["id_produto"],
                    "produto": produto["produto"],
                    "media_vendida": round(
                        media_vendida,
                        2,
                    ),
                    "quantidade_recomendada": round(
                        media_vendida
                    ),
                }
            )

        recomendacoes.sort(
            key=lambda item: item["id_produto"]
        )

        return {
            "ok": True,
            "tipo_calculo": "mock_deterministico",
            "feira": codigo_feira,
            "operacoes_consideradas": len(ids_operacoes),
            "recomendacoes": recomendacoes,
            "regras_aplicadas": {
                "produtos_excluidos": (
                    sorted(PRODUTOS_PROIBIDOS_FEIRAS_E)
                    if codigo_feira in FEIRAS_COM_RESTRICAO
                    else []
                )
            },
            "aviso": (
                "A recomendação utiliza apenas a média das vendas "
                "recentes. Ela não representa a previsão definitiva "
                "do TCC."
            ),
        }

    # --------------------------------------------------------
    # ESCRITA MOCK
    # --------------------------------------------------------

    def _registrar_plano_mock(
        self,
        codigo_feira: str,
        resumo_plano: str,
        confirmado_pelo_modelo: bool,
        solicitacao_original: str,
    ) -> dict:
        """
        Escrita reversível em arquivo JSONL.

        São verificadas duas confirmações:
        1. o argumento enviado pelo modelo;
        2. uma confirmação explícita no texto do proprietário.
        """
        confirmacao_no_texto = (
            self._possui_confirmacao_explicita(
                solicitacao_original
            )
        )

        if (
            not confirmado_pelo_modelo
            or not confirmacao_no_texto
        ):
            return {
                "ok": False,
                "erro": {
                    "codigo": "CONFIRMACAO_OBRIGATORIA",
                    "mensagem": (
                        "O plano não foi registrado porque não "
                        "houve confirmação explícita do proprietário."
                    ),
                    "orientacao": (
                        "Apresente o plano e peça ao proprietário "
                        "para escrever que aprova ou confirma "
                        "o registro."
                    ),
                },
            }

        diretorio = Path(settings.log_directory)
        diretorio.mkdir(parents=True, exist_ok=True)

        caminho = diretorio / "planos_aprovados.jsonl"

        registro = {
            "data_hora": datetime.now().isoformat(),
            "feira": codigo_feira.strip().upper(),
            "resumo": resumo_plano,
            "confirmado_pelo_proprietario": True,
            "tipo": "registro_mock_reversivel",
        }

        try:
            with caminho.open(
                "a",
                encoding="utf-8",
            ) as arquivo:
                arquivo.write(
                    json.dumps(
                        registro,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            return {
                "ok": True,
                "mensagem": (
                    "Plano mock registrado com sucesso."
                ),
                "arquivo": str(caminho),
                "reversivel": True,
            }

        except OSError as erro:
            return {
                "ok": False,
                "erro": {
                    "codigo": "ERRO_DE_ESCRITA",
                    "mensagem": str(erro),
                    "orientacao": (
                        "Verifique se o diretório de logs "
                        "permite escrita."
                    ),
                },
            }

    # --------------------------------------------------------
    # DESPACHO DAS FERRAMENTAS
    # --------------------------------------------------------

    def _executar_ferramenta(
        self,
        nome: str,
        argumentos: dict,
        solicitacao_original: str,
    ) -> dict:
        try:
            if nome == "consultar_historico":
                resultado = consultar_historico(
                    codigo_feira=argumentos["codigo_feira"],
                    limite_operacoes=argumentos.get(
                        "limite_operacoes",
                        5,
                    ),
                )

                return self._resumir_historico_para_modelo(
                    resultado
                )

            if nome == "consultar_operacao":
                return consultar_operacao(
                    id_operacao=argumentos["id_operacao"]
                )

            if nome == "calcular_recomendacao_mock":
                return self._calcular_recomendacao_mock(
                    codigo_feira=argumentos["codigo_feira"]
                )

            if nome == "registrar_plano_mock":
                return self._registrar_plano_mock(
                    codigo_feira=argumentos["codigo_feira"],
                    resumo_plano=argumentos["resumo_plano"],
                    confirmado_pelo_modelo=argumentos[
                        "confirmado"
                    ],
                    solicitacao_original=solicitacao_original,
                )

            return {
                "ok": False,
                "erro": {
                    "codigo": "FERRAMENTA_DESCONHECIDA",
                    "mensagem": (
                        f"Ferramenta desconhecida: {nome}"
                    ),
                    "orientacao": (
                        "Utilize somente as ferramentas "
                        "declaradas pelo sistema."
                    ),
                },
            }

        except (KeyError, TypeError, ValueError) as erro:
            return {
                "ok": False,
                "erro": {
                    "codigo": "ARGUMENTOS_INVALIDOS",
                    "mensagem": str(erro),
                    "orientacao": (
                        "Corrija os argumentos da ferramenta "
                        "e tente novamente."
                    ),
                },
            }

        except Exception as erro:
            return {
                "ok": False,
                "erro": {
                    "codigo": "ERRO_INESPERADO_FERRAMENTA",
                    "mensagem": str(erro),
                    "orientacao": (
                        "Revise os dados recebidos e escolha "
                        "uma alternativa segura."
                    ),
                },
            }

    # --------------------------------------------------------
    # LOG
    # --------------------------------------------------------

    def _salvar_log(
        self,
        estado: EstadoAgente,
    ) -> str:
        diretorio = Path(settings.log_directory)
        diretorio.mkdir(parents=True, exist_ok=True)

        data_hora = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        caminho = (
            diretorio
            / f"execucao_{data_hora}.json"
        )

        conteudo = asdict(estado)

        # O valor monotônico só é usado durante a execução e não
        # precisa aparecer no arquivo final.
        conteudo.pop("inicio_monotonico", None)

        conteudo["modelo"] = settings.llm_model
        conteudo["base_url"] = settings.llm_base_url
        conteudo["tempo_total_segundos"] = round(
            time.monotonic() - estado.inicio_monotonico,
            3,
        )

        conteudo["precos_configurados"] = {
            "entrada_por_milhao": self.preco_entrada,
            "saida_por_milhao": self.preco_saida,
        }

        caminho.write_text(
            json.dumps(
                conteudo,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return str(caminho)

    # --------------------------------------------------------
    # EXECUÇÃO PRINCIPAL
    # --------------------------------------------------------

    def executar(
        self,
        solicitacao: str,
    ) -> dict:
        estado = EstadoAgente(
            objetivo=solicitacao
        )

        mensagens: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self.prompt_sistema,
            },
            {
                "role": "user",
                "content": solicitacao,
            },
        ]

        while True:
            disponivel, motivo = (
                self._verificar_orcamento(estado)
            )

            if not disponivel:
                estado.motivo_termino = motivo
                estado.resposta_final = (
                    "A execução foi interrompida porque "
                    f"atingiu o orçamento: {motivo}."
                )
                break

            estado.passos += 1

            tokens_utilizados = (
                estado.tokens_entrada
                + estado.tokens_saida
            )

            tokens_restantes = (
                settings.agent_max_tokens
                - tokens_utilizados
            )

            # Técnica: zero-shot com chamadas de ferramentas.
            #
            # Motivo:
            # o modelo deve interpretar a solicitação em linguagem
            # natural e decidir dinamicamente qual ferramenta usar.
            #
            # Contrato de saída:
            # o modelo deve devolver uma resposta textual ou uma
            # chamada de ferramenta com argumentos JSON válidos.
            #
            # O que esta etapa impede:
            # o modelo não deve inventar dados do MySQL nem calcular
            # livremente quantidades de produção.
            try:
                resposta = (
                    self.client.chat.completions.create(
                        model=settings.llm_model,
                        messages=mensagens,
                        tools=FERRAMENTAS,
                        tool_choice="auto",
                        reasoning_effort="none",
                        max_completion_tokens=min(
                            600,
                            max(1, tokens_restantes),
                        ),
                    )
                )

            except Exception as erro:
                estado.motivo_termino = "ERRO_DO_MODELO"
                estado.resposta_final = (
                    "Não foi possível consultar o modelo: "
                    f"{erro}"
                )
                break

            uso = resposta.usage

            if uso is not None:
                tokens_entrada_chamada = (
                    uso.prompt_tokens or 0
                )

                tokens_saida_chamada = (
                    uso.completion_tokens or 0
                )

                estado.tokens_entrada += (
                    tokens_entrada_chamada
                )

                estado.tokens_saida += (
                    tokens_saida_chamada
                )

                estado.custo_estimado_usd += (
                    self._calcular_custo(
                        tokens_entrada=tokens_entrada_chamada,
                        tokens_saida=tokens_saida_chamada,
                    )
                )

            mensagem = resposta.choices[0].message

            if not mensagem.tool_calls:
                estado.resposta_final = (
                    mensagem.content
                    or "O modelo não devolveu uma resposta."
                )

                estado.motivo_termino = "RESPOSTA_FINAL"
                break

            mensagens.append(
                mensagem.model_dump(
                    exclude_none=True
                )
            )

            for chamada in mensagem.tool_calls:
                if (
                    estado.chamadas_ferramenta
                    >= settings.agent_max_tool_calls
                ):
                    estado.motivo_termino = (
                        "LIMITE_DE_FERRAMENTAS"
                    )

                    estado.resposta_final = (
                        "A execução atingiu o limite de "
                        "chamadas de ferramentas."
                    )
                    break

                try:
                    argumentos = json.loads(
                        chamada.function.arguments
                    )

                except json.JSONDecodeError as erro:
                    argumentos = {}

                    resultado = {
                        "ok": False,
                        "erro": {
                            "codigo": "JSON_INVALIDO",
                            "mensagem": str(erro),
                            "orientacao": (
                                "Gere novamente os argumentos "
                                "como um objeto JSON válido."
                            ),
                        },
                    }

                else:
                    resultado = (
                        self._executar_ferramenta(
                            nome=chamada.function.name,
                            argumentos=argumentos,
                            solicitacao_original=solicitacao,
                        )
                    )

                estado.chamadas_ferramenta += 1

                self._registrar_trajetoria(
                    estado=estado,
                    ferramenta=chamada.function.name,
                    argumentos=argumentos,
                    resultado=resultado,
                )

                mensagens.append(
                    {
                        "role": "tool",
                        "tool_call_id": chamada.id,
                        "content": json.dumps(
                            resultado,
                            ensure_ascii=False,
                        ),
                    }
                )

            if estado.motivo_termino:
                break

        caminho_log = self._salvar_log(estado)

        return {
            "resposta": estado.resposta_final,
            "motivo_termino": estado.motivo_termino,
            "passos": estado.passos,
            "chamadas_ferramenta": (
                estado.chamadas_ferramenta
            ),
            "tokens_entrada": estado.tokens_entrada,
            "tokens_saida": estado.tokens_saida,
            "custo_estimado_usd": round(
                estado.custo_estimado_usd,
                8,
            ),
            "log": caminho_log,
        }