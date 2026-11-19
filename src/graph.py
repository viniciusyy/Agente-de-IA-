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
from langgraph.types import Command, interrupt
from openai import OpenAI

from src import observabilidade as obs
from src.capacidade import pedido_plano_com_capacidade_zero
from src.config import settings
from src.database import consultar_historico, consultar_operacao
from src.domain import calcular_recomendacao, resumir_historico, resumir_operacao
from src.glossario import (
    CONSULTA_SOBRA_ZERO,
    detectar_pergunta_sobra_zero,
    responder_sobra_zero,
)
from src.memory import obter_memoria
from src.rag import buscar_conhecimento
from src.regras_feira import (
    consulta_da_regra,
    detectar_pedido_regra,
    responder_regra_feira,
)
from src.schemas import DecisaoHumana, FonteResposta, SaidaAgente
from src.seguranca import (
    ErroSeguranca,
    autorizar_preferencia,
    contrato_argumentos,
    validar_argumentos,
    validar_lote_chamadas,
    validar_plano_para_registro,
    validar_resumo_episodio,
)


def juntar_fontes(atual: list[dict], novas: list[dict]) -> list[dict]:
    """Acumula fontes sem repetir a mesma referência."""
    unicas: dict[tuple[str, str], dict] = {}
    for fonte in [*(atual or []), *(novas or [])]:
        chave = (fonte.get("tipo", "sistema"), fonte.get("referencia", ""))
        unicas[chave] = fonte
    return list(unicas.values())


class EstadoGrafo(TypedDict, total=False):
    # Conversa acumulada pelo reducer.
    mensagens: Annotated[list[dict[str, Any]], operator.add]

    # Contrato e identificação.
    entrada_texto: str
    usuario_id: str
    thread_id: str
    turno_id: str

    # Contexto recuperado.
    memoria_semantica: dict[str, str]
    memoria_episodica: list[dict]
    fontes: Annotated[list[dict], juntar_fontes]

    # Trajetória e proteção do laço.
    trajetoria: Annotated[list[dict], operator.add]
    assinaturas_passos: Annotated[list[str], operator.add]
    passos_turno: int
    chamadas_ferramenta_turno: int
    tokens_entrada_turno: int
    tokens_saida_turno: int
    custo_turno_usd: float
    inicio_turno_epoch: float

    # Produtos intermediários.
    ultimo_plano: dict | None
    turno_resultado_recomendacao: str | None
    resposta_validada: dict | None
    erro_fatal: str | None
    motivo_termino: str


# Os parâmetros enviados ao modelo usam o mesmo contrato validado no código.
_DESCRICOES_FERRAMENTAS = {
    "consultar_historico": "Consulta no MySQL as operações recentes de uma feira.",
    "consultar_operacao": "Consulta uma operação do MySQL pelo identificador.",
    "buscar_conhecimento": (
        "Busca regras, vocabulário, processo e exceções no corpus "
        "curado da Pastéis Miyata. Use quando a decisão depender de "
        "conhecimento do domínio, não de um registro do MySQL."
    ),
    "calcular_recomendacao": (
        "Calcula fora do LLM um baseline de produção pela média das "
        "cinco vendas recentes e aplica as restrições da feira."
    ),
    "salvar_preferencia": (
        "Guarda uma preferência operacional estável que o proprietário "
        "declarou explicitamente, como prioridade padrão."
    ),
    "registrar_plano": (
        "Solicita o registro do último plano calculado. Esta ferramenta "
        "sempre pausa o grafo para aprovação, rejeição ou edição humana."
    ),
}

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": contrato_argumentos(nome),
        },
    }
    for nome, descricao in _DESCRICOES_FERRAMENTAS.items()
]

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _ler_prompt(nome: str) -> str:
    return (PROMPT_DIR / nome).read_text(encoding="utf-8")


def _custo(tokens_entrada: int, tokens_saida: int) -> float:
    return (
        tokens_entrada / 1_000_000 * settings.llm_input_price_per_million
        + tokens_saida / 1_000_000 * settings.llm_output_price_per_million
    )


