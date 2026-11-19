"""Executa o agente da aplicação e grava o resumo das checagens."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from time import perf_counter

from .referencias_mysql import ErroPreflight, ambiente_demo, ler_snapshot


RAIZ = Path(__file__).resolve().parents[1]
DATASET = RAIZ / "evals" / "golden_dataset.json"
ERROS_MODELO = {"ERRO_MODELO", "ERRO_DO_MODELO"}


def carregar_dataset() -> dict:
    dataset = json.loads(DATASET.read_text(encoding="utf-8-sig"))
    casos = dataset["casos"]

    if len(casos) < 20 or any(
        not re.fullmatch(r"GD[0-9]+", c["id"])
        or c["origem"] not in {"desenvolvimento", "sintetico", "producao"}
        or not c["por_que_existe"].strip()
        or not c["entrada"]
        or len(c["entrada"]) != len(c["esperado"])
        for c in casos
    ):
        raise ValueError("Os casos do dataset estão incompletos ou inválidos.")

    if len({c["id"] for c in casos}) != len(casos):
        raise ValueError("O dataset contém identificadores repetidos.")

    contagens = Counter(c["classe"] for c in casos)
    if len(contagens) < 3 or min(contagens.values()) < 2:
        raise ValueError(
            "O dataset precisa de três classes com pelo menos dois casos cada."
        )

    return dataset


def _checar_modelo() -> str:
    from src.config import settings

    settings.validar_modelo()
    precos = (
        settings.llm_input_price_per_million,
        settings.llm_output_price_per_million,
    )
    if not all(isfinite(p) and p > 0 for p in precos):
        raise ValueError("Confira os dois preços do modelo no .env antes de medir custo.")

    return settings.llm_model


def _hash_dataset(dataset: dict) -> str:
    conteudo = json.dumps(
        dataset,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


def _marcar_codigo(dataset: dict) -> str:
    sha = hashlib.sha256()
    arquivos = [
        RAIZ / "requirements.txt",
        *sorted((RAIZ / "src").rglob("*.py")),
        *sorted((RAIZ / "src" / "prompts").rglob("*.md")),
        *sorted((RAIZ / "dados" / "corpus").rglob("*.md")),
        *sorted((RAIZ / "evals").glob("*.py")),
    ]

    for arquivo in arquivos:
        sha.update(arquivo.relative_to(RAIZ).as_posix().encode("utf-8"))
        sha.update(b"\0")
        sha.update(hashlib.sha256(arquivo.read_bytes()).digest())

    sha.update(_hash_dataset(dataset).encode("ascii"))
    return sha.hexdigest()


def _trajetoria(execucao: dict, pasta_logs: Path):
    caminho = execucao.get("log")
    if not isinstance(caminho, str):
        return None

    caminho = Path(caminho).resolve()
    if not caminho.is_relative_to(pasta_logs.resolve()):
        return None

    try:
        return json.loads(caminho.read_text(encoding="utf-8"))["trajetoria"]
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _diagnostico_gd02(id_caso: str, saida: dict) -> dict | None:
    if (
        id_caso != "GD02"
        or os.environ.get("EVAL_DIAGNOSTICO_GD02") != "1"
        or saida.get("status") != "precisa_informacao"
    ):
        return None

    return {
        campo: valor[:1500] if isinstance(valor := saida.get(chave), str) else None
        for campo, chave in (
            ("motivo", "motivo"),
            ("proxima_acao", "proxima_acao"),
            ("resultado_textual", "resultado"),
        )
    }


def _caso_interno(pasta: Path, id_caso: str) -> int:
    from src.config import settings

    from .verificadores import EvidenciasEtapa, ler_estado_sqlite, verificar_etapa

    env = ambiente_demo()
    if (
        settings.mysql_host != env["MYSQL_HOST"]
        or settings.mysql_port != int(env["MYSQL_PORT"])
        or settings.mysql_database != env["MYSQL_DATABASE"]
        or settings.mysql_user != env["MYSQL_USER"]
        or settings.mysql_password != env["MYSQL_PASSWORD"]
        or settings.checkpoint_database.resolve() != pasta / "checkpoints.sqlite3"
        or settings.memory_database.resolve() != pasta / "memoria.sqlite3"
        or settings.log_directory.resolve() != pasta / "logs"
    ):
        raise ErroPreflight("A configuração do caso não está isolada.")

    dataset = carregar_dataset()
    caso = next(c for c in dataset["casos"] if c["id"] == id_caso)
    snapshot = ler_snapshot(env, dataset["ambiente"])

    if snapshot.sha256 != os.environ["EVAL_SNAPSHOT_ESPERADO"]:
        raise ErroPreflight("O MySQL mudou desde a conferência inicial.")

    # O grafo abre o checkpoint ao ser importado. Os caminhos já estão isolados.
    from src.agent import AgentePlanejamento
    from src.memory import obter_memoria

    obter_memoria()
    agente = AgentePlanejamento()
    usuario_id = settings.default_user_id
    thread_id = f"eval-{id_caso}"
    anterior = None
    etapas = []

    for indice, (entrada, esperado) in enumerate(
        zip(caso["entrada"], caso["esperado"], strict=True), start=1
    ):
        tipo = entrada["tipo"]
        havia_pausa = bool(anterior and anterior.get("interrupcao"))
        if tipo not in {"mensagem", "decisao_humana"} or (
            (tipo == "decisao_humana") != havia_pausa
        ):
            etapas.append({
                "etapa": indice,
                "executada": False,
                "aprovado_automatico": False,
                "falhas": [
                    {"nivel": "trajetoria", "checagem": "sequencia_de_aprovacao"}
                ],
            })
            break

        antes = ler_estado_sqlite(settings.memory_database)
        inicio = perf_counter()
        kwargs = {"usuario_id": usuario_id, "thread_id": thread_id}

        if tipo == "mensagem":
            atual = agente.executar(entrada["texto"], **kwargs)
        else:
            atual = agente.retomar(entrada["decisao"], **kwargs)

        latencia_ms = round((perf_counter() - inicio) * 1000, 2)
        depois = ler_estado_sqlite(settings.memory_database)

        checagens = verificar_etapa(
            esperado,
            dataset["padroes_por_etapa"],
            EvidenciasEtapa(
                execucao=atual,
                trajetoria=_trajetoria(atual, settings.log_directory),
                antes=antes,
                depois=depois,
                entrada=entrada,
                usuario_id=usuario_id,
                thread_id=thread_id,
                anterior=anterior,
                mysql=snapshot.referencias,
            ),
        )

        saida = atual["saida"]
        diagnostico = _diagnostico_gd02(id_caso, saida)
        if diagnostico is not None:
            checagens["diagnostico_gd02"] = diagnostico

        etapas.append({
            "etapa": indice,
            "executada": True,
            **checagens,
            "status": saida["status"],
            "motivo_termino": atual["motivo_termino"],
            "latencia_ms": latencia_ms,
            "tokens_entrada": atual["tokens_entrada"],
            "tokens_saida": atual["tokens_saida"],
            "custo_estimado_usd": atual["custo_estimado_usd"],
        })

        if atual["motivo_termino"] in ERROS_MODELO or not checagens["aprovado_automatico"]:
            break

        anterior = atual

    resultado = {
        "id": id_caso,
        "origem": caso["origem"],
        "classe": caso["classe"],
        "aprovado_automatico": len(etapas) == len(caso["entrada"]) and all(
            etapa["aprovado_automatico"] for etapa in etapas
        ),
        "etapas": etapas,
    }

    (pasta / "resultado.json").write_text(
        json.dumps(resultado, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


def _executar_caso(
    caso: dict,
    env_demo: dict,
    sha256: str,
    *,
    diagnostico_gd02: bool = False,
) -> dict:
    with TemporaryDirectory(prefix="pasteis-eval-") as tmp:
        pasta = Path(tmp).resolve()
        env = {
            **env_demo,
            "EVAL_MYSQL_PASSWORD": env_demo["MYSQL_PASSWORD"],
            "EVAL_SNAPSHOT_ESPERADO": sha256,
            "EVAL_DIAGNOSTICO_GD02": "1" if diagnostico_gd02 else "0",
            "CHECKPOINT_DATABASE": str(pasta / "checkpoints.sqlite3"),
            "MEMORY_DATABASE": str(pasta / "memoria.sqlite3"),
            "LOG_DIRECTORY": str(pasta / "logs"),
            "AGENT_THREAD_ID": f"eval-{caso['id']}",
        }

        try:
            subprocess.run(
                [sys.executable, "-m", "evals.rodar", "--_interno", str(pasta), caso["id"]],
                cwd=RAIZ,
                env=env,
                check=True,
                timeout=600,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.TimeoutExpired as erro:
            raise RuntimeError(f"{caso['id']}: processo excedeu o tempo limite.") from erro
        except subprocess.CalledProcessError as erro:
            linhas = (erro.stderr or "").strip().splitlines()
            detalhe = next(
                (linha for linha in reversed(linhas) if linha.startswith("Falha interna: ")),
                "processo falhou",
            )
            raise RuntimeError(f"{caso['id']}: {detalhe}.") from erro

        return json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--_interno":
        try:
            return _caso_interno(Path(sys.argv[2]).resolve(), sys.argv[3])
        except ErroPreflight as erro:
            print(f"Falha interna: {erro}", file=sys.stderr)
            return 2
        except Exception as erro:
            print(f"Falha interna: {type(erro).__name__}", file=sys.stderr)
            return 2

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conferir", action="store_true", help="Não chama modelo nem roda casos.")
    ap.add_argument("--versao", help="Versão do sistema para identificar a rodada.")
    ap.add_argument("--caso", action="append", help="Executa apenas o ID escolhido; pode repetir.")
    ap.add_argument(
        "--confirmar-dados-autorizados",
        action="store_true",
        help="Confirma que o provedor pode receber os dados que o agente consulta.",
    )
    ap.add_argument(
        "--diagnostico-gd02",
        action="store_true",
        help="Guarda o texto do pedido de informação numa pasta temporária, fora do projeto.",
    )
    args = ap.parse_args()

    if args.diagnostico_gd02 and (args.conferir or args.caso != ["GD02"]):
        ap.error("--diagnostico-gd02 só pode ser usado com --caso GD02.")

    if not args.conferir and (
        not args.versao
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}", args.versao)
        or not args.confirmar_dados_autorizados
    ):
        ap.error("Informe --versao e --confirmar-dados-autorizados para chamar a API.")

    try:
        dataset = carregar_dataset()
        casos = [c for c in dataset["casos"] if not args.caso or c["id"] in args.caso]

        if args.caso and set(args.caso) != {c["id"] for c in casos}:
            raise ValueError("Informe um ID existente, como GD01.")

        env = ambiente_demo()
        snapshot = ler_snapshot(env, dataset["ambiente"])
        modo = env["EVAL_MYSQL_MODO"]
        alvo = "local, somente leitura" if modo == "local" else "Docker"

        print(
            f"MySQL ({alvo}): {snapshot.total_operacoes} operações e "
            f"{snapshot.total_registros} registros. Snapshot: {snapshot.sha256[:12]}"
        )

        if args.conferir:
            print("Ambiente conferido. Nenhuma chamada à API.")
            return 0

        revisao = dataset["revisao_sinteticos"]
        if len(casos) == len(dataset["casos"]) and (
            revisao.get("status") != "revisado"
            or not revisao.get("revisado_por")
            or not revisao.get("data")
        ):
            raise ValueError("Revise os casos sintéticos antes da rodada completa.")

        modelo = _checar_modelo()
        codigo = _marcar_codigo(dataset)
        grupo = defaultdict(lambda: {"total": 0, "aprovados": 0})
        saidas = []
        interrompida = False

        for caso in casos:
            resultado = _executar_caso(
                caso,
                env,
                snapshot.sha256,
                diagnostico_gd02=args.diagnostico_gd02,
            )
            saidas.append(resultado)
            dados = grupo[caso["classe"]]
            dados["total"] += 1
            dados["aprovados"] += int(resultado["aprovado_automatico"])
            situacao = "OK automático" if resultado["aprovado_automatico"] else "FALHOU"
            print(f"{caso['id']}: {situacao}", flush=True)

            if any(e.get("motivo_termino") in ERROS_MODELO for e in resultado["etapas"]):
                print("Rodada interrompida após falha do modelo.", file=sys.stderr)
                interrompida = True
                break

        posterior = ler_snapshot(env, dataset["ambiente"])
        estavel = posterior.sha256 == snapshot.sha256
        completa = len(saidas) == len(dataset["casos"]) and estavel and not interrompida

        rodada = {
            "sistema_versao": args.versao,
            "dataset_versao": dataset["versao"],
            "dataset_sha256": _hash_dataset(dataset),
            "mysql_modo": modo,
            "snapshot_sha256": snapshot.sha256,
            "snapshot_inalterado": estavel,
            "codigo_sha256": codigo,
            "modelo": modelo,
            "rodada_completa": completa,
            "juiz_llm": "nao_executado",
            "origens": dict(Counter(c["origem"] for c in saidas)),
            "classes": dict(grupo),
            "casos": saidas,
        }

        for classe, contagem in sorted(grupo.items()):
            print(f"{classe}: {contagem['aprovados']}/{contagem['total']} no verificador.")

        carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        if args.diagnostico_gd02:
            pasta_resultados = Path(gettempdir()) / "pasteis-eval-diagnosticos"
        else:
            pasta_resultados = RAIZ / "evals" / "resultados"

        pasta = pasta_resultados / f"{args.versao}-{carimbo}"
        pasta.mkdir(parents=True)
        destino = pasta / "resultado.json"

        with destino.open("x", encoding="utf-8") as arquivo:
            json.dump(rodada, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")

        if args.diagnostico_gd02:
            print(f"Diagnóstico local: {destino.resolve()}")
        else:
            print(f"Resultado: {destino.relative_to(RAIZ)}")

        if not estavel:
            print("O snapshot mudou; não use esta rodada para comparar versões.", file=sys.stderr)

        return 0 if estavel and not interrompida and len(saidas) == len(casos) and all(
            c["aprovado_automatico"] for c in saidas
        ) else 1

    except (ValueError, OSError, RuntimeError) as erro:
        print(f"Suíte: {erro}", file=sys.stderr)
    except Exception as erro:
        print(
            f"Não foi possível completar a suíte: {type(erro).__name__}. "
            "Confira o MySQL selecionado e a configuração da avaliação.",
            file=sys.stderr,
        )

    return 2


if __name__ == "__main__":
    raise SystemExit(main())