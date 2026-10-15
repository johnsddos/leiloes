#!/usr/bin/env python3
"""Normaliza as coletas brutas (Caixa, Zuk, Mega, LeilaoImovel/bancos) num único JSON compacto.
Uso: python3 normalizar.py <pasta_brutos> <data YYYYMMDD> <saida.json>
"""
import json, re, sys, unicodedata, datetime, os, csv, io

BR = sys.argv[1]; TAG = sys.argv[2]; OUT = sys.argv[3]
HOJE = datetime.date(int(TAG[:4]), int(TAG[4:6]), int(TAG[6:]))
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())

def num(s):
    if s is None: return None
    s = re.sub(r'[^\d,.\-]', '', str(s))
    if not s: return None
    if ',' in s: s = s.replace('.', '').replace(',', '.')
    try: return float(s)
    except: return None

def strip(s): return unicodedata.normalize('NFKD', s or '').encode('ascii','ignore').decode().lower()
def titulo(s):
    s = re.sub(r'\s+', ' ', (s or '').strip())
    if s.isupper() or s.islower():
        s = ' '.join(w.capitalize() if len(w) > 2 or i == 0 else w.lower() for i, w in enumerate(s.lower().split()))
    return s

def dt(s):
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', s or '')
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None

def tipo_norm(s):
    t = strip(s)
    if re.search(r'apart|apto|flat|cobertura|kitnet|studio', t): return 'Apartamento'
    if re.search(r'rural|fazenda|sitio|chacara|gleba|area rural|ha\b', t): return 'Rural'
    if re.search(r'galp|industr|armaz', t): return 'Galpão/Industrial'
    if re.search(r'garagem|vaga|box', t): return 'Vaga de garagem'
    if re.search(r'terreno|lote|area\b|incorpora', t): return 'Terreno'
    if re.search(r'loja|sala|comerc|predio|escritorio|agencia|hotel|posto|consultorio|ponto', t): return 'Comercial'
    if re.search(r'casa|sobrado|residenc|geminad', t): return 'Casa'
    return 'Outros'

def area_de(txt):
    m = re.search(r'([\d.]+,\d+|\d[\d.]*)\s*m²', txt or '')
    return num(m.group(1)) if m else None

out = []

# ---------- Caixa ----------
fc = [f for f in os.listdir(BR) if f.startswith('caixa_completa')]
if fc:
    for line in open(os.path.join(BR, fc[0]), encoding='utf-8'):
        p = [x.strip() for x in line.split(';')]
        if len(p) < 12: continue
        idn, uf, cid, bai, end, preco, aval, desc, fin, descr, mod, link = p[:12]
        tipo_txt = descr.split(',')[0]
        priv = re.search(r'([\d.]+) de área privativa', descr); ter = re.search(r'([\d.]+) de área do terreno', descr)
        a_priv = float(priv.group(1)) if priv else 0; a_ter = float(ter.group(1)) if ter else 0
        tp = tipo_norm(tipo_txt)
        area = a_priv if a_priv > 0 else (a_ter if a_ter > 0 else None)
        q = re.search(r'(\d+) qto', descr)
        modn = {'Venda Direta Online': 'Venda direta', 'Venda Online': 'Venda online', 'Licitação Aberta': 'Licitação', 'Leilão SFI - Edital Único': 'Leilão'}.get(mod, mod)
        out.append(dict(f='Caixa', c='Caixa', uf=uf, cid=titulo(cid), bai=titulo(bai), end=titulo(end), t=tp, tx=tipo_txt,
            m=modn, l=num(preco), av=num(aval), d=num(desc), a=area, q=int(q.group(1)) if q else None,
            fin=fin.lower().startswith('sim'), dt=None, pr=None, oc=None,
            u=link, ft=f'https://venda-imoveis.caixa.gov.br/fotos/F{idn}21.jpg', id='cx'+idn,
            at=a_ter or None, ds=(re.split(r'área do terreno,?', descr)[-1].strip(' .,') if 'área do terreno' in descr else None),
            vg=(int(re.search(r'(\d+) vaga', descr).group(1)) if re.search(r'(\d+) vaga', descr) else None)))

