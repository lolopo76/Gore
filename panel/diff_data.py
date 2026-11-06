"""Compara la carga anterior del panel con la nueva y resume qué cambió.

Uso: python3 -I diff_data.py <dir_anterior> <dir_nuevo>
Cada dir tiene proyectos_*.json y movimientos.json con {"items": [...]}.
"""
import glob
import json
import os
import sys


def load(d):
    P = {}
    for f in glob.glob(os.path.join(d, "**", "proyectos_*.json"), recursive=True):
        for p in json.load(open(f)).get("items", []):
            P[p["bip"]] = p
    M = {}
    f = glob.glob(os.path.join(d, "**", "movimientos.json"), recursive=True)
    if f:
        for m in json.load(open(f[0])).get("items", []):
            M[m["id"]] = m
    return P, M


def main():
    (P0, M0), (P1, M1) = load(sys.argv[1]), load(sys.argv[2])
    out = {"nuevos": [], "salen": [], "situacion": [], "transferido": [], "avance": [], "movNuevos": []}
    for b, p in P1.items():
        o = P0.get(b)
        if not o:
            out["nuevos"].append(f"{b} {p['nombre'][:60]} ({p['situacion']})")
            continue
        if o["situacion"] != p["situacion"]:
            out["situacion"].append(f"{b} {p['nombre'][:50]}: {o['situacion']} → {p['situacion']}")
        if o["transferido"] != p["transferido"]:
            out["transferido"].append(f"{b} {p['nombre'][:50]}: +$ {p['transferido'] - o['transferido']:,}".replace(",", "."))
        if o["avance"] != p["avance"]:
            out["avance"].append(f"{b} {p['nombre'][:50]}: {o['avance']:.0f}% → {p['avance']:.0f}%")
    out["salen"] = [f"{b} {o['nombre'][:60]}" for b, o in P0.items() if b not in P1]
    out["movNuevos"] = [f"{m['creado']} {m['tipo']} {m['bip']} $ {m['monto']:,} ({m['estado'] or m['ubicacion']})".replace(",", ".")
                        for i, m in M1.items() if i not in M0]
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
