"""
Busqueda informada para reparar un horario con conflictos.

Estado: horario completo. Accion: mover una sesion en conflicto a otro (franja, aula) de
su dominio. Costo g: numero de movimientos. Heuristica h: numero de restricciones
violadas (pares en conflicto y violaciones individuales). Se usa A* ponderado,
f = g + peso * h, que prioriza reducir conflictos con pocos movimientos.
"""
import heapq
import itertools
import random
import time

from .modelo import HD


def conflictos_sesion(ent, g, i, v):
    """Restricciones violadas que involucran a la sesion i si estuviera en v = (franja, aula)."""
    f, a = v
    d, gr, m = ent.doc[i], ent.grp[i], ent.mat[i]
    n = (ent.cap[a] < ent.tam[i]) + (f in ent.nd_doc[d]) + (f in ent.nd_aula[a])
    for j, (fj, aj) in enumerate(g):
        if j == i:
            continue
        if fj == f:
            n += (ent.doc[j] == d) + (ent.grp[j] == gr) + (aj == a)
        if ent.mat[j] == m and fj // HD == f // HD:
            n += 1
    return n


def heuristica(ent, g):
    """h(g): cada par en conflicto se cuenta una vez."""
    total = 0
    for i, v in enumerate(g):
        total += (ent.cap[v[1]] < ent.tam[i]) + (v[0] in ent.nd_doc[ent.doc[i]]) \
                 + (v[0] in ent.nd_aula[v[1]])
        for j in range(i + 1, ent.n):
            fj, aj = g[j]
            if fj == v[0]:
                total += (ent.doc[j] == ent.doc[i]) + (ent.grp[j] == ent.grp[i]) + (aj == v[1])
            if ent.mat[j] == ent.mat[i] and fj // HD == v[0] // HD:
                total += 1
    return total


def reparar(ent, g, peso=2.0, max_nodos=400, ramas=4, max_sesiones=4, semilla=0):
    """Devuelve (horario reparado | None, estadisticas)."""
    t0 = time.time()
    rng = random.Random(semilla)
    est = {"nodos": 0, "movimientos": 0, "movidas": 0, "resuelto": False, "tiempo": 0.0}
    inicio = tuple(g)
    h0 = heuristica(ent, g)
    est["h_inicial"] = h0
    cuenta = itertools.count()
    frontera = [(peso * h0, next(cuenta), 0, h0, inicio)]
    visitados = {inicio}
    while frontera and est["nodos"] < max_nodos:
        _, _, costo, h, estado = heapq.heappop(frontera)
        est["nodos"] += 1
        if h == 0:
            est.update(resuelto=True, movimientos=costo,
                       movidas=sum(1 for a, b in zip(inicio, estado) if a != b),
                       tiempo=time.time() - t0)
            return list(estado), est
        lista = list(estado)
        malas = sorted(((conflictos_sesion(ent, lista, i, estado[i]), i) for i in range(ent.n)),
                       reverse=True)
        malas = [(c, i) for c, i in malas if c > 0][:max_sesiones]
        for c_old, i in malas:
            candidatos = [(h - c_old + conflictos_sesion(ent, lista, i, v), rng.random(), v)
                          for v in ent.dominio[i] if v != estado[i]]
            candidatos.sort()
            for hn, _, v in candidatos[:ramas]:
                nuevo = estado[:i] + (v,) + estado[i + 1:]
                if nuevo not in visitados:
                    visitados.add(nuevo)
                    heapq.heappush(frontera, (costo + 1 + peso * hn, next(cuenta), costo + 1, hn, nuevo))
    est["tiempo"] = time.time() - t0
    return None, est


def pulir_sesiones(ent, g, ids, pasadas=2):
    """Mejora la calidad moviendo solo las sesiones ids; conserva el resto del horario (estabilidad)."""
    g = list(g)
    for _ in range(pasadas):
        for i in ids:
            mejor = (ent.penalizacion(g), g[i])
            for v in ent.dominio[i]:
                g[i] = v
                p = ent.penalizacion(g)
                if p < mejor[0]:
                    mejor = (p, v)
            g[i] = mejor[1]
    return g
