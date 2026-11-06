"""Convierte las planillas del sistema en documentos JSON para la base del panel.

Uso: python3 -I build_data.py <proyectos.xls> <pagos.xls> <transferencias.xls> <out_dir> [daf31.xlsx] [daf33.xlsx]
Los reportes DAF (opcionales; "-" para omitir) son la fuente del estado Pagado / No Pagado:
daf31 para los pagos 22, 29 y 31, daf33 para las transferencias 33 (incluye la bitácora del trámite).
Escribe: proyectos_<grupo>.json (sistema/proyectos_*), movimientos.json, meta.json
"""
import datetime as dt
import json
import os
import re
import sys

import xlrd

EPOCH = dt.date(1899, 12, 30)


def xl_date(v):
    if isinstance(v, float) and v > 1000:
        return (EPOCH + dt.timedelta(days=int(v))).isoformat()
    return None


def txt_date(v):
    try:
        return dt.datetime.strptime(str(v).strip(), "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def money(v):
    if isinstance(v, float):
        return round(v)
    s = re.sub(r"[^\d-]", "", str(v))
    return int(s) if s else 0


def num(v):
    try:
        return float(str(v).replace("%", "").strip())
    except ValueError:
        return 0.0


def code(v):
    return str(v).split(".")[0].strip()


def load_projects(path):
    s = xlrd.open_workbook(path).sheet_by_index(0)
    hr = next(i for i in range(min(10, s.nrows)) if str(s.cell_value(i, 0)).strip() == "Código")
    h = s.row_values(hr)
    out = []
    for r in range(hr + 1, s.nrows):
        x = dict(zip(h, s.row_values(r)))
        if not code(x["Código"]):
            continue
        fase = str(x["Fase"])
        m = re.search(r"(\d+)\s*$", fase)
        inicio = xl_date(x["Fecha Inicio"])
        dur = int(num(x["Duración Contrato"]))
        termino = None
        if inicio and dur:
            termino = (dt.date.fromisoformat(inicio) + dt.timedelta(days=dur)).isoformat()
        out.append({
            "bip": code(x["Código"]),
            "nombre": str(x["Nombre"]).strip(),
            "comuna": str(x["Comuna"]).strip(),
            "situacion": str(x["Situación"]).strip(),
            "sub": m.group(1) if m else "",
            "aprobado": money(x["Monto Aprobado Core"]),
            "contratado": money(x["Monto Contratado"]),
            "costoTotal": money(x["Costo Total"]),
            "transferido": money(x["Monto Transferido"]),
            "rendido": money(x["Monto Rendido"]),
            "ultimoMonto": money(x["Ultimo Monto"]),
            "ultimaFechaMonto": xl_date(x["Ultima Fecha Monto"]),
            "tipoSolicitud": str(x["Tipo Solicitud"]).strip(),
            "empresa": str(x["Empresa"]).strip(),
            "rutEmpresa": str(x["RUT Empresa"]).strip(),
            "duracion": dur,
            "inicio": inicio,
            "termino": termino,
            "avance": num(x["Avance Físico"]),
            "ultimaAct": xl_date(x["Última Actualización"]),
            "ultimaDesc": str(x["Última Descripción"]).strip()[:600],
            "submodalidad": str(x["Submodalidad"]).strip(),
            "marco": str(x["Marco Presupuestario"]).strip(),
            "convenio": xl_date(x["Fecha Convenio"]),
            "resolucion": code(x["Nº Resolución"]),
            "fechaResolucion": xl_date(x["Fecha Resolución"]),
            "unidadTecnica": str(x["Unidad Tecnica"]).strip(),
            "anio": int(num(x["Año aprobación"])) or None,
            "sitContable": str(x["Situacion Contable"]).strip(),
            "beneficiarios": int(num(x["Beneficiarios Total"])),
        })
    return out


def load_moves(path, bips, kind):
    s = xlrd.open_workbook(path).sheet_by_index(0)
    h = s.row_values(4)
    out = []
    for r in range(5, s.nrows):
        x = dict(zip(h, s.row_values(r)))
        if x.get("Id") in ("", None) or code(x["Código"]) not in bips:
            continue
        out.append({
            "id": code(x["Id"]),
            "bip": code(x["Código"]),
            "tipo": str(x["Tipo"]).strip(),
            "estado": str(x["Estado"]).strip(),
            "carpeta": str(x["Carpeta"]).strip(),
            "ubicacion": str(x["Ubicación"]).strip(),
            "creado": txt_date(x["Fecha Creado"]),
            "enviado": txt_date(x["Fecha Enviado"]),
            "memo": code(x["Numero Memo"]),
            "fechaMemo": txt_date(x.get("Fecha Memo", "")),
            "proveedor": str(x["Proveedor"]).strip(),
            "monto": money(x["Monto"]),
            "fechaPago": txt_date(x.get("Fecha Pago", "")),
            "transaccion": str(x["Tipo Transaccion"]).strip(),
            "vb": txt_date(x.get("Fecha VºBº Presupuesto", "")),
            "sigfe": code(x.get("SIGFE", "")),
            "egreso": code(x.get("Egreso", "")),
            "fuente": kind,
        })
        m = out[-1]
        if m["sigfe"] in ("0", ""):
            m["sigfe"] = ""
        if m["egreso"] in ("0", ""):
            m["egreso"] = ""
        # Etapa del trámite: rechazado, cursado (pagado o con VºBº de Presupuesto y transacción) o en trámite.
        if m["estado"] == "Rechazado":
            m["etapa"], m["fechaCurso"] = "rechazado", None
        elif m["fechaPago"]:
            m["etapa"], m["fechaCurso"] = "cursado", m["fechaPago"]
        elif m["vb"] and m["transaccion"]:
            m["etapa"], m["fechaCurso"] = "cursado", m["vb"]
        else:
            m["etapa"], m["fechaCurso"] = "tramite", None
    return out


def merge_daf(path, bips, moves):
    """Reemplaza los pagos SAGIR por las filas del reporte DAF (estado de pago oficial y más historia)."""
    import openpyxl
    rows = list(openpyxl.load_workbook(path, read_only=True, data_only=True).active.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == "Código")
    h = rows[hi]
    sagir = {(m["bip"], m["memo"]): m for m in moves if m["fuente"] == "pagos"}
    used = set()
    out = []
    for r in rows[hi + 1:]:
        x = dict(zip(h, r))
        bip = code(x.get("Código") or "")
        if bip not in bips:
            continue
        memo = code(x.get("N° Memo") or "")
        s = sagir.get((bip, memo))
        if s:
            used.add((bip, memo))
        pagado = str(x.get("¿Pagado?") or "").strip().lower() == "pagado"
        bruto = money(x.get("Bruto") or 0)
        m = {
            "id": f"daf-{bip}-{memo}-{code(x.get('N° Factura/Boleta') or '')}",
            "bip": bip,
            "tipo": f"Pago {code(x.get('Subtitulo') or '')}",
            "estado": s["estado"] if s else "",
            "carpeta": s["carpeta"] if s else "",
            "ubicacion": str(x.get("Ubicación") or "").strip(),
            "creado": txt_date(x.get("Fecha Memo") or ""),
            "enviado": s["enviado"] if s else None,
            "memo": memo,
            "fechaMemo": txt_date(x.get("Fecha Memo") or ""),
            "factura": code(x.get("N° Factura/Boleta") or ""),
            "proveedor": s["proveedor"] if s else "",
            "monto": bruto or (s["monto"] if s else 0),
            "fechaPago": txt_date(x.get("Fecha Pagado") or ""),
            "transaccion": s["transaccion"] if s else "",
            "vb": None, "sigfe": s["sigfe"] if s else "", "egreso": "",
            "fuente": "daf",
        }
        if pagado:
            m["etapa"], m["fechaCurso"] = "cursado", m["fechaPago"]
        elif s and s["estado"] == "Rechazado":
            m["etapa"], m["fechaCurso"] = "rechazado", None
        else:
            m["etapa"], m["fechaCurso"] = "tramite", None
        out.append(m)
    rest = [m for m in moves if not (m["fuente"] == "pagos" and (m["bip"], m["memo"]) in used)]
    return rest + out


HEADER = re.compile(r"^[ \t]*(.*?)[ \t]*-[ \t]*Escribio[ \t]*\([ \t]*(\d\d-\d\d-\d{4})[^)]*\)[ \t]*(-[ \t]*Archivado)?[ \t]*:[ \t]*$", re.M)


def parse_bitacora(txt):
    txt = str(txt or "")
    hs = list(HEADER.finditer(txt))
    out = []
    for i, m in enumerate(hs):
        body = txt[m.end():hs[i + 1].start() if i + 1 < len(hs) else len(txt)]
        body = re.sub(r"^\s*-{5,}\s*", "", body)
        who = m.group(1).strip()
        k = who.find("(")
        rol, persona = (who[:k].strip(), who[k + 1:].strip()) if k >= 0 else (who, "")
        if persona.endswith(")"):
            persona = persona[:-1].strip()
        out.append({
            "quien": rol or persona,
            "persona": persona,
            "fecha": txt_date(m.group(2)),
            "archivado": bool(m.group(3)),
            "texto": re.sub(r"\s+", " ", body).strip()[:240],
        })
    return out  # más reciente primero


def merge_daf33(path, bips, moves):
    """Reemplaza las transferencias SAGIR por el reporte DAF 33 (Pagado / No Pagado y bitácora)."""
    import openpyxl
    rows = list(openpyxl.load_workbook(path, read_only=True, data_only=True).active.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == "Código")
    h = rows[hi]
    sagir = {}
    for m in moves:
        if m["fuente"] == "transferencias" and m["tipo"].startswith("Transferencia"):
            sagir.setdefault((m["bip"], m["monto"]), m)
    used = set()
    out = []
    seen = {}
    for r in rows[hi + 1:]:
        x = dict(zip(h, r))
        bip = code(x.get("Código") or "")
        if bip not in bips:
            continue
        bruto = money(x.get("Bruto") or 0)
        s = sagir.get((bip, bruto))
        if s:
            used.add(s["id"])
        bit = parse_bitacora(x.get("Observaciones"))
        pagado = str(x.get("Pagado") or "").strip().lower() == "pagado"
        # id estable entre cargas: BIP + monto + fecha de la primera nota de la bitácora
        key = f"daf33-{bip}-{bruto}-{bit[-1]['fecha'] if bit else 'sf'}"
        seen[key] = seen.get(key, 0) + 1
        m = {
            "id": key if seen[key] == 1 else f"{key}-{seen[key]}",
            "bip": bip,
            "tipo": "Transferencia 33",
            "estado": s["estado"] if s else "",
            "carpeta": s["carpeta"] if s else "",
            "ubicacion": str(x.get("Ubicación") or "").strip(),
            "creado": (s["creado"] if s else None) or (bit[-1]["fecha"] if bit else None),
            "enviado": s["enviado"] if s else None,
            "memo": s["memo"] if s else "",
            "fechaMemo": s.get("fechaMemo") if s else None,
            "proveedor": s["proveedor"] if s else "",
            "monto": bruto,
            "fechaPago": txt_date(x.get("Fecha Pagado") or ""),
            "transaccion": s["transaccion"] if s else "",
            "vb": s["vb"] if s else None, "sigfe": s["sigfe"] if s else "", "egreso": s["egreso"] if s else "",
            "bitacora": bit[:8],
            "enviadoBitacora": next((e["fecha"] for e in reversed(bit[:-1]) if e["quien"] != bit[-1]["quien"]), None) if bit else None,
            "fuente": "daf33",
        }
        if pagado:
            m["etapa"], m["fechaCurso"] = "cursado", m["fechaPago"]
        elif s and s["estado"] == "Rechazado":
            m["etapa"], m["fechaCurso"] = "rechazado", None
        else:
            m["etapa"], m["fechaCurso"] = "tramite", None
        out.append(m)
    return [m for m in moves if m["id"] not in used] + out


def main():
    proj, pagos, transf, out_dir = sys.argv[1:5]
    os.makedirs(out_dir, exist_ok=True)
    # "nuevo.xls+anterior.xls": si la planilla nueva trae solo algunos subtítulos,
    # los subtítulos que no trae se completan con la planilla anterior.
    files = proj.split("+")
    projects = load_projects(files[0])
    for extra in files[1:]:
        subs = {p["sub"] for p in projects}
        have = {p["bip"] for p in projects}
        projects += [p for p in load_projects(extra) if p["sub"] not in subs and p["bip"] not in have]
    bips = {p["bip"] for p in projects}
    moves = load_moves(pagos, bips, "pagos") + load_moves(transf, bips, "transferencias")
    daf = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None
    daf33 = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    if daf:
        moves = merge_daf(daf, bips, moves)
    if daf33:
        moves = merge_daf33(daf33, bips, moves)
    # Fecha de envío del memo. "Fecha Enviado" de SAGIR es el último traspaso entre bandejas (suele ser
    # posterior al pago), así que se guarda aparte como ultimoEnvio. El envío del memo se toma de la bitácora
    # DAF (día en que otra bandeja lo recibió) y, si no hay bitácora, de la fecha del memo (o la de creación
    # del trámite si el memo tiene fecha anterior).
    for m in moves:
        m["ultimoEnvio"] = m.get("enviado")
        if m.get("enviadoBitacora"):
            m["enviado"], m["enviadoFuente"] = m["enviadoBitacora"], "bitacora"
        elif m.get("fechaMemo") or m.get("creado"):
            m["enviado"] = max(d for d in (m.get("fechaMemo"), m.get("creado")) if d)
            m["enviadoFuente"] = "memo" if m["enviado"] == m.get("fechaMemo") else "creado"
        else:
            m["enviado"], m["enviadoFuente"] = None, None
    for m in moves:
        m.pop("enviadoBitacora", None)
    # Un trámite sin cursar queda "reemplazado" si después se emitió otro del mismo tipo, proyecto y monto.
    for m in moves:
        if m["etapa"] != "tramite" or not m["monto"] or not m.get("creado"):
            continue
        kind = m["tipo"].split()[0]
        later = [o for o in moves if o is not m and o["bip"] == m["bip"] and o["monto"] == m["monto"]
                 and o["tipo"].split()[0] == kind and (o.get("creado") or "") > m["creado"]]
        if later:
            o = max(later, key=lambda o: o["creado"])
            m["etapa"], m["fechaCurso"] = "reemplazado", None
            m["reemplazo"] = o["memo"] if o.get("memo") and o["memo"] != m.get("memo") else None
            m["reemplazoFecha"] = o.get("creado")
    groups = {}
    for p in projects:
        g = re.sub(r"[^a-z]", "", p["comuna"].lower()) or "otros"
        if g == "regional":
            g = "otros"
        groups.setdefault(g, []).append(p)
    for g, items in groups.items():
        with open(os.path.join(out_dir, f"proyectos_{g}.json"), "w") as f:
            json.dump({"items": items}, f, ensure_ascii=False)
    with open(os.path.join(out_dir, "movimientos.json"), "w") as f:
        json.dump({"items": moves}, f, ensure_ascii=False)
    meta = {
        "cargado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "archivoProyectos": " + ".join(os.path.basename(f) for f in proj.split("+")),
        "archivoPagos": os.path.basename(pagos),
        "archivoTransferencias": os.path.basename(transf),
        "archivoDaf": os.path.basename(daf) if daf else None,
        "archivoDaf33": os.path.basename(daf33) if daf33 else None,
        "grupos": sorted(groups),
        "totalProyectos": len(projects),
        "totalMovimientos": len(moves),
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(json.dumps(meta, ensure_ascii=False))
    for fn in sorted(os.listdir(out_dir)):
        print(fn, os.path.getsize(os.path.join(out_dir, fn)))


if __name__ == "__main__":
    main()
