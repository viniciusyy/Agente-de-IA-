from __future__ import annotations

import hashlib
import json
import operator
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from openai import OpenAI

from src.config import settings
from src.database import consultar_historico, consultar_operacao
from src.domain import calcular_recomendacao, resumir_historico
from src.memory import obter_memoria
from src.rag import buscar_conhecimento
from src.schemas import DecisaoHumana, FonteResposta, SaidaAgente


def juntar_fontes(atual: list[dict], novas: list[dict]) -> list[dict]:
    """
    Reducer responsável por acumular as fontes utilizadas sem repetir
    a mesma referência.
    """
    unicas: dict[tuple[str, str], dict] = {}

    for fonte in [*(atual or []), *(novas or [])]:
        chave = (
            fonte.get("tipo", "sistema"),
            fonte.get("referencia", ""),
        )
        unicas[chave] = fonte

    return list(unicas.values())


class EstadoGrafo(TypedDict, total=False):
    """
    Estado explícito que atravessa todos os nós do LangGraph.

    Campos com Annotated utilizam reducers porque recebem valores
    produzidos por vários nós durante a execução.
    """

    # Histórico de mensagens do modelo, usuário e ferramentas.
    mensagens: Annotated[list[dict[str, Any]], operator.add]

    # Identificação da entrada e da conversa.
    entrada_texto: str
    usuario_id: str
    thread_id: str
    turno_id: str

    # Informações recuperadas da memória.
    memoria_semantica: dict[str, str]
    memoria_episodica: list[dict]

    # Fontes usadas para sustentar a resposta.
    fontes: Annotated[list[dict], juntar_fontes]

    # Registro da trajetória da execução.
    trajetoria: Annotated[list[dict], operator.add]
    assinaturas_passos: Annotated[list[str], operator.add]

    # Orçamentos da execução atual.
    passos_turno: int
    chamadas_ferramenta_turno: int
    tokens_entrada_turno: int
    tokens_saida_turno: int
    custo_turno_usd: float
    inicio_turno_epoch: float

    # Produtos intermediários e saída.
    ultimo_plano: dict | None
    resposta_validada: dict | None
    erro_fatal: str | None
    motivo_termino: str


FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_historico",
            "description": (
                "Consulta no banco MySQL as operações recentes "
                "de uma feira da Pastéis Miyata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_feira": {
                        "type": "string",
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
                "Consulta uma operação específica do banco MySQL "
                "utilizando seu identificador."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id_operacao": {
                        "type": "integer",
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
            "name": "buscar_conhecimento",
            "description": (
                "Busca regras, vocabulário, processo e exceções no corpus "
                "curado da Pastéis Miyata. Deve ser utilizada quando uma "
                "decisão depender de conhecimento do domínio, e não de um "
                "registro específico do MySQL."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "minLength": 2,
                    }
                },
                "required": ["consulta"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_recomendacao",
            "description": (
                "Calcula fora do modelo de linguagem uma recomendação "
                "simplificada de produção, utilizando a média das cinco "
                "vendas recentes e aplicando as restrições da feira."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_feira": {
                        "type": "string",
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
            "name": "salvar_preferencia",
            "description": (
                "Guarda uma preferência operacional estável que tenha sido "
                "declarada explicitamente pelo proprietário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chave": {
                        "type": "string",
                    },
                    "valor": {
                        "type": "string",
                    },
                },
                "required": ["chave", "valor"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_plano",
            "description": (
                "Solicita o registro do último plano calculado. A ferramenta "
                "sempre pausa o grafo para aprovação, rejeição ou edição "
                "pelo proprietário."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "resumo_plano": {
                        "type": "string",
                    }
                },
                "required": ["resumo_plano"],
                "additionalProperties": False,
            },
        },
    },
]


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _ler_prompt(nome: str) -> str:
    """
    Carrega um prompt versionado localizado em src/prompts.
    """
    caminho = PROMPT_DIR / nome

    if not caminho.exists():
        raise FileNotFoundError(
            f"O arquivo de prompt não foi encontrado: {caminho}"
        )

    return caminho.read_text(encoding="utf-8")


