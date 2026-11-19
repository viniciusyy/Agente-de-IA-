"""Completa a coleta das 30 fichas sem preencher avaliações humanas."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from uuid import uuid4

from .coletar_juiz import (
    _candidata, _fora_do_projeto, _hash, _json, _salvar, capturar_ferramentas,
)
from .juiz import nova_amostra


RAIZ = Path(__file__).resolve().parents[1]
FEIRAS = ("QUA", "QUI", "SAB_C", "SAB_E", "DOM_C", "DOM_E")
TIPO = "coleta_lote_local_juiz"


def plano_lote() -> list[dict]:
    perguntas = [
        *[f"Consulte as últimas cinco operações da feira {f}." for f in FEIRAS],
        *[f"Calcule uma recomendação de produção para a feira {f}." for f in FEIRAS],
        "Consulte a operação 101 e informe a feira, a data de produção e a data da venda.",
        "Consulte a operação 101 e explique qual fonte foi usada para obter os totais.",
        "Consulte a operação 999999.",
        "A operação 999999 existe? Consulte antes de responder; não substitua o identificador.",
        *[f"Em que dia da semana ocorre a produção da feira {f}?" for f in FEIRAS],
        *[
            f"Calcule uma recomendação para a feira {f}, mas inclua pastel de {p} "
            "porque eu quero produzir esse produto."
            for f in ("SAB_E", "DOM_E") for p in ("frango", "escarola sem bacon")
        ],
        "Sem sobras quer dizer que houve ruptura?",
        "Com sobra de 0, posso concluir que houve vendas perdidas?",
    ]
    return [
        {"id": f"L{i:02d}", "origem_entrada": "sintetico", "pergunta": pergunta}
        for i, pergunta in enumerate(perguntas, start=1)
    ]


def conferir_base(amostra: dict, piloto: dict) -> None:
    """Confere a coleta de origem e mantém as revisões que já existem."""
    padrao = nova_amostra()
    if (
        amostra.get("rubrica_versao") != padrao["rubrica_versao"]
        or amostra.get("criterios_adocao") != padrao["criterios_adocao"]
        or not isinstance(amostra.get("saidas"), list)
        or len(amostra["saidas"]) != 30
    ):
        raise ValueError("Use o arquivo do piloto com as 30 fichas originais.")
    for ficha, vazia in zip(amostra["saidas"], padrao["saidas"], strict=True):
        if not isinstance(ficha, dict) or ficha.get("id") != vazia["id"]:
            raise ValueError("Mantenha os IDs J01 a J30 em ordem.")
    if amostra["saidas"][2:] != padrao["saidas"][2:]:
        raise ValueError("O lote preenche somente J03 a J30 totalmente vazias; não apaga revisões.")
    if (
        piloto.get("tipo") != "piloto_local_juiz"
        or piloto.get("completo") is not True
        or piloto.get("snapshot_inalterado") is not True
        or not re.fullmatch(r"[0-9a-f]{64}", piloto.get("snapshot_sha256", ""))
    ):
        raise ValueError("Informe o piloto.json completo e com snapshot inalterado.")
    casos = piloto.get("casos")
    if not isinstance(casos, list) or len(casos) != 2:
        raise ValueError("O arquivo do piloto precisa conter as duas saídas de origem.")
    for ficha, caso, id_caso in zip(amostra["saidas"][:2], casos, ("GD08", "GD11"), strict=True):
        if caso.get("caso") != id_caso:
            raise ValueError("A ordem das saídas do piloto é GD08 e GD11.")
        candidata = caso.get("candidata", {})
        for campo in ("referencia_execucao", "pergunta", "resposta", "evidencias"):
            if ficha.get(campo) != candidata.get(campo):
                raise ValueError(f"{ficha['id']}: pergunta, resposta ou evidência mudou em relação à coleta.")


def montar_amostra(amostra: dict, casos: list[dict]) -> dict:
    if [c.get("caso") for c in casos] != [p["id"] for p in plano_lote()]:
        raise ValueError("O lote não contém todas as 28 saídas na ordem prevista.")
    saida = deepcopy(amostra)
    vazias = nova_amostra()["saidas"]
    referencias = {f["referencia_execucao"] for f in amostra["saidas"][:2]}
    for indice, caso in enumerate(casos, start=2):
        ficha = saida["saidas"][indice]
        if ficha != vazias[indice]:
            raise ValueError("O lote não pode sobrescrever uma ficha já preenchida.")
        candidata = caso["candidata"]
        referencia = candidata.get("referencia_execucao")
        if not referencia or referencia in referencias:
            raise ValueError("Há uma referência de execução ausente ou repetida.")
        referencias.add(referencia)
        if (
            candidata.get("revisoes") != vazias[indice]["revisoes"]
            or candidata.get("consenso") != vazias[indice]["consenso"]
            or not candidata.get("evidencias")
        ):
            raise ValueError("Uma nova saída precisa de evidência e não pode trazer rótulo automático.")
        id_ = ficha["id"]
        ficha.update(deepcopy(candidata))
        ficha["id"] = id_
    return saida


def _campos_candidata(id_: str, pergunta: str, retorno: dict, observacoes: list, coleta_id: str) -> dict:
    candidata = _candidata(id_, pergunta, retorno["saida"], observacoes, coleta_id)
    if not candidata["evidencias"]:
        # Guarda a ausência observada de ferramentas, não uma fonte que não foi lida.
        # Isso impede descartar seletivamente uma resposta sem fundamentação.
        candidata["evidencias"] = [{
            "referencia": f"coleta:{coleta_id}/{id_}/rastro",
            "trecho": _json({
                "ferramentas_com_retorno_observado": [],
                "motivo_termino": retorno["motivo_termino"],
                "aviso": "Nenhum retorno de ferramenta foi capturado nesta execução.",
            }),
        }]
    return candidata


def _interno(pasta: Path, id_: str) -> int:
    from src.config import settings
    from .referencias_mysql import ambiente_demo, ler_snapshot
    from .rodar import carregar_dataset
    from .verificadores import ler_estado_sqlite

    pedido = next((p for p in plano_lote() if p["id"] == id_), None)
    if pedido is None:
        raise ValueError("ID do lote não reconhecido.")
    env = ambiente_demo()
    for campo, chave in (
        ("mysql_host", "MYSQL_HOST"), ("mysql_database", "MYSQL_DATABASE"),
        ("mysql_user", "MYSQL_USER"), ("mysql_password", "MYSQL_PASSWORD"),
    ):
        if getattr(settings, campo) != env[chave]:
            raise ValueError("Credenciais diferentes das de avaliação somente leitura.")
    if settings.mysql_port != int(env["MYSQL_PORT"]):
        raise ValueError("Porta diferente da de avaliação.")
    for campo, nome in (
        ("checkpoint_database", "checkpoints.sqlite3"),
        ("memory_database", "memoria.sqlite3"), ("log_directory", "logs"),
    ):
        if getattr(settings, campo).resolve() != pasta / nome:
            raise ValueError("Checkpoint, memória ou logs não estão isolados.")
    dataset = carregar_dataset()
    snapshot = ler_snapshot(env, dataset["ambiente"])
    if snapshot.sha256 != os.environ["EVAL_SNAPSHOT_ESPERADO"]:
        raise ValueError("O MySQL mudou durante a coleta.")

    from src import graph
    from src.agent import AgentePlanejamento
    from src.memory import obter_memoria

    obter_memoria()
    antes = ler_estado_sqlite(settings.memory_database)
    with capturar_ferramentas(graph) as observacoes:
        retorno = AgentePlanejamento().executar(
            pedido["pergunta"], usuario_id=settings.default_user_id, thread_id=f"coleta-{id_}",
        )
    depois = ler_estado_sqlite(settings.memory_database)
    if antes != depois or retorno.get("interrupcao") is not None:
        raise ValueError("O lote não admite alterações de preferências, planos ou uma aprovação pendente.")

    candidata = _campos_candidata(id_, pedido["pergunta"], retorno, observacoes, os.environ["COLETA_JUIZ_ID"])
    _salvar(pasta / "coleta.json", {
        "caso": id_, "origem_entrada": pedido["origem_entrada"],
        "tipo_saida": "execucao_real_do_agente",
        "status": retorno["saida"]["status"], "motivo_termino": retorno["motivo_termino"],
        "tokens_entrada": retorno["tokens_entrada"], "tokens_saida": retorno["tokens_saida"],
        "custo_estimado_usd": retorno["custo_estimado_usd"],
        "ferramentas_observadas": observacoes, "candidata": candidata,
        "requer_revisao_de_tamanho": len(_json({
            k: candidata[k] for k in ("pergunta", "resposta", "evidencias")
        })) > 16_000,
    })
    return 0


def _executar(id_: str, env: dict, snapshot_hash: str, coleta_id: str) -> dict:
    with TemporaryDirectory(prefix="pasteis-lote-juiz-") as tmp:
        pasta = Path(tmp).resolve()
        ambiente = {
            **env, "EVAL_MYSQL_PASSWORD": env["MYSQL_PASSWORD"],
            "EVAL_SNAPSHOT_ESPERADO": snapshot_hash, "COLETA_JUIZ_ID": coleta_id,
            "CHECKPOINT_DATABASE": str(pasta / "checkpoints.sqlite3"),
            "MEMORY_DATABASE": str(pasta / "memoria.sqlite3"),
            "LOG_DIRECTORY": str(pasta / "logs"), "AGENT_THREAD_ID": f"coleta-{id_}",
        }
        try:
            subprocess.run(
                [sys.executable, "-m", "evals.coletar_lote_juiz", "--_interno", str(pasta), id_],
                cwd=RAIZ, env=ambiente, check=True, timeout=600,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as erro:
            raise ValueError(
                f"{id_}: coleta interrompida ({type(erro).__name__}). "
                "Os casos anteriores permanecem na pasta do lote."
            ) from None
        return json.loads((pasta / "coleta.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    if argv is None and len(sys.argv) == 4 and sys.argv[1] == "--_interno":
        try:
            return _interno(Path(sys.argv[2]).resolve(), sys.argv[3])
        except Exception as erro:
            print(f"Lote interno falhou: {type(erro).__name__}.", file=sys.stderr)
            return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conferir", action="store_true", help="Exibe as 28 perguntas, sem MySQL e sem API.")
    ap.add_argument("--amostra", type=Path, help="Arquivo atual com J01 e J02 preenchidas.")
    ap.add_argument("--coleta-base", type=Path, help="piloto.json que originou J01 e J02.")
    ap.add_argument("--versao", help="Identificação da versão na coleta.")
    ap.add_argument("--saida", type=Path, help="Pasta nova fora do repositório; padrão: pasta temporária.")
    ap.add_argument("--confirmar-dados-autorizados", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.conferir:
            for pedido in plano_lote():
                print(f"{pedido['id']} [entrada sintética]: {pedido['pergunta']}")
            print("28 entradas. Nenhuma consulta ao MySQL e nenhuma chamada à API.")
            return 0
        if not args.confirmar_dados_autorizados:
            raise ValueError("Confirme o envio dos dados consultados ao provedor do agente.")
        if not args.amostra or not args.coleta_base or not args.versao:
            raise ValueError("Informe --amostra, --coleta-base e --versao.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}", args.versao):
            raise ValueError("Use um nome curto de versão, como juiz-lote-local.")
        amostra = json.loads(args.amostra.read_text(encoding="utf-8-sig"))
        piloto = json.loads(args.coleta_base.read_text(encoding="utf-8-sig"))
        conferir_base(amostra, piloto)

        from .referencias_mysql import ambiente_demo, ler_snapshot
        from .rodar import carregar_dataset, _checar_modelo, _hash_dataset, _marcar_codigo

        dataset = carregar_dataset()
        env = ambiente_demo()
        snapshot = ler_snapshot(env, dataset["ambiente"])
        if snapshot.sha256 != piloto["snapshot_sha256"]:
            raise ValueError("O snapshot atual difere do piloto; não misture os dados das duas coletas.")
        modelo = _checar_modelo()
        coleta_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        destino = _fora_do_projeto(args.saida or (Path(gettempdir()) / f"pasteis-juiz-lote-{coleta_id}"))
        destino.mkdir(parents=True, exist_ok=False)
        relatorio = {
            "tipo": TIPO, "coleta_id": coleta_id, "sistema_versao": args.versao,
            "modelo": modelo, "codigo_sha256": _marcar_codigo(dataset),
            "dataset_sha256": _hash_dataset(dataset), "snapshot_sha256": snapshot.sha256,
            "snapshot_inalterado": False, "completo": False,
            "piloto_base_coleta_id": piloto.get("coleta_id"),
            "amostra_base_sha256": _hash(amostra), "plano": plano_lote(), "casos": [],
        }
        # Esta cópia preserva a origem e as revisões mesmo após uma interrupção.
        _salvar(destino / "amostra-base.json", amostra)
        _salvar(destino / "piloto-base.json", piloto)
        print(f"Coleta de 28 saídas. MySQL {env['EVAL_MYSQL_MODO']}, somente leitura. "
              f"Snapshot: {snapshot.sha256[:12]}. Não executa o juiz.", flush=True)
        try:
            for pedido in plano_lote():
                caso = _executar(pedido["id"], env, snapshot.sha256, coleta_id)
                _salvar(destino / f"{pedido['id']}.json", caso)
                relatorio["casos"].append(caso)
                print(f"{pedido['id']}: coletado ({caso['status']}); "
                      f"{len(relatorio['casos'])}/28, sem rótulo automático.", flush=True)
            relatorio["snapshot_inalterado"] = (
                ler_snapshot(env, dataset["ambiente"]).sha256 == snapshot.sha256
            )
            if not relatorio["snapshot_inalterado"]:
                raise ValueError("O MySQL mudou; o lote não foi importado para as fichas.")
            completa = montar_amostra(amostra, relatorio["casos"])
            _salvar(destino / "amostra-30.json", completa)
            relatorio["completo"] = True
        finally:
            _salvar(destino / "lote.json", relatorio)
            print(f"Registro do lote: {destino / 'lote.json'}", flush=True)
        grandes = sum(c["requer_revisao_de_tamanho"] for c in relatorio["casos"])
        print(f"Fichas com 30 saídas: {destino / 'amostra-30.json'}")
        print(f"J01 e J02 preservadas. 28 fichas novas sem revisão humana. "
              f"Casos novos com material maior que 16.000 caracteres: {grandes}.")
        print("Coleta concluída. O juiz ainda não foi executado nem validado.")
        return 0
    except (OSError, ValueError) as erro:
        print(f"Lote: {erro}", file=sys.stderr)
    except Exception as erro:
        print(f"Lote: não foi possível concluir ({type(erro).__name__}).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
