"""Libro de movimientos: registro permanente de transferencias, rendiciones y pagos.

Uso: python3 -I -W ignore ledger.py <data_dir> <estado_dir> [xlsx_salida] [gestion_dir]

<data_dir>    salida de build_data.py de esta carga (proyectos_*.json, movimientos.json, meta.json).
<estado_dir>  estado permanente (libro.json, historial.json, cargas.json, proyectos_prev.json).
              Se lee el estado anterior, se actualiza y se vuelve a escribir. Además deja en
              <data_dir> los documentos para el panel: libro.json, historial.json, cargas.json,
              cuadratura.json.
[xlsx_salida] planilla Excel del libro (opcional).
[gestion_dir] lectura de la colección gestion (comentarios propios) para incluirlos en el Excel.

Reglas:
- Un movimiento nunca se borra. Si deja de venir en los archivos queda con enArchivo=false.
- Se empareja primero por id y, si no, por BIP + tipo + monto (+ memo si ambos lo tienen),
  para no duplicar un movimiento que pasó de SAGIR al reporte DAF.
- Cada cambio de estado, ubicación, monto o fecha de curse queda en historial con la fecha de carga.
"""
import glob
import json
import os
import sys

SEGUIDOS = ["etapa", "estado", "ubicacion", "carpeta", "monto", "fechaCurso", "fechaPago", "vb", "memo", "reemplazo"]
CAMPOS_PROY = ["situacion", "aprobado", "contratado", "transferido", "rendido", "avance", "inicio", "termino", "duracion", "empresa"]


def load(path, default):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return default


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def clase(tipo):
    t = (tipo or "").lower()
    return "rendicion" if "rendic" in t else "transferencia" if "transf" in t else "pago"


