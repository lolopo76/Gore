"""Datos para el resumen diario del panel, separados por Sub. 33 y Sub. 29/31.

Uso: python3 -I daily_summary.py <dir_lectura> [YYYY-MM-DD]
<dir_lectura> contiene sistema/*.json y gestion/*.json leídos con ArtifactData (out_dir).
"""
import datetime as dt
import glob
import json
import os
import re
import sys

ACTIVOS = {"EN EJECUCION", "ADJUDICADO", "EN LICITACION", "POR LICITAR", "POR LICITAR 3 O MÁS"}


def body(f):
    d = json.load(open(f))
    return d.get("data", d)


def main():
    root = sys.argv[1]
    hoy = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today()
    ayer = hoy - dt.timedelta(days=3 if hoy.weekday() == 0 else 1)
    P = [p for f in glob.glob(os.path.join(root, "sistema", "proyectos_*.json")) for p in body(f)["items"]]
    lib = os.path.join(root, "sistema", "libro.json")
    M = [m for m in body(lib if os.path.exists(lib) else os.path.join(root, "sistema", "movimientos.json"))["items"] if m.get("enArchivo", True)]
    G = {os.path.basename(f)[:-5]: body(f) for f in glob.glob(os.path.join(root, "gestion", "*.json"))}
    fam = {p["bip"]: ("33" if p["sub"] == "33" else "29/31") for p in P}
    out = {}
    for F in ("33", "29/31"):
        r = {"devueltos": [], "vencidos": [], "vencen7": [], "tramite": [], "cursadoAyer": [], "rechazados": [], "proximas": []}
        for p in P:
            if fam[p["bip"]] != F:
                continue
            g = G.get(p["bip"], {})
            sit = (g.get("estado") or p["situacion"]).upper()
            t = g.get("vigencia") or p["termino"]
            if sit in ACTIVOS and t and p["avance"] < 100:
                d = (dt.date.fromisoformat(t) - hoy).days
                item = f"{p['bip']} {p['nombre'][:45]} (término {t}, avance {p['avance']:.0f}%)"
                if d < 0:
                    r["vencidos"].append((d, item))
                elif d <= 7:
                    r["vencen7"].append((d, item))
            if g.get("proxima"):
                r["proximas"].append(f"{p['bip']}: {g['proxima']}")
        for m in M:
            if fam.get(m["bip"]) != F:
                continue
            desc = f"{m['tipo']} {m['bip']} $ {m['monto']:,}".replace(",", ".")
            if m.get("etapa") == "tramite" and re.search(r"\(\d+\)\s*$", m.get("ubicacion") or ""):
                notas = [e for e in m.get("bitacora", []) if e["texto"] and not re.match(r"(?i)^ok\.?$", e["texto"])]
                nota = next((e for e in notas if not e["quien"].startswith("Jefe Inversi")), notas[0] if notas else None)
                r["devueltos"].append(desc + (f": {nota['fecha']} {nota['quien']}: {nota['texto'][:90]}" if nota else ""))
            elif m.get("etapa") == "tramite" and m.get("creado"):
                dias = (hoy - dt.date.fromisoformat(m["creado"])).days
                r["tramite"].append((-dias, f"{desc}: {dias} días en {m['ubicacion']}"))
            elif m.get("etapa") == "rechazado":
                r["rechazados"].append(f"{desc} (memo {m['memo']})")
            elif m.get("etapa") == "cursado" and m.get("fechaCurso") and ayer.isoformat() <= m["fechaCurso"] < hoy.isoformat():
                r["cursadoAyer"].append(desc)
        for k in ("vencidos", "vencen7", "tramite"):
            r[k] = [x for _, x in sorted(r[k])]
        out[F] = r
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
