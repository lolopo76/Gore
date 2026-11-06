import json,re,sys,unicodedata,os
ORG={'Paine':'100728','Buin':'100090','Calera de Tango':'116219','San Bernardo':'86548'}
STOP=set('DE LA EL LOS LAS DEL Y EN A AL PARA POR CON SU SUS COMUNA SECTOR CALLE CALLES N NO NUMERO CODIGO BIP ETAPA PROYECTO OBRAS OBRA CONSTRUCCION MEJORAMIENTO REPOSICION ADQUISICION CONSERVACION AMPLIACION HABILITACION REPARACION INSTALACION SERVICIO SERVICIOS DISENO EJECUCION LICITACION PUBLICA I II III MUNICIPAL MUNICIPALIDAD PAINE BUIN SAN BERNARDO CALERA TANGO UN UNA E O'.split())
def nrm(s):
    s=unicodedata.normalize('NFD',str(s or '').upper()); s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return re.sub(r'[^A-Z0-9 ]',' ',s)
def toks(s): return {t for t in nrm(s).split() if t not in STOP and len(t)>2 and not t.isdigit()}
def sim(pn,ln):
    a,b=toks(pn),toks(ln)
    if not a or not b: return 0.0
    i=len(a&b); return i/len(a)*0.6 + i/len(b)*0.4
def bips_in(s): return set(re.findall(r'\b(\d{8})\b', nrm(s).replace(' - ','-')))

import math
IDF={}
def build_idf(names):
    N=len(names); df={}
    for n in names:
        for t in toks(n): df[t]=df.get(t,0)+1
    IDF.clear(); IDF.update({t:math.log((N+1)/(c+0.5)) for t,c in df.items()})
    IDF['_max']=math.log((N+1)/0.5)
def wsim(pn,ln):
    a,b=toks(pn),toks(ln)
    if not a or not b: return 0.0
    w=lambda S: sum(IDF.get(t,IDF.get('_max',5)) for t in S)
    i=w(a&b); return i/w(a)*0.6 + i/w(b)*0.4