def main():
    data, estado = sys.argv[1], sys.argv[2]
    xlsx = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    gdir = sys.argv[4] if len(sys.argv) > 4 else None
    os.makedirs(estado, exist_ok=True)
    meta = json.load(open(os.path.join(data, "meta.json")))
    carga = meta["cargado"][:10]
    P = [p for f in sorted(glob.glob(os.path.join(data, "proyectos_*.json"))) for p in json.load(open(f))["items"]]
    PB = {p["bip"]: p for p in P}
    M = json.load(open(os.path.join(data, "movimientos.json")))["items"]

    libro = load(os.path.join(estado, "libro.json"), {"items": []})["items"]
    cargas = load(os.path.join(estado, "cargas.json"), {"items": []})["items"]
    hist = load(os.path.join(estado, "historial.json"), {"items": {}})["items"]
    prevP = {p["bip"]: p for p in load(os.path.join(estado, "proyectos_prev.json"), {"items": []})["items"]}
    prev_carga = cargas[-1]["fecha"] if cargas else None
    if prev_carga == carga:  # recarga del mismo día: rehacer sobre el estado anterior a esa carga
        snap = os.path.join(estado, "antes_" + carga)
        libro = load(os.path.join(snap, "libro.json"), {"items": []})["items"]
        hist = load(os.path.join(snap, "historial.json"), {"items": {}})["items"]
        prevP = {p["bip"]: p for p in load(os.path.join(snap, "proyectos_prev.json"), {"items": []})["items"]}
        cargas = cargas[:-1]
        prev_carga = cargas[-1]["fecha"] if cargas else None
    else:
        snap = os.path.join(estado, "antes_" + carga)
        os.makedirs(snap, exist_ok=True)
        for n in ("libro.json", "historial.json", "proyectos_prev.json"):
            src = os.path.join(estado, n)
            if os.path.exists(src):
                dump(os.path.join(snap, n), json.load(open(src)))

    by_id = {e["id"]: e for e in libro}
    matched = set()
    nuevos, cambiados = [], []

    def find(m):
        if m["id"] in by_id and m["id"] not in matched:
            return by_id[m["id"]]
        for e in libro:
            if e["id"] in matched or e["bip"] != m["bip"] or clase(e["tipo"]) != clase(m["tipo"]) or e["monto"] != m["monto"]:
                continue
            if e.get("memo") and m.get("memo") and e["memo"] != m["memo"]:
                continue
            return e
        return None

    for m in M:
        p = PB.get(m["bip"], {})
        e = find(m)
        if e is None:
            e = dict(m)
            e.update(ut=p.get("unidadTecnica", ""), comuna=p.get("comuna", ""), fam="33" if p.get("sub") == "33" else "pagos",
                     primeraCarga=carga, ultimaCarga=carga, enArchivo=True,
                     historial=[{"carga": carga, "evento": "Primera vez en archivos" if prev_carga else "Carga inicial"}])
            libro.append(e)
            by_id[e["id"]] = e
            nuevos.append(e["id"])
        else:
            cambios = {k: [e.get(k), m.get(k)] for k in SEGUIDOS if (e.get(k) or None) != (m.get(k) or None)}
            if not e.get("enArchivo", True):
                cambios["enArchivo"] = [False, True]
            keep = {k: e[k] for k in ("id", "primeraCarga", "historial", "ut", "comuna", "fam")}
            e.clear()
            e.update(m)
            e.update(keep)
            e.update(ultimaCarga=carga, enArchivo=True)
            if p:
                e.update(ut=p.get("unidadTecnica", e["ut"]), comuna=p.get("comuna", e["comuna"]))
            if cambios:
                e["historial"].append({"carga": carga, "cambios": cambios})
                cambiados.append(e["id"])
        matched.add(e["id"])

    desaparecidos = []
    for e in libro:
        if e["id"] not in matched and e.get("enArchivo", True):
            e["enArchivo"] = False
            e["historial"].append({"carga": carga, "evento": "Ya no viene en los archivos"})
            desaparecidos.append(e["id"])

    # historial de la planilla de proyectos
    camb_proy = 0
    for b, p in PB.items():
        q = prevP.get(b)
        if q is None:
            if prevP:
                hist.setdefault(b, []).append({"carga": carga, "evento": "Proyecto nuevo en la planilla"})
                camb_proy += 1
            continue
        c = {k: [q.get(k), p.get(k)] for k in CAMPOS_PROY if q.get(k) != p.get(k)}
        if c:
            hist.setdefault(b, []).append({"carga": carga, "cambios": c})
            camb_proy += 1
    for b in prevP:
        if b not in PB:
            hist.setdefault(b, []).append({"carga": carga, "evento": "Ya no viene en la planilla"})
            camb_proy += 1

    # cuadratura planilla vs libro
    cuad = []
    vivos = [e for e in libro if e.get("enArchivo", True) and e.get("etapa") not in ("reemplazado", "rechazado")]
    for b, p in PB.items():
        fam = "33" if p["sub"] == "33" else "pagos"
        base = p["contratado"] if p["contratado"] > 0 else p["aprobado"]
        saldo = max(0, base - p["transferido"])
        tram = [e for e in vivos if e["bip"] == b and e.get("etapa") == "tramite" and clase(e["tipo"]) != "rendicion"]
        tm = sum(e["monto"] for e in tram)
        verbo = "transferir" if fam == "33" else "pagar"
        if tm and tm > saldo:
            cuad.append({"bip": b, "fam": fam, "regla": "tramite_sobre_saldo", "monto": tm - saldo,
                         "detalle": f"Hay {len(tram)} en trámite por ${tm:,} pero la planilla deja solo ${saldo:,} por {verbo}".replace(",", ".")})
        if p["transferido"] - base > 1000 and base > 0:
            cuad.append({"bip": b, "fam": fam, "regla": "sobre_base", "monto": p["transferido"] - base,
                         "detalle": f"{'Transferido' if fam == '33' else 'Pagado'} ${p['transferido']:,} supera lo {'contratado' if p['contratado'] > 0 else 'aprobado'} ${base:,}".replace(",", ".")})
        if fam == "33" and p["rendido"] - p["transferido"] > 1000:
            cuad.append({"bip": b, "fam": fam, "regla": "rendido_sobre_transferido", "monto": p["rendido"] - p["transferido"],
                         "detalle": f"Rendido ${p['rendido']:,} supera lo transferido ${p['transferido']:,}".replace(",", ".")})
        q = prevP.get(b)
        if q and prev_carga:
            for campo, cl in (("transferido", "transferencia" if fam == "33" else "pago"), ("rendido", "rendicion")):
                if fam != "33" and campo == "rendido":
                    continue
                dp = p[campo] - q[campo]
                cur = [e for e in vivos if e["bip"] == b and e.get("etapa") == "cursado" and clase(e["tipo"]) == cl
                       and e.get("fechaCurso") and prev_carga < e["fechaCurso"] <= carga]
                dl = sum(e["monto"] for e in cur)
                if dp != dl:
                    nom = {"transferencia": "transferencias", "pago": "pagos", "rendicion": "rendiciones"}[cl]
                    cuad.append({"bip": b, "fam": fam, "regla": "delta_" + campo, "monto": abs(dp - dl),
                                 "detalle": f"Desde la carga del {prev_carga} la planilla sube {campo if fam == '33' else 'pagado'} en ${dp:,}; los {nom} cursados en el libro suman ${dl:,}".replace(",", ".")})

    cargas.append({"fecha": carga, "cargado": meta["cargado"],
                   "archivos": [meta.get(k) for k in ("archivoProyectos", "archivoPagos", "archivoTransferencias", "archivoDaf", "archivoDaf33") if meta.get(k)],
                   "nuevos": len(nuevos), "cambiados": len(cambiados), "desaparecidos": len(desaparecidos),
                   "proyectosCambiados": camb_proy, "cuadratura": len(cuad), "totalLibro": len(libro)})

    libro.sort(key=lambda e: (e.get("creado") or "", e["id"]))
    dump(os.path.join(estado, "libro.json"), {"items": libro})
    dump(os.path.join(estado, "historial.json"), {"items": hist})
    dump(os.path.join(estado, "cargas.json"), {"items": cargas})
    dump(os.path.join(estado, "proyectos_prev.json"), {"items": P})
    dump(os.path.join(data, "libro.json"), {"items": libro})
    dump(os.path.join(data, "historial.json"), {"items": hist})
    dump(os.path.join(data, "cargas.json"), {"items": cargas[-60:]})
    dump(os.path.join(data, "cuadratura.json"), {"carga": carga, "items": cuad})

    if xlsx:
        write_xlsx(xlsx, libro, PB, gdir)
    print(json.dumps(cargas[-1], ensure_ascii=False))