def _fontes_do_resultado(nome: str, resultado: dict, turno_id: str) -> list[dict]:
    fontes: list[dict] = []

    if nome in {"consultar_historico", "consultar_operacao", "calcular_recomendacao"}:
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
                referencia=f"{item['caminho']}#{item['documento_id']}",
                detalhe=f"{item['titulo']} — versão {item['versao']}",
            ).model_dump()
            fonte["turno_id"] = turno_id
            fontes.append(fonte)

    elif nome == "salvar_preferencia":
        fonte = FonteResposta(
            tipo="memoria",
            referencia=f"memoria_semantica:{resultado.get('chave', '')}",
            detalhe="Fato declarado pelo proprietário.",
        ).model_dump()
        fonte["turno_id"] = turno_id
        fontes.append(fonte)

    return fontes


def rotear_entrada(
    estado: EstadoGrafo,
) -> Literal[
    "recusar_capacidade_zero",
    "consultar_regra_feira",
    "consultar_glossario",
    "preparar_contexto",
]:
    entrada = estado.get("entrada_texto", "")

    if pedido_plano_com_capacidade_zero(entrada):
        return "recusar_capacidade_zero"

    if detectar_pedido_regra(entrada) is not None:
        return "consultar_regra_feira"

    if detectar_pergunta_sobra_zero(entrada):
        return "consultar_glossario"

    return "preparar_contexto"


def consultar_glossario(estado: EstadoGrafo) -> dict:
    consulta = CONSULTA_SOBRA_ZERO
    try:
        recuperacao = obs.ferramenta(
            "buscar_conhecimento",
            {"consulta": consulta},
            lambda: buscar_conhecimento(consulta),
        )
    except (OSError, ValueError):
        recuperacao = {
            "ok": False,
            "erro": {
                "codigo": "BUSCA_GLOSSARIO_FALHOU",
                "mensagem": "A consulta ao glossário não pôde ser concluída.",
            },
        }

    dados_saida, documento_usado = responder_sobra_zero(recuperacao)
    obs.registrar_decisao_rag("consultar_glossario", documento_usado, dados_saida)
    saida = SaidaAgente(**dados_saida)
    fontes = (
        _fontes_do_resultado(
            "buscar_conhecimento",
            {"resultados": [documento_usado]},
            estado["turno_id"],
        )
        if documento_usado is not None
        else []
    )

    return {
        "mensagens": [{"role": "assistant", "content": saida.model_dump_json()}],
        "turno_resultado_recomendacao": None,
        "fontes": fontes,
        "chamadas_ferramenta_turno": estado.get("chamadas_ferramenta_turno", 0) + 1,
        "trajetoria": [
            {
                "no": "consultar_glossario",
                "ferramenta": "buscar_conhecimento",
                "argumentos": {"consulta": consulta},
                "ok": recuperacao.get("ok") is True,
                "erro": recuperacao.get("erro"),
            }
        ],
    }


def consultar_regra_feira(estado: EstadoGrafo) -> dict:
    pedido = detectar_pedido_regra(estado["entrada_texto"])
    if pedido is None:
        raise RuntimeError("A rota de regras recebeu uma entrada não reconhecida.")

    consulta = consulta_da_regra(pedido)
    try:
        recuperacao = obs.ferramenta(
            "buscar_conhecimento",
            {"consulta": consulta},
            lambda: buscar_conhecimento(consulta),
        )
    except (OSError, ValueError):
        recuperacao = {
            "ok": False,
            "erro": {
                "codigo": "BUSCA_DE_REGRA_FALHOU",
                "mensagem": "A consulta ao corpus não pôde ser concluída.",
            },
        }

    dados_saida, documento_usado = responder_regra_feira(pedido, recuperacao)
    obs.registrar_decisao_rag(
        "consultar_regra_feira", documento_usado, dados_saida, pedido
    )
    saida = SaidaAgente(**dados_saida)

    fontes = (
        _fontes_do_resultado(
            "buscar_conhecimento",
            {"resultados": [documento_usado]},
            estado["turno_id"],
        )
        if documento_usado is not None
        else []
    )

    return {
        "mensagens": [{"role": "assistant", "content": saida.model_dump_json()}],
        "turno_resultado_recomendacao": None,
        "fontes": fontes,
        "chamadas_ferramenta_turno": estado.get("chamadas_ferramenta_turno", 0) + 1,
        "trajetoria": [
            {
                "no": "consultar_regra_feira",
                "ferramenta": "buscar_conhecimento",
                "argumentos": {"consulta": consulta},
                "ok": recuperacao.get("ok") is True,
                "erro": recuperacao.get("erro"),
            }
        ],
    }


