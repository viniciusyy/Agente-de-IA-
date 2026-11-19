"""Prepara e calibra o juiz qualitativo sem alterar o placar automático."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


RUBRICA = Path(__file__).with_name("rubrica_justificativa_v1.md")
VERSAO_RUBRICA = "1.0.0"
QUANTIDADE = 30
LIMIAR_PCT = 90
MAX_FALSOS_POSITIVOS = 1
ROTULOS = ("SIM", "NAO")
PAPEIS = ("tecnica", "operacional")
CRITERIOS = {
    "quantidade_saidas": QUANTIDADE,
    "limiar_pct": LIMIAR_PCT,
    "max_falsos_positivos": MAX_FALSOS_POSITIVOS,
}
FORMATO_ESTRITO = {
    "type": "json_schema",
    "json_schema": {
        "name": "veredito_justificativa",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "rotulo": {"type": "string", "enum": list(ROTULOS)},
                "justificativa": {"type": "string"},
            },
            "required": ["rotulo", "justificativa"],
            "additionalProperties": False,
        },
    },
}


def _texto(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def nova_amostra() -> dict:
    return {
        "rubrica_versao": VERSAO_RUBRICA,
        "criterios_adocao": dict(CRITERIOS),
        "saidas": [
            {
                "id": f"J{i:02d}",
                "referencia_execucao": "",
                "pergunta": "",
                "resposta": "",
                "evidencias": [{"referencia": "", "trecho": ""}],
                "revisoes": {papel: {"rotulo": None, "nota": ""} for papel in PAPEIS},
                "consenso": {"rotulo": None, "nota": ""},
            }
            for i in range(1, QUANTIDADE + 1)
        ],
    }


def _dados_para_juiz(caso: dict) -> dict:
    # Lista fechada: notas e rótulos humanos, referência do log e identidade do
    # revisor não são enviados ao modelo.
    return {
        "pergunta": caso["pergunta"],
        "resposta": caso["resposta"],
        "evidencias": [
            {"referencia": item["referencia"], "trecho": item["trecho"]}
            for item in caso["evidencias"]
        ],
    }


def _rotulo_com_nota(obj) -> bool:
    return (
        isinstance(obj, dict)
        and obj.get("rotulo") in ROTULOS
        and _texto(obj.get("nota"))
    )


def validar_amostra(amostra: dict) -> list[dict]:
    if (
        not isinstance(amostra, dict)
        or amostra.get("rubrica_versao") != VERSAO_RUBRICA
        or amostra.get("criterios_adocao") != CRITERIOS
    ):
        raise ValueError("Use a amostra e os critérios da rubrica v1.0.0, sem alterar o limiar.")
    saidas = amostra.get("saidas")
    if not isinstance(saidas, list) or len(saidas) != QUANTIDADE:
        raise ValueError(f"A amostra precisa de {QUANTIDADE} saídas.")

    vistos = set()
    referencias = set()
    erros = []
    for indice, caso in enumerate(saidas, start=1):
        id_ = f"J{indice:02d}"
        if not isinstance(caso, dict) or caso.get("id") != id_ or id_ in vistos:
            erros.append(f"{id_}: mantenha o ID da ficha, sem duplicar ou reordenar.")
            continue
        vistos.add(id_)
        referencia = caso.get("referencia_execucao")
        if not _texto(referencia) or not _texto(caso.get("pergunta")):
            erros.append(f"{id_}: informe a execução de origem e a pergunta.")
        if _texto(referencia):
            if referencia.strip() in referencias:
                erros.append(f"{id_}: a referência da saída já foi usada em outra ficha.")
            referencias.add(referencia.strip())
        resposta = caso.get("resposta")
        if not (_texto(resposta) or isinstance(resposta, dict) and resposta):
            erros.append(f"{id_}: informe a resposta original, em texto ou objeto JSON.")
        evidencias = caso.get("evidencias")
        evidencias_validas = isinstance(evidencias, list) and evidencias and all(
            isinstance(e, dict) and _texto(e.get("referencia")) and _texto(e.get("trecho"))
            for e in evidencias
        )
        if not evidencias_validas:
            erros.append(f"{id_}: informe a referência e o trecho efetivamente consultado.")
        revisoes = caso.get("revisoes")
        if not isinstance(revisoes, dict) or not all(
            _rotulo_com_nota(revisoes.get(papel)) for papel in PAPEIS
        ):
            erros.append(f"{id_}: registre os dois rótulos humanos independentes e suas notas.")
        if not _rotulo_com_nota(caso.get("consenso")):
            erros.append(f"{id_}: registre o rótulo humano consensual e sua nota.")
        if evidencias_validas and _texto(caso.get("pergunta")) and resposta:
            if len(json.dumps(_dados_para_juiz(caso), ensure_ascii=False)) > 16_000:
                erros.append(f"{id_}: reduza o material enviado a 16.000 caracteres relevantes.")

    if erros:
        mostrados = "\n".join(erros[:10])
        restantes = f"\nOutras pendências: {len(erros) - 10}." if len(erros) > 10 else ""
        raise ValueError(f"Amostra incompleta; nenhuma chamada à API.\n{mostrados}{restantes}")
    if {c["consenso"]["rotulo"] for c in saidas} != set(ROTULOS):
        raise ValueError("Inclua casos com ambos os rótulos; 30 saídas de uma classe não validam o juiz.")
    return saidas


def _veredito(completion) -> dict:
    if len(completion.choices) != 1:
        raise ValueError("Resposta do juiz sem uma única opção.")
    escolha, = completion.choices
    if escolha.finish_reason != "stop" or getattr(escolha.message, "refusal", None):
        raise ValueError("Resposta do juiz incompleta ou recusada.")
    conteudo = escolha.message.content
    if not _texto(conteudo):
        raise ValueError("Resposta do juiz sem JSON.")
    objeto = json.loads(conteudo)
    if (
        not isinstance(objeto, dict) or set(objeto) != {"rotulo", "justificativa"}
        or objeto["rotulo"] not in ROTULOS or not _texto(objeto["justificativa"])
    ):
        raise ValueError("A saída do juiz não atende ao contrato binário.")
    return objeto


def _relatorio(amostra: dict, julgamentos: list[dict], *, modelo: str, rubrica: str, modo: str) -> dict:
    matriz = {h: {j: 0 for j in ROTULOS} for h in ROTULOS}
    desacordos = []
    for item in julgamentos:
        humano, juiz = item["rotulo_humano"], item["rotulo_juiz"]
        matriz[humano][juiz] += 1
        if humano != juiz:
            desacordos.append({
                "id": item["id"],
                "rotulo_humano": humano,
                "rotulo_juiz": juiz,
                "classificacao": None,
                "nota_revisao": "",
            })
    total = len(julgamentos)
    acertos = matriz["SIM"]["SIM"] + matriz["NAO"]["NAO"]
    fp = matriz["NAO"]["SIM"]
    atingiu = acertos * 100 >= LIMIAR_PCT * total and fp <= MAX_FALSOS_POSITIVOS
    return {
        "tipo": "validacao_juiz",
        "rubrica_versao": VERSAO_RUBRICA,
        "rubrica_sha256": hashlib.sha256(rubrica.encode("utf-8")).hexdigest(),
        "amostra_sha256": hashlib.sha256(json.dumps(
            amostra, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
        "modelo": modelo,
        "formato_json": modo,
        **CRITERIOS,
        "matriz_humano_por_juiz": matriz,
        "contagens_humanas": dict(Counter(i["rotulo_humano"] for i in julgamentos)),
        "concordancia_pct": round(100 * acertos / total, 2),
        "falsos_positivos": fp,
        "atingiu_criterios_numericos": atingiu,
        "situacao": (
            "criterios_numericos_nao_atingidos" if not atingiu else
            "aguardando_revisao_dos_desacordos" if desacordos else
            "apto_para_decisao_de_adocao"
        ),
        "desacordos": desacordos,
        "julgamentos": julgamentos,
    }


def avaliar(amostra: dict, cliente, *, modelo: str, modo: str = "schema", openai_oficial=False) -> dict:
    casos = validar_amostra(amostra)
    rubrica = RUBRICA.read_text(encoding="utf-8")
    formato = FORMATO_ESTRITO if modo == "schema" else {"type": "json_object"}
    julgamentos = []
    for caso in casos:
        try:
            completion = cliente.chat.completions.create(
                model=modelo,
                messages=[
                    {"role": "system", "content": rubrica},
                    {"role": "user", "content": json.dumps(_dados_para_juiz(caso), ensure_ascii=False)},
                ],
                response_format=formato,
                max_completion_tokens=700,
                **({"store": False} if openai_oficial else {}),
            )
            veredito = _veredito(completion)
        except Exception as erro:
            # Não loga o retorno bruto, o conteúdo da amostra nem a credencial.
            raise ValueError(
                f"O juiz falhou em {caso['id']} ({type(erro).__name__}); "
                "a calibração ficou incompleta e não deve ser usada."
            ) from None
        julgamentos.append({
            "id": caso["id"], "rotulo_humano": caso["consenso"]["rotulo"],
            "rotulo_juiz": veredito["rotulo"], "justificativa_juiz": veredito["justificativa"],
        })
    return _relatorio(amostra, julgamentos, modelo=modelo, rubrica=rubrica, modo=modo)


def _gravar(caminho: Path, dados: dict) -> None:
    with caminho.open("x", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    comandos = ap.add_subparsers(dest="comando", required=True)
    preparar = comandos.add_parser("preparar", help="Gera fichas de rotulagem vazias, sem API.")
    preparar.add_argument("--saida", type=Path, required=True)
    conferir = comandos.add_parser("conferir", help="Valida as fichas preenchidas, sem API.")
    conferir.add_argument("amostra", type=Path)
    avaliar_ap = comandos.add_parser("avaliar", help="Executa a calibração após as duas revisões humanas.")
    avaliar_ap.add_argument("amostra", type=Path)
    avaliar_ap.add_argument("--modelo", required=True, help="Modelo do juiz no provedor configurado.")
    avaliar_ap.add_argument("--saida", type=Path, required=True)
    avaliar_ap.add_argument("--formato", choices=("schema", "objeto"), default="schema")
    avaliar_ap.add_argument("--confirmar-dados-autorizados", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.comando == "preparar":
            _gravar(args.saida, nova_amostra())
            print(f"Fichas para {QUANTIDADE} saídas salvas em: {args.saida}. Nenhuma chamada à API.")
            return 0

        if args.comando == "avaliar" and not args.confirmar_dados_autorizados:
            raise ValueError("Confirme que as evidências revisadas podem ir ao provedor escolhido.")
        amostra = json.loads(args.amostra.read_text(encoding="utf-8-sig"))
        casos = validar_amostra(amostra)
        if args.comando == "conferir":
            contagens = Counter(c["consenso"]["rotulo"] for c in casos)
            print(f"Amostra conferida: {len(casos)} saídas, {contagens['SIM']} SIM e "
                  f"{contagens['NAO']} NAO. Nenhuma chamada à API.")
            return 0

        if args.saida.exists() or not args.saida.parent.is_dir():
            raise ValueError("Escolha um arquivo de saída novo em uma pasta que já exista.")
        if not args.modelo.strip():
            raise ValueError("Informe o modelo do juiz.")

        from openai import OpenAI
        from src.config import settings

        if not settings.openai_api_key:
            raise ValueError("A chave da API não está configurada no projeto.")
        with OpenAI(api_key=settings.openai_api_key, base_url=settings.llm_base_url,
                    max_retries=0, timeout=45.0) as cliente:
            relatorio = avaliar(
                amostra, cliente, modelo=args.modelo.strip(), modo=args.formato,
                openai_oficial=urlsplit(settings.llm_base_url).hostname == "api.openai.com",
            )
        _gravar(args.saida, relatorio)
        print(f"Juiz: {relatorio['concordancia_pct']}% · {relatorio['falsos_positivos']} FP · "
              f"{relatorio['situacao']}. Relatório: {args.saida}")
        return 0
    except (OSError, ValueError) as erro:
        print(f"Juiz: {erro}", file=sys.stderr)
    except Exception as erro:
        print(f"Juiz: não foi possível concluir ({type(erro).__name__}).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
