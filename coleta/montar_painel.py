#!/usr/bin/env python3
"""Junta a base normalizada com a análise dos destaques e gera dados/imoveis.js para o painel.
Uso: python3 montar_painel.py <base.json> <destaques.json> <saida.js> <data YYYY-MM-DD>
"""
import json, sys
base = json.load(open(sys.argv[1])); dest = {d['id']: d for d in json.load(open(sys.argv[2]))}
achados = 0
for r in base:
    a = dest.get(r['id'])
    if not a: continue
    achados += 1
    if a.get('l'): r['l'] = a['l']
    if a.get('dt'): r['dt'] = a['dt']
    if a.get('a') and a.get('aok'): r['a'] = a['a']
    if r.get('a') and r.get('l'): r['m2'] = round(r['l'] / r['a'])
    if r.get('av') and r.get('l'): r['d'] = round((1 - r['l'] / r['av']) * 100, 2)
    r['x'] = {k: a.get(k) for k in ('a', 'aok', 'mn', 'mx', 'fm', 'cf', 'oc', 'fn', 'fd', 'nt', 'ed') if a.get(k) is not None}
for r in base:
    if r.get('f') == 'Caixa':
        r.pop('u', None); r.pop('ft', None)
    for k in ('l', 'av', 'a'):
        if isinstance(r.get(k), float): r[k] = round(r[k], 2)
det = {}
for r in base:
    v = [r.pop('ds', None), r.pop('ps', None), r.pop('at', None), r.pop('vg', None)]
    if any(x is not None for x in v):
        while v and v[-1] is None: v.pop()
        det[r['id']] = v
open(sys.argv[3].replace('imoveis.js', 'detalhes.js'), 'w').write('window.DETALHES=' + json.dumps(det, ensure_ascii=False, separators=(',', ':')) + ';\n')
meta = {'atualizado': sys.argv[4], 'fontes': {'Caixa': 'Caixa (lista oficial)', 'Zuk': 'Portal Zuk', 'Mega': 'Mega Leilões', 'Bancos': 'Bancos (via Leilão Imóvel)', 'Leiloeiras': 'Outras leiloeiras (via Leilão Imóvel)'}, 'd': base}
open(sys.argv[3], 'w').write('window.IMOVEIS=' + json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + ';\n')
print('imóveis', len(base), 'destaques casados', achados, 'de', len(dest))
