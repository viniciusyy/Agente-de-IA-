"""Tracing do agente, opt-in e local. Nunca serializa objetos de negócio inteiros."""

from __future__ import annotations

import json
import logging
import math
import os
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache, wraps
from hashlib import sha256
from pathlib import Path
from threading import Lock
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

AGENTE = "pasteis-miyata"
VERSAO_INSTRUMENTACAO = "1.0.0"
PERGUNTA_DEMO = "Sobra zero prova que faltou produto?"

_FEIRAS = frozenset({"QUA", "QUI", "SAB_C", "SAB_E", "DOM_C", "DOM_E"})
_FERRAMENTAS = frozenset({
    "consultar_historico", "consultar_operacao", "calcular_recomendacao",
    "buscar_conhecimento", "salvar_preferencia", "registrar_plano",
})
_STATUS = frozenset({
    "concluido", "recusado", "precisa_informacao", "aguardando_aprovacao", "erro",
})
_LIMITES = frozenset({
    "LIMITE_DE_PASSOS", "LIMITE_DE_FERRAMENTAS", "LIMITE_DE_TOKENS",
    "LIMITE_DE_TEMPO", "LIMITE_DE_CUSTO",
})
_POLITICA = frozenset({
    "APROVACAO_AUSENTE", "APROVACAO_OBRIGATORIA", "APROVACAO_PENDENTE",
    "ARGUMENTOS_INVALIDOS", "CHAMADA_INVALIDA", "CREDENCIAL_NAO_PERMITIDA",
    "EPISODIO_NAO_VERIFICADO", "FERRAMENTA_DESCONHECIDA",
    "LOTE_DE_FERRAMENTAS_INVALIDO", "PLANO_INVALIDO", "PREFERENCIA_NAO_PERMITIDA",
    "PREFERENCIA_SEM_AUTORIZACAO", "THREAD_NAO_AUTORIZADA", "USUARIO_NAO_AUTORIZADO",
})
_SEM_DADOS = frozenset({
    "REGISTRO_NAO_ENCONTRADO", "HISTORICO_NAO_ENCONTRADO", "SEM_RECOMENDACOES",
})
_ERROS_FERRAMENTA = frozenset({
    "CONEXAO_INATIVA", "ERRO_DE_CONEXAO", "ERRO_NA_CONSULTA",
    "BUSCA_DE_REGRA_FALHOU", "BUSCA_GLOSSARIO_FALHOU",
})
_CATEGORIAS = {
    "CONCLUIDO": "respondeu",
    "PRECISA_INFORMACAO": "pediu_esclarecimento",
    "RECUSADO": "recusou",
    "AGUARDANDO_APROVACAO": "aguardando_humano",
    "LACO_DETECTADO": "laco_detectado",
    "INTERROMPIDO": "interrompido",
    "ERRO_VALIDADO": "erro",
    "ERRO_DO_MODELO": "erro",
    "ERRO_FATAL": "erro",
    "ERRO_NA_EXECUCAO": "erro",
    "CHECKPOINT_INDISPONIVEL": "erro",
    "ENTRADA_INVALIDA": "bloqueado_politica",
    "SEM_MOTIVO": "indeterminado",
    **dict.fromkeys(_LIMITES, "orcamento_esgotado"),
    **dict.fromkeys(_POLITICA, "bloqueado_politica"),
}
_ROTULO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")
_DOC_ID = re.compile(r"[a-z][a-z0-9_]{1,60}_v[1-9][0-9]*(?:_revogado)?")
_HEX = re.compile(r"[0-9a-f]{64}")
_FEIRA_RE = re.compile(r"\b(?:QUA|QUI|SAB_C|SAB_E|DOM_C|DOM_E)\b", re.I)
_OPERACAO_RE = re.compile(r"\bopera[cç][aã]o\s+(\d{1,9})(?!\d)", re.I)
_DIAS = frozenset({
    "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
})
_TIPOS_ERRO = frozenset({
    "APIConnectionError", "APITimeoutError", "APIStatusError", "AuthenticationError",
    "BadRequestError", "RateLimitError", "InternalServerError", "NotFoundError",
    "TimeoutError", "ConnectionError", "OperationalError", "DatabaseError",
    "ValueError", "ValidationError", "TypeError", "OSError", "RuntimeError",
    "KeyboardInterrupt", "GraphRecursionError",
})
_LOG = logging.getLogger(__name__)