def recusar_capacidade_zero(estado: EstadoGrafo) -> dict:
    obs.registrar_capacidade_zero()

    saida = SaidaAgente(
        status="recusado",
        resultado=None,
        suficiente=False,
        motivo=(
            "A capacidade total informada é zero. Não é possível recomendar "
            "produção positiva dentro desse limite. Nenhum plano foi gerado."
        ),
        proxima_acao=(
            "Consulte o histórico ou peça uma estimativa sem um teto obrigatório. "
            "O baseline atual não ajusta a produção à capacidade informada."
        ),
    )

    fonte = FonteResposta(
        tipo="usuario",
        referencia="entrada:capacidade_total",
        detalhe="Capacidade total zero informada no pedido.",
    ).model_dump()
    fonte["turno_id"] = estado["turno_id"]

    return {
        "mensagens": [{"role": "assistant", "content": saida.model_dump_json()}],
        "turno_resultado_recomendacao": None,
        "fontes": [fonte],
        "trajetoria": [
            {"no": "recusar_capacidade_zero", "codigo": "CAPACIDADE_TOTAL_ZERO"}
        ],
    }


def preparar_contexto(estado: EstadoGrafo) -> dict:
    memoria = obter_memoria()
    fatos = memoria.ler_fatos_semanticos(estado["usuario_id"])
    episodios = memoria.buscar_episodios(
        estado["usuario_id"], estado["entrada_texto"], limite=3
    )
    obs.registrar_memoria(fatos, episodios)

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
    if estado.get("passos_turno", 0) >= settings.agent_max_steps:
        return "LIMITE_DE_PASSOS"

    if estado.get("chamadas_ferramenta_turno", 0) >= settings.agent_max_tool_calls:
        return "LIMITE_DE_FERRAMENTAS"

    if (
        estado.get("tokens_entrada_turno", 0) + estado.get("tokens_saida_turno", 0)
        >= settings.agent_max_tokens
    ):
        return "LIMITE_DE_TOKENS"

    if (
        time.time() - estado.get("inicio_turno_epoch", time.time())
        >= settings.agent_max_time_seconds
    ):
        return "LIMITE_DE_TEMPO"

    if estado.get("custo_turno_usd", 0.0) >= settings.agent_max_cost_usd:
        return "LIMITE_DE_CUSTO"

    return None