def _custo(tokens_entrada: int, tokens_saida: int) -> float:
    """
    Calcula o custo estimado da chamada ao modelo.
    """
    custo_entrada = (
        tokens_entrada
        / 1_000_000
        * settings.llm_input_price_per_million
    )

    custo_saida = (
        tokens_saida
        / 1_000_000
        * settings.llm_output_price_per_million
    )

    return custo_entrada + custo_saida


def _fontes_do_resultado(
    nome: str,
    resultado: dict,
    turno_id: str,
) -> list[dict]:
    """
    Converte as evidências devolvidas pelas ferramentas no contrato
    de fontes utilizado pela saída do agente.
    """
    fontes: list[dict] = []

    ferramentas_mysql = {
        "consultar_historico",
        "consultar_operacao",
        "calcular_recomendacao",
    }

    if nome in ferramentas_mysql:
        referencia = resultado.get("fonte")

        if referencia:
            fonte = FonteResposta(
                tipo="mysql",
                referencia=referencia,
                detalhe=f"Retornado pela ferramenta {nome}.",
            ).model_dump()

            fonte["turno_id"] = turno_id
            fontes.append(fonte)

    elif nome == "buscar_conhecimento":
        for item in resultado.get("resultados", []):
            fonte = FonteResposta(
                tipo="corpus",
                referencia=(
                    f"{item['caminho']}#{item['documento_id']}"
                ),
                detalhe=(
                    f"{item['titulo']} — versão {item['versao']}"
                ),
            ).model_dump()

            fonte["turno_id"] = turno_id
            fontes.append(fonte)

    elif nome == "salvar_preferencia":
        fonte = FonteResposta(
            tipo="memoria",
            referencia=(
                f"memoria_semantica:{resultado.get('chave', '')}"
            ),
            detalhe="Fato declarado pelo proprietário.",
        ).model_dump()

        fonte["turno_id"] = turno_id
        fontes.append(fonte)

    return fontes


def preparar_contexto(estado: EstadoGrafo) -> dict:
    """
    Recupera as memórias de longo prazo antes de chamar o modelo.

    A memória semântica contém preferências estáveis.
    A memória episódica contém execuções anteriores relevantes.
    """
    memoria = obter_memoria()

    fatos = memoria.ler_fatos_semanticos(
        estado["usuario_id"]
    )

    episodios = memoria.buscar_episodios(
        estado["usuario_id"],
        estado["entrada_texto"],
        limite=3,
    )

    return {
        "memoria_semantica": fatos,
        "memoria_episodica": episodios,
        "trajetoria": [
            {
                "no": "preparar_contexto",
                "fatos_semanticos": len(fatos),
                "episodios_recuperados": len(episodios),
            }
        ],
    }


def _verificar_orcamento(estado: EstadoGrafo) -> str | None:
    """
    Verifica todos os limites da execução antes de uma nova
    chamada ao modelo.
    """
    if estado.get("passos_turno", 0) >= settings.agent_max_steps:
        return "LIMITE_DE_PASSOS"

    if (
        estado.get("chamadas_ferramenta_turno", 0)
        >= settings.agent_max_tool_calls
    ):
        return "LIMITE_DE_FERRAMENTAS"

    total_tokens = (
        estado.get("tokens_entrada_turno", 0)
        + estado.get("tokens_saida_turno", 0)
    )

    if total_tokens >= settings.agent_max_tokens:
        return "LIMITE_DE_TOKENS"

    inicio = estado.get(
        "inicio_turno_epoch",
        time.time(),
    )

    if (
        time.time() - inicio
        >= settings.agent_max_time_seconds
    ):
        return "LIMITE_DE_TEMPO"

    if (
        estado.get("custo_turno_usd", 0.0)
        >= settings.agent_max_cost_usd
    ):
        return "LIMITE_DE_CUSTO"

    return None


