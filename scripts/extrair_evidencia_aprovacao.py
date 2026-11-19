"""Reconstrói um registro novo usando apenas os traces de uma rodada."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


AP = "pasteis.aprovacao."
EX = "pasteis.execucao."
SA = "pasteis.saida."
FE = "pasteis.ferramenta."
NOME = "gen_ai.tool.name"
CASO = "pasteis.avaliacao.caso_id"
CONVERSA = "gen_ai.conversation.id"
EVENTOS = (
    "aprovacao.solicitada",
    "aprovacao.decidida",
    "aprovacao.escrita",
)


def instante(valor):
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def trace_id(span):
    return span["context"]["trace_id"]


def atributos(span):
    return span.get("attributes") or {}


def dados(span, chave):
    valor = atributos(span).get(chave)
    return json.loads(valor) if isinstance(valor, str) else {}


def selecao(obj, *chaves):
    return {chave: obj[chave] for chave in chaves if chave in obj}


def ferramentas(filhos, nome):
    return [f for f in filhos if atributos(f).get(NOME) == nome]


def ler_traces(pasta, versao):
    grupos = defaultdict(list)
    for arq in sorted(pasta.glob("otel-*.jsonl")):
        for linha in arq.read_text(encoding="utf-8-sig").splitlines():
            span = json.loads(linha)
            grupos[trace_id(span)].append(span)

    if not grupos:
        raise ValueError(f"Nenhum trace encontrado em {pasta}.")

    entradas = []
    for spans in grupos.values():
        raizes = [span for span in spans if span["parent_id"] is None]
        if len(raizes) != 1:
            raise ValueError("Trace sem raiz única.")

        raiz = raizes[0]
        a = atributos(raiz)
        if (
            a.get("gen_ai.operation.name") != "invoke_agent"
            or a.get(EX + "coorte") != "avaliacao"
            or a.get("pasteis.sistema.versao") != versao
        ):
            raise ValueError("Pasta com traces fora da versão ou coorte esperada.")

        filhos = [span for span in spans if span is not raiz]
        if any(f["parent_id"] != raiz["context"]["span_id"] for f in filhos):
            raise ValueError("Span filho desvinculado da raiz.")

        entradas.append((raiz, filhos))

    return entradas


def itens(plano, campo):
    return sorted(
        (p["id_produto"], p["quantidade_recomendada"])
        for p in plano.get(campo, [])
    )


def metadados(raiz, filhos):
    a = atributos(raiz)
    return {
        "trace_id": trace_id(raiz),
        "modelo_configurado": a.get("pasteis.modelo.configurado"),
        "prompts": {
            nome: {
                "versao": a.get(f"pasteis.prompt.{nome}.versao"),
                "sha256": a.get(f"pasteis.prompt.{nome}.sha256"),
            }
            for nome in ("orquestrador", "procedimento")
        },
        "modelos_observados": [
            selecao(
                atributos(f),
                "gen_ai.provider.name",
                "gen_ai.request.model",
                "gen_ai.response.model",
            )
            for f in filhos
            if atributos(f).get("gen_ai.operation.name") == "chat"
        ],
    }


def contexto(etapas):
    memoria, documentos = [], []
    for raiz, filhos in etapas:
        for evento in raiz.get("events", []):
            if evento["name"] == "contexto.memoria":
                a = atributos(evento)
                memoria.append({
                    "trace_id": trace_id(raiz),
                    "chaves": a.get("pasteis.memoria.preferencias", []),
                    "episodios_prefixos": [
                        hash_[:12] for hash_ in a.get("pasteis.memoria.episodios", [])
                    ],
                })

        for f in ferramentas(filhos, "buscar_conhecimento"):
            for doc in dados(f, FE + "resultado").get("documentos", []):
                ref = selecao(doc, "documento_id", "versao", "status")
                if ref and ref not in documentos:
                    documentos.append(ref)

    return {"memoria_recuperada": memoria, "documentos_rag": documentos}


def calcular_origem(etapas, pausa, solicitacao, proposta):
    a = atributos(pausa)
    propostas = itens(proposta, "produtos")
    candidatos = []
    if not propostas:
        return None

    for r, filhos in etapas:
        b = atributos(r)
        if b.get(CASO) != a[CASO] or b.get(CONVERSA) != a[CONVERSA]:
            continue

        for f in ferramentas(filhos, "calcular_recomendacao"):
            resultado = dados(f, FE + "resultado")
            argumentos = dados(f, FE + "argumentos")
            if (
                instante(f["end_time"]) <= instante(solicitacao["timestamp"])
                and atributos(f).get(FE + "desfecho") == "ok"
                and argumentos.get("codigo_feira") == proposta["feira"]
                and resultado.get("feira") == proposta["feira"]
                and resultado.get("total_recomendado") == proposta["total_recomendado"]
                and itens(resultado, "recomendacoes") == propostas
            ):
                candidatos.append((r, filhos, f))

    return max(candidatos, key=lambda item: instante(item[2]["end_time"]), default=None)


def reconstruir(etapas, indice, versao, rodada, caso_desejado):
    achados = []

    for id_, eventos in indice.items():
        if not all(len(eventos[nome]) == 1 for nome in EVENTOS):
            continue

        (pausa, filhos_pausa, s), (retoma, filhos_retoma, d), (raiz_escrita, _, e) = (
            eventos[nome][0] for nome in EVENTOS
        )
        a, b = atributos(pausa), atributos(retoma)
        decisao, escrita = atributos(d), atributos(e)
        caso = a.get(CASO)

        if caso_desejado and caso != caso_desejado:
            continue

        if (
            not caso or b.get(CASO) != caso
            or not a.get(CONVERSA) or a[CONVERSA] != b.get(CONVERSA)
            or a.get(AP + "id") != id_ or b.get(AP + "id") != id_
            or pausa is retoma or raiz_escrita is not retoma
            or a.get(EX + "tipo") != "nova_entrada"
            or b.get(EX + "tipo") != "retomada_humana"
            or a.get(EX + "motivo_termino") != "AGUARDANDO_APROVACAO"
            or ferramentas(filhos_pausa, "registrar_plano")
            or decisao.get(AP + "decisao") not in {"aprovar", "editar"}
            or decisao.get(AP + "decisao_invalida") is not False
            or not decisao.get(AP + "identidade_opaca")
            or escrita.get(AP + "desfecho") != "ok"
            or escrita.get(AP + "ja_existia") is not False
        ):
            continue

        registros = ferramentas(filhos_retoma, "registrar_plano")
        if len(registros) != 1:
            continue

        gravacao = registros[0]
        argumentos = dados(gravacao, FE + "argumentos")
        resultado = dados(gravacao, FE + "resultado")
        proposta = dados(s, AP + "plano")
        registro_id = escrita.get(AP + "registro_id")
        prazo = atributos(s)[AP + "expira_em"]

        if (
            not proposta.get("feira") or "total_recomendado" not in proposta
            or argumentos.get("feira") != proposta["feira"]
            or argumentos.get("total_recomendado") != proposta["total_recomendado"]
            or type(registro_id) is not int or registro_id <= 0
            or resultado.get("registro_id") != registro_id
            or resultado.get("ja_existia") is not False
            or atributos(gravacao).get(FE + "desfecho") != "ok"
            or not (
                instante(s["timestamp"]) <= instante(pausa["end_time"])
                <= instante(retoma["start_time"]) <= instante(d["timestamp"])
                <= instante(gravacao["start_time"]) <= instante(e["timestamp"])
                <= instante(gravacao["end_time"]) <= instante(retoma["end_time"])
            )
            or instante(d["timestamp"]) > instante(prazo)
        ):
            continue

        origem = calcular_origem(etapas, pausa, s, proposta)
        if origem is None:
            continue

        r_calc, filhos_calc, calculo = origem
        res_calc = dados(calculo, FE + "resultado")
        relacionadas = {
            trace_id(r): (r, f)
            for r, f in (
                (r_calc, filhos_calc),
                (pausa, filhos_pausa),
                (retoma, filhos_retoma),
            )
        }

        evid = {
            "versao": versao,
            "coorte": "avaliacao",
            "rodada": rodada,
            "caso": caso,
            "aprovacao_id": id_,
            "calculo": {
                **metadados(r_calc, filhos_calc),
                "ferramenta": "calcular_recomendacao",
                "argumentos": selecao(dados(calculo, FE + "argumentos"), "codigo_feira"),
                "termino_utc": calculo["end_time"],
                "resultado": selecao(
                    res_calc, "feira", "metodo", "operacoes_consideradas",
                    "total_recomendado",
                ),
                "itens_coincidem_com_proposta": True,
            },
            "pausa": {
                **metadados(pausa, filhos_pausa),
                "rota": a.get("pasteis.entrada.rota"),
                "feiras_mencionadas": a.get("pasteis.entrada.feiras_mencionadas", []),
                "solicitada_em_utc": s["timestamp"],
                "expira_em_utc": prazo,
                "perfil_plano": {
                    **selecao(proposta, "feira", "total_recomendado"),
                    "total_itens": len(itens(proposta, "produtos")),
                },
                "motivo_termino": a[EX + "motivo_termino"],
                "sem_tentativa_de_registro_na_pausa": True,
            },
            "retomada": {
                **metadados(retoma, filhos_retoma),
                "decidida_em_utc": d["timestamp"],
                "acao": decisao[AP + "decisao"],
                "identidade_tecnica_prefixo": decisao[AP + "identidade_opaca"][:12],
                "ferramenta": "registrar_plano",
                "tentativa_iniciada_em_utc": gravacao["start_time"],
                "evento_escrita_em_utc": e["timestamp"],
                "argumentos": selecao(argumentos, "feira", "total_recomendado"),
                "desfecho": escrita[AP + "desfecho"],
                "registro_id": registro_id,
                "ja_existia": resultado["ja_existia"],
                "saida": {
                    "status": b.get(SA + "status"),
                    "suficiente": b.get(SA + "suficiente"),
                    "normalizada": b.get(SA + "normalizada"),
                    "campos": selecao(
                        dados(retoma, SA + "campos"), "registro_id", "ja_existia",
                    ),
                    "motivo_termino": b.get(EX + "motivo_termino"),
                },
            },
            "contexto_recuperado": contexto(relacionadas.values()),
        }
        achados.append((instante(s["timestamp"]), evid))

    if not achados:
        raise ValueError(
            "Não encontrei registro novo com cálculo, pausa e aprovação conciliados."
        )

    return min(achados, key=lambda item: item[0])[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pasta", type=Path)
    ap.add_argument("--versao", required=True)
    ap.add_argument("--caso")
    ap.add_argument("--saida", type=Path)
    args = ap.parse_args()
    indice = defaultdict(lambda: defaultdict(list))

    try:
        etapas = ler_traces(args.pasta, args.versao)
        for r, filhos in etapas:
            for evento in r.get("events", []):
                id_ = atributos(evento).get(AP + "id")
                if id_ and evento["name"] in EVENTOS:
                    indice[id_][evento["name"]].append((r, filhos, evento))

        resumo = reconstruir(etapas, indice, args.versao, args.pasta.name, args.caso)
        texto = json.dumps(resumo, ensure_ascii=False, indent=2)

        if args.saida:
            with args.saida.open("x", encoding="utf-8") as fluxo:
                fluxo.write(texto + "\n")

        print(texto)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        ap.exit(2, f"Evidência não extraída: {erro}\n")


if __name__ == "__main__":
    main()