def _assinatura_chamadas(chamadas: list[dict], turno_id: str) -> str:
    canonico = json.dumps(
        {"turno_id": turno_id, "chamadas": chamadas},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _janela_conversa(mensagens: list[dict]) -> list[dict]:
    """Mantém turnos completos e nunca começa por retorno de ferramenta."""
    posicoes_usuario = [
        indice
        for indice, mensagem in enumerate(mensagens)
        if mensagem.get("role") == "user"
    ]
    if len(posicoes_usuario) <= settings.conversation_max_turns:
        return mensagens

    inicio = posicoes_usuario[-settings.conversation_max_turns]
    return mensagens[inicio:]


def chamar_modelo(estado: EstadoGrafo) -> dict:
    motivo_orcamento = _verificar_orcamento(estado)
    if motivo_orcamento:
        return {
            "erro_fatal": motivo_orcamento,
            "motivo_termino": motivo_orcamento,
            "trajetoria": [{"no": "chamar_modelo", "erro": motivo_orcamento}],
        }

    try:
        settings.validar_modelo()
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url,
        )

        prompt = _ler_prompt("orquestrador_v2.md")
        procedimento = _ler_prompt("procedimento_planejamento_v1.md")
        contexto = {
            "memoria_semantica": estado.get("memoria_semantica", {}),
            "episodios_relevantes": estado.get("memoria_episodica", []),
        }

        mensagens = [
            {
                "role": "system",
                "content": (
                    prompt
                    + "\n\n# Memória procedural\n"
                    + procedimento
                    + "\n\n# Memória recuperada para esta execução\n"
                    + json.dumps(contexto, ensure_ascii=False)
                ),
            },
            *_janela_conversa(estado.get("mensagens", [])),
        ]

        kwargs: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": mensagens,
            "tools": FERRAMENTAS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "max_completion_tokens": settings.llm_max_output_tokens,
        }
        if "api.openai.com" in settings.llm_base_url:
            kwargs["reasoning_effort"] = "none"

        resposta = obs.chat(
            client.chat.completions.create, kwargs, settings, prompt, procedimento
        )

        mensagem = resposta.choices[0].message.model_dump(exclude_none=True)
        chamadas = mensagem.get("tool_calls", [])
        if chamadas:
            validar_lote_chamadas(chamadas)

        assinatura = _assinatura_chamadas(chamadas, estado["turno_id"]) if chamadas else ""
        repeticoes = (
            estado.get("assinaturas_passos", [])[-settings.loop_repeat_limit :].count(assinatura)
            if assinatura
            else 0
        )

        if assinatura and repeticoes >= settings.loop_repeat_limit - 1:
            return {
                "erro_fatal": "LACO_DETECTADO",
                "motivo_termino": "LACO_DETECTADO",
                "trajetoria": [
                    {
                        "no": "chamar_modelo",
                        "erro": "A mesma decisão de ferramenta se repetiu.",
                        "assinatura": assinatura,
                    }
                ],
            }

        tokens_entrada = resposta.usage.prompt_tokens if resposta.usage else 0
        tokens_saida = resposta.usage.completion_tokens if resposta.usage else 0

        return {
            "mensagens": [mensagem],
            "passos_turno": estado.get("passos_turno", 0) + 1,
            "tokens_entrada_turno": estado.get("tokens_entrada_turno", 0) + tokens_entrada,
            "tokens_saida_turno": estado.get("tokens_saida_turno", 0) + tokens_saida,
            "custo_turno_usd": estado.get("custo_turno_usd", 0.0)
            + _custo(tokens_entrada, tokens_saida),
            "assinaturas_passos": [assinatura] if assinatura else [],
            "trajetoria": [
                {
                    "no": "chamar_modelo",
                    "modelo": settings.llm_model,
                    "chamadas": [
                        chamada.get("function", {}).get("name")
                        for chamada in chamadas
                    ],
                    "tokens_entrada": tokens_entrada,
                    "tokens_saida": tokens_saida,
                }
            ],
        }

    except ErroSeguranca as erro:
        return {
            "erro_fatal": str(erro),
            "motivo_termino": erro.codigo,
            "trajetoria": [{"no": "chamar_modelo", "erro": erro.codigo}],
        }

    except Exception as erro:
        tipo = type(erro).__name__
        return {
            "erro_fatal": f"ERRO_DO_MODELO: {tipo}. Detalhes do provedor omitidos.",
            "motivo_termino": "ERRO_DO_MODELO",
            "trajetoria": [
                {"no": "chamar_modelo", "erro": f"{tipo}: detalhes omitidos"}
            ],
        }


def _ultima_mensagem(estado: EstadoGrafo) -> dict:
    return estado.get("mensagens", [{}])[-1]


def rotear_apos_modelo(
    estado: EstadoGrafo,
) -> Literal["executar_ferramentas", "aprovar_plano", "validar_saida"]:
    if estado.get("erro_fatal"):
        return "validar_saida"

    chamadas = _ultima_mensagem(estado).get("tool_calls", [])
    if not chamadas:
        return "validar_saida"

    if any(
        chamada.get("function", {}).get("name") == "registrar_plano"
        for chamada in chamadas
    ):
        return "aprovar_plano"

    return "executar_ferramentas"


def _executar(nome: str, argumentos: dict, estado: EstadoGrafo) -> dict:
    try:
        argumentos = validar_argumentos(nome, argumentos)
        if nome == "salvar_preferencia":
            autorizar_preferencia(estado.get("entrada_texto", ""), argumentos)
    except ErroSeguranca as erro:
        return erro.como_resultado()

    if nome == "registrar_plano":
        return ErroSeguranca(
            "APROVACAO_OBRIGATORIA",
            "O registro só pode ocorrer no nó de aprovação humana.",
        ).como_resultado()

    if nome == "consultar_historico":
        return obs.ferramenta(
            nome,
            argumentos,
            lambda: resumir_historico(
                consultar_historico(
                    argumentos["codigo_feira"], argumentos.get("limite_operacoes", 5)
                )
            ),
            chamada_id=obs.id_chamada(estado, nome),
        )

    if nome == "consultar_operacao":
        return obs.ferramenta(
            nome,
            argumentos,
            lambda: resumir_operacao(consultar_operacao(argumentos["id_operacao"])),
            chamada_id=obs.id_chamada(estado, nome),
        )

    if nome == "buscar_conhecimento":
        return obs.ferramenta(
            nome,
            argumentos,
            lambda: buscar_conhecimento(argumentos["consulta"]),
            chamada_id=obs.id_chamada(estado, nome),
        )

    if nome == "calcular_recomendacao":
        return obs.ferramenta(
            nome,
            argumentos,
            lambda: calcular_recomendacao(argumentos["codigo_feira"]),
            chamada_id=obs.id_chamada(estado, nome),
        )

    if nome == "salvar_preferencia":
        return obs.ferramenta(
            nome,
            argumentos,
            lambda: obter_memoria().salvar_fato_semantico(
                estado["usuario_id"], argumentos["chave"], argumentos["valor"]
            ),
            chamada_id=obs.id_chamada(estado, nome),
        )

    return {
        "ok": False,
        "erro": {
            "codigo": "FERRAMENTA_DESCONHECIDA",
            "mensagem": f"Ferramenta desconhecida: {nome}",
            "orientacao": "Use somente as ferramentas declaradas.",
        },
    }


