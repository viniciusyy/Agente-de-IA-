"""Coleta duas saídas reais para revisão local, sem executar o juiz."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from unittest.mock import patch
from uuid import uuid4

from .juiz import nova_amostra


RAIZ = Path(__file__).resolve().parents[1]
CASOS_PILOTO = ("GD08", "GD11")
FERRAMENTAS_LEITURA = {
    "consultar_operacao", "consultar_historico", "calcular_recomendacao",
}
_CAMPOS_LINHA = (
    "id_operacao", "id_produto", "produto", "feira", "data_producao", "data_venda",
    "quantidade_produzida", "quantidade_vendida", "quantidade_sobra",
    "total_produzido", "total_vendido", "total_sobra", "eh_feriado", "nome_feriado",
)


def _json(objeto) -> str:
    return json.dumps(objeto, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _hash(objeto) -> str:
    return hashlib.sha256(_json(objeto).encode("utf-8")).hexdigest()


def _salvar(caminho: Path, dados: dict) -> None:
    with caminho.open("x", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2, allow_nan=False)
        arquivo.write("\n")


def _fora_do_projeto(caminho: Path) -> Path:
    caminho = caminho.resolve()
    if caminho.is_relative_to(RAIZ):
        raise ValueError("Guarde as saídas brutas e fichas de revisão fora do repositório.")
    return caminho


def _reduzir_retorno(nome: str, retorno: dict) -> dict:
    """Projeta campos observados, sem recalcular números nem reconsultar fontes."""
    if nome == "buscar_conhecimento":
        campos = ("ok", "suficiente", "consulta", "motivo", "forma", "erro")
        reduzido = {k: deepcopy(retorno[k]) for k in campos if k in retorno}
        reduzido["resultados"] = [
            {k: deepcopy(d[k]) for k in (
                "documento_id", "titulo", "caminho", "status", "versao", "score", "conteudo",
            ) if k in d}
            for d in retorno.get("resultados", [])
        ]
        return reduzido

    campos = (
        "ok", "fonte", "erro", "id_operacao", "feira", "quantidade_registros",
        "quantidade_operacoes", "total_produzido", "total_vendido", "total_sobra",
        "metodo", "operacoes_consideradas", "recomendacoes", "total_recomendado",
        "regras_aplicadas", "aviso",
    )
    reduzido = {k: deepcopy(retorno[k]) for k in campos if k in retorno}
    for chave in ("dados", "operacoes"):
        if chave in retorno:
            reduzido[chave] = [
                {k: deepcopy(linha[k]) for k in _CAMPOS_LINHA if k in linha}
                for linha in retorno[chave]
            ]
    return reduzido


@contextmanager
def capturar_ferramentas(graph):
    """Observa os retornos reais no processo isolado, inclusive o RAG direto."""
    observacoes = []
    executar_original = graph._executar
    buscar_original = graph.buscar_conhecimento

    def observar(nome, argumentos, retorno):
        if not isinstance(retorno, dict):
            raise ValueError("A ferramenta não devolveu um objeto estruturado.")
        observacoes.append({
            "ferramenta": nome,
            "argumentos": deepcopy(argumentos),
            "retorno_observado_sha256": _hash(retorno),
            "retorno": _reduzir_retorno(nome, retorno),
        })
        return retorno

    def buscar(consulta):
        return observar("buscar_conhecimento", {"consulta": consulta}, buscar_original(consulta))

    def executar(nome, argumentos, estado):
        if nome == "buscar_conhecimento":
            # O wrapper da busca registra uma vez, mesmo quando chamado por _executar.
            return executar_original(nome, argumentos, estado)
        if nome not in FERRAMENTAS_LEITURA:
            # RuntimeError interrompe a coleta em vez de gerar um retorno
            # artificial de ferramenta que pudesse ser confundido com evidência.
            raise RuntimeError("O piloto não autoriza uma ferramenta de escrita.")
        return observar(nome, argumentos, executar_original(nome, argumentos, estado))

    with patch.object(graph, "_executar", executar), patch.object(graph, "buscar_conhecimento", buscar):
        yield observacoes


def _candidata(id_caso: str, pergunta: str, resposta: dict, observacoes: list, coleta_id: str) -> dict:
    evidencias = [
        {
            "referencia": f"coleta:{coleta_id}/{id_caso}/ferramenta/{i}",
            "trecho": _json({
                "ferramenta": obs["ferramenta"],
                "argumentos": obs["argumentos"],
                "retorno": obs["retorno"],
            }),
        }
        for i, obs in enumerate(observacoes, start=1)
    ]
    return {
        "referencia_execucao": f"coleta:{coleta_id}/{id_caso}",
        "pergunta": pergunta,
        "resposta": deepcopy(resposta),
        "evidencias": evidencias,
        "revisoes": {
            "tecnica": {"rotulo": None, "nota": ""},
            "operacional": {"rotulo": None, "nota": ""},
        },
        "consenso": {"rotulo": None, "nota": ""},
    }


def _interno(pasta: Path, id_caso: str) -> int:
    from src.config import settings
    from .referencias_mysql import ambiente_demo, ler_snapshot
    from .rodar import carregar_dataset
    from .verificadores import ler_estado_sqlite

    env = ambiente_demo()
    if id_caso not in CASOS_PILOTO:
        raise ValueError("O piloto admite apenas GD08 e GD11.")
    for campo, chave in (
        ("mysql_host", "MYSQL_HOST"), ("mysql_database", "MYSQL_DATABASE"),
        ("mysql_user", "MYSQL_USER"), ("mysql_password", "MYSQL_PASSWORD"),
    ):
        if getattr(settings, campo) != env[chave]:
            raise ValueError("As credenciais do processo não são as da avaliação somente leitura.")
    if settings.mysql_port != int(env["MYSQL_PORT"]):
        raise ValueError("A porta do processo não é a da avaliação.")
    for campo, nome in (
        ("checkpoint_database", "checkpoints.sqlite3"),
        ("memory_database", "memoria.sqlite3"), ("log_directory", "logs"),
    ):
        if getattr(settings, campo).resolve() != pasta / nome:
            raise ValueError("O checkpoint, a memória ou os logs não estão isolados.")

    dataset = carregar_dataset()
    snapshot = ler_snapshot(env, dataset["ambiente"])
    if snapshot.sha256 != os.environ["EVAL_SNAPSHOT_ESPERADO"]:
        raise ValueError("O MySQL mudou desde o início da coleta.")
    caso = next(c for c in dataset["casos"] if c["id"] == id_caso)
    if len(caso["entrada"]) != 1 or caso["entrada"][0]["tipo"] != "mensagem":
        raise ValueError("Os casos do piloto precisam conter uma única mensagem.")

    from src import graph
    from src.agent import AgentePlanejamento
    from src.memory import obter_memoria

    obter_memoria()
    antes = ler_estado_sqlite(settings.memory_database)
    pergunta = caso["entrada"][0]["texto"]
    with capturar_ferramentas(graph) as observacoes:
        retorno = AgentePlanejamento().executar(
            pergunta, usuario_id=settings.default_user_id, thread_id=f"coleta-{id_caso}",
        )
    depois = ler_estado_sqlite(settings.memory_database)
    if antes != depois or retorno.get("interrupcao") is not None:
        raise ValueError("O piloto tentou criar uma preferência, plano ou aprovação.")
    if not observacoes:
        raise ValueError("Não houve ferramenta observada; não inventaremos evidência para esta saída.")
    candidata = _candidata(
        id_caso, pergunta, retorno["saida"], observacoes, os.environ["COLETA_JUIZ_ID"],
    )
    dados = {
        "caso": id_caso,
        "modelo": settings.llm_model,
        "status": retorno["saida"]["status"],
        "motivo_termino": retorno["motivo_termino"],
        "tokens_entrada": retorno["tokens_entrada"],
        "tokens_saida": retorno["tokens_saida"],
        "custo_estimado_usd": retorno["custo_estimado_usd"],
        "ferramentas_observadas": observacoes,
        "candidata": candidata,
        "requer_revisao_de_tamanho": len(_json({
            k: candidata[k] for k in ("pergunta", "resposta", "evidencias")
        })) > 16_000,
    }
    _salvar(pasta / "coleta.json", dados)
    return 0


def _executar(id_caso: str, env: dict, snapshot_hash: str, coleta_id: str) -> dict:
    with TemporaryDirectory(prefix="pasteis-coleta-") as tmp:
        pasta = Path(tmp).resolve()
        ambiente = {
            **env,
            "EVAL_MYSQL_PASSWORD": env["MYSQL_PASSWORD"],
            "EVAL_SNAPSHOT_ESPERADO": snapshot_hash,
            "COLETA_JUIZ_ID": coleta_id,
            "CHECKPOINT_DATABASE": str(pasta / "checkpoints.sqlite3"),
            "MEMORY_DATABASE": str(pasta / "memoria.sqlite3"),
            "LOG_DIRECTORY": str(pasta / "logs"),
            "AGENT_THREAD_ID": f"coleta-{id_caso}",
        }
        try:
            subprocess.run(
                [sys.executable, "-m", "evals.coletar_juiz", "--_interno", str(pasta), id_caso],
                cwd=RAIZ, env=ambiente, check=True, timeout=600,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as erro:
            # Não imprime stderr bruto, credenciais nem dados do MySQL.
            raise ValueError(f"{id_caso}: coleta não concluída ({type(erro).__name__}).") from None
        return json.loads((pasta / "coleta.json").read_text(encoding="utf-8"))


def importar(coleta: dict, amostra: dict) -> dict:
    """Preenche fichas vazias em uma cópia; nenhum rótulo é inferido."""
    modelo = nova_amostra()
    if (
        coleta.get("tipo") != "piloto_local_juiz" or coleta.get("completo") is not True
        or coleta.get("snapshot_inalterado") is not True
    ):
        raise ValueError("Importe somente uma coleta completa com snapshot inalterado.")
    if (
        amostra.get("rubrica_versao") != modelo["rubrica_versao"]
        or amostra.get("criterios_adocao") != modelo["criterios_adocao"]
        or not isinstance(amostra.get("saidas"), list)
        or len(amostra["saidas"]) != len(modelo["saidas"])
    ):
        raise ValueError("Use as 30 fichas originais da rubrica, sem mudar os critérios.")
    saidas = deepcopy(amostra["saidas"])
    vazias, referencias = [], set()
    for ficha, padrao in zip(saidas, modelo["saidas"], strict=True):
        if ficha.get("id") != padrao["id"]:
            raise ValueError("Mantenha os IDs J01 a J30 na ordem original.")
        if ficha == padrao:
            vazias.append(ficha)
        referencia = ficha.get("referencia_execucao")
        if referencia:
            referencias.add(referencia)
    casos = coleta.get("casos")
    if (
        not isinstance(casos, list) or len(casos) != 2
        or {c.get("caso") for c in casos} != set(CASOS_PILOTO)
    ):
        raise ValueError("O piloto precisa conter exatamente as saídas de GD08 e GD11.")
    candidatas = [c["candidata"] for c in casos]
    if len(vazias) < len(candidatas):
        raise ValueError("Não há fichas totalmente vazias suficientes; não sobrescreveremos uma revisão.")
    for ficha, candidata in zip(vazias, candidatas):
        referencia = candidata.get("referencia_execucao")
        if not referencia or referencia in referencias:
            raise ValueError("Esta saída já foi importada, ou não tem referência de execução.")
        referencias.add(referencia)
        if (
            not candidata.get("evidencias")
            or candidata.get("consenso") != {"rotulo": None, "nota": ""}
            or candidata.get("revisoes") != modelo["saidas"][0]["revisoes"]
        ):
            raise ValueError("A coleta precisa trazer evidências e deixar os rótulos humanos vazios.")
        id_ = ficha["id"]
        ficha.update(deepcopy(candidata))
        ficha["id"] = id_
    return {**deepcopy(amostra), "saidas": saidas}


def main(argv: list[str] | None = None) -> int:
    if argv is None and len(sys.argv) == 4 and sys.argv[1] == "--_interno":
        try:
            return _interno(Path(sys.argv[2]).resolve(), sys.argv[3])
        except Exception as erro:
            print(f"Coleta interna falhou: {type(erro).__name__}.", file=sys.stderr)
            return 2

    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="comando", required=True)
    piloto = sub.add_parser("piloto", help="Executa GD08 e GD11, com possíveis custos do agente.")
    piloto.add_argument("--versao", required=True)
    piloto.add_argument("--saida", type=Path, help="Pasta nova fora do projeto; padrão: pasta temporária.")
    piloto.add_argument("--confirmar-dados-autorizados", action="store_true")
    imp = sub.add_parser("importar", help="Preenche duas fichas vazias, sem API e sem MySQL.")
    imp.add_argument("coleta", type=Path, help="piloto.json gerado pelo coletor.")
    imp.add_argument("--amostra", type=Path, required=True)
    imp.add_argument("--saida", type=Path, required=True, help="Novo JSON fora do projeto.")
    args = ap.parse_args(argv)

    try:
        if args.comando == "importar":
            destino = _fora_do_projeto(args.saida)
            coleta = json.loads(args.coleta.read_text(encoding="utf-8-sig"))
            amostra = json.loads(args.amostra.read_text(encoding="utf-8-sig"))
            _salvar(destino, importar(coleta, amostra))
            print(f"Duas fichas preenchidas, sem rótulos: {destino}. Nenhuma chamada à API.")
            return 0

        if not args.confirmar_dados_autorizados:
            raise ValueError("Confirme o envio dos dados consultados ao provedor do agente.")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}", args.versao):
            raise ValueError("Informe um nome curto de versão, como juiz-piloto-local.")
        from .referencias_mysql import ambiente_demo, ler_snapshot
        from .rodar import carregar_dataset, _checar_modelo, _hash_dataset, _marcar_codigo

        dataset = carregar_dataset()
        env = ambiente_demo()
        snapshot = ler_snapshot(env, dataset["ambiente"])
        modelo = _checar_modelo()
        coleta_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        destino = _fora_do_projeto(args.saida or (Path(gettempdir()) / f"pasteis-juiz-{coleta_id}"))
        destino.mkdir(parents=True, exist_ok=False)
        relatorio = {
            "tipo": "piloto_local_juiz", "coleta_id": coleta_id,
            "sistema_versao": args.versao, "modelo": modelo,
            "codigo_sha256": _marcar_codigo(dataset), "dataset_sha256": _hash_dataset(dataset),
            "snapshot_sha256": snapshot.sha256, "snapshot_inalterado": False,
            "mysql_modo": env["EVAL_MYSQL_MODO"], "completo": False, "casos": [],
        }
        print(f"Piloto de duas saídas. MySQL {env['EVAL_MYSQL_MODO']}, somente leitura. "
              f"Snapshot: {snapshot.sha256[:12]}", flush=True)
        try:
            for id_caso in CASOS_PILOTO:
                caso = _executar(id_caso, env, snapshot.sha256, coleta_id)
                _salvar(destino / f"{id_caso}.json", caso)
                relatorio["casos"].append(caso)
                print(f"{id_caso}: coletado; {len(caso['ferramentas_observadas'])} "
                      "retorno(s) real(is), rótulos humanos vazios.", flush=True)
            relatorio["snapshot_inalterado"] = (
                ler_snapshot(env, dataset["ambiente"]).sha256 == snapshot.sha256
            )
            relatorio["completo"] = relatorio["snapshot_inalterado"]
        finally:
            _salvar(destino / "piloto.json", relatorio)
            print(f"Coleta local: {destino / 'piloto.json'}", flush=True)
        if not relatorio["completo"]:
            raise ValueError("Snapshot alterado. Não use a coleta para calibrar o juiz.")
        print("Piloto concluído. Não chamou o juiz nem validou a amostra de 30 saídas.")
        return 0
    except (OSError, ValueError) as erro:
        print(f"Coletor: {erro}", file=sys.stderr)
    except Exception as erro:
        print(f"Coletor: não foi possível concluir ({type(erro).__name__}).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
