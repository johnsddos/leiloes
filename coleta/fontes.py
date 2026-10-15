"""Coletores de cada fonte de imóveis.

Cada função devolve a lista de registros no MESMO formato que normalizar.py espera
(o formato das coletas feitas antes pelo navegador). Nada aqui grava arquivo.
"""
import math
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sessao(base):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9", "Referer": base})
    return s


def pegar(s, url, metodo="GET", tentativas=6, espera_429=30, **kw):
    """GET/POST com novas tentativas em 429/5xx/erro de rede."""
    for k in range(tentativas):
        try:
            r = s.request(metodo, url, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503, 502, 504, 520, 522):
                time.sleep(espera_429 * (k + 1))
                continue
            log("HTTP", r.status_code, url)
            return None
        except requests.RequestException as e:
            log("erro de rede", url, e.__class__.__name__)
            time.sleep(5 * (k + 1))
    return None


def txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el is not None else ""


# ---------------------------------------------------------------- Caixa
def caixa(ufs=None):
    """Lista oficial: um CSV por UF (ISO-8859-1, separado por ;). Devolve as linhas de dados."""
    base = "https://venda-imoveis.caixa.gov.br"
    s = sessao(base + "/sistema/download-lista.asp")
    pegar(s, base + "/sistema/download-lista.asp", tentativas=2)
    linhas, por_uf = [], {}
    for uf in (ufs or UFS):
        n = 0
        for _ in range(3):
            r = pegar(s, f"{base}/listaweb/Lista_imoveis_{uf}.csv", tentativas=3, espera_429=10)
            if r is None:
                continue
            t = r.content.decode("iso-8859-1")
            ls = [l.strip() for l in t.split("\n") if re.match(r"^\s*\d{6,}", l)]
            if ls:
                linhas += ls
                n = len(ls)
                break
            time.sleep(3)
        por_uf[uf] = n
        time.sleep(1)
    log("Caixa por UF:", por_uf)
    return linhas


# ---------------------------------------------------------------- Zuk
def _zuk_card(c):
    a = c.select_one(".card-property-image-wrapper a")
    title = a.get("title", "") if a else ""
    addr = c.select(".card-property-address span")
    pr = []
    for li in c.select("li.card-property-price"):
        v = li.select_one(".card-property-price-value")
        if v is None:
            continue
        p = v.select_one(".card-property-price-percent")
        pct = txt(p) if p else None
        if p is not None:
            p.extract()
        vt = v.get_text(" ", strip=True)
        pr.append({"lab": txt(li.select_one(".card-property-price-label")), "val": re.sub(r"\s+", " ", vt).strip(),
                   "pct": pct, "data": txt(li.select_one(".card-property-price-data"))})
    img = c.select_one("img")
    return {"url": a.get("href") if a else None, "foto": img.get("src") if img else None,
            "tipo": txt(c.select_one(".card-property-price-lote")),
            "loc": txt(addr[0]) if addr else "", "end": txt(addr[1]) if len(addr) > 1 else "",
            "infos": [txt(x) for x in c.select(".card-property-info-label")],
            "tag": txt(c.select_one(".card-property-news")),
            "comit": (title.split(" - ")[-1] if title else "").strip(), "title": title, "pr": pr}


def zuk_parse(html):
    soup = BeautifulSoup(html, "lxml")
    return [_zuk_card(c) for c in soup.select("div.card-property.card_lotes_div")]


def zuk(limite=1500):
    base = "https://www.portalzuk.com.br"
    s = sessao(base + "/leilao-de-imoveis")
    r = pegar(s, base + "/leilao-de-imoveis")
    if r is None:
        raise RuntimeError("Zuk: página inicial não abriu")
    m = re.search(r'name="_token" value="([^"]+)"', r.text) or re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("Zuk: token não encontrado")
    tok = m.group(1)
    vistos, out = set(), []
    for c in zuk_parse(r.text):
        if c["url"] and c["url"] not in vistos:
            vistos.add(c["url"]); out.append(c)
    off = 0
    while off < limite:
        time.sleep(2.5)
        dados = {"limit": off, "count_imovel_zuk": off, "path": base + "/leilao-de-imoveis", "order": "data_leilao",
                 "div_parceiro_count": 0, "_token": tok}
        r = pegar(s, base + "/leilao-de-imoveis/mais", "POST", data=dados,
                  headers={"X-Requested-With": "XMLHttpRequest"}, espera_429=25)
        if r is None:
            break
        cards = zuk_parse(r.text)
        if not cards and off > 0:
            break
        for c in cards:
            if c["url"] and c["url"] not in vistos:
                vistos.add(c["url"]); out.append(c)
        off += 30
    log("Zuk:", len(out))
    return out


