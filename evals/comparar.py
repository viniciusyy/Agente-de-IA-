"""Compara duas rodadas completas, sem consultar MySQL ou chamar modelos."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def carregar_json(caminho: Path) -> dict:
    if caminho.is_dir():
        caminho = caminho / "resultado.json"
    obj = json.loads(caminho.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"Esperava um objeto JSON em {caminho}.")
    return obj


def _casos(rodada: dict) -> dict[str, tuple[str, str, bool]]:
    if rodada.get("rodada_completa") is not True:
        raise ValueError("Use apenas rodadas completas, sem --caso.")
    if rodada.get("snapshot_inalterado") is not True:
        raise ValueError("O snapshot precisa ter permanecido estável durante as duas rodadas.")

    lista = rodada.get("casos")
    if not isinstance(lista, list) or not lista:
        raise ValueError("Rodada sem lista de casos.")
    casos = {}
    for caso in lista:
        if not isinstance(caso, dict):
            raise ValueError("Caso inválido no resultado da rodada.")
        id_, classe, origem = (caso.get(k) for k in ("id", "classe", "origem"))
        passou = caso.get("aprovado_automatico")
        if (
            not isinstance(id_, str) or not id_.strip() or id_ in casos
            or not isinstance(classe, str) or not classe.strip()
            or origem not in ("producao", "desenvolvimento", "sintetico")
            or type(passou) is not bool
        ):
            raise ValueError("Caso duplicado ou com metadados/resultado automático inválidos.")
        casos[id_] = classe, origem, passou
    return casos


def _linha(nome: str, ids: list[str], a: dict, b: dict) -> dict:
    total = len(ids)
    acertos_a = sum(a[id_][2] for id_ in ids)
    acertos_b = sum(b[id_][2] for id_ in ids)
    return {
        "classe": nome,
        "total": total,
        "acertos_a": acertos_a,
        "acertos_b": acertos_b,
        "taxa_a_pct": round(100 * acertos_a / total, 2),
        "taxa_b_pct": round(100 * acertos_b / total, 2),
        "delta_pp": round(100 * (acertos_b - acertos_a) / total, 2),
    }


def comparar(antiga: dict, nova: dict) -> dict:
    a, b = _casos(antiga), _casos(nova)
    for campo, rotulo in (
        ("dataset_versao", "versão do dataset"),
        ("dataset_sha256", "conteúdo do dataset"),
        ("snapshot_sha256", "snapshot MySQL"),
        ("mysql_modo", "modo do MySQL"),
    ):
        valor = antiga.get(campo)
        if not isinstance(valor, str) or not valor.strip() or valor != nova.get(campo):
            raise ValueError(f"Rodadas incompatíveis: {rotulo} diferente ou ausente.")
    if a.keys() != b.keys() or any(a[id_][:2] != b[id_][:2] for id_ in a):
        raise ValueError("Os IDs, as classes ou as origens dos casos são diferentes.")

    return {
        "tipo": "comparacao_automatica_de_rodadas",
        "dataset_versao": antiga["dataset_versao"],
        "dataset_sha256": antiga["dataset_sha256"],
        "snapshot_sha256": antiga["snapshot_sha256"],
        "mysql_modo": antiga["mysql_modo"],
        "origens": dict(Counter(origem for _, origem, _ in a.values())),
        "rodada_a": {k: antiga.get(k) for k in ("sistema_versao", "codigo_sha256", "modelo")},
        "rodada_b": {k: nova.get(k) for k in ("sistema_versao", "codigo_sha256", "modelo")},
        "classes": [
            _linha(classe, [id_ for id_, v in a.items() if v[0] == classe], a, b)
            for classe in sorted({v[0] for v in a.values()})
        ],
        "geral": _linha("GERAL", list(a), a, b),
        "melhoraram": sorted(id_ for id_ in a if not a[id_][2] and b[id_][2]),
        "pioraram": sorted(id_ for id_ in a if a[id_][2] and not b[id_][2]),
        "juiz_calibracao": None,
    }


def _resumo_juiz(relatorio: dict) -> dict:
    campos = (
        "rubrica_versao", "quantidade_saidas", "concordancia_pct",
        "limiar_pct", "falsos_positivos", "situacao",
    )
    if relatorio.get("tipo") != "validacao_juiz" or any(k not in relatorio for k in campos):
        raise ValueError("O arquivo --juiz não é um relatório de calibração do juiz.")
    return {k: relatorio[k] for k in campos}


def _imprimir(r: dict) -> None:
    origens = " · ".join(f"{k} {r['origens'].get(k, 0)}" for k in (
        "producao", "desenvolvimento", "sintetico",
    ))
    print(f"DATASET v{r['dataset_versao']} · {r['geral']['total']} casos ({origens})")
    print(f"SNAPSHOT {r['snapshot_sha256'][:12]} · MySQL {r['mysql_modo']}")
    for lado in ("a", "b"):
        versao = r[f"rodada_{lado}"]
        codigo = (versao["codigo_sha256"] or "não registrado")[:12]
        print(f"{lado.upper()}: {versao['sistema_versao']} · código {codigo} · {versao['modelo']}")
    if r["rodada_a"]["modelo"] != r["rodada_b"]["modelo"]:
        print("Os modelos diferem; o delta não isola apenas uma mudança de código.")
    juiz = r["juiz_calibracao"]
    if juiz is None:
        print("JUIZ: calibração não anexada; os percentuais abaixo são automáticos.")
    else:
        print(f"JUIZ rubrica v{juiz['rubrica_versao']} · concordância "
              f"{juiz['concordancia_pct']}% · limiar {juiz['limiar_pct']}% · {juiz['situacao']}")
    print(f"{'classe':<20} {'versão A':>9} {'versão B':>9} {'delta pp':>9}")
    for item in [*r["classes"], r["geral"]]:
        print(f"{item['classe']:<20} {item['taxa_a_pct']:>8.1f}% "
              f"{item['taxa_b_pct']:>8.1f}% {item['delta_pp']:>+9.1f}")
    print(f"Casos que melhoraram: {', '.join(r['melhoraram']) or 'nenhum'}")
    print(f"Casos que pioraram: {', '.join(r['pioraram']) or 'nenhum'}")
    print("Comparação descritiva de duas rodadas; não calcula pass^3 nem promove a versão.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("antiga", type=Path, help="Pasta da rodada A ou seu resultado.json.")
    ap.add_argument("nova", type=Path, help="Pasta da rodada B ou seu resultado.json.")
    ap.add_argument("--juiz", type=Path, help="Relatório separado de calibração do juiz.")
    ap.add_argument("--saida", type=Path, help="Opcional: salva a comparação em um JSON novo.")
    args = ap.parse_args(argv)
    try:
        r = comparar(carregar_json(args.antiga), carregar_json(args.nova))
        if args.juiz:
            r["juiz_calibracao"] = _resumo_juiz(carregar_json(args.juiz))
        if args.saida:
            with args.saida.open("x", encoding="utf-8") as arquivo:
                json.dump(r, arquivo, ensure_ascii=False, indent=2)
                arquivo.write("\n")
        _imprimir(r)
    except (OSError, ValueError) as erro:
        print(f"Comparação: {erro}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