# ---------- Zuk ----------
fz = sorted([f for f in os.listdir(BR) if f.startswith('zuk') and f.endswith('.json')])
if fz:
    for x in json.load(open(os.path.join(BR, fz[-1]))):
        loc = x.get('loc') or ''
        m = re.match(r'(.+?)\s*/\s*([A-Z]{2})\s*-?\s*(.*)', loc)
        if not m: continue
        cid, uf, bai = m.group(1), m.group(2), m.group(3)
        prs = []
        for p in x.get('pr', []):
            v = num(p.get('val')); d = dt(p.get('data'))
            if v: prs.append(dict(lab=p.get('lab'), v=v, d=d, pct=num(p.get('pct'))))
        if not prs: continue
        fut = [p for p in prs if p['d'] and p['d'] >= HOJE.isoformat()]
        cur = fut[0] if fut else prs[-1]
        aval = None
        if cur.get('pct') and cur['pct'] < 100: aval = round(cur['v'] / (1 - cur['pct'] / 100), 2)
        elif len(prs) == 2: aval = prs[0]['v']
        desc = round((1 - cur['v'] / aval) * 100, 2) if aval else None
        ar = None
        for i in x.get('infos', []):
            if 'm²' in i and ('constru' in i or 'privat' in i or 'útil' in i): ar = area_de(i); break
        if ar is None:
            for i in x.get('infos', []):
                if 'm²' in i: ar = area_de(i); break
        comit = re.sub(r'\s*\|\s*Z\d+.*$', '', x.get('comit') or '').strip()
        lab = (prs[0].get('lab') or '').lower()
        modn = 'Leilão' if 'leil' in lab else ('Venda direta' if 'valor' in lab else 'Leilão')
        if re.search(r'tribunal|judici', strip(comit)): modn = 'Judicial'
        out.append(dict(f='Zuk', c=comit, uf=uf, cid=titulo(cid), bai=titulo(bai), end=x.get('end'), t=tipo_norm(x.get('tipo')), tx=x.get('tipo'),
            m=modn, l=cur['v'], av=aval, d=desc, a=ar, q=None, fin=None, dt=cur['d'], pr=('2ª' if prs.index(cur) == 1 else ('1ª' if len(prs) == 2 else 'Única')),
            oc=('Desocupado' if x.get('tag') == 'Desocupado' else None), u=x['url'], ft=x.get('foto'), id='zk'+x['url'].rsplit('-', 1)[-1],
            ps=[[q.get('lab') or '', q['d'], q['v']] for q in prs], ds=(' · '.join(i for i in x.get('infos', []) if not i.isdigit()) or None)))

# ---------- Mega ----------
fm = sorted([f for f in os.listdir(BR) if f.startswith('mega')])
BANCOS_MEGA = {'santander': 'Santander', 'itau': 'Itaú', 'bradesco': 'Bradesco', 'sicoob': 'Sicoob'}
if fm:
    for x in json.load(open(os.path.join(BR, fm[-1]))):
        m = re.match(r'(.+?),\s*([A-Z]{2})$', x.get('loc') or '')
        if not m: continue
        cid, uf = m.group(1), m.group(2)
        partes = [p.strip() for p in (x.get('tit') or '').split(' - ')]
        bai = partes[-3] if len(partes) >= 4 else ''
        prs = []
        for i in x.get('inst_list', []):
            v = num(i.get('v')); d = dt(i.get('d'))
            if v: prs.append(dict(v=v, d=d, passed='passed' in (i.get('cls') or '')))
        if not prs: continue
        fut = [p for p in prs if not p['passed'] and (p['d'] or '9') >= HOJE.isoformat()]
        cur = fut[0] if fut else prs[-1]
        aval = prs[0]['v'] if len(prs) == 2 else None
        desc = round((1 - cur['v'] / aval) * 100, 2) if aval and aval > cur['v'] else (0 if aval else None)
        seg = x['url'].split('/')[4]
        b = x.get('banco') or ''
        comit = next((v for k, v in BANCOS_MEGA.items() if k in b), 'Mega Leilões (outros)')
        if x.get('inst') == 'Judicial' or comit.startswith('Mega'): comit = 'Mega Leilões'
        out.append(dict(f='Mega', c=comit, uf=uf, cid=titulo(cid), bai=bai, end=None, t=tipo_norm(seg + ' ' + partes[0]), tx=partes[0],
            m=x.get('inst') or 'Leilão', l=cur['v'], av=aval, d=desc, a=area_de(partes[0]), q=None, fin=None, dt=cur['d'],
            pr=('2ª' if len(prs) == 2 and prs.index(cur) == 1 else ('1ª' if len(prs) == 2 else 'Única')),
            oc=None, u=x['url'], ft=x.get('foto'), id='mg'+(x.get('cod') or x['url'][-8:]), dir=('direitos' in strip(x.get('tit'))),
            ps=[[('%dª praça' % (k + 1)) if len(prs) > 1 else 'Praça única', q['d'], q['v']] for k, q in enumerate(prs)], ds=x.get('tit')))

# ---------- LeilaoImovel (bancos) ----------
fl = sorted([f for f in os.listdir(BR) if f.startswith(('bancos', 'agregador')) and f.endswith('.json')])
NB = {'santander': 'Santander', 'itau-unibanco': 'Itaú', 'bradesco': 'Bradesco', 'banco-do-brasil': 'Banco do Brasil', 'banco-brb': 'BRB',
      'judicial': 'Judicial', 'extrajudicial': 'Extrajudicial', 'venda-direta': 'Venda direta', 'btg-pactual': 'BTG Pactual', 'banco-inter': 'Banco Inter', 'sicoob': 'Sicoob', 'emgea': 'Emgea', 'banco-bv': 'Banco BV', 'porto-bank': 'Porto Bank', 'reverts': 'Reverts'}
