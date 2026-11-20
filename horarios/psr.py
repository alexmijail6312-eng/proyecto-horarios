"""
Problema de satisfaccion de restricciones (PSR).

Variables: sesiones. Dominios: pares (franja, aula).
Restricciones: docente unico, aula unica, cruce de grupo, capacidad, disponibilidad de
docente y de aula, y una sesion por dia de cada materia.
Resolucion: consistencia de arcos AC-3, backtracking, heuristica MRV (con grado como
desempate) y comprobacion hacia adelante.
"""
import random
import sys
import time
from collections import deque

from .modelo import HD

sys.setrecursionlimit(10000)


def _revisar(ent, dom, i, j):
    dF, dD = ent.vec[i][j]
    FJ = {f for f, a in dom[j]}
    quitar = {f for f in {f for f, a in dom[i]}
              if not any((not dF or fj != f) and (not dD or fj // HD != f // HD) for fj in FJ)}
    if quitar:
        dom[i] = {v for v in dom[i] if v[0] not in quitar}
    return bool(quitar)


def ac3(ent, dom):
    cola = deque((i, j) for i in ent.vec for j in ent.vec[i])
    while cola:
        i, j = cola.popleft()
        if _revisar(ent, dom, i, j):
            if not dom[i]:
                return False
            cola.extend((k, i) for k in ent.vec[i] if k != j)
    return True


def _propagar(ent, dom, asign, i, v):
    """Comprobacion hacia adelante tras asignar v a la sesion i. None si algun dominio queda vacio."""
    f = v[0]
    nuevo = {}
    for j, d in dom.items():
        if j == i:
            continue
        if j in asign:
            w = asign[j]
            if w == v:
                return None
            if j in ent.vec[i]:
                dF, dD = ent.vec[i][j]
                if (dF and w[0] == f) or (dD and w[0] // HD == f // HD):
                    return None
        else:
            if j in ent.vec[i]:
                dF, dD = ent.vec[i][j]
                d = {w for w in d if w != v and (not dF or w[0] != f)
                     and (not dD or w[0] // HD != f // HD)}
            elif v in d:
                d = d - {v}
            if not d:
                return None
        nuevo[j] = d
    nuevo[i] = {v}
    return nuevo


def resolver(ent, semilla=0, limite=20000, heuristica="mrv", fijos=None):
    """
    Devuelve (horario | None, estadisticas).
    fijos: dict sesion -> (franja, aula) con asignaciones que se conservan (re-planificacion parcial).
    heuristica: "mrv" o "ninguna" (orden fijo de sesiones, para comparar).
    """
    t0 = time.time()
    rng = random.Random(semilla)
    est = {"nodos": 0, "retrocesos": 0, "resuelto": False, "tiempo": 0.0}
    dom = {i: set(ent.dominio[i]) for i in range(ent.n)}
    asign = {}

    def terminar(res):
        est["tiempo"] = time.time() - t0
        est["resuelto"] = res is not None
        return res, est

    if any(not d for d in dom.values()):
        return terminar(None)
    for i, v in (fijos or {}).items():
        if v not in dom[i]:
            return terminar(None)
        dom = _propagar(ent, dom, asign, i, v)
        if dom is None:
            return terminar(None)
        asign[i] = v
    if not ac3(ent, dom):
        return terminar(None)

    def siguiente(dom):
        libres = (x for x in range(ent.n) if x not in asign)
        if heuristica == "mrv":
            return min(libres, key=lambda x: (len(dom[x]), -len(ent.vec[x])))
        return next(libres)

    def bt(dom):
        est["nodos"] += 1
        if len(asign) == ent.n:
            return True
        if est["nodos"] > limite:
            return False
        i = siguiente(dom)
        valores = list(dom[i])
        rng.shuffle(valores)
        for v in valores:
            asign[i] = v
            nuevo = _propagar(ent, dom, asign, i, v)
            if nuevo is not None and bt(nuevo):
                return True
            del asign[i]
            est["retrocesos"] += 1
        return False

    return terminar([asign[i] for i in range(ent.n)] if bt(dom) else None)