def executar_ferramentas(estado: EstadoGrafo) -> dict:
    mensagens, trajetoria, fontes = [], [], []
    ultimo_plano = estado.get("ultimo_plano")
    turno_resultado_recomendacao = None
    chamadas_executadas = 0

    for chamada in _ultima_mensagem(estado).get("tool_calls", []):
        nome = chamada["function"]["name"]
        argumentos: dict = {}

        if (
            estado.get("chamadas_ferramenta_turno", 0) + chamadas_executadas
            >= settings.agent_max_tool_calls
        ):
            resultado = {
                "ok": False,
                "erro": {
                    "codigo": "LIMITE_DE_FERRAMENTAS",
                    "mensagem": "O teto de ferramentas desta execução foi atingido.",
                    "orientacao": "Encerre com o que já foi verificado.",
                },
            }
        else:
            try:
                argumentos = validar_argumentos(
                    nome, chamada["function"].get("arguments", "{}")
                )
                resultado = _executar(nome, argumentos, estado)
            except ErroSeguranca as erro:
                argumentos = {}
                resultado = erro.como_resultado()
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                argumentos = {}
                resultado = {
                    "ok": False,
                    "erro": {
                        "codigo": "ARGUMENTOS_INVALIDOS",
                        "mensagem": "Argumentos fora do contrato da ferramenta.",
                        "orientacao": "Corrija os argumentos e tente novamente.",
                    },
                }

        obs.registrar_bloqueio(nome, resultado)

        if nome == "calcular_recomendacao" and resultado.get("ok") is True:
            ultimo_plano = resultado
            turno_resultado_recomendacao = estado["turno_id"]
        else:
            # Outra operação ou uma tentativa malsucedida não conclui o plano.
            turno_resultado_recomendacao = None

        fontes.extend(_fontes_do_resultado(nome, resultado, estado["turno_id"]))
        chamadas_executadas += 1
        trajetoria.append({
            "no": "executar_ferramentas",
            "ferramenta": nome,
            "argumentos": argumentos,
            "ok": resultado.get("ok", False),
            "erro": resultado.get("erro"),
        })
        mensagens.append({
            "role": "tool",
            "tool_call_id": chamada["id"],
            "content": json.dumps(resultado, ensure_ascii=False),
        })

    return {
        "mensagens": mensagens,
        "trajetoria": trajetoria,
        "fontes": fontes,
        "ultimo_plano": ultimo_plano,
        "turno_resultado_recomendacao": turno_resultado_recomendacao,
        "chamadas_ferramenta_turno": (
            estado.get("chamadas_ferramenta_turno", 0) + chamadas_executadas
        ),
    }