BCOD = {'2': 'banco-do-brasil', '4': 'banco-brb', '21': 'banco-bv', '3': 'banco-inter', '6': 'santander', '38': 'bradesco', '8': 'emgea', '19': 'itau-unibanco', '55': 'porto-bank', '53': 'reverts', '54': 'sicoob'}
VCOD = {'3': 'Judicial', '4': 'Extrajudicial', '5': 'Leilão', '8': 'Venda direta', '12': 'PGFN'}
li_items = {}
for arq in fl:
    for x in json.load(open(os.path.join(BR, arq))):
        if not x.get('url'): continue
        if 'venda' in x or (x.get('bank') or '').isdigit():   # formato novo (agregador por filtros)
            b = x.get('bank'); x['bank'] = BCOD.get(b) if b else None; x['_venda'] = VCOD.get(x.get('venda'))
        o = li_items.get(x['url'])
        if o:
            if x.get('bank') and not o.get('bank'): o['bank'] = x['bank']
            if x.get('_venda') and not o.get('_venda'): o['_venda'] = x['_venda']
        else: li_items[x['url']] = x
if True:
    for x in li_items.values():
        m = re.search(r'(?:Leil[aã]o|Venda|Direta|Judicial|Extrajudicial)\s+(?:em|no|na|nos|nas)\s+(.+?) / ([A-Z]{2}) - (\d+)$', x.get('tit') or '') or re.search(r'.* em (.+?) / ([A-Z]{2}) - (\d+)$', x.get('tit') or '')
        if not m: continue
        cid, uf, idn = m.group(1), m.group(2), m.group(3)
        tp_txt = re.split(r'\s+(?:em|no|na)\s+', (x.get('tit') or ''))[0]; tp_txt = re.sub(r'\s+(Banco .*|Emgea|Santander|Ita[uú].*|Bradesco|Sicoob|Porto.*|Reverts|BRB|BV|Caixa.*)$', '', tp_txt).strip()
        prs = []
        for s in x.get('pr', []):
            v = num(s.split('R$')[-1]) if 'R$' in s else None; d = dt(s)
            if v: prs.append(dict(v=v, d=d))
        preco = num(x.get('preco'))
        fut = [p for p in prs if p['d'] and p['d'] >= HOJE.isoformat()]
        cur = fut[0] if fut else (prs[-1] if prs else dict(v=preco, d=dt(x.get('enc'))))
        if not cur['v']: continue
        desc = num(x.get('desc'))
        aval = prs[0]['v'] if len(prs) == 2 else (round(preco / (1 - desc / 100), 2) if desc and preco and desc < 100 else None)
        if aval and cur['v']: desc = round((1 - cur['v'] / aval) * 100, 2) if aval > cur['v'] else 0
        alt = x.get('alt') or ''
        bai = ''
        mm = re.search(r" - ([^-]+?) - [^-]+? / [A-Z]{2}$", alt.replace('Imóvel ' + idn + '- ', ''))
        if mm: bai = mm.group(1).strip()
        cat = x.get('cat') or ''
        modn = x.get('_venda') or ('Judicial' if 'Judicial' in cat else ('Venda direta' if 'Venda Direta' in cat else ('Extrajudicial' if 'Extrajudicial' in cat else 'Leilão')))
        url = x['url'] if x['url'].startswith('http') else 'https://www.leilaoimovel.com.br' + x['url']
        foto = x.get('foto') or ''
        leiloeiro = None
        mb = re.search(r'leiloeiro-parceiro/([^/]+)/', foto)
        if mb:
            leiloeiro = ' '.join(w.capitalize() for w in re.sub(r'(?<=[a-z])leiloes$', ' leiloes', mb.group(1)).replace('_', ' ').split()).replace('Frazao', 'Frazão').replace('Leiloeiro Publico', 'Leiloeiro Público').replace('Leiloes', 'Leilões').replace('Leilao', 'Leilão')
            foto = None
        out.append(dict(f=('Bancos' if x.get('bank') in NB and x.get('bank') not in ('judicial','extrajudicial','venda-direta') else 'Leiloeiras'), c=(NB.get(x.get('bank')) if x.get('bank') in NB and x.get('bank') not in ('judicial','extrajudicial','venda-direta') else ('PGFN' if modn == 'PGFN' else (leiloeiro or 'Leiloeira não identificada'))), uf=uf, cid=titulo(cid), bai=bai, end=(x.get('end') or '').split(' - ')[0],
            t=tipo_norm(tp_txt + ' ' + x['url']), tx=tp_txt, m=modn, l=cur['v'], av=aval, d=desc, a=(float(re.search(r'[a-z]-(\d{2,4})-m-', x['url']).group(1)) if re.search(r'[a-z]-(\d{2,4})-m-', x['url']) else None), q=None, fin=None, dt=cur['d'],
            pr=('2ª' if len(prs) == 2 and prs.index(cur) == 1 else ('1ª' if len(prs) == 2 else 'Única')), oc=None, u=url, ft=foto, id='li'+idn,
            ps=[[('%dª praça' % (k + 1)) if len(prs) > 1 else 'Praça única', q['d'], q['v']] for k, q in enumerate(prs)] or None, ds=(x.get('end') or None)))