@dataclass
class _Execucao:
    tracer: object
    raiz: object
    custo: float = 0.0
    custo_completo: bool = True
    chamadas_modelo: int = 0
    erros: int = 0
    normalizada: bool = False
    id_aprovacao: str | None = None


_ATUAL: ContextVar[_Execucao | None] = ContextVar(
    "pasteis_execucao_observada", default=None,
)


def _obj(valor) -> Mapping:
    return valor if isinstance(valor, Mapping) else {}


def _itens(valor):
    return valor if isinstance(valor, (list, tuple)) else ()


def _enum(valor, permitidos):
    return valor if isinstance(valor, str) and valor in permitidos else None


def _numero(valor):
    return valor if type(valor) is int and 0 <= valor < 2**63 else None


def _rotulo(valor):
    if isinstance(valor, str) and _ROTULO.fullmatch(valor) and not valor.lower().startswith(
        ("sk-", "sk_", "bearer", "eyj", "ghp_", "gho_", "github_pat_")
    ):
        return valor
    return None


def _hash(valor: str) -> str:
    return sha256(valor.encode("utf-8", errors="replace")).hexdigest()


def _hash_se_texto(valor):
    return _hash(valor) if isinstance(valor, str) and valor else None


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _attrs(**campos) -> dict:
    return {chave: valor for chave, valor in campos.items() if valor is not None}


def _aviso(mensagem: str) -> None:
    # Mensagem fixa e sem traceback: caminhos/credenciais não viram diagnóstico.
    _LOG.warning("%s", mensagem)


@lru_cache(maxsize=16)
def _tracer(diretorio: str, versao: str):
    # Sem tracing ativo, o agente não precisa importar o SDK.
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import SpanLimits, TracerProvider
    from opentelemetry.sdk.trace.export import (
        SimpleSpanProcessor,
        SpanExporter,
        SpanExportResult,
    )
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON

    class _Jsonl(SpanExporter):
        def __init__(self):
            caminho = Path(diretorio)
            caminho.mkdir(parents=True, exist_ok=True)
            self.arquivo = caminho / f"otel-{uuid4().hex}.jsonl"
            self.lock = Lock()
            self.falha_reportada = False

        def export(self, spans):
            try:
                conteudo = "".join(span.to_json(indent=None) + "\n" for span in spans)
                with self.lock, self.arquivo.open(
                    "a", encoding="utf-8", newline="\n",
                ) as fluxo:
                    fluxo.write(conteudo)
                return SpanExportResult.SUCCESS
            except Exception:
                if not self.falha_reportada:
                    self.falha_reportada = True
                    _aviso("Não foi possível salvar um span. A coleta local pode estar incompleta.")
                return SpanExportResult.FAILURE

    provider = TracerProvider(
        resource=Resource({"service.name": AGENTE, "service.version": versao}),
        sampler=ALWAYS_ON,
        span_limits=SpanLimits(max_attributes=64, max_events=64, max_event_attributes=16),
        shutdown_on_exit=False,
    )
    provider.add_span_processor(SimpleSpanProcessor(_Jsonl()))
    return provider.get_tracer("pasteis.observabilidade", VERSAO_INSTRUMENTACAO)


def _abrir_span(tracer, nome, *, raiz=None, cliente=False, atributos=None):
    from opentelemetry.context import Context
    from opentelemetry.trace import SpanKind, set_span_in_context

    contexto = Context()
    if raiz is not None:
        contexto = set_span_in_context(raiz, contexto)

    # Não instala provider global nem adota um pai/exportador externo.
    return tracer.start_as_current_span(
        nome,
        context=contexto,
        kind=SpanKind.CLIENT if cliente else SpanKind.INTERNAL,
        attributes=atributos,
        record_exception=False,
        set_status_on_exception=False,
    )