def _assinatura_chamadas(
    chamadas: list[dict],
    turno_id: str,
) -> str:
    """
    Produz uma assinatura determinística das chamadas de ferramentas.

    Ela é utilizada para identificar quando o agente entra em um laço
    e repete continuamente a mesma decisão.
    """
    canonico = json.dumps(
        {
            "turno_id": turno_id,
            "chamadas": chamadas,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(
        canonico.encode("utf-8")
    ).hexdigest()


def _janela_conversa(
    mensagens: list[dict],
) -> list[dict]:
    """
    Limita o histórico enviado ao modelo.

    A função mantém turnos completos e impede que o contexto comece
    diretamente por uma resposta de ferramenta.
    """
    posicoes_usuario = [
        indice
        for indice, mensagem in enumerate(mensagens)
        if mensagem.get("role") == "user"
    ]

    if (
        len(posicoes_usuario)
        <= settings.conversation_max_turns
    ):
        return mensagens

    inicio = posicoes_usuario[
        -settings.conversation_max_turns
    ]

    return mensagens[inicio:]

def chamar_modelo(estado: EstadoGrafo) -> dict:
    """
    Chama o modelo de linguagem para interpretar a solicitação,
    decidir se alguma ferramenta é necessária e produzir a resposta.

    Técnica utilizada:
    - zero-shot orientado por ferramentas;
    - contrato de saída JSON;
    - memória procedural carregada por arquivo;
    - contexto semântico e episódico recuperado antes da chamada.

    O modelo não calcula recomendações nem consulta o banco diretamente.
    """
    motivo_orcamento = _verificar_orcamento(estado)

    if motivo_orcamento:
        return {
            "erro_fatal": motivo_orcamento,
            "motivo_termino": motivo_orcamento,
            "trajetoria": [
                {
                    "no": "chamar_modelo",
                    "erro": motivo_orcamento,
                }
            ],
        }

    try:
        settings.validar_modelo()

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url,
        )

        prompt_orquestrador = _ler_prompt(
            "orquestrador_v2.md"
        )

        procedimento = _ler_prompt(
            "procedimento_planejamento_v1.md"
        )

        contexto_memoria = {
            "memoria_semantica": estado.get(
                "memoria_semantica",
                {},
            ),
            "episodios_relevantes": estado.get(
                "memoria_episodica",
                [],
            ),
        }

        mensagem_sistema = (
            prompt_orquestrador
            + "\n\n# Memória procedural\n"
            + procedimento
            + "\n\n# Memória recuperada para esta execução\n"
            + json.dumps(
                contexto_memoria,
                ensure_ascii=False,
            )
        )

        mensagens = [
            {
                "role": "system",
                "content": mensagem_sistema,
            },
            *_janela_conversa(
                estado.get("mensagens", [])
            ),
        ]

        parametros: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": mensagens,
            "tools": FERRAMENTAS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "max_completion_tokens": (
                settings.llm_max_output_tokens
            ),
        }

        # Alguns modelos da OpenAI não aceitam ferramentas junto de
        # níveis elevados de raciocínio no endpoint Chat Completions.
        if "api.openai.com" in settings.llm_base_url:
            parametros["reasoning_effort"] = "none"

        resposta = client.chat.completions.create(
            **parametros
        )

        mensagem = (
            resposta
            .choices[0]
            .message
            .model_dump(exclude_none=True)
        )

        chamadas = mensagem.get(
            "tool_calls",
            [],
        )

        assinatura = (
            _assinatura_chamadas(
                chamadas,
                estado["turno_id"],
            )
            if chamadas
            else ""
        )

        assinaturas_anteriores = estado.get(
            "assinaturas_passos",
            [],
        )

        repeticoes = (
            assinaturas_anteriores[
                -settings.loop_repeat_limit:
            ].count(assinatura)
            if assinatura
            else 0
        )

        if (
            assinatura
            and repeticoes
            >= settings.loop_repeat_limit - 1
        ):
            return {
                "erro_fatal": "LACO_DETECTADO",
                "motivo_termino": "LACO_DETECTADO",
                "trajetoria": [
                    {
                        "no": "chamar_modelo",
                        "erro": (
                            "A mesma decisão de ferramenta "
                            "foi repetida pelo modelo."
                        ),
                        "assinatura": assinatura,
                    }
                ],
            }

        tokens_entrada = (
            resposta.usage.prompt_tokens
            if resposta.usage
            else 0
        )

        tokens_saida = (
            resposta.usage.completion_tokens
            if resposta.usage
            else 0
        )

        return {
            "mensagens": [mensagem],
            "passos_turno": (
                estado.get("passos_turno", 0) + 1
            ),
            "tokens_entrada_turno": (
                estado.get(
                    "tokens_entrada_turno",
                    0,
                )
                + tokens_entrada
            ),
            "tokens_saida_turno": (
                estado.get(
                    "tokens_saida_turno",
                    0,
                )
                + tokens_saida
            ),
            "custo_turno_usd": (
                estado.get(
                    "custo_turno_usd",
                    0.0,
                )
                + _custo(
                    tokens_entrada,
                    tokens_saida,
                )
            ),
            "assinaturas_passos": (
                [assinatura]
                if assinatura
                else []
            ),
            "trajetoria": [
                {
                    "no": "chamar_modelo",
                    "modelo": settings.llm_model,
                    "chamadas": [
                        chamada
                        .get("function", {})
                        .get("name")
                        for chamada in chamadas
                    ],
                    "tokens_entrada": tokens_entrada,
                    "tokens_saida": tokens_saida,
                }
            ],
        }

    except Exception as erro:
        descricao = (
            f"{type(erro).__name__}: {erro}"
        )

        return {
            "erro_fatal": (
                f"ERRO_DO_MODELO: {descricao}"
            ),
            "motivo_termino": "ERRO_DO_MODELO",
            "trajetoria": [
                {
                    "no": "chamar_modelo",
                    "erro": descricao,
                }
            ],
        }


