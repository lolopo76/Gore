import json,os,sys,time,datetime as D,urllib.request,urllib.error
T=os.environ.get('MERCADOPUBLICO_TICKET') or os.environ['MPT']; OUT=sys.argv[1]; start=D.date.fromisoformat(sys.argv[2]); end=D.date.fromisoformat(sys.argv[3])
ORGS=['100728','100090','116219','86548']
os.makedirs(OUT,exist_ok=True); done_f=os.path.join(OUT,'done.txt')
done=set(open(done_f).read().split()) if os.path.exists(done_f) else set()
def get(url):
    for a in range(8):
        try:
            with urllib.request.urlopen(url,timeout=60) as r: d=json.load(r)
            if 'Listado' in d: return d
            print('ERR',d,flush=True); time.sleep(3*(a+1))
        except Exception as e:
            print('EXC',e,flush=True); time.sleep(3*(a+1))
    return None
d=end; n=0
with open(os.path.join(OUT,'lista.jsonl'),'a') as f, open(done_f,'a') as df:
    while d>=start:
        if d.weekday()>=5 and os.environ.get('SKIPWE'): d-=D.timedelta(days=1); continue
        for o in ORGS:
            k=f'{d.isoformat()}_{o}'
            if k in done: continue
            r=get(f'https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={d:%d%m%Y}&CodigoOrganismo={o}&ticket={T}')
            if r is None: print('FAIL',k,flush=True); continue
            time.sleep(0.3)
            for x in r['Listado']: x['_fecha']=d.isoformat(); x['_org']=o; f.write(json.dumps(x,ensure_ascii=False)+'\n')
            f.flush(); df.write(k+'\n'); df.flush(); n+=1
            if n%200==0: print(n,k,flush=True)
        d-=D.timedelta(days=1)
print('FIN',n)