def aprovar_plano(
    estado: EstadoGrafo,
) -> Command[Literal["chamar_modelo", "validar_saida"]]:
    chamada = next(
        chamada
        for chamada in _ultima_mensagem(estado).get("tool_calls", [])
        if chamada["function"]["name"] == "registrar_plano"
    )
    rejeicao_explicita = False
    plano = estado.get("ultimo_plano")
    erro_precondicao = None

    try:
        argumentos = validar_argumentos(
            "registrar_plano", chamada["function"].get("arguments", "{}")
        )
        if plano:
            validar_plano_para_registro(plano)

        if estado.get("chamadas_ferramenta_turno", 0) >= settings.agent_max_tool_calls:
            raise ErroSeguranca(
                "LIMITE_DE_FERRAMENTAS", "O teto de ferramentas foi atingido."
            )
    except ErroSeguranca as erro:
        argumentos = {}
        erro_precondicao = erro

    if erro_precondicao is not None:
        resultado = erro_precondicao.como_resultado()

    elif not plano:
        resultado = {
            "ok": False,
            "erro": {
                "codigo": "PLANO_AUSENTE",
                "mensagem": "Não existe plano calculado nesta conversa para registrar.",
                "orientacao": "Calcule uma recomendação antes de pedir o registro.",
            },
        }

    else:
        solicitado_epoch = estado.get("inicio_turno_epoch", time.time())
        prazo = datetime.fromtimestamp(solicitado_epoch, timezone.utc) + timedelta(
            hours=settings.approval_timeout_hours
        )
        pedido = {
            "acao": "registrar_plano",
            "argumentos": {
                "feira": plano["feira"],
                "total_recomendado": plano["total_recomendado"],
                "resumo_plano": argumentos.get(
                    "resumo_plano", "Plano calculado pelo agente."
                ),
                "plano": plano["recomendacoes"],
            },
            "consequencia": (
                "O plano será gravado em dados/memoria.sqlite3. "
                "A operação é idempotente e reversível por exclusão do registro."
            ),
            "respostas_aceitas": ["aprovar", "rejeitar", "editar"],
            "expira_em": prazo.isoformat(),
        }

        decisao_bruta = obs.aguardar_aprovacao(interrupt, pedido, estado, chamada)
        try:
            decisao = DecisaoHumana.model_validate(decisao_bruta)
        except Exception:
            decisao = DecisaoHumana(acao="rejeitar")
            erro_decisao = "Decisão humana fora do contrato permitido."
        else:
            erro_decisao = ""
            rejeicao_explicita = decisao.acao == "rejeitar"

        if datetime.now(timezone.utc) > prazo:
            decisao = DecisaoHumana(acao="expirar")
            rejeicao_explicita = False

        obs.registrar_decisao_aprovacao(decisao, estado, chamada, erro_decisao)

        if decisao.acao in {"rejeitar", "expirar"}:
            resultado = {
                "ok": False,
                "erro": {
                    "codigo": (
                        "APROVACAO_EXPIRADA"
                        if decisao.acao == "expirar"
                        else "APROVACAO_REJEITADA"
                    ),
                    "mensagem": (
                        "O prazo de aprovação venceu."
                        if decisao.acao == "expirar"
                        else "O proprietário rejeitou o registro."
                    ),
                    "orientacao": "Nenhuma escrita foi realizada.",
                    "detalhe_validacao": erro_decisao,
                },
            }
        else:
            payload = pedido["argumentos"].copy()
            if decisao.acao == "editar" and decisao.resumo_plano is not None:
                payload["resumo_plano"] = decisao.resumo_plano

            try:
                # A edição humana muda somente o resumo.
                validar_argumentos(
                    "registrar_plano", {"resumo_plano": payload["resumo_plano"]}
                )
            except ErroSeguranca as erro:
                resultado = erro.como_resultado()
            else:
                resultado = obs.ferramenta(
                    "registrar_plano",
                    payload,
                    lambda: obter_memoria().registrar_plano_idempotente(
                        estado["usuario_id"], estado["thread_id"], payload
                    ),
                    chamada_id=chamada["id"],
                )

    obs.registrar_bloqueio("registrar_plano", resultado)

    atualizacao: EstadoGrafo = {
        # Após registrar ou rejeitar, a saída é da aprovação, não do cálculo.
        "turno_resultado_recomendacao": None,
        "mensagens": [
            {
                "role": "tool",
                "tool_call_id": chamada["id"],
                "content": json.dumps(resultado, ensure_ascii=False),
            }
        ],
        "fontes": [
            dict(
                FonteResposta(
                    tipo="ferramenta",
                    referencia="memoria.sqlite3#planos_aprovados",
                    detalhe="Registro idempotente após decisão do proprietário.",
                ).model_dump(),
                turno_id=estado["turno_id"],
            )
        ]
        if resultado.get("ok")
        else [],
        "trajetoria": [
            {
                "no": "aprovar_plano",
                "ferramenta": "registrar_plano",
                "ok": resultado.get("ok", False),
                "ja_existia": resultado.get("ja_existia"),
                "erro": resultado.get("erro"),
            }
        ],
        "chamadas_ferramenta_turno": estado.get("chamadas_ferramenta_turno", 0) + 1,
    }

    if rejeicao_explicita:
        # A rejeição é definitiva e não precisa ser reinterpretada pelo modelo.
        recusa = SaidaAgente(
            status="recusado",
            resultado=None,
            suficiente=False,
            motivo="O proprietário rejeitou o registro. Nenhum plano foi gravado.",
        )
        atualizacao["mensagens"].append(
            {"role": "assistant", "content": recusa.model_dump_json()}
        )
        return Command(update=atualizacao, goto="validar_saida")

    return Command(update=atualizacao, goto="chamar_modelo")