def _erro_span(span, tipo: str, execucao: _Execucao) -> None:
    from opentelemetry.trace import StatusCode

    execucao.erros += 1
    span.set_attribute("error.type", tipo)
    span.set_status(StatusCode.ERROR)


def _tipo_erro(erro: BaseException) -> str:
    return _enum(type(erro).__name__, _TIPOS_ERRO) or "Excecao"


def _observacao(funcao):
    """Protege somente metadados; não envolve nem repete ações de negócio."""
    @wraps(funcao)
    def executar(*args, **kwargs):
        execucao = _ATUAL.get()
        if execucao is not None:
            try:
                funcao(execucao, *args, **kwargs)
            except Exception:
                _aviso("Não foi possível registrar metadados de um trace local.")
    return executar


def _campos_resultado(resultado) -> dict:
    dado = _obj(resultado)
    campos = {
        chave: _numero(dado.get(chave))
        for chave in (
            "id_operacao", "quantidade_operacoes", "quantidade_registros",
            "operacoes_consideradas", "total_recomendado", "total_produzido",
            "total_vendido", "total_sobra", "registro_id",
        )
    }
    campos.update(
        feira=_enum(dado.get("feira"), _FEIRAS),
        dia_producao=_enum(dado.get("dia_producao"), _DIAS),
        dia_venda=_enum(dado.get("dia_venda"), _DIAS),
        metodo=_enum(dado.get("metodo"), {"baseline_media_vendas_5_operacoes"}),
    )
    for chave in ("ja_existia", "prova_falta"):
        if type(dado.get(chave)) is bool:
            campos[chave] = dado[chave]
    return _attrs(**campos)


@_observacao
def _finalizar(execucao, motivo, saida, inicio, tipo_erro=None):
    motivo = _enum(motivo, _CATEGORIAS) or "SEM_MOTIVO"
    categoria = _CATEGORIAS[motivo]
    if categoria == "erro" and execucao.erros == 0:
        _erro_span(execucao.raiz, tipo_erro or motivo, execucao)
    elif execucao.erros:
        from opentelemetry.trace import StatusCode

        execucao.raiz.set_status(StatusCode.ERROR)

    dado = _obj(saida)
    execucao.raiz.set_attributes(_attrs(**{
        "pasteis.execucao.motivo_termino": motivo,
        "pasteis.execucao.categoria_termino": categoria,
        "pasteis.execucao.latencia_ms": round((perf_counter() - inicio) * 1000, 3),
        "pasteis.execucao.chamadas_modelo": execucao.chamadas_modelo,
        "pasteis.execucao.custo_estimado_usd": (
            round(execucao.custo, 10) if execucao.custo_completo else None
        ),
        "pasteis.execucao.custo_completo": execucao.custo_completo,
        "pasteis.execucao.erros_tecnicos": execucao.erros,
        "pasteis.saida.status": _enum(dado.get("status"), _STATUS),
        "pasteis.saida.suficiente": (
            dado.get("suficiente") if type(dado.get("suficiente")) is bool else None
        ),
        "pasteis.saida.normalizada": execucao.normalizada,
        "pasteis.saida.campos": _json(_campos_resultado(dado.get("resultado"))),
    }))