# ---------- limpeza e deduplicação ----------
limpo = []
for r in out:
    if r['uf'] not in UFS or not r['l'] or r['l'] < 5000: continue
    if r.get('av') and r['av'] < 1000: r['av'] = None; r['d'] = None
    if r['dt'] and r['dt'] < HOJE.isoformat(): continue          # leilão já encerrado
    if r['d'] is not None and (r['d'] < 0 or r['d'] > 99): r['d'] = None
    limpo.append(r)
ordem = {'Caixa': 0, 'Zuk': 1, 'Mega': 2, 'Bancos': 3, 'Leiloeiras': 4}
limpo.sort(key=lambda r: ordem[r['f']])
def chave_end(e):
    e = strip(e or '')
    m = re.search(r'\d+', e)
    if not m: return None
    w = [x for x in re.findall(r'[a-z]{3,}', e.split(m.group(0))[0]) if x not in ('rua', 'avenida', 'travessa', 'alameda', 'estrada', 'rodovia', 'praca', 'dos', 'das', 'del')]
    return ' '.join(w[:3]) + '#' + m.group(0) if w else None

vistos = {}; final = []; dup = 0
for r in limpo:
    k = (r['uf'], strip(r['cid']))
    lst = vistos.setdefault(k, [])
    ce = chave_end(r.get('end'))
    eh_dup = False
    for o in lst:
        if o['f'] == r['f']: continue
        if ce and ce == o.get('_ce') and o['t'] == r['t']: eh_dup = True; break
        if r['f'] != 'Caixa' and o['f'] != 'Caixa' and o['t'] == r['t'] and abs(o['l'] - r['l']) <= 0.001 * r['l']: eh_dup = True; break
    if eh_dup: dup += 1; continue
    r['_ce'] = ce; lst.append(r); final.append(r)
for r in final: r.pop('_ce', None)
CURTO = [('santander', 'Santander'), ('itau', 'Itaú'), ('bradesco', 'Bradesco'), ('banco inter', 'Banco Inter'), ('sicoob', 'Sicoob'),
         ('bb administradora', 'Banco do Brasil'), ('banco do brasil', 'Banco do Brasil'), ('c6 bank', 'C6 Bank'), ('creditas', 'Creditas'),
         ('tribunal de justica', 'Judicial (TJ)'), ('poder judiciario', 'Judicial (TJ)')]
for r in final:
    sc = strip(r.get('c'))
    for k, v in CURTO:
        if k in sc: r['c'] = v; break
# grafia canônica da cidade e do bairro
from collections import Counter as _C
PART = {'de', 'da', 'do', 'das', 'dos', 'e', 'del'}
def fix(s): return ' '.join(w.lower() if w.lower() in PART and i else w for i, w in enumerate((s or '').split()))
grafia = {}
for r in final:
    r['cid'] = fix(r['cid']); r['bai'] = fix(r.get('bai'))
    grafia.setdefault((r['uf'], strip(r['cid'])), _C())[r['cid']] += 1
def _melhor(c):
    # prefere a grafia com acentos (a da Caixa vem sem); depois a mais comum
    return max(c.items(), key=lambda kv: (sum(1 for ch in kv[0] if ord(ch) > 127), kv[0] != kv[0].upper(), kv[1]))[0]
for r in final: r['cid'] = _melhor(grafia[(r['uf'], strip(r['cid']))])
for r in final:
    if r.get('a') and r['l']: r['m2'] = round(r['l'] / r['a'])
    for k in [k for k, v in list(r.items()) if v in (None, '', False)]: del r[k]
json.dump(final, open(OUT, 'w'), ensure_ascii=False, separators=(',', ':'))
from collections import Counter
print('total', len(final), 'duplicados removidos', dup)
print(Counter(r['f'] for r in final)); print(Counter(r['t'] for r in final)); print(Counter(r['m'] for r in final))
print('UFs', len(Counter(r['uf'] for r in final)), 'cidades', len({(r['uf'], r['cid']) for r in final}))