def _fontes_validadas(estado: EstadoGrafo) -> list[FonteResposta]:
    fontes = [
        {chave: valor for chave, valor in fonte.items() if chave != "turno_id"}
        for fonte in estado.get("fontes", [])
        if fonte.get("turno_id") == estado.get("turno_id")
    ]
    if not fontes:
        fontes = [
            FonteResposta(
                tipo="sistema",
                referencia="src/prompts/orquestrador_v2.md",
                detalhe="Contrato e limites do agente.",
            ).model_dump()
        ]

    return [FonteResposta.model_validate(fonte) for fonte in fontes]


def _resultado_recomendacao_do_turno(estado: EstadoGrafo) -> dict | None:
    turno_id = estado.get("turno_id")
    plano = estado.get("ultimo_plano")

    if (
        not turno_id
        or estado.get("turno_resultado_recomendacao") != turno_id
        or not isinstance(plano, dict)
        or plano.get("ok") is not True
    ):
        return None

    # A fonte já é representada no campo superior `fontes`.
    return {chave: valor for chave, valor in plano.items() if chave not in {"ok", "fonte"}}


def _totais_operacao_do_turno(estado: EstadoGrafo) -> dict[str, int] | None:
    retorno = None

    for mensagem in reversed(estado.get("mensagens", [])):
        papel = mensagem.get("role")
        if papel == "user":
            break

        if retorno is None:
            if papel == "tool":
                if not mensagem.get("tool_call_id"):
                    return None
                retorno = mensagem
            continue

        if papel != "assistant":
            continue

        for chamada in mensagem.get("tool_calls") or []:
            if chamada.get("id") != retorno["tool_call_id"]:
                continue

            funcao = chamada.get("function") or {}
            if funcao.get("name") != "consultar_operacao":
                return None

            try:
                resultado = json.loads(retorno.get("content") or "{}")
            except (TypeError, json.JSONDecodeError):
                return None

            if not isinstance(resultado, dict) or resultado.get("ok") is not True:
                return None

            campos = ("id_operacao", "total_produzido", "total_vendido", "total_sobra")
            if not all(type(resultado.get(campo)) is int for campo in campos):
                return None

            return {campo: resultado[campo] for campo in campos}

    return None


def validar_saida(estado: EstadoGrafo) -> dict:
    if estado.get("erro_fatal"):
        saida = SaidaAgente(
            status="erro",
            resultado=None,
            fontes=_fontes_validadas(estado),
            suficiente=False,
            motivo=estado["erro_fatal"],
            proxima_acao="Revise a configuração ou reduza a solicitação e tente novamente.",
        )
        motivo_termino = estado.get("motivo_termino", "ERRO_FATAL")

    else:
        conteudo = _ultima_mensagem(estado).get("content") or ""
        bruto = None

        try:
            bruto = json.loads(conteudo)
            saida = SaidaAgente.model_validate(bruto)
        except Exception:
            # O contrato externo continua válido se o modelo falhar no JSON.
            obs.marcar_saida_normalizada()
            saida = SaidaAgente(
                status="concluido" if conteudo else "erro",
                resultado=conteudo or None,
                fontes=_fontes_validadas(estado),
                suficiente=bool(conteudo),
                motivo=(
                    "Resposta normalizada pelo código após falha no formato JSON."
                    if conteudo
                    else "O modelo não devolveu conteúdo."
                ),
            )
        else:
            saida.fontes = _fontes_validadas(estado)

        # Uma falha de formato não permite ignorar uma recusa explícita.
        admite_recomendacao = not isinstance(bruto, dict) or (
            bruto.get("status", "concluido") == "concluido"
            and bruto.get("suficiente", True) is True
        )

        if saida.status == "concluido" and saida.suficiente and admite_recomendacao:
            recomendacao = _resultado_recomendacao_do_turno(estado)
            if recomendacao is not None:
                saida.resultado = recomendacao
            else:
                totais = _totais_operacao_do_turno(estado)
                if totais is not None:
                    if isinstance(saida.resultado, dict):
                        detalhes = saida.resultado
                    elif isinstance(saida.resultado, list):
                        detalhes = {"dados": saida.resultado}
                    else:
                        detalhes = {}

                    # Os valores da ferramenta prevalecem sobre os do modelo.
                    saida.resultado = {**detalhes, **totais}

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
            }
        ],
    }