def rastrear_execucao(tipo: str, obter_settings):
    def decorar(funcao):
        @wraps(funcao)
        def executar(self, *args, **kwargs):
            diretorio = os.environ.get("PASTEIS_TRACE_DIR", "").strip()
            if not diretorio:
                return funcao(self, *args, **kwargs)

            inicio = perf_counter()
            versao = _rotulo(os.environ.get("PASTEIS_TRACE_VERSAO"))
            coorte = os.environ.get("PASTEIS_TRACE_COORTE", "operacional")
            if not versao or coorte not in {"operacional", "avaliacao", "teste"}:
                _aviso("Tracing desativado: verifique PASTEIS_TRACE_VERSAO e PASTEIS_TRACE_COORTE.")
                return funcao(self, *args, **kwargs)

            try:
                config = obter_settings()
                tracer = _tracer(str(Path(diretorio).resolve()), versao)
                thread = kwargs.get("thread_id") or config.default_thread_id
                dados = _attrs(**{
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.agent.name": AGENTE,
                    "gen_ai.conversation.id": _hash_se_texto(thread),
                    "pasteis.sistema.versao": versao,
                    "pasteis.instrumentacao.versao": VERSAO_INSTRUMENTACAO,
                    "pasteis.modelo.configurado": _rotulo(config.llm_model),
                    "pasteis.execucao.tipo": tipo,
                    "pasteis.execucao.coorte": coorte,
                    "pasteis.prompt.orquestrador.versao": "orquestrador_v2",
                    "pasteis.prompt.procedimento.versao": "procedimento_planejamento_v1",
                })
                if (
                    coorte == "avaliacao"
                    and isinstance(thread, str)
                    and re.fullmatch(r"eval-GD[0-9]{2}", thread)
                ):
                    dados["pasteis.avaliacao.caso_id"] = thread.removeprefix("eval-")

                texto = args[0] if args else kwargs.get("texto")
                if tipo == "nova_entrada" and isinstance(texto, str):
                    feiras = sorted({m.upper() for m in _FEIRA_RE.findall(texto[:8192])})
                    if feiras:
                        dados["pasteis.entrada.feiras_mencionadas"] = feiras
                    if operacao := _OPERACAO_RE.search(texto[:8192]):
                        dados["pasteis.entrada.id_operacao"] = int(operacao[1])
                    if coorte == "teste" and texto == PERGUNTA_DEMO:
                        dados["pasteis.entrada.pergunta_demo"] = PERGUNTA_DEMO

                contexto = _abrir_span(tracer, f"invoke_agent {AGENTE}", atributos=dados)
            except Exception:
                _aviso("Não foi possível inicializar o tracing local.")
                return funcao(self, *args, **kwargs)

            with contexto as raiz:
                token = _ATUAL.set(_Execucao(tracer, raiz))
                try:
                    try:
                        retorno = funcao(self, *args, **kwargs)
                    except BaseException as erro:
                        codigo = _enum(
                            getattr(erro, "codigo", None),
                            _POLITICA | {"CHECKPOINT_INDISPONIVEL"},
                        )
                        if not codigo:
                            if isinstance(erro, KeyboardInterrupt):
                                codigo = "INTERROMPIDO"
                            elif _tipo_erro(erro) == "ValidationError":
                                codigo = "ENTRADA_INVALIDA"
                            else:
                                codigo = "ERRO_NA_EXECUCAO"
                        _finalizar(codigo, None, inicio, _tipo_erro(erro))
                        raise

                    dado = _obj(retorno)
                    _finalizar(dado.get("motivo_termino"), dado.get("saida"), inicio)
                    return retorno
                finally:
                    _ATUAL.reset(token)
        return executar
    return decorar


def chat(criar, kwargs: dict, settings, prompt: str, procedimento: str):
    execucao = _ATUAL.get()
    if execucao is None:
        return criar(**kwargs)

    modelo = _rotulo(kwargs.get("model")) or "omitido"
    try:
        provedor = (
            "openai"
            if urlsplit(settings.llm_base_url).hostname == "api.openai.com"
            else "openai_compativel"
        )
    except ValueError:
        provedor = "desconhecido"

    execucao.raiz.set_attributes({
        "pasteis.prompt.orquestrador.sha256": _hash(prompt),
        "pasteis.prompt.procedimento.sha256": _hash(procedimento),
    })

    with _abrir_span(
        execucao.tracer,
        f"chat {modelo}",
        raiz=execucao.raiz,
        cliente=True,
        atributos={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": provedor,
            "gen_ai.request.model": modelo,
        },
    ) as span:
        execucao.chamadas_modelo += 1
        try:
            resposta = criar(**kwargs)
        except BaseException as erro:
            execucao.custo_completo = False
            if not isinstance(erro, KeyboardInterrupt):
                _erro_span(span, _tipo_erro(erro), execucao)
            raise

        if not _anotar_chat(execucao, span, resposta, settings):
            execucao.custo_completo = False
        return resposta


