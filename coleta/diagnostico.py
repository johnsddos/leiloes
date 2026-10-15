import requests
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "pt-BR,pt;q=0.9"}
for u in ["https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp", "https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_MS.csv", "https://www.leilaoimovel.com.br/leilao-de-imoveis/ms"]:
    try:
        r = requests.get(u, headers=H, timeout=40)
        print(u, r.status_code, len(r.content), dict((k, v) for k, v in r.headers.items() if k.lower() in ("server", "content-type", "cf-ray", "set-cookie"))[:0] if False else {k: v for k, v in r.headers.items() if k.lower() in ("server", "content-type", "cf-mitigated")})
        print("   ", r.content[:300])
    except Exception as e:
        print(u, "ERRO", e)