def memorizar_episodio(estado: EstadoGrafo) -> dict:
    saida = estado.get("resposta_validada") or {}
    if saida.get("status") != "concluido" or not saida.get("suficiente"):
        return {
            "trajetoria": [
                {"no": "memorizar_episodio", "gravados": 0, "motivo": "saída não conclusiva"}
            ]
        }

    plano = _resultado_recomendacao_do_turno(estado)
    if plano is None:
        return {
            "trajetoria": [
                {
                    "no": "memorizar_episodio",
                    "gravados": 0,
                    "motivo": "nenhum plano verificável calculado neste turno",
                }
            ]
        }

    try:
        resumo = validar_resumo_episodio(
            json.dumps(
                {
                    "tipo": "plano_calculado_v1",
                    "feira": plano.get("feira"),
                    "total_recomendado": plano.get("total_recomendado"),
                    "operacoes_consideradas": plano.get("operacoes_consideradas"),
                },
                ensure_ascii=False,
            )
        )
    except ErroSeguranca as erro:
        return {
            "trajetoria": [
                {"no": "memorizar_episodio", "gravados": 0, "erro": erro.codigo}
            ]
        }

    resultado = obter_memoria().salvar_episodio(estado["usuario_id"], resumo)
    if resultado.get("ok") is not True:
        return {
            "trajetoria": [
                {
                    "no": "memorizar_episodio",
                    "gravados": 0,
                    "erro": (resultado.get("erro") or {}).get(
                        "codigo", "EPISODIO_NAO_VERIFICADO"
                    ),
                }
            ]
        }

    return {
        "trajetoria": [
            {
                "no": "memorizar_episodio",
                "gravados": 0 if resultado["ja_existia"] else 1,
                "ja_existia": resultado["ja_existia"],
                "content_hash": resultado["content_hash"],
            }
        ]
    }


construtor = StateGraph(EstadoGrafo)
construtor.add_node("preparar_contexto", preparar_contexto)
construtor.add_node("recusar_capacidade_zero", recusar_capacidade_zero)
construtor.add_node("consultar_regra_feira", consultar_regra_feira)
construtor.add_node("chamar_modelo", chamar_modelo)
construtor.add_node("executar_ferramentas", executar_ferramentas)
construtor.add_node("aprovar_plano", aprovar_plano)
construtor.add_node("validar_saida", validar_saida)
construtor.add_node("memorizar_episodio", memorizar_episodio)
construtor.add_node("consultar_glossario", consultar_glossario)

construtor.add_conditional_edges(
    START,
    rotear_entrada,
    {
        "recusar_capacidade_zero": "recusar_capacidade_zero",
        "consultar_regra_feira": "consultar_regra_feira",
        "preparar_contexto": "preparar_contexto",
        "consultar_glossario": "consultar_glossario",
    },
)
construtor.add_edge("recusar_capacidade_zero", "validar_saida")
construtor.add_edge("consultar_regra_feira", "validar_saida")
construtor.add_edge("consultar_glossario", "validar_saida")
construtor.add_edge("preparar_contexto", "chamar_modelo")
construtor.add_conditional_edges(
    "chamar_modelo",
    rotear_apos_modelo,
    {
        "executar_ferramentas": "executar_ferramentas",
        "aprovar_plano": "aprovar_plano",
        "validar_saida": "validar_saida",
    },
)
construtor.add_edge("executar_ferramentas", "chamar_modelo")
construtor.add_edge("validar_saida", "memorizar_episodio")
construtor.add_edge("memorizar_episodio", END)

# O checkpointer em SQLite persiste conversas e aprovações pendentes.
settings.checkpoint_database.parent.mkdir(parents=True, exist_ok=True)
_checkpoint_connection = sqlite3.connect(
    settings.checkpoint_database, check_same_thread=False
)
checkpointer = SqliteSaver(_checkpoint_connection)

# O limite de recursão é declarado na configuração de cada invocação.
grafo = construtor.compile(checkpointer=checkpointer)