def _anotar_chat(execucao, span, resposta, settings) -> bool:
    try:
        uso = getattr(resposta, "usage", None)
        entrada = _numero(getattr(uso, "prompt_tokens", None))
        saida = _numero(getattr(uso, "completion_tokens", None))
        span.set_attributes(_attrs(**{
            "gen_ai.response.model": _rotulo(getattr(resposta, "model", None)),
            "gen_ai.usage.input_tokens": entrada,
            "gen_ai.usage.output_tokens": saida,
        }))
        if entrada is None or saida is None:
            return False

        preco_entrada = settings.llm_input_price_per_million
        preco_saida = settings.llm_output_price_per_million
        if not all(math.isfinite(p) and p >= 0 for p in (preco_entrada, preco_saida)):
            return False

        unitario = (entrada * preco_entrada + saida * preco_saida) / 1_000_000
        if not math.isfinite(unitario):
            return False

        span.set_attributes({
            "pasteis.chat.preco_entrada_por_milhao_usd": preco_entrada,
            "pasteis.chat.preco_saida_por_milhao_usd": preco_saida,
            "pasteis.chat.custo_estimado_usd": unitario,
        })
        execucao.custo += unitario
        return True
    except Exception:
        _aviso("Não foi possível registrar uso ou estimar o custo de uma chamada.")
        return False


def _documento(dado) -> dict:
    dado = _obj(dado)
    id_ = dado.get("documento_id")
    if not isinstance(id_, str) or not _DOC_ID.fullmatch(id_):
        return {}

    versao = str(dado.get("versao", "")) if type(dado.get("versao")) in (int, str) else ""
    versao = (
        versao
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", versao) and len(versao) <= 16
        else None
    )
    return _attrs(
        documento_id=id_,
        versao=versao,
        status=_enum(dado.get("status"), {"vigente", "revogado"}),
    )


def _produtos(valores) -> list[dict]:
    itens = []
    for valor in _itens(valores)[:100]:
        item = _obj(valor)
        id_ = _numero(item.get("id_produto"))
        quantidade = _numero(item.get("quantidade_recomendada"))
        if id_ is not None and quantidade is not None:
            itens.append({"id_produto": id_, "quantidade_recomendada": quantidade})
    return itens


def _argumentos(argumentos) -> dict:
    args = _obj(argumentos)
    return _attrs(
        codigo_feira=_enum(args.get("codigo_feira"), _FEIRAS),
        id_operacao=_numero(args.get("id_operacao")),
        limite_operacoes=_numero(args.get("limite_operacoes")),
        consulta_informada=True if isinstance(args.get("consulta"), str) else None,
        chave=_enum(args.get("chave"), {"prioridade"}),
        feira=_enum(args.get("feira"), _FEIRAS),
        total_recomendado=_numero(args.get("total_recomendado")),
    )


def _erro_resultado(resultado) -> str | None:
    return _enum(
        _obj(_obj(resultado).get("erro")).get("codigo"),
        _ERROS_FERRAMENTA | _SEM_DADOS | _POLITICA | _LIMITES | {
            "PLANO_AUSENTE", "APROVACAO_EXPIRADA", "APROVACAO_REJEITADA",
            "FEIRA_INVALIDA", "LIMITE_INVALIDO", "IDENTIFICADOR_INVALIDO",
        },
    )