# ---------------------------------------------------------------- Mega Leilões
def mega_parse(html):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for c in soup.select(".card"):
        a = c.select_one("a.card-title")
        if a is None:
            continue
        img = c.select_one(".card-bank img")
        out.append({
            "url": a.get("href", "").split("?")[0], "foto": (c.select_one(".card-image").get("data-bg", "") if c.select_one(".card-image") else ""),
            "tit": txt(a), "cod": txt(c.select_one(".card-number")), "loc": txt(c.select_one(".card-locality")),
            "preco": txt(c.select_one(".card-price")), "inst": txt(c.select_one(".card-instance-title a")),
            "lote": txt(c.select_one(".card-batch-number")), "pracas": txt(c.select_one(".card-instances")),
            "status": txt(c.select_one(".card-status")),
            "inst_list": [{"cls": " ".join(i.get("class", [])), "d": txt(i.select_one("[class*=date]")),
                           "v": txt(i.select_one(".card-instance-value"))} for i in c.select(".card-instance-info .instance")],
            "banco": img.get("src") if img else None})
    return out


def mega(max_paginas=60):
    base = "https://www.megaleiloes.com.br"
    s = sessao(base + "/imoveis")
    vistos, out = set(), []
    for p in range(1, max_paginas + 1):
        time.sleep(1.5)
        r = pegar(s, f"{base}/imoveis?pagina={p}")
        if r is None:
            break
        novos = 0
        for c in mega_parse(r.text):
            if c["url"] and c["url"] not in vistos:
                vistos.add(c["url"]); out.append(c); novos += 1
        if not novos:
            break
    log("Mega:", len(out))
    return out


# ---------------------------------------------------------------- Leilão Imóvel (bancos e leiloeiras)
LI_BASE = "https://www.leilaoimovel.com.br"
LI_VENDAS = ["3", "4", "5", "8", "12"]  # judicial, extrajudicial, outro, venda direta, PGFN
LI_BANCOS = ["2", "4", "21", "3", "6", "38", "8", "19", "55", "53", "54"]  # todos menos Caixa (1)
LI_TIPOS = ["22", "2", "16", "5", "1", "6", "20", "13", "0", "11", "3"]


def li_parse(html, q):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for c in soup.select(".place-box"):
        a = c.select_one("a.Link_Redirecter")
        img = c.select_one("img")
        out.append({"bank": q.get("banco"), "venda": q.get("venda"), "url": a.get("href") if a else None,
                    "foto": img.get("src") if img else None, "enc": txt(c.select_one(".tag span")),
                    "cat": "|".join(txt(x) for x in c.select(".categories a")), "preco": txt(c.select_one(".discount-price")),
                    "desc": txt(c.select_one(".down b")), "tit": txt(c.select_one(".address p b")),
                    "end": txt(c.select_one(".address p span")), "alt": img.get("title", "") if img else "",
                    "pr": [t for t in (txt(s) for s in c.select(".infos span")) if t]})
    return out


def li_total(html):
    m = re.search(r"([\d.]+)\s+Im[oó]veis Encontrados", BeautifulSoup(html, "lxml").get_text(" "), re.I)
    return int(m.group(1).replace(".", "")) if m else 0


def _li_url(q, p=1):
    prm = [(k, q[k]) for k in ("venda", "banco", "tipo") if q.get(k)]
    if p > 1:
        prm.append(("pag", str(p)))
    return LI_BASE + "/leilao-de-imoveis" + ("/" + q["uf"] if q.get("uf") else "") + "?" + "&".join(f"{k}={v}" for k, v in prm)


def agregador(trabalhadores=3, tempo_max=80 * 60):
    s = sessao(LI_BASE + "/")
    pegar(s, LI_BASE + "/", tentativas=2)
    itens, trava = [], threading.Lock()
    fila = [("plan", {"venda": v}, 1) for v in LI_VENDAS] + [("plan", {"banco": b}, 1) for b in LI_BANCOS]
    inicio = time.time()
    falhas = [0]

    def tarefa(job):
        tipo, q, p = job
        time.sleep(1.0)
        r = pegar(s, _li_url(q, p), espera_429=20)
        if r is None:
            with trava:
                falhas[0] += 1
            return []
        novos = []
        if tipo == "plan":
            n = li_total(r.text)
            if n > 980:
                if not q.get("tipo"):
                    return [("plan", dict(q, tipo=t), 1) for t in LI_TIPOS]
                if not q.get("uf"):
                    return [("plan", dict(q, uf=u.lower()), 1) for u in UFS]
            if not n:
                return []
            novos = [("page", q, pg) for pg in range(2, min(50, math.ceil(n / 20) + 1) + 1)]
        with trava:
            itens.extend(li_parse(r.text, q))
        return novos

    with ThreadPoolExecutor(trabalhadores) as ex:
        while fila and time.time() - inicio < tempo_max:
            lote, fila = fila[:trabalhadores * 4], fila[trabalhadores * 4:]
            for novos in ex.map(tarefa, lote):
                fila.extend(novos)
    if fila:
        log("Leilão Imóvel: tempo esgotado com", len(fila), "páginas na fila")
    log("Leilão Imóvel:", len(itens), "cards,", len({i["url"] for i in itens}), "únicos, falhas", falhas[0])
    return itens