def _ultima_mensagem(
    estado: EstadoGrafo,
) -> dict:
    """
    Devolve a mensagem mais recente do estado.
    """
    mensagens = estado.get(
        "mensagens",
        [],
    )

    if not mensagens:
        return {}

    return mensagens[-1]


def rotear_apos_modelo(
    estado: EstadoGrafo,
) -> Literal[
    "executar_ferramentas",
    "aprovar_plano",
    "validar_saida",
]:
    """
    Router determinístico executado depois da decisão do modelo.

    O código, e não o modelo, escolhe o próximo nó a partir
    da presença e do tipo das chamadas de ferramentas.
    """
    if estado.get("erro_fatal"):
        return "validar_saida"

    chamadas = _ultima_mensagem(
        estado
    ).get("tool_calls", [])

    if not chamadas:
        return "validar_saida"

    solicitou_registro = any(
        chamada
        .get("function", {})
        .get("name")
        == "registrar_plano"
        for chamada in chamadas
    )

    if solicitou_registro:
        return "aprovar_plano"

    return "executar_ferramentas"


def _executar(
    nome: str,
    argumentos: dict,
    estado: EstadoGrafo,
) -> dict:
    """
    Mapeia o nome solicitado pelo modelo para uma função Python.

    Essa função impede que o modelo execute livremente funções que
    não estejam explicitamente autorizadas.
    """
    if nome == "consultar_historico":
        dados = consultar_historico(
            argumentos["codigo_feira"],
            argumentos.get(
                "limite_operacoes",
                5,
            ),
        )

        return resumir_historico(dados)

    if nome == "consultar_operacao":
        return consultar_operacao(
            int(argumentos["id_operacao"])
        )

    if nome == "buscar_conhecimento":
        return buscar_conhecimento(
            argumentos["consulta"]
        )

    if nome == "calcular_recomendacao":
        return calcular_recomendacao(
            argumentos["codigo_feira"]
        )

    if nome == "salvar_preferencia":
        return (
            obter_memoria()
            .salvar_fato_semantico(
                estado["usuario_id"],
                argumentos["chave"],
                argumentos["valor"],
            )
        )

    return {
        "ok": False,
        "erro": {
            "codigo": "FERRAMENTA_DESCONHECIDA",
            "mensagem": (
                f"Ferramenta desconhecida: {nome}"
            ),
            "orientacao": (
                "Use somente as ferramentas declaradas."
            ),
        },
    }


