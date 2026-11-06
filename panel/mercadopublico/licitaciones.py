"""Vincula licitaciones de Mercado Público con los BIP de la cartera.
Uso: MERCADOPUBLICO_TICKET=... python3 licitaciones.py <proyectos_prev.json> <lista.jsonl> <cache_dir> <salida.json>
lista.jsonl: listado diario por organismo (crawl.py). cache_dir guarda el detalle de cada licitación.
"""
import json,os,re,sys,time,urllib.request,datetime as D
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from match import ORG,nrm,bips_in,build_idf,wsim as sim
T=os.environ.get('MERCADOPUBLICO_TICKET') or os.environ.get('MPT')
proy_f,lista_f,cache,out_f=sys.argv[1:5]; os.makedirs(cache,exist_ok=True)
P=json.load(open(proy_f))['items']
L={}
for l in open(lista_f):
    x=json.loads(l); k=x['CodigoExterno']
    if k not in L or x['_fecha']>L[k]['_fecha']: L[k]=x
build_idf([x['Nombre'] for x in L.values()])
byorg={}
for x in L.values(): byorg.setdefault(x['_org'],[]).append(x)
ESTADOS={5:'Publicada',6:'Cerrada',7:'Desierta',8:'Adjudicada',18:'Revocada',19:'Suspendida'}
def detalle(c):
    f=os.path.join(cache,c+'.json')
    if os.path.exists(f): return json.load(open(f))
    for a in range(8):
        try:
            with urllib.request.urlopen(f'https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?codigo={c}&ticket={T}',timeout=60) as r: d=json.load(r)
            if d.get('Listado'):
                json.dump(d['Listado'][0],open(f,'w'),ensure_ascii=False); time.sleep(0.3); return d['Listado'][0]
            if 'Cantidad' in d: return None
        except Exception as e: print('EXC',c,e,flush=True)
        time.sleep(3*(a+1))
    return None
rutn=lambda r: re.sub(r'[^0-9K]','',str(r or '').upper())
def resumen(d,x):
    adj={}
    for it in (d.get('Items') or {}).get('Listado') or []:
        a=it.get('Adjudicacion') or {}
        if a.get('RutProveedor'):
            k=rutn(a['RutProveedor']); e=adj.setdefault(k,{'rut':a['RutProveedor'],'nombre':a.get('NombreProveedor',''),'monto':0})
            e['monto']+=round((a.get('Cantidad') or 0)*(a.get('MontoUnitario') or 0))
    F=d.get('Fechas') or {}
    return {'codigo':d['CodigoExterno'],'nombre':d.get('Nombre','').strip(),'estado':d.get('Estado') or ESTADOS.get(x.get('CodigoEstado'),''),
        'tipo':d.get('Tipo',''),'publicada':(F.get('FechaPublicacion') or '')[:10],'cierre':(F.get('FechaCierre') or '')[:10],
        'adjudicada':(F.get('FechaAdjudicacion') or (d.get('Adjudicacion') or {}).get('Fecha') or '')[:10],
        'montoEstimado':d.get('MontoEstimado') or 0,'adjudicados':list(adj.values()),'bipFicha':str(d.get('CodigoBIP') or '').strip(),
        'oferentes':(d.get('Adjudicacion') or {}).get('NumeroOferentes'),'urlActa':(d.get('Adjudicacion') or {}).get('UrlActa') or '',
        'url':'https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion='+d['CodigoExterno']}
res={}; nfetch=0
for p in P:
    org=ORG.get(p['comuna']); 
    if not org: continue
    cands=[]
    for x in byorg.get(org,[]):
        s=sim(p['nombre'],x['Nombre']); b=p['bip'] in bips_in(x['Nombre'])
        if b or s>=0.5: cands.append((1.0 if b else s,x))
    cands.sort(key=lambda t:-t[0]); cands=cands[:6]
    out=[]
    for s,x in cands:
        d=detalle(x['CodigoExterno']); nfetch+=1
        if not d: continue
        r=resumen(d,x); motivos=[]; fuerte=False
        bf=re.sub(r'\D','',r['bipFicha'])[:8]
        if bf==p['bip']: motivos.append('la licitación trae el código BIP'); fuerte=True
        elif bf and len(bf)==8: 
            continue  # trae otro BIP: no es este proyecto
        if p['bip'] in bips_in(r['nombre']+' '+(d.get('Descripcion') or '')): motivos.append('el BIP aparece en el nombre o la descripción'); fuerte=True
        re_=rutn(p.get('rutEmpresa')); ruts={rutn(a['rut']) for a in r['adjudicados']}
        rut_ok = bool(re_) and re_ in ruts
        if rut_ok: motivos.append('el RUT adjudicado es el de la empresa de la planilla')
        tot=sum(a['monto'] for a in r['adjudicados'])
        c=p.get('contratado') or 0
        monto_ok = c>0 and tot>0 and min(abs(tot-c)/c, abs(tot*1.19-c)/c)<=0.02
        if monto_ok: motivos.append('el monto adjudicado calza con lo contratado' + ('' if abs(tot-c)/c<=0.02 else ' (con IVA)'))
        ns=sim(p['nombre'],r['nombre'])
        if ns>=0.85: motivos.append('el nombre coincide')
        elif ns>=0.5: motivos.append('el nombre se parece')
        conf = fuerte or (rut_ok and (monto_ok or ns>=0.65)) or (monto_ok and ns>=0.6) or ns>=0.85
        if not conf and ((ns<0.6 and not rut_ok and not monto_ok) or re.search(r'-L1\d\d$',r['codigo'])): continue
        r.update({'confirmada':bool(conf),'motivo':'; '.join(motivos),'montoAdjudicado':tot,'similitud':round(ns,2)})
        out.append(r)
    if out:
        out.sort(key=lambda r:(r['adjudicada'] or r['publicada'] or ''), reverse=True)
        out.sort(key=lambda r:not r['confirmada'])
        res[p['bip']]=out
best={}
for b,v in res.items():
    for r in v:
        if r['confirmada']: best[r['codigo']]=max(best.get(r['codigo'],0),r['similitud'])
for b,v in res.items():
    for r in v:
        if r['confirmada'] and 'BIP' not in r['motivo'] and r['similitud']<best[r['codigo']]:
            r['confirmada']=False; r['motivo']+='; también calza con otro proyecto de nombre más parecido'
conf_de={}
for b,v in res.items():
    for r in v:
        if r['confirmada']: conf_de.setdefault(r['codigo'],set()).add(b)
for b in list(res):
    res[b]=[r for r in res[b] if r['confirmada'] or not (conf_de.get(r['codigo'],set())-{b})]
    if not res[b]: del res[b]
json.dump({'actualizado':D.date.today().isoformat(),'items':res},open(out_f,'w'),ensure_ascii=False)
print('proyectos con licitación',len(res),'confirmadas',sum(any(r['confirmada'] for r in v) for v in res.values()),'detalles',nfetch)