def ferramenta(nome: str, argumentos: dict, acao, *, chamada_id=None):
    execucao = _ATUAL.get()
    if execucao is None:
        return acao()

    nome = _enum(nome, _FERRAMENTAS) or "desconhecida"
    with _abrir_span(
        execucao.tracer,
        f"execute_tool {nome}",
        raiz=execucao.raiz,
        atributos=_attrs(**{
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": nome,
            "gen_ai.tool.call.id": _hash_se_texto(chamada_id),
            "pasteis.ferramenta.argumentos": _json(_argumentos(argumentos)),
        }),
    ) as span:
        try:
            resultado = acao()
        except BaseException as erro:
            if isinstance(erro, KeyboardInterrupt):
                desfecho = "interrompida"
            else:
                desfecho = "erro_tecnico"
                _erro_span(span, _tipo_erro(erro), execucao)
            span.set_attribute("pasteis.ferramenta.desfecho", desfecho)
            if nome == "registrar_plano":
                _registrar_escrita(desfecho, {})
            raise

        _anotar_ferramenta(span, nome, resultado)
        return resultado


@_observacao
def _anotar_ferramenta(execucao, span, nome, resultado):
    dado = _obj(resultado)
    erro = _erro_resultado(dado)
    campos = _campos_resultado(dado)

    if nome == "buscar_conhecimento":
        if type(dado.get("suficiente")) is bool:
            campos["suficiente"] = dado["suficiente"]
        campos["documentos"] = [
            ref
            for item in _itens(dado.get("resultados"))[:20]
            if (ref := _documento(item))
        ]
    elif nome == "calcular_recomendacao":
        campos["recomendacoes"] = _produtos(dado.get("recomendacoes"))
        regras = _obj(dado.get("regras_aplicadas"))
        campos["produtos_excluidos"] = [
            id_ for id_ in _itens(regras.get("produtos_excluidos"))[:100]
            if _numero(id_) is not None
        ]
    elif nome == "consultar_historico":
        campos["operacoes"] = [
            _campos_resultado(op) for op in _itens(dado.get("operacoes"))[:10]
        ]

    if erro in _SEM_DADOS or (
        nome == "buscar_conhecimento"
        and dado.get("ok") is True
        and dado.get("suficiente") is False
    ):
        desfecho = "sem_dados"
    elif dado.get("ok") is True:
        desfecho = "ok"
    elif erro in {"FEIRA_INVALIDA", "LIMITE_INVALIDO", "IDENTIFICADOR_INVALIDO"}:
        desfecho = "entrada_invalida"
    else:
        desfecho = "erro_tecnico"
        _erro_span(span, erro or "FALHA_FERRAMENTA", execucao)

    span.set_attributes(_attrs(**{
        "pasteis.ferramenta.desfecho": desfecho,
        "pasteis.ferramenta.erro_codigo": erro,
        "pasteis.ferramenta.resultado": _json(campos),
    }))
    if nome == "registrar_plano":
        _registrar_escrita(desfecho, campos)


@_observacao
def _registrar_escrita(execucao, desfecho, campos):
    execucao.raiz.add_event("aprovacao.escrita", _attrs(**{
        "pasteis.aprovacao.id": execucao.id_aprovacao,
        "pasteis.aprovacao.desfecho": desfecho,
        "pasteis.aprovacao.registro_id": campos.get("registro_id"),
        "pasteis.aprovacao.ja_existia": campos.get("ja_existia"),
    }))


def id_chamada(estado: dict, nome: str):
    if _ATUAL.get() is None:
        return None

    mensagens = _itens(estado.get("mensagens"))
    for item in _itens(_obj(mensagens[-1]).get("tool_calls")) if mensagens else ():
        chamada = _obj(item)
        if _obj(chamada.get("function")).get("name") == nome:
            return chamada.get("id")
    return None


@_observacao
def registrar_bloqueio(execucao, nome, resultado):
    erro = _erro_resultado(resultado)
    if erro in (_POLITICA | _LIMITES | {"PLANO_AUSENTE"}):
        execucao.raiz.add_event("ferramenta.nao_executada", {
            "gen_ai.tool.name": _enum(nome, _FERRAMENTAS) or "desconhecida",
            "pasteis.ferramenta.erro_codigo": erro,
        })


