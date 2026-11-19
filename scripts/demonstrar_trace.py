"""Gera e confere um trace local do glossário sem MySQL ou provedor remoto."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from src.observabilidade import PERGUNTA_DEMO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versao", default="observabilidade-v1-demo")
    args = parser.parse_args()

    projeto = Path(__file__).resolve().parents[1]
    traces = projeto / "logs" / "traces" / f"demo-{uuid4().hex[:12]}"

    with TemporaryDirectory(prefix="pasteis-demo-trace-") as temporaria:
        pasta = Path(temporaria)
        env = {
            "PYTHON_DOTENV_DISABLED": "1",
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "CHECKPOINT_DATABASE": str(pasta / "checkpoint.sqlite3"),
            "MEMORY_DATABASE": str(pasta / "memoria.sqlite3"),
            "LOG_DIRECTORY": str(pasta / "logs"),
            "CORPUS_DIRECTORY": str(projeto / "dados" / "corpus"),
            "PASTEIS_TRACE_DIR": str(traces),
            "PASTEIS_TRACE_VERSAO": args.versao,
            "PASTEIS_TRACE_COORTE": "teste",
            "AGENT_USER_ID": "proprietario",
            "AGENT_THREAD_ID": "demo-trace",
        }

        with patch.dict(os.environ, env):
            from src import agent, graph

            try:
                with (
                    patch.object(
                        graph, "OpenAI",
                        side_effect=AssertionError("API não permitida na demo"),
                    ),
                    patch(
                        "mysql.connector.connect",
                        side_effect=AssertionError("MySQL não permitido na demo"),
                    ),
                ):
                    retorno = agent.AgentePlanejamento().executar(PERGUNTA_DEMO)
            finally:
                graph._checkpoint_connection.close()

    arquivos = list(traces.glob("otel-*.jsonl"))
    spans = [
        json.loads(linha)
        for arq in arquivos
        for linha in arq.read_text(encoding="utf-8").splitlines()
    ]
    raiz = next((span for span in spans if span["name"] == "invoke_agent pasteis-miyata"), None)
    busca = next((span for span in spans if span["name"] == "execute_tool buscar_conhecimento"), None)

    if (
        len(spans) != 2
        or raiz is None
        or busca is None
        or busca["parent_id"] != raiz["context"]["span_id"]
    ):
        parser.exit(1, "Trace incompleto: esperava uma raiz e uma busca filha, sem chat.\n")

    campos = raiz["attributes"]
    resultado = json.loads(campos["pasteis.saida.campos"])
    if (
        retorno["saida"]["status"] != "concluido"
        or resultado.get("prova_falta") is not False
        or campos["pasteis.execucao.custo_estimado_usd"] != 0
    ):
        parser.exit(1, "A demonstração não confirmou a resposta do glossário.\n")

    decisao = next(e for e in raiz["events"] if e["name"] == "rag.decisao")
    doc = json.loads(decisao["attributes"]["pasteis.rag.documento_usado"])
    print(f"Pergunta: {campos['pasteis.entrada.pergunta_demo']}")
    print(f"Trace: {raiz['context']['trace_id']}")
    print("Spans: invoke_agent pasteis-miyata -> execute_tool buscar_conhecimento")
    print(f"Documento usado: {doc['documento_id']} (versão {doc['versao']})")
    print("Saída: concluido; prova_falta=false. Nenhuma chamada ao MySQL ou à API.")
    print(f"Arquivo: {arquivos[0]}")
    print("Coorte: teste. Não usar este trace para medir o SLO.")


if __name__ == "__main__":
    main()