def write_xlsx(path, libro, PB, gdir):
    import openpyxl
    from openpyxl.styles import Font
    com = {}
    if gdir:
        for f in glob.glob(os.path.join(gdir, "*.json")):
            d = json.load(open(f))
            d = d.get("data", d)
            for mid, L in (d.get("comentarios") or {}).items():
                if L:
                    com[mid] = L[-1].get("texto", "")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Libro de movimientos"
    head = ["Subtítulo", "Unidad técnica", "BIP", "Proyecto", "Tipo", "Memo", "Memo creado (SGD)", "Memo enviado", "Factura", "Monto", "Creado", "Cursado/pagado",
            "Estado", "Ubicación", "Comentario sistema", "Tu comentario", "En archivos", "Primera carga", "Cambios registrados"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
    for e in libro:
        p = PB.get(e["bip"], {})
        bit = [b for b in e.get("bitacora") or [] if b.get("texto")]
        est = {"cursado": "Pagado" if clase(e["tipo"]) == "pago" else "Cursado", "tramite": "En trámite",
               "rechazado": "Rechazado", "reemplazado": "Reemplazado"}.get(e.get("etapa"), e.get("etapa") or "")
        ws.append(["33" if e.get("fam") == "33" else "29/31", e.get("ut", ""), e["bip"], p.get("nombre", ""), e["tipo"], e.get("memo", ""), e.get("fechaMemo") or "",
                   (e.get("enviado") or "") + {"bitacora": " (bitácora)", "creado": " (creación)"}.get(e.get("enviadoFuente"), ""),
                   e.get("factura", ""), e["monto"], e.get("creado"), e.get("fechaCurso"), est, e.get("ubicacion", ""),
                   f"{bit[0]['fecha']} {bit[0]['quien']}: {bit[0]['texto']}" if bit else "", com.get(e["id"], ""),
                   "Sí" if e.get("enArchivo", True) else "No", e.get("primeraCarga"),
                   " | ".join(f"{h['carga']}: " + (h.get("evento") or ", ".join(f"{k} {v[0]} → {v[1]}" for k, v in h["cambios"].items())) for h in e.get("historial", []))])
    for row in ws.iter_rows(min_row=2, min_col=10, max_col=10):
        for c in row:
            c.number_format = "#,##0"
    widths = [9, 30, 10, 45, 16, 7, 14, 22, 8, 14, 11, 12, 12, 26, 50, 40, 9, 12, 60]
    for i, w in enumerate(widths):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


if __name__ == "__main__":
    main()