@_observacao
def registrar_memoria(execucao, fatos, episodios):
    execucao.raiz.set_attribute("pasteis.entrada.rota", "orquestracao")
    ids = [
        h for item in _itens(episodios)[:3]
        if isinstance((h := _obj(item).get("content_hash")), str) and _HEX.fullmatch(h)
    ]
    execucao.raiz.add_event("contexto.memoria", {
        "pasteis.memoria.preferencias": ("prioridade",) if "prioridade" in _obj(fatos) else (),
        "pasteis.memoria.episodios": ids,
    })


@_observacao
def registrar_decisao_rag(execucao, rota, documento, dados_saida, pedido=None):
    execucao.raiz.set_attribute("pasteis.entrada.rota", rota)
    execucao.raiz.add_event("rag.decisao", _attrs(**{
        "pasteis.rag.rota": rota,
        "pasteis.rag.documento_usado": _json(_documento(documento)),
        "pasteis.rag.resultado": _json(_campos_resultado(_obj(dados_saida).get("resultado"))),
        "pasteis.rag.status": _enum(_obj(dados_saida).get("status"), _STATUS),
        "pasteis.rag.tipo": _enum(getattr(pedido, "tipo", None), {"calendario", "inclusao"}),
        "pasteis.rag.feira": _enum(getattr(pedido, "feira", None), _FEIRAS),
        "pasteis.rag.produto": _enum(
            getattr(pedido, "produto", None), {"frango", "escarola sem bacon"},
        ),
    }))


@_observacao
def marcar_saida_normalizada(execucao):
    execucao.normalizada = True


@_observacao
def registrar_capacidade_zero(execucao):
    execucao.raiz.set_attribute("pasteis.entrada.rota", "recusar_capacidade_zero")
    execucao.raiz.add_event("dominio.capacidade_zero", {"pasteis.capacidade_total": 0})


def _id_aprovacao(estado, chamada):
    turno, id_ = estado.get("turno_id"), chamada.get("id")
    # São os mesmos campos no checkpoint antes e depois de interrupt().
    if isinstance(turno, str) and isinstance(id_, str):
        return _hash(_json([turno, id_, _numero(estado.get("chamadas_ferramenta_turno"))]))
    return None


def aguardar_aprovacao(interromper, pedido, estado, chamada):
    if _ATUAL.get() is None:
        return interromper(pedido)

    from langgraph.errors import GraphInterrupt

    try:
        return interromper(pedido)
    except GraphInterrupt:
        _registrar_pausa(pedido, estado, chamada)
        raise


@_observacao
def _registrar_pausa(execucao, pedido, estado, chamada):
    id_ = _id_aprovacao(estado, chamada)
    if id_ is None:
        return

    execucao.id_aprovacao = id_
    execucao.raiz.set_attribute("pasteis.aprovacao.id", id_)
    args = _obj(pedido.get("argumentos"))
    prazo = datetime.fromisoformat(pedido["expira_em"]).astimezone(timezone.utc).isoformat()
    execucao.raiz.add_event("aprovacao.solicitada", _attrs(**{
        "pasteis.aprovacao.id": id_,
        "pasteis.aprovacao.expira_em": prazo,
        "pasteis.aprovacao.plano": _json({
            **_argumentos(args), "produtos": _produtos(args.get("plano")),
        }),
    }))


@_observacao
def registrar_decisao_aprovacao(execucao, decisao, estado, chamada, erro_decisao):
    id_ = _id_aprovacao(estado, chamada)
    if id_ is None:
        return

    execucao.id_aprovacao = id_
    execucao.raiz.set_attribute("pasteis.aprovacao.id", id_)
    execucao.raiz.add_event("aprovacao.decidida", _attrs(**{
        "pasteis.aprovacao.id": id_,
        "pasteis.aprovacao.identidade_opaca": _hash_se_texto(estado.get("usuario_id")),
        "pasteis.aprovacao.decisao": _enum(
            decisao.acao, {"aprovar", "editar", "rejeitar", "expirar"},
        ),
        "pasteis.aprovacao.decisao_invalida": bool(erro_decisao),
    }))