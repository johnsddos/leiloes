#!/usr/bin/env python3
"""Atualização diária: coleta todas as fontes, normaliza e gera os dados do site.

Uso (na raiz do repositório):  python coleta/rodar.py [--so caixa,zuk] [--sem-coleta]

- Cada fonte é coletada separadamente. Se uma falhar ou vier pequena demais, o site usa a
  última coleta boa dela (guardada em brutos/), e a página mostra a data dessa coleta.
- Lotes com data vencida saem na normalização, mesmo quando a fonte usa dados antigos.
"""
import argparse
import datetime as dt
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
import fontes  # noqa: E402

BRUTOS = os.path.join(RAIZ, "brutos")
INICIAIS = os.path.join(RAIZ, "brutos-iniciais")
SITE_DADOS = os.path.join(RAIZ, "site", "dados")
STATUS = os.path.join(BRUTOS, "_status.json")

# nome do arquivo bruto, função de coleta, mínimo de registros para aceitar a coleta, nome exibido
FONTES = {
    "caixa": ("caixa_completa.csv", fontes.caixa, 5000, "Caixa"),
    "zuk": ("zuk2.json", fontes.zuk, 200, "Zuk"),
    "mega": ("mega.json", fontes.mega, 200, "Mega Leilões"),
    "agregador": ("agregador.json", fontes.agregador, 3000, "Leilão Imóvel"),
}


def agora_ms():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))  # Mato Grosso do Sul (UTC-4)


def hoje_ms():
    return agora_ms().date()


def gravar(nome, dados):
    caminho = os.path.join(BRUTOS, nome)
    tmp = caminho + ".tmp"
    if nome.endswith(".csv"):
        open(tmp, "w", encoding="utf-8").write("\n".join(dados))
    else:
        json.dump(dados, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, caminho)


def garantir_inicial(nome):
    """Na primeira execução não há coleta anterior: usa a semente que vem no repositório."""
    destino = os.path.join(BRUTOS, nome)
    semente = os.path.join(INICIAIS, nome + ".gz")
    if not os.path.exists(destino) and os.path.exists(semente):
        with gzip.open(semente, "rb") as f, open(destino, "wb") as g:
            shutil.copyfileobj(f, g)
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", help="coletar só estas fontes (separadas por vírgula)")
    ap.add_argument("--sem-coleta", action="store_true", help="só remonta o site com os brutos que já existem")
    ap.add_argument("--teste", action="store_true", help="coleta um pedaço pequeno de cada fonte, mostra o resultado e não grava nada")
    a = ap.parse_args()
    os.makedirs(BRUTOS, exist_ok=True)
    os.makedirs(SITE_DADOS, exist_ok=True)
    status = json.load(open(STATUS)) if os.path.exists(STATUS) else {}
    hoje = hoje_ms()
    escolhidas = a.so.split(",") if a.so else list(FONTES)
    if a.teste:
        testes = {"caixa": lambda: fontes.caixa(ufs=["MS", "AC"]), "zuk": lambda: fontes.zuk(limite=60),
                  "mega": lambda: fontes.mega(max_paginas=2), "agregador": lambda: fontes.agregador(tempo_max=90)}
        for chave in escolhidas:
            try:
                d = testes[chave]()
                fontes.log("TESTE", chave, "OK" if d else "VAZIO", len(d), "registros", json.dumps(d[:1], ensure_ascii=False)[:300])
            except Exception as e:
                fontes.log("TESTE", chave, "FALHOU", repr(e)[:300])
        return

    for chave, (arquivo, func, minimo, nome) in FONTES.items():
        st = status.setdefault(chave, {"nome": nome})
        st["nome"] = nome
        if garantir_inicial(arquivo) and "data" not in st:
            st.update(data="2026-10-14", ok=False, msg="usando a coleta inicial de 14/10/2026")
        if a.sem_coleta or chave not in escolhidas:
            continue
        fontes.log("== coletando", nome)
        try:
            dados = func()
            if len(dados) < minimo:
                raise RuntimeError(f"só {len(dados)} registros (mínimo {minimo})")
            gravar(arquivo, dados)
            st.update(data=hoje.isoformat(), ok=True, n=len(dados), msg="")
        except Exception as e:  # mantém a coleta anterior desta fonte
            traceback.print_exc()
            st.update(ok=False, msg=f"falhou hoje ({str(e)[:120]}); usando a coleta de {st.get('data', '?')}")
        json.dump(status, open(STATUS, "w"), ensure_ascii=False, indent=1)

    # normaliza e monta os arquivos do site
    tag = hoje.strftime("%Y%m%d")
    base = os.path.join(tempfile.gettempdir(), "leiloes_base.json")
    subprocess.run([sys.executable, os.path.join(AQUI, "normalizar.py"), BRUTOS, tag, base], check=True)
    destaques = os.path.join(RAIZ, "analise", "destaques.json")
    subprocess.run([sys.executable, os.path.join(AQUI, "montar_painel.py"), base, destaques,
                    os.path.join(SITE_DADOS, "imoveis.js"), hoje.isoformat()], check=True)
    agora = agora_ms().strftime("%Y-%m-%dT%H:%M")
    pub = {"gerado": agora, "fontes": [{k: v for k, v in st.items()} for st in status.values()]}
    open(os.path.join(SITE_DADOS, "status.js"), "w", encoding="utf-8").write(
        "window.STATUS=" + json.dumps(pub, ensure_ascii=False) + ";\n")
    json.dump(status, open(STATUS, "w"), ensure_ascii=False, indent=1)
    fontes.log("pronto:", pub)


if __name__ == "__main__":
    main()