def executar_ferramentas(
    estado: EstadoGrafo,
) -> dict:
    """
    Executa as ferramentas escolhidas pelo modelo.

    Os resultados, inclusive os erros, são transformados em mensagens
    de ferramenta. Dessa forma, um erro vira informação para que o
    modelo possa corrigir a decisão na próxima volta do laço.
    """
    mensagens: list[dict] = []
    trajetoria: list[dict] = []
    fontes: list[dict] = []

    ultimo_plano = estado.get(
        "ultimo_plano"
    )

    chamadas_executadas = 0

    chamadas = _ultima_mensagem(
        estado
    ).get("tool_calls", [])

    for chamada in chamadas:
        nome = chamada["function"]["name"]
        argumentos: dict = {}

        chamadas_anteriores = estado.get(
            "chamadas_ferramenta_turno",
            0,
        )

        limite_atingido = (
            chamadas_anteriores
            + chamadas_executadas
            >= settings.agent_max_tool_calls
        )

        if limite_atingido:
            resultado = {
                "ok": False,
                "erro": {
                    "codigo": (
                        "LIMITE_DE_FERRAMENTAS"
                    ),
                    "mensagem": (
                        "O teto de ferramentas desta "
                        "execução foi atingido."
                    ),
                    "orientacao": (
                        "Encerre a execução utilizando "
                        "somente o que já foi verificado."
                    ),
                },
            }

        else:
            try:
                argumentos = json.loads(
                    chamada["function"].get(
                        "arguments",
                        "{}",
                    )
                )

                resultado = _executar(
                    nome,
                    argumentos,
                    estado,
                )

            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as erro:
                argumentos = {}

                resultado = {
                    "ok": False,
                    "erro": {
                        "codigo": (
                            "ARGUMENTOS_INVALIDOS"
                        ),
                        "mensagem": str(erro),
                        "orientacao": (
                            "Corrija os argumentos e "
                            "tente novamente."
                        ),
                    },
                }

            except Exception as erro:
                resultado = {
                    "ok": False,
                    "erro": {
                        "codigo": (
                            "ERRO_DA_FERRAMENTA"
                        ),
                        "mensagem": (
                            f"{type(erro).__name__}: "
                            f"{erro}"
                        ),
                        "orientacao": (
                            "Analise o erro retornado e "
                            "decida se é possível corrigir "
                            "a chamada ou se a execução "
                            "deve terminar."
                        ),
                    },
                }

        if (
            nome == "calcular_recomendacao"
            and resultado.get("ok")
        ):
            ultimo_plano = resultado

        fontes.extend(
            _fontes_do_resultado(
                nome,
                resultado,
                estado["turno_id"],
            )
        )

        chamadas_executadas += 1

        trajetoria.append(
            {
                "no": "executar_ferramentas",
                "ferramenta": nome,
                "argumentos": argumentos,
                "ok": resultado.get(
                    "ok",
                    False,
                ),
                "erro": resultado.get("erro"),
            }
        )

        mensagens.append(
            {
                "role": "tool",
                "tool_call_id": chamada["id"],
                "content": json.dumps(
                    resultado,
                    ensure_ascii=False,
                ),
            }
        )

    return {
        "mensagens": mensagens,
        "trajetoria": trajetoria,
        "fontes": fontes,
        "ultimo_plano": ultimo_plano,
        "chamadas_ferramenta_turno": (
            estado.get(
                "chamadas_ferramenta_turno",
                0,
            )
            + chamadas_executadas
        ),
    }

