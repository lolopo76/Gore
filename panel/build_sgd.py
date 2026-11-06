"""Documentos SGD por BIP de la cartera.
Uso: python3 -I build_sgd.py <sgd1.xls[+sgd2.xls+...]> (en orden de fecha) <dir_con_proyectos_json> <salida sgd.json>
Cada documento (Id) que menciona un BIP de la cartera en su nombre, materia o palabras clave queda con su ruta."""
import sys, re, json, glob, os, xlrd

def fecha(v, dm):
    if isinstance(v, float) and v > 0:
        return xlrd.xldate_as_datetime(v, dm).strftime('%Y-%m-%d %H:%M')
    return str(v or '').strip()


def tiempo(t):
    m = re.match(r'(\d+) dias (\d+) horas', t)
    return f"{m.group(1)}d {m.group(2)}h" if m else t


def main():
    srcs, pdir, out = sys.argv[1].split('+'), sys.argv[2], sys.argv[3]
    bips = set()
    for f in glob.glob(os.path.join(pdir, 'proyectos_*.json')):
        bips |= {p['bip'] for p in json.load(open(f))['items']}
    docs = {}
    last = ''
    filas = 0
    cortados = []
    for fi, src in enumerate(srcs):
        wb = xlrd.open_workbook(src)
        s = wb.sheet_by_index(0)
        hi = next(i for i in range(min(s.nrows, 20)) if s.cell_value(i, 0) == 'Id')
        h = s.row_values(hi)
        filas += s.nrows - hi - 1
        if s.nrows >= 65535:
            cortados.append(os.path.basename(src))
        visto = set()
        for r in range(hi + 1, s.nrows):
            x = dict(zip(h, s.row_values(r)))
            idv = x.get('Id')
            if idv in ('', None):
                continue
            idv = str(int(idv)) if isinstance(idv, float) else str(idv).strip()
            txt = ' '.join(str(x.get(k) or '') for k in ('Documento', 'Materia', 'P. Claves'))
            found = sorted({b for b in re.findall(r'(?<!\d)(\d{8})(?!\d)', txt) if b in bips})
            if not found:
                continue
            d = docs.get(idv)
            if d and idv not in visto:
                # el mismo documento en un archivo posterior trae su ubicación más reciente
                d['estado'] = str(x.get('Estado') or '').strip() or d['estado']
                d['ubicacion'] = str(x.get('Ubicación') or '').strip() or d['ubicacion']
            visto.add(idv)
            if not d:
                num = x.get('Número DOC')
                num = str(int(num)) if isinstance(num, float) else str(num or '').strip()
                fd = fecha(x.get('Fecha Documento'), wb.datemode)
                last = max(last, fd)
                d = docs[idv] = {
                    'id': idv, 'bips': found, 'doc': str(x.get('Documento') or '').strip(),
                    'materia': str(x.get('Materia') or '').strip(), 'numero': num,
                    'fecha': fd[:10], 'enviado': fecha(x.get('Fecha Enviado'), wb.datemode)[:10],
                    'estado': str(x.get('Estado') or '').strip(),
                    'ubicacion': str(x.get('Ubicación') or '').strip(),
                    'propietario': str(x.get('Propietario') or '').strip(), 'claves': str(x.get('P. Claves') or '').strip(),
                    'ruta': []}
                m = re.match(r'(MEMO|OFICIO|RESOLUCION(?:_EXENTA)?)_N_(\d+)_F_(\d{8})', d['doc'])
                if m:
                    d['tipoDoc'] = m.group(1).replace('_', ' ').title()
                    d['nDoc'] = m.group(2)
            paso = [str(x.get('Origen') or '').strip(), str(x.get('Destino') or '').strip(), tiempo(str(x.get('Tiempo de Respuesta') or '').strip())]
            if paso not in d['ruta']:
                d['ruta'].append(paso)
    items = {}
    for d in docs.values():
        for b in d['bips']:
            items.setdefault(b, []).append({k: v for k, v in d.items() if k != 'bips'} | ({'otros': [o for o in d['bips'] if o != b]} if len(d['bips']) > 1 else {}))
    for b in items:
        items[b].sort(key=lambda d: d['fecha'], reverse=True)
    json.dump({'archivo': ' + '.join(os.path.basename(x) for x in srcs), 'hasta': last[:10], 'filas': filas, 'cortados': cortados, 'items': items},
              open(out, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'docs': len(docs), 'bips': len(items), 'hasta': last, 'cortados': cortados, 'bytes': os.path.getsize(out)}))

main()
