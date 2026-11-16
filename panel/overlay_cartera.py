"""Actualiza proyectos_*.json con los reportes de cartera del sistema (cartera_33 / cartera_31 .xlsx).

Uso: python3 -I overlay_cartera.py <out_dir de build_data> [cartera_33.xlsx|-] [cartera_31.xlsx|-]
- cartera_33: Situación para los proyectos Sub. 33. Si Monto Aprob Core o Monto Contratado difieren de la planilla,
  solo se informa (no se aplica): en algunos proyectos el reporte trae otro concepto de monto.
- cartera_31: Estado Situación, Avance Fisico, Última Modificación y Último Estado para Sub. 22, 29 y 31.
Solo toca proyectos que ya están en la cartera; imprime un resumen de lo que cambió.
"""
import datetime as dt
import glob
import json
import os
import sys

import openpyxl


def code(v):
    return str(v if v is not None else "").split(".")[0].strip()


def rows(path):
    R = list(openpyxl.load_workbook(path, read_only=True, data_only=True).active.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(R) if r and "Código" in r)
    h = R[hi]
    return {code(x.get("Código")): x for x in (dict(zip(h, r)) for r in R[hi + 1:]) if code(x.get("Código"))}


def fecha(v):
    try:
        return dt.datetime.strptime(str(v).strip(), "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def main():
    out = sys.argv[1]
    c33 = rows(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else {}
    c31 = rows(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else {}
    cambios, avisos = [], []
    for f in glob.glob(os.path.join(out, "proyectos_*.json")):
        doc = json.load(open(f))
        for p in doc["items"]:
            nuevo = {}
            if p["sub"] == "33" and p["bip"] in c33:
                x = c33[p["bip"]]
                if x.get("Situación"):
                    nuevo["situacion"] = str(x["Situación"]).strip()
                for k, col in (("aprobado", "Monto Aprob Core"), ("contratado", "Monto Contratado")):
                    v = x.get(col)
                    if isinstance(v, (int, float)) and v > 0 and abs(round(v) - (p.get(k) or 0)) > 1:
                        avisos.append((p["bip"], k, p.get(k), round(v)))
            elif p["sub"] != "33" and p["bip"] in c31:
                x = c31[p["bip"]]
                if x.get("Estado Situación"):
                    nuevo["situacion"] = str(x["Estado Situación"]).strip()
                if isinstance(x.get("Avance Fisico"), (int, float)):
                    nuevo["avance"] = float(x["Avance Fisico"])
                f_ = fecha(x.get("Última Modificación"))
                if f_ and f_ >= (p.get("ultimaAct") or ""):
                    nuevo["ultimaAct"] = f_
                    if x.get("Último Estado"):
                        nuevo["ultimaDesc"] = str(x["Último Estado"]).strip()
            for k, v in nuevo.items():
                if p.get(k) != v:
                    cambios.append((p["bip"], k, p.get(k), v))
                    p[k] = v
        json.dump(doc, open(f, "w"), ensure_ascii=False)
    for c in cambios:
        print(*c, sep=" | ")
    print(f"{len(cambios)} cambios")
    for a in avisos:
        print("DIFERENCIA (no aplicada)", *a, sep=" | ")


main()