def aprovar_plano(
    estado: EstadoGrafo,
) -> dict:
    """
    Suspende o grafo antes da gravação do plano.

    Somente o proprietário pode aprovar, rejeitar ou editar o resumo.
    Se o prazo terminar, nenhuma escrita é realizada.
    """
    chamada = next(
        chamada
        for chamada in _ultima_mensagem(
            estado
        ).get("tool_calls", [])
        if (
            chamada["function"]["name"]
            == "registrar_plano"
        )
    )

    try:
        argumentos = json.loads(
            chamada["function"].get(
                "arguments",
                "{}",
            )
        )
    except json.JSONDecodeError:
        argumentos = {}

    plano = estado.get("ultimo_plano")

    if not plano:
        resultado = {
            "ok": False,
            "erro": {
                "codigo": "PLANO_AUSENTE",
                "mensagem": (
                    "Não existe um plano calculado "
                    "nesta conversa para registrar."
                ),
                "orientacao": (
                    "Calcule uma recomendação antes "
                    "de solicitar seu registro."
                ),
            },
        }

    else:
        solicitado_epoch = estado.get(
            "inicio_turno_epoch",
            time.time(),
        )

        prazo = (
            datetime.fromtimestamp(
                solicitado_epoch,
                timezone.utc,
            )
            + timedelta(
                hours=settings.approval_timeout_hours
            )
        )

        pedido = {
            "acao": "registrar_plano",
            "argumentos": {
                "feira": plano["feira"],
                "total_recomendado": (
                    plano["total_recomendado"]
                ),
                "resumo_plano": argumentos.get(
                    "resumo_plano",
                    "Plano calculado pelo agente.",
                ),
                "plano": plano["recomendacoes"],
            },
            "consequencia": (
                "O plano será gravado em "
                "dados/memoria.sqlite3. "
                "A operação é idempotente e pode ser "
                "revertida pela exclusão do registro."
            ),
            "respostas_aceitas": [
                "aprovar",
                "rejeitar",
                "editar",
            ],
            "expira_em": prazo.isoformat(),
        }

        # O interrupt grava o checkpoint e suspende o grafo.
        # A execução será retomada posteriormente com Command(resume=...).
        decisao_bruta = interrupt(pedido)

        try:
            decisao = DecisaoHumana.model_validate(
                decisao_bruta
            )
            erro_decisao = ""

        except Exception as erro:
            # Uma decisão inválida é tratada como rejeição segura.
            decisao = DecisaoHumana(
                acao="rejeitar"
            )
            erro_decisao = str(erro)

        if datetime.now(timezone.utc) > prazo:
            decisao = DecisaoHumana(
                acao="expirar"
            )

        if decisao.acao in {
            "rejeitar",
            "expirar",
        }:
            codigo = (
                "APROVACAO_EXPIRADA"
                if decisao.acao == "expirar"
                else "APROVACAO_REJEITADA"
            )

            mensagem = (
                "O prazo de aprovação venceu."
                if decisao.acao == "expirar"
                else (
                    "O proprietário rejeitou "
                    "o registro do plano."
                )
            )

            resultado = {
                "ok": False,
                "erro": {
                    "codigo": codigo,
                    "mensagem": mensagem,
                    "orientacao": (
                        "Nenhuma escrita foi realizada."
                    ),
                    "detalhe_validacao": (
                        erro_decisao
                    ),
                },
            }

        else:
            payload = pedido[
                "argumentos"
            ].copy()

            if decisao.acao == "editar":
                if (
                    decisao.resumo_plano
                    is not None
                ):
                    payload["resumo_plano"] = (
                        decisao.resumo_plano
                    )

            resultado = (
                obter_memoria()
                .registrar_plano_idempotente(
                    estado["usuario_id"],
                    estado["thread_id"],
                    payload,
                )
            )

    fontes: list[dict] = []

    if resultado.get("ok"):
        fonte = FonteResposta(
            tipo="ferramenta",
            referencia=(
                "memoria.sqlite3"
                "#planos_aprovados"
            ),
            detalhe=(
                "Registro idempotente realizado "
                "após decisão do proprietário."
            ),
        ).model_dump()

        fonte["turno_id"] = estado["turno_id"]
        fontes.append(fonte)

    return {
        "mensagens": [
            {
                "role": "tool",
                "tool_call_id": chamada["id"],
                "content": json.dumps(
                    resultado,
                    ensure_ascii=False,
                ),
            }
        ],
        "fontes": fontes,
        "trajetoria": [
            {
                "no": "aprovar_plano",
                "ferramenta": (
                    "registrar_plano"
                ),
                "ok": resultado.get(
                    "ok",
                    False,
                ),
                "ja_existia": resultado.get(
                    "ja_existia"
                ),
                "erro": resultado.get("erro"),
            }
        ],
        "chamadas_ferramenta_turno": (
            estado.get(
                "chamadas_ferramenta_turno",
                0,
            )
            + 1
        ),
    }


def _fontes_validadas(
    estado: EstadoGrafo,
) -> list[FonteResposta]:
    """
    Devolve somente as fontes realmente produzidas pelas ferramentas
    no turno atual.

    Fontes inventadas pelo modelo não atravessam esta validação.
    """
    fontes = [
        {
            chave: valor
            for chave, valor in fonte.items()
            if chave != "turno_id"
        }
        for fonte in estado.get(
            "fontes",
            [],
        )
        if (
            fonte.get("turno_id")
            == estado.get("turno_id")
        )
    ]

    if not fontes:
        fontes = [
            FonteResposta(
                tipo="sistema",
                referencia=(
                    "src/prompts/"
                    "orquestrador_v2.md"
                ),
                detalhe=(
                    "Contrato e limites do agente."
                ),
            ).model_dump()
        ]

    return [
        FonteResposta.model_validate(fonte)
        for fonte in fontes
    ]

