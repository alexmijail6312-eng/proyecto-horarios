"""
Busqueda local sobre un horario completo.

Vecindario: intercambio de las asignaciones de dos sesiones o, en modo mixto, cambio de
una sesion a otra (franja, aula) de su dominio.
Metodos: recocido simulado e hill climbing con reinicios.
"""
import math
import random
import time


def _mover(ent, g, rng, mixto):
    """Aplica un movimiento al azar sobre g y devuelve la funcion que lo deshace."""
    if mixto and rng.random() < 0.3:
        i = rng.randrange(ent.n)
        previo = g[i]
        g[i] = rng.choice(ent.dominio[i])
        return lambda: g.__setitem__(i, previo)
    i, j = rng.sample(range(ent.n), 2)
    g[i], g[j] = g[j], g[i]
    return lambda: _swap(g, i, j)


def _swap(g, i, j):
    g[i], g[j] = g[j], g[i]


def recocido(ent, g, pasos=None, t0=3.0, semilla=0, mixto=True):
    """Devuelve (mejor horario, historia, estadisticas)."""
    ini = time.time()
    rng = random.Random(semilla)
    pasos = pasos or 60 * ent.n
    act = list(g)
    pa = ent.penalizacion(act)
    mejor = (pa, list(act))
    historia = [{"paso": 0, "mejor": pa}]
    t, enf = t0, (0.01 / t0) ** (1 / pasos)
    aceptados = 0
    for paso in range(1, pasos + 1):
        deshacer = _mover(ent, act, rng, mixto)
        pn = ent.penalizacion(act)
        if pn <= pa or rng.random() < math.exp(-(pn - pa) / t):
            pa = pn
            aceptados += 1
            if pa < mejor[0]:
                mejor = (pa, list(act))
        else:
            deshacer()
        t *= enf
        if paso % max(1, pasos // 40) == 0:
            historia.append({"paso": paso, "mejor": mejor[0]})
    return mejor[1], historia, {"tiempo": time.time() - ini, "pasos": pasos, "aceptados": aceptados}


def hill_climbing(ent, g, reinicios=4, pasos=None, semilla=0, mixto=True):
    ini = time.time()
    rng = random.Random(semilla)
    pasos = pasos or 15 * ent.n
    mejor = (ent.penalizacion(g), list(g))
    historia = [{"paso": 0, "mejor": mejor[0]}]
    total = 0
    for r in range(reinicios):
        act = list(mejor[1])
        if r:
            for _ in range(3):                                   # reinicio: perturbacion del mejor
                _mover(ent, act, rng, mixto)
        pa = ent.penalizacion(act)
        for _ in range(pasos):
            deshacer = _mover(ent, act, rng, mixto)
            pn = ent.penalizacion(act)
            if pn < pa:
                pa = pn
            else:
                deshacer()
            total += 1
        if pa < mejor[0]:
            mejor = (pa, list(act))
        historia.append({"paso": total, "mejor": mejor[0]})
    return mejor[1], historia, {"tiempo": time.time() - ini, "pasos": total, "reinicios": reinicios}
