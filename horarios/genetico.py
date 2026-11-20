"""
Algoritmo genetico.

Individuo: horario completo; cada gen guarda (franja, aula) de una sesion.
Fitness: penalizacion total (se minimiza); los conflictos pesan mucho mas que las
ventanas, la concentracion, la separacion y el desperdicio de aula.
Seleccion por torneo, cruce por bloques de materias, mutacion por cambio de franja y
aula o por intercambio de sesiones, y elitismo.
"""
import random
import time

from . import psr


def cruce_bloques(ent, a, b, rng):
    hijo = [None] * ent.n
    for idx in ent.sesiones_de.values():
        padre = a if rng.random() < 0.5 else b
        for i in idx:
            hijo[i] = padre[i]
    return hijo


def mutar(ent, g, rng, n_mut=None):
    g = list(g)
    for _ in range(n_mut or rng.choice([1, 2])):
        if rng.random() < 0.6:
            i = rng.randrange(ent.n)
            g[i] = rng.choice(ent.dominio[i])
        else:
            i, j = rng.sample(range(ent.n), 2)
            g[i], g[j] = g[j], g[i]
    return g


def poblacion_inicial(ent, tam, n_psr, semilla):
    """Soluciones factibles del PSR (con orden de valores aleatorio) y copias mutadas."""
    base = []
    for s in range(n_psr):
        g, _ = psr.resolver(ent, semilla=semilla * 1000 + s)
        if g:
            base.append(g)
    if not base:
        return []
    rng = random.Random(semilla)
    pop = list(base)
    while len(pop) < tam:
        pop.append(mutar(ent, rng.choice(base), rng, n_mut=4))
    return pop


def evolucionar(ent, poblacion=30, generaciones=80, p_mut=0.4, k=3, semilla=0,
                n_psr=10, paciencia=30):
    """Devuelve (mejor horario | None, historia, estadisticas)."""
    t0 = time.time()
    rng = random.Random(semilla)
    inicial = poblacion_inicial(ent, poblacion, n_psr, semilla)
    if not inicial:
        return None, [], {"tiempo": time.time() - t0, "evaluaciones": 0}
    pop = sorted(((ent.penalizacion(g), g) for g in inicial), key=lambda x: x[0])
    evals = len(pop)
    historia = [{"gen": 0, "mejor": pop[0][0], "media": sum(p for p, _ in pop) / len(pop)}]
    sin_mejora = 0
    for gen in range(1, generaciones + 1):
        nueva = pop[:2]                                          # elitismo
        torneo = lambda: min(rng.sample(pop, min(k, len(pop))), key=lambda x: x[0])[1]
        while len(nueva) < len(pop):
            hijo = cruce_bloques(ent, torneo(), torneo(), rng)
            if rng.random() < p_mut:
                hijo = mutar(ent, hijo, rng)
            nueva.append((ent.penalizacion(hijo), hijo))
            evals += 1
        previo = pop[0][0]
        pop = sorted(nueva, key=lambda x: x[0])
        historia.append({"gen": gen, "mejor": pop[0][0], "media": sum(p for p, _ in pop) / len(pop)})
        sin_mejora = sin_mejora + 1 if pop[0][0] >= previo else 0
        if sin_mejora >= paciencia:
            break
    return pop[0][1], historia, {"tiempo": time.time() - t0, "evaluaciones": evals,
                                 "generaciones": len(historia) - 1}