def _plano_calculado_neste_turno(
    estado: EstadoGrafo,
) -> bool:
    """Confirma que o último plano foi calculado no turno atual."""

    return (
        estado.get("ultimo_plano") is not None
        and any(
            fonte.get("turno_id") == estado.get("turno_id")
            and fonte.get("tipo") == "mysql"
            and fonte.get("detalhe")
            == "Retornado pela ferramenta calcular_recomendacao."
            for fonte in estado.get("fontes", [])
        )
    )

def validar_saida(estado: EstadoGrafo) -> dict:
    fontes_validadas = _fontes_validadas(estado)
    normalizado_pelo_codigo = False
    plano_deterministico = _plano_calculado_neste_turno(
        estado
    )

    if estado.get("erro_fatal"):
        saida = SaidaAgente(
            status="erro",
            resultado=None,
            fontes=fontes_validadas,
            suficiente=False,
            motivo=estado["erro_fatal"],
            proxima_acao=(
                "Revise a configuração ou reduza a solicitação "
                "e tente novamente."
            ),
        )

        motivo_termino = estado.get(
            "motivo_termino",
            "ERRO_FATAL",
        )

    else:
        conteudo = _ultima_mensagem(estado).get("content") or ""

        try:
            bruto = json.loads(conteudo)

            if not isinstance(bruto, dict):
                raise ValueError(
                    "A resposta final precisa ser um objeto JSON."
                )

            # As fontes fornecidas pelo modelo não são confiáveis.
            # O código substitui esse campo pelas fontes que foram
            # realmente recuperadas durante o turno.
            bruto["fontes"] = []

            saida = SaidaAgente.model_validate(bruto)

        except Exception:
            normalizado_pelo_codigo = True

            if plano_deterministico:
                saida = SaidaAgente(
                    status="concluido",
                    resultado=estado["ultimo_plano"],
                    fontes=[],
                    suficiente=True,
                    motivo=(
                        "A recomendação foi calculada por uma "
                        "ferramenta determinística e validada "
                        "pelo código."
                    ),
                    proxima_acao=(
                        "O proprietário pode solicitar uma "
                        "explicação, outra simulação ou o "
                        "registro do plano."
                    ),
                )

            else:
                saida = SaidaAgente(
                    status="concluido" if conteudo else "erro",
                    resultado=conteudo or None,
                    fontes=[],
                    suficiente=bool(conteudo),
                    motivo=(
                        "Resposta normalizada pelo código após "
                        "falha no formato JSON."
                        if conteudo
                        else "O modelo não devolveu conteúdo."
                    ),
                    proxima_acao=(
                        "Revise a resposta e tente novamente."
                        if not conteudo
                        else None
                    ),
                )

        # Se uma recomendação foi calculada no turno atual,
        # o objeto devolvido ao proprietário vem diretamente
        # da ferramenta determinística. O LLM não precisa
        # repetir nem reconstruir as quantidades.
        if plano_deterministico:
            saida.status = "concluido"
            saida.resultado = estado["ultimo_plano"]
            saida.suficiente = True
            saida.motivo = (
                "A recomendação foi calculada por uma ferramenta "
                "determinística e validada pelo código."
            )

            if saida.proxima_acao is None:
                saida.proxima_acao = (
                    "O proprietário pode solicitar uma explicação, "
                    "outra simulação ou o registro do plano."
                )

        # As fontes finais sempre vêm das ferramentas realmente
        # utilizadas, nunca do texto produzido pelo modelo.
        saida.fontes = fontes_validadas

        mapa_motivos = {
            "concluido": "CONCLUIDO",
            "precisa_informacao": "PRECISA_INFORMACAO",
            "recusado": "RECUSADO",
            "aguardando_aprovacao": "AGUARDANDO_APROVACAO",
            "erro": "ERRO_VALIDADO",
        }

        motivo_termino = mapa_motivos[saida.status]

    return {
        "resposta_validada": saida.model_dump(mode="json"),
        "motivo_termino": motivo_termino,
        "trajetoria": [
            {
                "no": "validar_saida",
                "status": saida.status,
                "suficiente": saida.suficiente,
                "normalizado_pelo_codigo": normalizado_pelo_codigo,
                "resultado_deterministico": plano_deterministico,
            }
        ],
    }


