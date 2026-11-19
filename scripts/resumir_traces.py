"""Concilia duas rodadas da suíte com seus traces locais, sem rede."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


META = (
    "sistema_versao", "codigo_sha256", "dataset_versao", "dataset_sha256",
    "snapshot_sha256", "mysql_modo", "modelo",
)
EX = "pasteis.execucao."
SA = "pasteis.saida."
FE = "pasteis.ferramenta."
MINIMO_SLO = 30


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def numero(valor):
    return type(valor) in (int, float) and math.isfinite(valor) and valor >= 0


def instante(valor):
    data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    exigir(data.tzinfo is not None, "Timestamp sem fuso horário.")
    return data.astimezone(timezone.utc)


def percentis(valores):
    dados = sorted(valores)
    return {
        "n": len(dados),
        "p50_ms": round(dados[math.ceil(0.50 * len(dados)) - 1], 3) if dados else None,
        "p95_ms": round(dados[math.ceil(0.95 * len(dados)) - 1], 3) if dados else None,
    }


def ler_rodada(arquivo):
    rodada = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    exigir(rodada["rodada_completa"] is True, f"{arquivo.parent.name}: rodada incompleta.")
    exigir(rodada["snapshot_inalterado"] is True, f"{arquivo.parent.name}: snapshot mudou.")

    meta = {campo: rodada[campo] for campo in META}
    exigir(all(isinstance(v, str) and v for v in meta.values()), "Metadados inválidos.")

    esperadas = {}
    for caso in rodada["casos"]:
        id_ = caso["id"]
        exigir(id_ not in esperadas, f"Caso repetido no resultado: {id_}.")
        esperadas[id_] = [e for e in caso["etapas"] if e.get("executada") is True]

    exigir(len(esperadas) >= 20, "O resultado não tem a suíte completa.")
    aprovados = sum(c.get("aprovado_automatico") is True for c in rodada["casos"])
    return meta, esperadas, aprovados


def ler_grupos(pasta, versao):
    arquivos = sorted(pasta.glob("otel-*.jsonl"))
    exigir(bool(arquivos), f"Nenhum JSONL em {pasta}.")
    grupos = defaultdict(list)
    vistos = set()

    for arquivo in arquivos:
        with arquivo.open(encoding="utf-8-sig") as fluxo:
            for n, linha in enumerate(fluxo, start=1):
                span = json.loads(linha)
                ctx = span["context"]
                chave = ctx["trace_id"], ctx["span_id"]
                exigir(chave not in vistos, f"Span duplicado em {arquivo.name}:{n}.")
                vistos.add(chave)

                recurso = span["resource"]["attributes"]
                exigir(
                    recurso["service.name"] == "pasteis-miyata"
                    and recurso["service.version"] == versao,
                    f"Versão ou serviço diferente em {arquivo.name}:{n}.",
                )
                grupos[chave[0]].append(span)

    return grupos


def duracao(span):
    ms = (
        instante(span["end_time"]) - instante(span["start_time"])
    ).total_seconds() * 1000
    exigir(ms >= 0, "Duração negativa em span.")
    return ms


def cruzar(pasta, meta, esperadas, rodada):
    por_caso = defaultdict(list)

    for trace_id, spans in ler_grupos(pasta, meta["sistema_versao"]).items():
        raizes = [s for s in spans if s["parent_id"] is None]
        exigir(len(raizes) == 1, f"{pasta.name}: trace órfão ou com raiz duplicada.")
        raiz = raizes[0]
        a = raiz["attributes"]

        exigir(
            a["gen_ai.operation.name"] == "invoke_agent"
            and a["pasteis.sistema.versao"] == meta["sistema_versao"]
            and a["pasteis.modelo.configurado"] == meta["modelo"]
            and a[EX + "coorte"] == "avaliacao",
            f"{pasta.name}: raiz de outra versão, modelo ou coorte.",
        )
        caso = a["pasteis.avaliacao.caso_id"]
        exigir(caso in esperadas, f"{pasta.name}: caso sem etapa correspondente.")

        filhos = [s for s in spans if s is not raiz]
        exigir(
            all(
                f["parent_id"] == raiz["context"]["span_id"]
                and f["attributes"]["gen_ai.operation.name"] in {"chat", "execute_tool"}
                for f in filhos
            ),
            f"{pasta.name}/{caso}: span filho sem pai válido.",
        )
        chats = [
            f for f in filhos if f["attributes"]["gen_ai.operation.name"] == "chat"
        ]
        exigir(
            type(a[EX + "chamadas_modelo"]) is int
            and len(chats) == a[EX + "chamadas_modelo"],
            f"{pasta.name}/{caso}: faltam spans de modelo ou há spans extras.",
        )
        por_caso[caso].append((raiz, filhos, trace_id))

    execucoes = []
    for caso, etapas in esperadas.items():
        itens = sorted(por_caso[caso], key=lambda item: instante(item[0]["start_time"]))
        exigir(
            len(itens) == len(etapas),
            f"{pasta.name}/{caso}: {len(itens)} raízes para {len(etapas)} etapas executadas.",
        )
        pausa_anterior = False

        for etapa, (raiz, filhos, trace_id) in zip(etapas, itens, strict=True):
            a = raiz["attributes"]
            tipo = "retomada_humana" if pausa_anterior else "nova_entrada"
            exigir(
                a[EX + "tipo"] == tipo
                and a[EX + "motivo_termino"] == etapa["motivo_termino"]
                and a.get(SA + "status") == etapa["status"],
                f"{pasta.name}/{caso}: trace não corresponde à etapa {etapa['etapa']}.",
            )
            pausa_anterior = etapa["status"] == "aguardando_aprovacao" and any(
                evento["name"] == "aprovacao.solicitada" for evento in raiz["events"]
            )
            execucoes.append((rodada, caso, etapa["etapa"], raiz, filhos, trace_id))

    return execucoes


def resumir(meta, execucoes, cobertura):
    trace_ids = {item[-1] for item in execucoes}
    exigir(len(trace_ids) == len(execucoes), "As rodadas compartilham traces duplicados.")

    fins = [instante(raiz["end_time"]) for _, _, _, raiz, _, _ in execucoes]
    exigir(bool(fins), "Nenhuma execução conciliada.")
    fim = max(fins)
    inicio_janela = fim - timedelta(days=7)
    exigir(min(fins) >= inicio_janela, "As rodadas não cabem na mesma janela de sete dias.")

    motivos = Counter()
    latencias = defaultdict(list)
    desfechos = defaultdict(Counter)
    latencias_spans = defaultdict(list)
    custos = []
    precos = set()
    tokens = Counter()
    esperas = {}
    decisoes = {}
    registros = []
    boas = pausas = canceladas = normalizadas = com_erro = 0

    for rodada, caso, etapa, raiz, filhos, _ in execucoes:
        a = raiz["attributes"]
        categoria, motivo = a[EX + "categoria_termino"], a[EX + "motivo_termino"]
        latencia, tipo = a[EX + "latencia_ms"], a[EX + "tipo"]
        normalizada, erros = a[SA + "normalizada"], a[EX + "erros_tecnicos"]
        completo = a[EX + "custo_completo"]

        exigir(
            numero(latencia) and type(erros) is int and erros >= 0
            and type(normalizada) is bool and type(completo) is bool,
            "Raiz com métricas ausentes ou inválidas.",
        )
        motivos[categoria, motivo] += 1
        latencias["todas"].append(latencia)
        latencias[tipo].append(latencia)
        normalizadas += int(normalizada)
        com_erro += int(erros > 0)

        eventos = raiz["events"]
        pausa = categoria == "aguardando_humano" and any(
            e["name"] == "aprovacao.solicitada" for e in eventos
        )
        cancelada = categoria == "interrompido"
        pausas += int(pausa)
        canceladas += int(cancelada)

        status = a.get(SA + "status")
        termino_bom = (
            (
                categoria == "respondeu"
                and status == "concluido"
                and a.get(SA + "suficiente") is True
            )
            or (categoria, status) in {
                ("pediu_esclarecimento", "precisa_informacao"),
                ("recusou", "recusado"),
            }
        )
        elegivel = not (pausa or cancelada)
        boa = elegivel and termino_bom and not normalizada and erros == 0
        boas += int(boa)

        soma_chat = 0.0
        chats_com_custo = 0

        for filho in filhos:
            f = filho["attributes"]
            op = f["gen_ai.operation.name"]
            latencias_spans[op].append(duracao(filho))

            if op == "execute_tool":
                desfechos[f["gen_ai.tool.name"]][f[FE + "desfecho"]] += 1
                continue

            tokens["chamadas"] += 1
            entrada = f.get("gen_ai.usage.input_tokens")
            saida = f.get("gen_ai.usage.output_tokens")
            if type(entrada) is int and type(saida) is int and entrada >= 0 and saida >= 0:
                tokens["com_uso"] += 1
                tokens["entrada"] += entrada
                tokens["saida"] += saida

            unitario = f.get("pasteis.chat.custo_estimado_usd")
            if numero(unitario):
                chats_com_custo += 1
                soma_chat += unitario
                precos.add((
                    f["pasteis.chat.preco_entrada_por_milhao_usd"],
                    f["pasteis.chat.preco_saida_por_milhao_usd"],
                ))

        custo = a.get(EX + "custo_estimado_usd") if completo else None
        if completo:
            exigir(
                numero(custo) and chats_com_custo == a[EX + "chamadas_modelo"]
                and math.isclose(custo, soma_chat, rel_tol=0, abs_tol=1e-10),
                "Custo da raiz não confere com os spans de modelo.",
            )
            custos.append(custo)

        for evento in eventos:
            nome = evento["name"]
            if nome in {"aprovacao.solicitada", "aprovacao.decidida"}:
                chave = rodada, evento["attributes"]["pasteis.aprovacao.id"]
                mapa = esperas if nome == "aprovacao.solicitada" else decisoes
                exigir(chave not in mapa, "Evento de aprovação duplicado.")
                mapa[chave] = instante(evento["timestamp"])

        registros.append({
            "rodada": rodada,
            "caso": caso,
            "etapa": etapa,
            "tipo": tipo,
            "categoria": categoria,
            "motivo": motivo,
            "latencia_ms": latencia,
            "custo_estimado_usd": custo,
            "elegivel": elegivel,
            "boa_se_elegivel": boa if elegivel else None,
        })

    total = len(registros)
    n = total - pausas - canceladas
    ruins = n - boas
    latencia = {tipo: percentis(valores) for tipo, valores in latencias.items()}
    espera_ms = [
        (decisoes[chave] - esperas[chave]).total_seconds() * 1000
        for chave in esperas.keys() & decisoes.keys()
    ]
    exigir(all(ms >= 0 for ms in espera_ms), "Decisão registrada antes da solicitação.")

    return {
        "metadados": meta,
        "coorte": "avaliacao",
        "janela_inicio_utc": inicio_janela.isoformat(),
        "janela_fim_utc": fim.isoformat(),
        "primeiro_termino_utc": min(fins).isoformat(),
        "cobertura": cobertura,
        "latencia_agente": latencia,
        "latencia_spans_filhos": {
            op: percentis(valores) for op, valores in latencias_spans.items()
        },
        "slo_p95_ate_15s_na_amostra": (
            latencia["todas"]["p95_ms"] <= 15_000 if total >= MINIMO_SLO else None
        ),
        "qualidade_termino": {
            "validas": n,
            "boas": boas,
            "ruins": ruins,
            "pausas_excluidas": pausas,
            "cancelamentos_excluidos": canceladas,
            "normalizadas": normalizadas,
            "com_erro_tecnico": com_erro,
            "sli_pct": round(100 * boas / n, 2) if n else None,
            "orcamento_ruins": n * 5 // 100,
            "consumo_orcamento_pct": round(100 * ruins / (0.05 * n), 2) if n else None,
            "slo_95_pct_na_amostra": (100 * boas >= 95 * n) if n >= MINIMO_SLO else None,
        },
        "custo_usd": {
            "raizes_com_custo_completo": len(custos),
            "raizes_com_custo_incompleto": total - len(custos),
            "subtotal_conhecido": round(math.fsum(custos), 10),
            "media_entre_completas": (
                round(math.fsum(custos) / len(custos), 10) if custos else None
            ),
            "maximo_conhecido": max(custos) if custos else None,
            "acima_de_0_01": sum(c > 0.01 for c in custos),
            "precos_entrada_saida_por_milhao": sorted(precos),
        },
        "uso_modelo": {k: tokens[k] for k in ("chamadas", "com_uso", "entrada", "saida")},
        "espera_por_aprovacao": {
            **percentis(espera_ms),
            "solicitacoes_sem_decisao_medida": len(esperas.keys() - decisoes.keys()),
            "decisoes_sem_solicitacao_medida": len(decisoes.keys() - esperas.keys()),
        },
        "motivos_termino": [
            {"categoria": c, "motivo": m, "n": v, "pct": round(100 * v / total, 2)}
            for (c, m), v in sorted(motivos.items())
        ],
        "ferramentas_observadas": {
            nome: {
                "chamadas": sum(contagem.values()),
                "desfechos": dict(contagem),
                "erro_pct": round(
                    100 * contagem["erro_tecnico"] / sum(contagem.values()), 2
                ),
            }
            for nome, contagem in sorted(desfechos.items())
        },
        "execucoes": registros,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("coleta", type=Path)
    ap.add_argument("resultado1", type=Path)
    ap.add_argument("resultado2", type=Path)
    ap.add_argument("--saida", type=Path)
    args = ap.parse_args()

    try:
        exigir(
            args.resultado1.resolve() != args.resultado2.resolve(),
            "Informe dois resultados distintos.",
        )
        meta1, etapas1, aprovados1 = ler_rodada(args.resultado1)
        meta2, etapas2, aprovados2 = ler_rodada(args.resultado2)
        exigir(
            meta1 == meta2,
            "As rodadas diferem em versão, código, dataset, snapshot ou modelo.",
        )
        exigir(etapas1.keys() == etapas2.keys(), "As rodadas não contêm os mesmos casos.")

        r1 = cruzar(args.coleta / "rodada-1", meta1, etapas1, 1)
        r2 = cruzar(args.coleta / "rodada-2", meta2, etapas2, 2)
        exigir(bool(r1 and r2), "Uma das rodadas não teve execuções.")
        exigir(
            max(instante(item[3]["end_time"]) for item in r1)
            <= min(instante(item[3]["start_time"]) for item in r2),
            "Confira a associação entre as pastas e os resultados: rodadas fora de ordem.",
        )

        cobertura = [
            {
                "rodada": i,
                "casos": len(etapas),
                "aprovados_verificador": aprovados,
                "etapas_executadas": sum(map(len, etapas.values())),
                "raizes": len(r),
            }
            for i, etapas, aprovados, r in (
                (1, etapas1, aprovados1, r1),
                (2, etapas2, aprovados2, r2),
            )
        ]
        relatorio = resumir(meta1, r1 + r2, cobertura)

        if args.saida:
            with args.saida.open("x", encoding="utf-8") as destino:
                json.dump(relatorio, destino, ensure_ascii=False, indent=2, allow_nan=False)
                destino.write("\n")

    except (OSError, ValueError, KeyError, TypeError) as erro:
        ap.exit(2, f"Coleta não validada: {erro}\n")

    # Imprime somente medidas, sem prompts, respostas ou argumentos brutos.
    resumo = {k: v for k, v in relatorio.items() if k != "execucoes"}
    print(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False))

    if args.saida:
        print(f"Relatório com custo e latência por execução: {args.saida}")


if __name__ == "__main__":
    main()