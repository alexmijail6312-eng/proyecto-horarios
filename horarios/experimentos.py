"""
Experimentacion.

1. Calidad: referencia manual vs PSR vs genetico vs genetico + recocido vs genetico + hill climbing,
   en tres tamanos (pocas, medianas y muchas materias).
2. PSR: backtracking con MRV vs sin heuristica (nodos explorados y porcentaje resuelto).
3. Cambio sorpresa: un docente deja de estar disponible; se compara la reparacion con A*
   contra volver a resolver desde cero con PSR y contra re-planificar todo el pipeline.
Los resultados se guardan en la carpeta de salida (JSON, CSV y, si hay matplotlib, graficos).
"""
import csv
import json
import os
import time
from collections import defaultdict

from . import busqueda, datos, genetico, local, psr
from .modelo import HD

METODOS = ["Manual (referencia)", "PSR", "Genetico", "Genetico + recocido", "Genetico + hill climbing"]


def _media(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def correr(repeticiones=3, semilla=1, salida="resultados", tamanos=None, limite_sin_mrv=1000,
           callback=None):
    tamanos = tamanos or datos.TAMANOS
    say = callback or (lambda m: None)
    calidad, psr_filas, sorpresa, conv = [], [], [], defaultdict(list)
    for nombre, n in tamanos.items():
        for r in range(repeticiones):
            sem = semilla + r
            say(f"Tamano {nombre} ({n} materias), repeticion {r + 1} de {repeticiones}")
            ent = datos.generar_entorno(n, sem)

            def fila(metodo, g, tiempo, resuelto=True):
                d = ent.detalle(g) if g else {}
                calidad.append({"tamano": nombre, "sesiones": ent.n, "rep": r, "metodo": metodo,
                                "resuelto": resuelto, "tiempo": round(tiempo, 4), **d})

            fila(METODOS[0], datos.horario_referencia(ent), 0.0)

            g_psr, e1 = psr.resolver(ent, semilla=sem)
            fila(METODOS[1], g_psr, e1["tiempo"], g_psr is not None)
            _, e2 = psr.resolver(ent, semilla=sem, heuristica="ninguna", limite=limite_sin_mrv)
            psr_filas.append({"tamano": nombre, "rep": r, "heuristica": "MRV", "nodos": e1["nodos"],
                              "retrocesos": e1["retrocesos"], "tiempo": round(e1["tiempo"], 4),
                              "resuelto": e1["resuelto"]})
            psr_filas.append({"tamano": nombre, "rep": r, "heuristica": "Sin heuristica", "nodos": e2["nodos"],
                              "retrocesos": e2["retrocesos"], "tiempo": round(e2["tiempo"], 4),
                              "resuelto": e2["resuelto"]})
            ent_t = datos.generar_entorno(n, sem, tension=True)          # problema ajustado
            for etiqueta, h, lim in (("MRV", "mrv", 20000), ("Sin heuristica", "ninguna", limite_sin_mrv)):
                _, et_ = psr.resolver(ent_t, semilla=sem, heuristica=h, limite=lim)
                psr_filas.append({"tamano": f"{nombre} (ajustada)", "rep": r, "heuristica": etiqueta,
                                  "nodos": et_["nodos"], "retrocesos": et_["retrocesos"],
                                  "tiempo": round(et_["tiempo"], 4), "resuelto": et_["resuelto"]})
            if g_psr is None:
                continue

            g_ga, hist, eg = genetico.evolucionar(ent, semilla=sem)
            fila(METODOS[2], g_ga, eg["tiempo"])
            conv[nombre].append([h["mejor"] for h in hist])
            g_sa, _, es = local.recocido(ent, g_ga, semilla=sem)
            fila(METODOS[3], g_sa, eg["tiempo"] + es["tiempo"])
            g_hc, _, eh = local.hill_climbing(ent, g_ga, semilla=sem)
            fila(METODOS[4], g_hc, eg["tiempo"] + eh["tiempo"])

            docente = max(ent.docentes, key=lambda d: sum(1 for x in ent.doc if x == d))
            franjas = sorted(f for i, (f, _) in enumerate(g_sa) if ent.doc[i] == docente)[:2]
            ent.docente_no_disponible(docente, franjas)
            conf = ent.conflictos(g_sa)
            g_a, ea = busqueda.reparar(ent, g_sa, semilla=sem)
            g_s, et = psr.resolver(ent, semilla=sem)
            sorpresa.append({
                "tamano": nombre, "rep": r, "docente": docente, "conflictos_tras_cambio": conf,
                "a_tiempo": round(ea["tiempo"], 5), "a_nodos": ea["nodos"], "a_movidas": ea["movidas"],
                "a_resuelto": g_a is not None,
                "psr_tiempo": round(et["tiempo"], 5),
                "psr_movidas": sum(1 for x, y in zip(g_sa, g_s) if x != y) if g_s else None,
                "replanificacion_tiempo": round(eg["tiempo"] + es["tiempo"] + e1["tiempo"], 4)})

    resumen = _resumir(calidad, psr_filas, sorpresa)
    res = {"calidad": resumen["calidad"], "psr": resumen["psr"], "sorpresa": resumen["sorpresa"],
           "convergencia": {k: v for k, v in conv.items()},
           "crudo": {"calidad": calidad, "psr": psr_filas, "sorpresa": sorpresa},
           "repeticiones": repeticiones, "tamanos": tamanos}
    if salida:
        guardar(res, salida)
    return res


def _resumir(calidad, psr_filas, sorpresa):
    def agrupar(filas, claves):
        g = defaultdict(list)
        for f in filas:
            g[tuple(f[c] for c in claves)].append(f)
        return g

    cal = []
    for (tam, met), fs in agrupar(calidad, ["tamano", "metodo"]).items():
        cal.append({"tamano": tam, "metodo": met, "sesiones": fs[0]["sesiones"],
                    "resueltos_pct": round(100 * sum(1 for f in fs if f["resuelto"]) / len(fs), 1),
                    **{k: _media([f[k] for f in fs if k in f]) for k in
                       ["conflictos", "ventanas", "concentracion", "separacion", "penalizacion", "tiempo"]}})
    ps = []
    for (tam, h), fs in agrupar(psr_filas, ["tamano", "heuristica"]).items():
        ps.append({"tamano": tam, "heuristica": h,
                   "resueltos_pct": round(100 * sum(1 for f in fs if f["resuelto"]) / len(fs), 1),
                   "nodos": _media([f["nodos"] for f in fs]), "retrocesos": _media([f["retrocesos"] for f in fs]),
                   "tiempo": _media([f["tiempo"] for f in fs])})
    so = []
    for (tam,), fs in agrupar(sorpresa, ["tamano"]).items():
        so.append({"tamano": tam, "conflictos_tras_cambio": _media([f["conflictos_tras_cambio"] for f in fs]),
                   "a_resueltos_pct": round(100 * sum(1 for f in fs if f["a_resuelto"]) / len(fs), 1),
                   "a_tiempo": _media([f["a_tiempo"] for f in fs]), "a_nodos": _media([f["a_nodos"] for f in fs]),
                   "a_movidas": _media([f["a_movidas"] for f in fs]),
                   "psr_tiempo": _media([f["psr_tiempo"] for f in fs]),
                   "psr_movidas": _media([f["psr_movidas"] for f in fs if f["psr_movidas"] is not None]),
                   "replanificacion_tiempo": _media([f["replanificacion_tiempo"] for f in fs])})
    return {"calidad": cal, "psr": ps, "sorpresa": so}


def guardar(res, salida):
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "resultados.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for nombre in ("calidad", "psr", "sorpresa"):
        filas = res[nombre]
        if filas:
            with open(os.path.join(salida, f"{nombre}.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
                w.writeheader()
                w.writerows(filas)
    graficar(res, salida)


def graficar(res, salida):
    """Graficos sobrios en escala de grises (requiere matplotlib; si falta, se omiten)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    estilos = ["-", "--", ":"]
    fig, ax = plt.subplots(figsize=(7, 4))
    for k, (tam, corridas) in enumerate(res["convergencia"].items()):
        if not corridas:
            continue
        m = min(len(c) for c in corridas)
        ax.plot(range(m), [sum(c[i] for c in corridas) / len(corridas) for i in range(m)],
                estilos[k % 3], color="black", label=tam)
    ax.set_xlabel("Generacion")
    ax.set_ylabel("Penalizacion del mejor individuo")
    ax.set_title("Convergencia del algoritmo genetico")
    ax.legend()
    ax.grid(True, color="#dddddd")
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "convergencia.png"), dpi=150)
    plt.close(fig)

    tams = list(res["tamanos"].keys())
    fig, ax = plt.subplots(figsize=(8, 4))
    ancho = 0.16
    tonos = ["#e6e6e6", "#bfbfbf", "#8c8c8c", "#595959", "#1a1a1a"]
    for k, met in enumerate(METODOS):
        vals = [next((f["penalizacion"] for f in res["calidad"] if f["tamano"] == t and f["metodo"] == met), 0)
                for t in tams]
        ax.bar([x + k * ancho for x in range(len(tams))], vals, ancho, label=met, color=tonos[k],
               edgecolor="black", linewidth=0.5)
    ax.set_xticks([x + 2 * ancho for x in range(len(tams))])
    ax.set_xticklabels(tams)
    ax.set_ylabel("Penalizacion total (menor es mejor)")
    ax.set_title("Calidad del horario por metodo")
    ax.legend(fontsize=7)
    ax.grid(True, axis="y", color="#dddddd")
    fig.tight_layout()
    fig.savefig(os.path.join(salida, "comparacion.png"), dpi=150)
    plt.close(fig)


def imprimir(res):
    print("\nCALIDAD (promedio de las repeticiones)")
    print(f'{"Tamano":<9}{"Metodo":<27}{"Conf":>5}{"Vent":>6}{"Conc":>6}{"Sep":>6}{"Penal":>9}{"Tiempo s":>10}{"Resuel %":>9}')
    for f in res["calidad"]:
        print(f'{f["tamano"]:<9}{f["metodo"]:<27}{f["conflictos"]:>5.1f}{f["ventanas"]:>6.1f}{f["concentracion"]:>6.1f}'
              f'{f["separacion"]:>6.1f}{f["penalizacion"]:>9.1f}{f["tiempo"]:>10.3f}{f["resueltos_pct"]:>9.0f}')
    print("\nPSR: MRV frente a sin heuristica")
    print(f'{"Tamano":<20}{"Heuristica":<16}{"Nodos":>9}{"Retroc.":>9}{"Tiempo s":>10}{"Resuel %":>9}')
    for f in res["psr"]:
        print(f'{f["tamano"]:<20}{f["heuristica"]:<16}{f["nodos"]:>9.0f}{f["retrocesos"]:>9.0f}'
              f'{f["tiempo"]:>10.3f}{f["resueltos_pct"]:>9.0f}')
    print("\nCAMBIO SORPRESA: un docente deja de estar disponible")
    print(f'{"Tamano":<9}{"Conf.":>6}{"A* s":>9}{"Nodos":>7}{"Mov.":>6}{"PSR s":>9}{"Mov.":>6}{"Replan. s":>11}')
    for f in res["sorpresa"]:
        print(f'{f["tamano"]:<9}{f["conflictos_tras_cambio"]:>6.1f}{f["a_tiempo"]:>9.4f}{f["a_nodos"]:>7.1f}'
              f'{f["a_movidas"]:>6.1f}{f["psr_tiempo"]:>9.4f}{f["psr_movidas"]:>6.1f}{f["replanificacion_tiempo"]:>11.3f}')
