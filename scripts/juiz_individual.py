"""Revisão humana individual e calibração do juiz."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from evals import juiz


RAIZ = Path(__file__).resolve().parents[1]
PROTOCOLO = "individual-v1"


def carregar(caminho):
    return json.loads(caminho.read_text(encoding="utf-8-sig"))


def resumo_sha(dados):
    serializado = json.dumps(
        dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def materiais(amostra):
    if (
        not isinstance(amostra, dict)
        or amostra.get("rubrica_versao") != juiz.VERSAO_RUBRICA
        or amostra.get("criterios_adocao") != juiz.CRITERIOS
    ):
        raise ValueError("Use as fichas da rubrica v1.0.0, sem alterar os critérios.")

    casos = amostra.get("saidas")
    if not isinstance(casos, list) or len(casos) != juiz.QUANTIDADE:
        raise ValueError(f"Esperadas {juiz.QUANTIDADE} fichas completas de coleta.")

    referencias = set()
    base = []
    for n, caso in enumerate(casos, start=1):
        id_ = f"J{n:02d}"
        if not isinstance(caso, dict) or caso.get("id") != id_:
            raise ValueError(f"{id_}: ID ausente ou fora de ordem.")

        ref = caso.get("referencia_execucao")
        if not juiz._texto(ref) or ref.strip() in referencias:
            raise ValueError(f"{id_}: referência de execução ausente ou repetida.")
        referencias.add(ref.strip())

        resposta = caso.get("resposta")
        if not juiz._texto(caso.get("pergunta")) or not (
            juiz._texto(resposta) or isinstance(resposta, dict) and resposta
        ):
            raise ValueError(f"{id_}: falta pergunta ou resposta original.")

        evidencias = caso.get("evidencias")
        if not isinstance(evidencias, list) or not evidencias or not all(
            isinstance(e, dict)
            and juiz._texto(e.get("referencia"))
            and juiz._texto(e.get("trecho"))
            for e in evidencias
        ):
            raise ValueError(f"{id_}: faltam referências ou trechos das evidências.")

        dados = juiz._dados_para_juiz(caso)
        if len(json.dumps(dados, ensure_ascii=False)) > 16_000:
            raise ValueError(f"{id_}: material acima do limite de 16.000 caracteres.")

        base.append({
            "id": id_,
            "referencia_execucao": ref,
            "proveniencia": caso.get("proveniencia"),
            "dados": dados,
        })

    return base


def fora_do_projeto(caminho):
    resolvido = caminho.resolve()
    if resolvido.is_relative_to(RAIZ):
        raise ValueError("Guarde a amostra revisada ou o relatório fora do repositório.")
    return resolvido


def abrir_copia(origem, destino):
    if origem.resolve() == destino:
        raise ValueError("Use um arquivo de saída diferente da amostra original.")

    amostra = carregar(origem)
    assinatura = resumo_sha(materiais(amostra))

    if destino.exists():
        atual = carregar(destino)
        if (
            atual.get("protocolo_revisao") != PROTOCOLO
            or atual.get("material_sha256") != assinatura
            or resumo_sha(materiais(atual)) != assinatura
        ):
            raise ValueError("O arquivo de saída já existe, mas não é desta revisão.")
        return atual

    copia = deepcopy(amostra)
    copia["protocolo_revisao"] = PROTOCOLO
    copia["material_sha256"] = assinatura

    for caso in copia["saidas"]:
        caso.pop("revisoes", None)
        caso.pop("consenso", None)
        caso["revisao_individual"] = {"rotulo": None, "nota": ""}

    juiz._gravar(destino, copia)
    return copia


def salvar_atualizacao(caminho, dados):
    temporario = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp",
            dir=caminho.parent, delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def exibir(valor):
    if isinstance(valor, str):
        try:
            objeto = json.loads(valor)
        except ValueError:
            print(valor)
            return
        if not isinstance(objeto, (dict, list)):
            print(valor)
            return
        valor = objeto

    print(json.dumps(valor, ensure_ascii=False, indent=2))


def revisar(origem, destino):
    destino = fora_do_projeto(destino)
    amostra = abrir_copia(origem, destino)
    casos = amostra["saidas"]

    print("Compare a resposta com as evidências.")
    print("SIM = sustentada; NAO = não sustentada.")
    print("Cada ficha concluída é salva. Digite SAIR para pausar.")

    try:
        for caso in casos:
            if juiz._rotulo_com_nota(caso.get("revisao_individual")):
                continue

            print(f"\n{caso['id']} de {len(casos)}: {caso['pergunta']}")
            print("\nRESPOSTA:")
            exibir(caso["resposta"])

            for evidencia in caso["evidencias"]:
                print(f"\nEVIDÊNCIA — {evidencia['referencia']}:")
                exibir(evidencia["trecho"])

            while True:
                rotulo = input("\nSeu rótulo (SIM/NAO/SAIR): ").strip().upper()
                if rotulo == "SAIR":
                    return
                if rotulo == "NÃO":
                    rotulo = "NAO"
                if rotulo in juiz.ROTULOS:
                    break
                print("Digite SIM, NAO ou SAIR.")

            while True:
                nota = input("Sua nota: qual afirmação tem ou não tem suporte? ").strip()
                if nota.upper() == "SAIR":
                    return
                if nota:
                    break
                print("A nota não pode ficar vazia.")

            caso["revisao_individual"] = {"rotulo": rotulo, "nota": nota}
            salvar_atualizacao(destino, amostra)
            print(f"{caso['id']} salva.")

    except (EOFError, KeyboardInterrupt):
        print("\nRevisão pausada. As fichas anteriores estão salvas.")
    finally:
        prontas = sum(
            juiz._rotulo_com_nota(caso.get("revisao_individual"))
            for caso in casos
        )
        print(f"Fichas com revisão individual: {prontas}/{len(casos)}.")
        print(f"Cópia de revisão: {destino}")


def conferir(amostra):
    assinatura = resumo_sha(materiais(amostra))
    if (
        amostra.get("protocolo_revisao") != PROTOCOLO
        or amostra.get("material_sha256") != assinatura
    ):
        raise ValueError("Informe a cópia do protocolo individual, sem alterar os materiais.")

    casos = amostra["saidas"]
    faltam = [
        caso["id"] for caso in casos
        if not juiz._rotulo_com_nota(caso.get("revisao_individual"))
    ]
    if faltam:
        raise ValueError(
            f"Faltam rótulo e/ou nota em {len(faltam)} fichas: {', '.join(faltam)}."
        )

    contagem = Counter(caso["revisao_individual"]["rotulo"] for caso in casos)
    if set(contagem) != set(juiz.ROTULOS):
        raise ValueError(
            "As 30 fichas foram revisadas, mas há apenas uma classe. "
            "Não altere rótulos para balancear; reporte a limitação da amostra."
        )

    return contagem


def prompt_do_juiz():
    texto = juiz.RUBRICA.read_text(encoding="utf-8")
    inicio, separador, protocolo = texto.partition(
        "## Protocolo registrado antes da avaliação"
    )
    formato = "## Formato da saída do modelo"

    if not separador or formato not in protocolo:
        raise ValueError("A estrutura da rubrica mudou; confira antes da calibração.")

    return inicio.rstrip() + "\n\n" + formato + protocolo.split(formato, 1)[1]


def avaliar(amostra, cliente, *, modelo, oficial=False):
    conferir(amostra)
    rubrica = prompt_do_juiz()
    julgamentos = []

    for caso in amostra["saidas"]:
        try:
            resposta = cliente.chat.completions.create(
                model=modelo,
                messages=[
                    {"role": "system", "content": rubrica},
                    {
                        "role": "user",
                        "content": json.dumps(
                            juiz._dados_para_juiz(caso), ensure_ascii=False,
                        ),
                    },
                ],
                response_format=juiz.FORMATO_ESTRITO,
                max_completion_tokens=700,
                **({"store": False} if oficial else {}),
            )
            veredito = juiz._veredito(resposta)
        except Exception as erro:
            raise ValueError(
                f"Falha em {caso['id']} ({type(erro).__name__}); calibração incompleta."
            ) from None

        julgamentos.append({
            "id": caso["id"],
            "rotulo_humano": caso["revisao_individual"]["rotulo"],
            "rotulo_juiz": veredito["rotulo"],
            "justificativa_juiz": veredito["justificativa"],
        })

    relatorio = juiz._relatorio(
        amostra, julgamentos, modelo=modelo, rubrica=rubrica, modo="schema",
    )
    relatorio["protocolo_revisao"] = PROTOCOLO
    relatorio["numero_revisores_humanos_declarados"] = 1
    relatorio["material_sha256"] = amostra["material_sha256"]
    return relatorio


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    comandos = ap.add_subparsers(dest="comando", required=True)

    revisao = comandos.add_parser("revisar")
    revisao.add_argument("amostra", type=Path)
    revisao.add_argument("--saida", type=Path, required=True)

    checagem = comandos.add_parser("conferir")
    checagem.add_argument("amostra", type=Path)

    avaliacao = comandos.add_parser("avaliar")
    avaliacao.add_argument("amostra", type=Path)
    avaliacao.add_argument("--modelo", required=True)
    avaliacao.add_argument("--saida", type=Path, required=True)
    avaliacao.add_argument("--confirmar-dados-autorizados", action="store_true")

    args = ap.parse_args()
    try:
        if args.comando == "revisar":
            revisar(args.amostra, args.saida)
            return

        if args.comando == "avaliar" and not args.confirmar_dados_autorizados:
            raise ValueError(
                "Confirme a autorização de envio das evidências antes de chamar a API."
            )

        amostra = carregar(args.amostra)
        contagem = conferir(amostra)

        if args.comando == "conferir":
            print(f"Amostra individual conferida: {sum(contagem.values())} saídas.")
            print(f"SIM: {contagem['SIM']} | NAO: {contagem['NAO']}. Nenhuma chamada à API.")
            return

        saida = fora_do_projeto(args.saida)
        if saida.exists() or not saida.parent.is_dir():
            raise ValueError("Escolha um arquivo de relatório novo em uma pasta existente.")
        if not args.modelo.strip():
            raise ValueError("Informe um modelo para o juiz.")

        from openai import OpenAI
        from src.config import settings

        if not settings.openai_api_key:
            raise ValueError("A chave da API não está configurada.")

        with OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.llm_base_url,
            max_retries=0,
            timeout=45.0,
        ) as cliente:
            relatorio = avaliar(
                amostra, cliente, modelo=args.modelo.strip(),
                oficial=urlsplit(settings.llm_base_url).hostname == "api.openai.com",
            )

        juiz._gravar(saida, relatorio)
        print(json.dumps({
            chave: relatorio[chave]
            for chave in (
                "protocolo_revisao", "matriz_humano_por_juiz",
                "concordancia_pct", "falsos_positivos", "situacao",
            )
        }, ensure_ascii=False, indent=2))
        print(f"Relatório local: {saida}")

    except (OSError, ValueError, TypeError, KeyError) as erro:
        ap.exit(2, f"Juiz individual: {erro}\n")


if __name__ == "__main__":
    main()