def memorizar_episodio(
    estado: EstadoGrafo,
) -> dict:
    """
    Guarda apenas resultados conclusivos e suficientes na memória
    episódica de longo prazo.

    Recusas, erros e pedidos incompletos não são memorizados.
    """
    saida = (
        estado.get("resposta_validada")
        or {}
    )

    if (
        saida.get("status") != "concluido"
        or not saida.get("suficiente")
    ):
        return {
            "trajetoria": [
                {
                    "no": "memorizar_episodio",
                    "gravados": 0,
                    "motivo": (
                        "A saída não foi conclusiva "
                        "e suficiente."
                    ),
                }
            ]
        }

    resultado_resumido = json.dumps(
        saida.get("resultado"),
        ensure_ascii=False,
    )[:800]

    resumo = (
        f"Pedido: {estado['entrada_texto']} | "
        f"Resultado: {resultado_resumido}"
    )

    resultado = (
        obter_memoria()
        .salvar_episodio(
            estado["usuario_id"],
            resumo,
            tags=[
                saida.get(
                    "status",
                    "concluido",
                )
            ],
        )
    )

    return {
        "trajetoria": [
            {
                "no": "memorizar_episodio",
                "gravados": (
                    0
                    if resultado["ja_existia"]
                    else 1
                ),
                "ja_existia": resultado[
                    "ja_existia"
                ],
                "content_hash": resultado[
                    "content_hash"
                ],
            }
        ]
    }


# ============================================================
# CONSTRUÇÃO DO GRAFO
# ============================================================

construtor = StateGraph(EstadoGrafo)

construtor.add_node(
    "preparar_contexto",
    preparar_contexto,
)

construtor.add_node(
    "chamar_modelo",
    chamar_modelo,
)

construtor.add_node(
    "executar_ferramentas",
    executar_ferramentas,
)

construtor.add_node(
    "aprovar_plano",
    aprovar_plano,
)

construtor.add_node(
    "validar_saida",
    validar_saida,
)

construtor.add_node(
    "memorizar_episodio",
    memorizar_episodio,
)


# Entrada do grafo.
construtor.add_edge(
    START,
    "preparar_contexto",
)

construtor.add_edge(
    "preparar_contexto",
    "chamar_modelo",
)


# O router decide se o modelo solicitou ferramenta,
# aprovação humana ou se já produziu a resposta final.
construtor.add_conditional_edges(
    "chamar_modelo",
    rotear_apos_modelo,
    {
        "executar_ferramentas": (
            "executar_ferramentas"
        ),
        "aprovar_plano": (
            "aprovar_plano"
        ),
        "validar_saida": (
            "validar_saida"
        ),
    },
)


# Depois de uma ferramenta, o resultado volta ao modelo.
construtor.add_edge(
    "executar_ferramentas",
    "chamar_modelo",
)


# Depois da decisão humana, o resultado também volta ao modelo.
construtor.add_edge(
    "aprovar_plano",
    "chamar_modelo",
)


# A resposta final passa pela validação e pela política de memória.
construtor.add_edge(
    "validar_saida",
    "memorizar_episodio",
)

construtor.add_edge(
    "memorizar_episodio",
    END,
)


# ============================================================
# CHECKPOINT PERSISTENTE
# ============================================================_fontes_validada

# O SQLite utilizado aqui não substitui o MySQL do negócio.
# Ele serve somente para persistir o estado do LangGraph e permitir
# que uma execução interrompida seja retomada posteriormente.
settings.checkpoint_database.parent.mkdir(
    parents=True,
    exist_ok=True,
)

_checkpoint_connection = sqlite3.connect(
    settings.checkpoint_database,
    check_same_thread=False,
)

checkpointer = SqliteSaver(
    _checkpoint_connection
)


# O grafo é compilado apenas uma vez.
# GRAPH_RECURSION_LIMIT será informado no momento da invocação.
grafo = construtor.compile(
    checkpointer=checkpointer
)