"""
Sistema multiagente para generar y mantener horarios academicos.

Entorno: totalmente observable, determinista, estatico durante la planificacion,
discreto, secuencial y multiagente. Todos los datos se cargan desde archivos CSV.

Agentes:
  AgenteDemanda       red bayesiana: estima el tamano de cada grupo
  AgentePlanificador  PSR -> algoritmo genetico -> busqueda local; reparacion
  AgenteVerificador   acepta, rechaza o senala el conflicto
  AgenteCarrera       negociacion de aulas con minimax y poda alfa-beta
  HMMOcupacion        prediccion de picos de ocupacion de aulas

Uso:
  python horarios_agentes.py ejecutar --materias 20
  python horarios_agentes.py ejecutar --materias 20 --sorpresa D03
  python horarios_agentes.py experimento
  python horarios_agentes.py generar --materias 40 --carpeta datos
Solo requiere la biblioteca estandar de Python 3.8 o superior.
"""
import argparse
import csv
import math
import os
import random
import time
from collections import Counter, defaultdict, deque

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie"]
HORAS = ["07:00", "08:30", "10:00", "11:30", "14:00", "15:30"]
HD = len(HORAS)                 # horas por dia
NF = len(DIAS) * HD             # numero de franjas
PESO = {"conflicto": 1000, "ventana": 5, "concentracion": 3, "desperdicio": 2}
MAX_DIA = 3                     # sesiones por dia a partir de las cuales hay concentracion


# ----------------------------------------------------------------------------
# Datos de ejemplo (CSV)
# ----------------------------------------------------------------------------
def escribir(ruta, campos, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(campos)
        w.writerows(filas)


def leer(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def generar_datos(carpeta, n_materias, semilla=1):
    rng = random.Random(semilla)
    os.makedirs(carpeta, exist_ok=True)
    carreras = ["Sistemas", "Industrial", "Civil"]
    n_grupos = max(2, math.ceil(n_materias / 5))
    n_docentes = max(3, math.ceil(n_materias * 0.6))
    mats = []
    for m in range(n_materias):
        g = m % n_grupos
        mats.append([f"M{m+1:02d}", f"Materia {m+1}", carreras[g % 3], f"G{g+1}",
                     1 + (g // 3) % 3, f"D{rng.randrange(n_docentes)+1:02d}",
                     rng.choice([2, 2, 3]), rng.randint(0, 12),
                     rng.choice([20, 25, 30, 35, 40, 45, 50, 60, 70])])
    escribir(os.path.join(carpeta, "materias.csv"),
             ["id", "nombre", "carrera", "grupo", "nivel", "docente", "sesiones",
              "repitentes", "cupo_anterior"], mats)
    docs = [[f"D{d+1:02d}", ";".join(map(str, sorted(rng.sample(range(NF), 3))))]
            for d in range(n_docentes)]
    escribir(os.path.join(carpeta, "docentes.csv"), ["docente", "no_disponible"], docs)
    total = sum(m[6] for m in mats)
    n_aulas = max(3, math.ceil(total / NF * 2.2))
    caps = [40, 60, 50, 80, 100, 30, 60]
    escribir(os.path.join(carpeta, "aulas.csv"), ["aula", "capacidad"],
             [[f"A{a+1:02d}", caps[a % len(caps)]] for a in range(n_aulas)])
    escribir(os.path.join(carpeta, "franjas.csv"), ["franja", "dia", "hora"],
             [[f, DIAS[f // HD], HORAS[f % HD]] for f in range(NF)])
    hist = []
    for _ in range(300):
        niv, rep = rng.randint(1, 3), rng.randint(0, 12)
        cupo = rng.choice([20, 25, 30, 35, 40, 45, 50, 60, 70])
        mat = max(5, round(cupo * (1 - 0.08 * (niv - 1)) + 0.8 * rep + rng.gauss(0, 4)))
        hist.append([niv, rep, cupo, mat])
    escribir(os.path.join(carpeta, "historico.csv"),
             ["nivel", "repitentes", "cupo_anterior", "matricula_real"], hist)


# ----------------------------------------------------------------------------
# Agente de demanda: red bayesiana  Nivel, Repitentes, Cupo -> Matricula
# ----------------------------------------------------------------------------
class RedBayesiana:
    NOMBRES = ["pequena", "mediana", "grande"]

    @staticmethod
    def disc_nivel(x): return int(x) - 1
    @staticmethod
    def disc_rep(x): return 0 if int(x) <= 5 else 1
    @staticmethod
    def disc_cupo(x): return 0 if int(x) < 30 else (1 if int(x) < 60 else 2)
    @staticmethod
    def disc_mat(x): return 0 if int(x) < 30 else (1 if int(x) < 60 else 2)

    def ajustar(self, filas):
        """Aprende la tabla de probabilidad condicional por conteo (suavizado de Laplace)."""
        self.cuentas = {}
        sumas, n = [0.0] * 3, [0] * 3
        for r in filas:
            padres = (self.disc_nivel(r["nivel"]), self.disc_rep(r["repitentes"]),
                      self.disc_cupo(r["cupo_anterior"]))
            m = self.disc_mat(r["matricula_real"])
            self.cuentas.setdefault(padres, [1, 1, 1])[m] += 1
            sumas[m] += int(r["matricula_real"])
            n[m] += 1
        self.media = [sumas[k] / n[k] if n[k] else 30 for k in range(3)]

    def distribucion(self, nivel, rep, cupo):
        c = self.cuentas.get((self.disc_nivel(nivel), self.disc_rep(rep),
                              self.disc_cupo(cupo)), [1, 1, 1])
        t = sum(c)
        return [x / t for x in c]

    def tam_esperado(self, nivel, rep, cupo):
        p = self.distribucion(nivel, rep, cupo)
        return math.ceil(sum(pi * mi for pi, mi in zip(p, self.media)))


class AgenteDemanda:
    def __init__(self, carpeta):
        self.red = RedBayesiana()
        self.red.ajustar(leer(os.path.join(carpeta, "historico.csv")))

    def actuar(self, ent):
        """Percibe nivel, repitentes y cupo anterior; entrega el tamano esperado del grupo."""
        for m in ent.materias:
            ent.tam[m["id"]] = min(self.red.tam_esperado(m["nivel"], m["repitentes"],
                                                         m["cupo_anterior"]), max(ent.cap))
        ent.construir()


# ----------------------------------------------------------------------------
# Entorno: materias, docentes, aulas, franjas y tamano de grupos
# ----------------------------------------------------------------------------
class Entorno:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.materias = leer(os.path.join(carpeta, "materias.csv"))
        self.no_disp = {r["docente"]: {int(x) for x in r["no_disponible"].split(";") if x}
                        for r in leer(os.path.join(carpeta, "docentes.csv"))}
        aulas = leer(os.path.join(carpeta, "aulas.csv"))
        self.aulas = [a["aula"] for a in aulas]
        self.cap = [int(a["capacidad"]) for a in aulas]
        self.na = len(self.aulas)
        self.tam = {}

    def construir(self):
        """Variables = sesiones; dominios = pares (franja, aula); vecinos del PSR."""
        self.mat, self.doc, self.grp, self.carr, self.nombre = [], [], [], [], []
        self.sesiones_de = defaultdict(list)
        for m in self.materias:
            for s in range(int(m["sesiones"])):
                self.sesiones_de[m["id"]].append(len(self.mat))
                self.mat.append(m["id"]); self.doc.append(m["docente"])
                self.grp.append(m["grupo"]); self.carr.append(m["carrera"])
                self.nombre.append(f'{m["id"]}.{s+1}')
        self.n = len(self.mat)
        self.grupos_de = defaultdict(set)
        for i in range(self.n):
            self.grupos_de[self.carr[i]].add(self.grp[i])
        self.actualizar_dominios()
        self.vec = defaultdict(dict)
        for i in range(self.n):
            for j in range(i + 1, self.n):
                dF = self.doc[i] == self.doc[j] or self.grp[i] == self.grp[j]
                dD = self.mat[i] == self.mat[j]
                if dF or dD:
                    self.vec[i][j] = self.vec[j][i] = (dF, dD)

    def actualizar_dominios(self):
        self.dominio = []
        for i in range(self.n):
            t = self.tam[self.mat[i]]
            self.dominio.append([(f, a) for f in range(NF) if f not in self.no_disp[self.doc[i]]
                                 for a in range(self.na) if self.cap[a] >= t])

    # --- evaluacion --------------------------------------------------------
    def diagnostico(self, g):
        """Lista de (mensaje, sesiones) con cada restriccion obligatoria violada."""
        grupos = defaultdict(list)
        out = []
        for i, (f, a) in enumerate(g):
            grupos[("Docente", self.doc[i], f)].append(i)
            grupos[("Grupo", self.grp[i], f)].append(i)
            grupos[("Aula", self.aulas[a], f)].append(i)
            grupos[("Materia repetida en el dia", self.mat[i], f // HD)].append(i)
            if self.cap[a] < self.tam[self.mat[i]]:
                out.append((f"Capacidad insuficiente: {self.nombre[i]} en {self.aulas[a]}", [i]))
            if f in self.no_disp[self.doc[i]]:
                out.append((f"Docente {self.doc[i]} no disponible: {self.nombre[i]} en franja {f}", [i]))
        for (tipo, clave, f), lst in grupos.items():
            if len(lst) > 1:
                out.append((f"{tipo} {clave} repetido en franja/dia {f}: "
                            + ", ".join(self.nombre[i] for i in lst), lst))
        return out

    def conflictos(self, g):
        c = [Counter(), Counter(), Counter(), Counter()]
        n = 0
        for i, (f, a) in enumerate(g):
            c[0][(self.doc[i], f)] += 1
            c[1][(self.grp[i], f)] += 1
            c[2][(a, f)] += 1
            c[3][(self.mat[i], f // HD)] += 1
            if self.cap[a] < self.tam[self.mat[i]]:
                n += 1
            if f in self.no_disp[self.doc[i]]:
                n += 1
        return n + sum(v - 1 for cc in c for v in cc.values() if v > 1)

    def blandas(self, g, grupos=None):
        """Ventanas y concentracion excesiva por grupo y dia."""
        por = defaultdict(list)
        for i, (f, a) in enumerate(g):
            if grupos is None or self.grp[i] in grupos:
                por[(self.grp[i], f // HD)].append(f % HD)
        v = k = 0
        for horas in por.values():
            h = set(horas)
            v += max(h) - min(h) + 1 - len(h)
            k += max(0, len(horas) - MAX_DIA)
        return v, k

    def desperdicio(self, g):
        return sum((self.cap[a] - self.tam[self.mat[i]]) / self.cap[a]
                   for i, (f, a) in enumerate(g) if self.cap[a] >= self.tam[self.mat[i]])

    def penalizacion(self, g):
        v, k = self.blandas(g)
        return (PESO["conflicto"] * self.conflictos(g) + PESO["ventana"] * v
                + PESO["concentracion"] * k + PESO["desperdicio"] * self.desperdicio(g))

    def resumen(self, g):
        v, k = self.blandas(g)
        return {"conflictos": self.conflictos(g), "ventanas": v, "concentracion": k,
                "penalizacion": round(self.penalizacion(g), 2)}


# ----------------------------------------------------------------------------
# PSR: AC-3 + backtracking con MRV y comprobacion hacia adelante
# ----------------------------------------------------------------------------
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


def psr(ent, semilla=0, limite=20000):
    rng = random.Random(semilla)
    dom = {i: set(ent.dominio[i]) for i in range(ent.n)}
    if not ac3(ent, dom):
        return None
    asign, nodos = {}, [0]

    def propagar(dom, i, v):
        f = v[0]
        nuevo = {}
        for j, d in dom.items():
            if j not in asign:
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

    def bt(dom):
        nodos[0] += 1
        if len(asign) == ent.n:
            return True
        if nodos[0] > limite:
            return False
        i = min((x for x in range(ent.n) if x not in asign),
                key=lambda x: (len(dom[x]), -len(ent.vec[x])))        # MRV y grado
        valores = list(dom[i])
        rng.shuffle(valores)
        for v in valores:
            asign[i] = v
            nuevo = propagar(dom, i, v)
            if nuevo is not None and bt(nuevo):
                return True
            del asign[i]
        return False

    return [asign[i] for i in range(ent.n)] if bt(dom) else None


# ----------------------------------------------------------------------------
# Algoritmo genetico
# ----------------------------------------------------------------------------
def _cruce(ent, a, b, rng):
    hijo = [None] * ent.n
    for idx in ent.sesiones_de.values():                  # cruce por bloques de materias
        padre = a if rng.random() < 0.5 else b
        for i in idx:
            hijo[i] = padre[i]
    return hijo


def _mutar(ent, g, rng):
    g = list(g)
    for _ in range(rng.choice([1, 2])):
        if rng.random() < 0.6:                            # cambio de franja y aula
            i = rng.randrange(ent.n)
            g[i] = rng.choice(ent.dominio[i])
        else:                                             # intercambio de sesiones
            i, j = rng.sample(range(ent.n), 2)
            g[i], g[j] = g[j], g[i]
    return g


def genetico(ent, inicial, generaciones=60, p_mut=0.4, k=3, semilla=0):
    rng = random.Random(semilla)
    pop = sorted(((ent.penalizacion(g), g) for g in inicial), key=lambda x: x[0])
    historia = [pop[0][0]]
    for _ in range(generaciones):
        nueva = pop[:2]                                   # elitismo
        torneo = lambda: min(rng.sample(pop, min(k, len(pop))), key=lambda x: x[0])[1]
        while len(nueva) < len(pop):
            hijo = _cruce(ent, torneo(), torneo(), rng)
            if rng.random() < p_mut:
                hijo = _mutar(ent, hijo, rng)
            nueva.append((ent.penalizacion(hijo), hijo))
        pop = sorted(nueva, key=lambda x: x[0])
        historia.append(pop[0][0])
    return pop[0][1], historia


# ----------------------------------------------------------------------------
# Busqueda local: recocido simulado o hill climbing con reinicios
# ----------------------------------------------------------------------------
def recocido(ent, g, pasos=4000, t0=3.0, semilla=0):
    rng = random.Random(semilla)
    act, pa = list(g), ent.penalizacion(g)
    mejor = (pa, list(act))
    t, enf = t0, (0.01 / t0) ** (1 / pasos)
    for _ in range(pasos):
        i, j = rng.sample(range(ent.n), 2)                # intercambio de pares de sesiones
        act[i], act[j] = act[j], act[i]
        pn = ent.penalizacion(act)
        if pn <= pa or rng.random() < math.exp(-(pn - pa) / t):
            pa = pn
            if pa < mejor[0]:
                mejor = (pa, list(act))
        else:
            act[i], act[j] = act[j], act[i]
        t *= enf
    return mejor[1]


def hill_climbing(ent, g, reinicios=4, pasos=1000, semilla=0):
    rng = random.Random(semilla)
    mejor = (ent.penalizacion(g), list(g))
    for r in range(reinicios):
        act = list(mejor[1])
        if r:
            for _ in range(3):
                i, j = rng.sample(range(ent.n), 2)
                act[i], act[j] = act[j], act[i]
        pa = ent.penalizacion(act)
        for _ in range(pasos):
            i, j = rng.sample(range(ent.n), 2)
            act[i], act[j] = act[j], act[i]
            pn = ent.penalizacion(act)
            if pn < pa:
                pa = pn
            else:
                act[i], act[j] = act[j], act[i]
        if pa < mejor[0]:
            mejor = (pa, list(act))
    return mejor[1]


# ----------------------------------------------------------------------------
# Reparacion: busqueda sobre movimientos; heuristica = conflictos restantes
# ----------------------------------------------------------------------------
def reparar(ent, g, max_pasos=300, semilla=0):
    rng = random.Random(semilla)
    g, pasos, movidas = list(g), 0, set()
    while pasos < max_pasos:
        malas = sorted({i for _, ids in ent.diagnostico(g) for i in ids})
        if not malas:
            break
        i = rng.choice(malas)
        mejor, mv = None, []
        for v in ent.dominio[i]:                          # mover la sesion i a otra franja/aula
            g[i] = v
            h = ent.penalizacion(g)
            if mejor is None or h < mejor:
                mejor, mv = h, [v]
            elif h == mejor:
                mv.append(v)
        g[i] = rng.choice(mv)
        movidas.add(i)
        pasos += 1
    return g, pasos, len(movidas)


# ----------------------------------------------------------------------------
# Agentes de carrera: minimax con poda alfa-beta
# ----------------------------------------------------------------------------
class AgenteCarrera:
    def __init__(self, nombre):
        self.nombre = nombre

    def mejoras(self, ent, g, libres, base, maximo=3):
        """Mejora (reduccion de ventanas y concentracion) de mover una sesion a cada franja libre."""
        grupos = ent.grupos_de[self.nombre]
        pen = lambda x: (lambda v, k: PESO["ventana"] * v + PESO["concentracion"] * k)(*ent.blandas(x, grupos))
        antes, res = pen(g), {}
        if antes == 0:
            return res
        gg = list(g)
        for i in (i for i in range(ent.n) if ent.carr[i] == self.nombre):
            orig = gg[i]
            for s in libres:
                if s in ent.dominio_set[i]:
                    gg[i] = s
                    if ent.conflictos(gg) <= base:
                        res[(i, s)] = antes - pen(gg)
            gg[i] = orig
        mejores = sorted({i for i, _ in res}, key=lambda i: -max(u for (x, _), u in res.items() if x == i))
        return {m: u for m, u in res.items() if m[0] in mejores[:maximo]}


def negociar(ent, g, car_a, car_b, k=2, pool=6):
    """Juego de suma cero por turnos. A maximiza (utilA - utilB); B minimiza."""
    g = list(g)
    ocupadas = set(g)
    libres = [(f, a) for f in range(NF) for a in range(ent.na) if (f, a) not in ocupadas]
    ent.dominio_set = [set(d) for d in ent.dominio]
    base = ent.conflictos(g)
    ag = [AgenteCarrera(car_a), AgenteCarrera(car_b)]
    util = [x.mejoras(ent, g, libres, base) for x in ag]
    if not util[0] or not util[1]:
        return g, {"valor": 0, "nodos": 0, "podas": 0, "movimientos": []}
    mejor_slot = lambda u, s: max([v for (_, x), v in u.items() if x == s] or [0])
    candidatos = {s for u in util for (_, s) in u}
    slots = sorted(candidatos, key=lambda s: -min(mejor_slot(util[0], s), mejor_slot(util[1], s)))[:pool]
    cand = [sorted({i for i, _ in u}) for u in util]
    est = {"nodos": 0, "podas": 0}

    def minimax(t, tomados, usados, alfa, beta, valor):
        est["nodos"] += 1
        if t == 2 * k:
            return valor, []
        j = t % 2
        movs = [(i, s) for i in cand[j] if i not in usados[j] for s in slots
                if s not in tomados and (i, s) in util[j]]
        movs.sort(key=lambda m: -util[j][m])
        movs.append(None)                                 # pasar el turno
        mejor_v, mejor_l = (-1e9 if j == 0 else 1e9), []
        for m in movs:
            if m is None:
                v, l = minimax(t + 1, tomados, usados, alfa, beta, valor)
            else:
                u = util[j][m]
                us = [set(usados[0]), set(usados[1])]
                us[j].add(m[0])
                v, l = minimax(t + 1, tomados | {m[1]}, us, alfa, beta, valor + (u if j == 0 else -u))
                l = [(j, m)] + l
            if (j == 0 and v > mejor_v) or (j == 1 and v < mejor_v):
                mejor_v, mejor_l = v, l
            if j == 0:
                alfa = max(alfa, mejor_v)
            else:
                beta = min(beta, mejor_v)
            if beta <= alfa:
                est["podas"] += 1
                break
        return mejor_v, mejor_l

    valor, linea = minimax(0, frozenset(), [set(), set()], -1e9, 1e9, 0)
    aplicados = []
    for j, (i, s) in linea:                               # aplicar solo si no genera conflictos
        previo, p0 = g[i], ent.penalizacion(g)
        g[i] = s
        if ent.conflictos(g) > base or ent.penalizacion(g) > p0:
            g[i] = previo
        else:
            aplicados.append((ag[j].nombre, ent.nombre[i], s))
    return g, {"valor": valor, "nodos": est["nodos"], "podas": est["podas"], "movimientos": aplicados}


def elegir_carreras(ent, g):
    """Las dos carreras con mayor penalizacion blanda son las que mas ganan disputando aulas."""
    pen = {c: PESO["ventana"] * v + PESO["concentracion"] * k
           for c, gr in ent.grupos_de.items() for v, k in [ent.blandas(g, gr)]}
    orden = sorted(pen, key=lambda c: -pen[c])
    return orden[:2] if len(orden) >= 2 else None


# ----------------------------------------------------------------------------
# HMM sobre la ocupacion de aulas durante la semana
# ----------------------------------------------------------------------------
class HMMOcupacion:
    ESTADOS = ["Valle", "Normal", "Pico"]

    def __init__(self):
        self.pi = [0.4, 0.4, 0.2]
        self.A = [[0.70, 0.25, 0.05], [0.20, 0.60, 0.20], [0.05, 0.35, 0.60]]
        self.B = [[0.80, 0.15, 0.05], [0.20, 0.60, 0.20], [0.05, 0.25, 0.70]]

    @staticmethod
    def nivel(fraccion):
        return 0 if fraccion < 1 / 3 else (1 if fraccion < 2 / 3 else 2)

    def viterbi(self, obs):
        n = 3
        d = [[math.log(self.pi[s]) + math.log(self.B[s][obs[0]]) for s in range(n)]]
        bp = []
        for o in obs[1:]:
            fila, ptr = [], []
            for s in range(n):
                c = [d[-1][r] + math.log(self.A[r][s]) for r in range(n)]
                r = max(range(n), key=lambda x: c[x])
                fila.append(c[r] + math.log(self.B[s][o])); ptr.append(r)
            d.append(fila); bp.append(ptr)
        s = max(range(n), key=lambda x: d[-1][x])
        ruta = [s]
        for ptr in reversed(bp):
            s = ptr[s]; ruta.append(s)
        return ruta[::-1]

    def predecir_siguiente(self, obs):
        """Filtrado hacia adelante y distribucion del estado en la siguiente franja."""
        a = [self.pi[s] * self.B[s][obs[0]] for s in range(3)]
        for o in obs[1:]:
            a = [sum(a[r] * self.A[r][s] for r in range(3)) * self.B[s][o] for s in range(3)]
        t = sum(a)
        a = [x / t for x in a]
        return [sum(a[r] * self.A[r][s] for r in range(3)) for s in range(3)]


def analizar_ocupacion(ent, g, hmm):
    cuenta = Counter(f for f, _ in g)
    estados = {}
    for d in range(len(DIAS)):
        obs = [hmm.nivel(min(1.0, cuenta[d * HD + h] / ent.na)) for h in range(HD)]
        estados[d] = (obs, hmm.viterbi(obs))
    return estados


def sugerir_reasignaciones(ent, g, hmm, maximo=5):
    est = analizar_ocupacion(ent, g, hmm)
    picos = [d * HD + h for d, (_, ruta) in est.items() for h, s in enumerate(ruta) if s == 2]
    valles = [d * HD + h for d, (_, ruta) in est.items() for h, s in enumerate(ruta) if s == 0]
    base, p0, ocup, sug = ent.conflictos(g), ent.penalizacion(g), set(g), []
    for fp in picos:
        for i in [i for i, (f, _) in enumerate(g) if f == fp]:
            for fv in valles:
                for a in range(ent.na):
                    if (fv, a) in ocup or (fv, a) not in set(ent.dominio[i]):
                        continue
                    h = list(g); h[i] = (fv, a)
                    if ent.conflictos(h) <= base and ent.penalizacion(h) <= p0 + 3:
                        sug.append((ent.nombre[i], fp, fv, a, round(ent.penalizacion(h) - p0, 2)))
                        break
    return est, sug[:maximo]


# ----------------------------------------------------------------------------
# Agentes planificador y verificador
# ----------------------------------------------------------------------------
class AgenteVerificador:
    def actuar(self, ent, g):
        d = ent.diagnostico(g)
        return ("aceptar", []) if not d else ("rechazar", [m for m, _ in d])


class AgentePlanificador:
    def __init__(self, ent, semilla=0, poblacion=20, generaciones=60, local="sa"):
        self.ent, self.semilla = ent, semilla
        self.poblacion, self.generaciones, self.local = poblacion, generaciones, local

    def actuar(self):
        ent, t = self.ent, {}
        t0 = time.time()
        inicial = [x for x in (psr(ent, self.semilla + s) for s in range(self.poblacion)) if x]
        t["psr"] = time.time() - t0
        if not inicial:
            return None, t
        t0 = time.time()
        g, historia = genetico(ent, inicial, self.generaciones, semilla=self.semilla)
        t["genetico"] = time.time() - t0
        t0 = time.time()
        car = elegir_carreras(ent, g)
        self.negociacion = None
        if car:
            g, self.negociacion = negociar(ent, g, *car)
            self.negociacion["carreras"] = car
        t["negociacion"] = time.time() - t0
        t0 = time.time()
        g = (recocido if self.local == "sa" else hill_climbing)(ent, g, semilla=self.semilla)
        t["local"] = time.time() - t0
        self.historia = historia
        return g, t


# ----------------------------------------------------------------------------
# Referencia manual simulada: asignacion secuencial sin optimizar
# ----------------------------------------------------------------------------
def horario_manual(ent):
    """Cada sesion va a la primera franja y aula libres, en orden, sin optimizar."""
    g = []
    for i in range(ent.n):
        elegido = ent.dominio[i][0]
        for v in ent.dominio[i]:
            if all(g[j] != v
                   and not ((ent.doc[i] == ent.doc[j] or ent.grp[i] == ent.grp[j]) and g[j][0] == v[0])
                   and not (ent.mat[i] == ent.mat[j] and g[j][0] // HD == v[0] // HD)
                   for j in range(len(g))):
                elegido = v
                break
        g.append(elegido)
    return g


# ----------------------------------------------------------------------------
# Presentacion
# ----------------------------------------------------------------------------
def mostrar_grilla(ent, g, max_grupos=2):
    grupos = sorted(set(ent.grp), key=lambda x: int(x[1:]))[:max_grupos]
    for gr in grupos:
        print(f"\nGrupo {gr}")
        celdas = {}
        for i, (f, a) in enumerate(g):
            if ent.grp[i] == gr:
                celdas[(f // HD, f % HD)] = f"{ent.mat[i]} {ent.aulas[a]}"
        print("Hora  | " + " | ".join(f"{d:^11}" for d in DIAS))
        print("------+-" + "-+-".join("-" * 11 for _ in DIAS))
        for h in range(HD):
            print(f"{HORAS[h]} | " + " | ".join(f"{celdas.get((d, h), ''):^11}" for d in range(len(DIAS))))


def exportar(ent, g, ruta="horario.csv"):
    filas = [[ent.nombre[i], ent.grp[i], ent.carr[i], ent.doc[i], DIAS[f // HD], HORAS[f % HD], ent.aulas[a]]
             for i, (f, a) in enumerate(g)]
    escribir(ruta, ["sesion", "grupo", "carrera", "docente", "dia", "hora", "aula"], filas)


def cargar(carpeta):
    ent = Entorno(carpeta)
    AgenteDemanda(carpeta).actuar(ent)
    return ent


def pipeline(ent, semilla=0, local="sa", verbose=True):
    plan, ver = AgentePlanificador(ent, semilla, local=local), AgenteVerificador()
    g, t = plan.actuar()
    if g is None:
        print("El PSR no encontro un horario completo con los datos dados.")
        return None
    res = {"g": g, "t": t, "resumen": ent.resumen(g), "negociacion": plan.negociacion}
    res["veredicto"] = ver.actuar(ent, g)[0]
    return res


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------
def ejecutar(args):
    if not os.path.exists(os.path.join(args.carpeta, "materias.csv")):
        generar_datos(args.carpeta, args.materias, args.semilla)
    ent = cargar(args.carpeta)
    print(f"Entorno: {len(ent.materias)} materias, {ent.n} sesiones, {ent.na} aulas, {NF} franjas "
          "(totalmente observable)")
    man = horario_manual(ent)
    print("Referencia manual simulada:", ent.resumen(man))
    r = pipeline(ent, args.semilla, args.local)
    if r is None:
        return
    g = r["g"]
    print("Horario optimizado:", r["resumen"], "| verificador:", r["veredicto"])
    print("Tiempos (s):", {k: round(v, 2) for k, v in r["t"].items()})
    info = r["negociacion"]
    if info:
        print(f"Negociacion {info['carreras'][0]} vs {info['carreras'][1]}: valor minimax {info['valor']:.1f}, "
              f"nodos {info['nodos']}, podas {info['podas']}, movimientos {info['movimientos']}")
    hmm = HMMOcupacion()
    est, sug = sugerir_reasignaciones(ent, g, hmm)
    print("HMM, estados por dia (V=Valle, N=Normal, P=Pico):")
    for d, (_, ruta) in est.items():
        print("  ", DIAS[d], "".join("VNP"[s] for s in ruta))
    for s in sug:
        print(f"  Sugerencia: mover {s[0]} de franja {s[1]} a franja {s[2]} aula {ent.aulas[s[3]]} "
              f"(cambio de penalizacion {s[4]})")
    ok, msgs = AgenteVerificador().actuar(ent, g)
    print("Verificacion final:", ok, msgs[:3])
    mostrar_grilla(ent, g)
    exportar(ent, g)
    print("\nHorario completo guardado en horario.csv")
    if args.sorpresa:
        d = args.sorpresa
        franjas = {f for i, (f, _) in enumerate(g) if ent.doc[i] == d}
        ent.no_disp[d] = ent.no_disp.get(d, set()) | set(sorted(franjas)[:2])
        ent.actualizar_dominios()
        print(f"\nCambio sorpresa: docente {d} ya no esta disponible en {sorted(franjas)[:2]}")
        print("Conflictos tras el cambio:", ent.conflictos(g))
        t0 = time.time()
        g2, pasos, movidas = reparar(ent, g, semilla=args.semilla)
        print(f"Reparacion: {pasos} pasos, {movidas} sesiones movidas, "
              f"{time.time()-t0:.3f} s, conflictos finales {ent.conflictos(g2)}")


def experimento(args):
    print(f"{'Tamano':<9}{'Sesiones':>9} | {'Manual c/v/pen':>17} | {'Sistema c/v/pen':>17} "
          f"| {'PSR':>6}{'GA':>7}{'LS':>7} | {'Reparacion':>11}")
    for nombre, n in [("pocas", 8), ("medianas", 20), ("muchas", 40)]:
        carpeta = f"datos_{nombre}"
        generar_datos(carpeta, n, args.semilla)
        ent = cargar(carpeta)
        m = ent.resumen(horario_manual(ent))
        r = pipeline(ent, args.semilla, args.local)
        if r is None:
            print(f"{nombre:<9}{ent.n:>9} | sin solucion")
            continue
        g, s = r["g"], r["resumen"]
        d = Counter(ent.doc[i] for i in range(ent.n)).most_common(1)[0][0]
        fr = sorted(f for i, (f, _) in enumerate(g) if ent.doc[i] == d)[:2]
        ent.no_disp[d] |= set(fr)
        ent.actualizar_dominios()
        t0 = time.time()
        g2, _, _ = reparar(ent, g, semilla=args.semilla)
        tr = time.time() - t0
        fm = lambda x: f"{x['conflictos']}/{x['ventanas']}/{x['penalizacion']:.0f}"
        print(f"{nombre:<9}{ent.n:>9} | {fm(m):>17} | {fm(s):>17} | {r['t']['psr']:>6.2f}"
              f"{r['t']['genetico']:>7.2f}{r['t']['local']:>7.2f} | {tr:>7.3f} s ({ent.conflictos(g2)} conf.)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", choices=["generar", "ejecutar", "experimento"])
    ap.add_argument("--carpeta", default="datos")
    ap.add_argument("--materias", type=int, default=20)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--local", choices=["sa", "hc"], default="sa", help="sa = recocido, hc = hill climbing")
    ap.add_argument("--sorpresa", default=None, help="docente que deja de estar disponible, ej. D03")
    a = ap.parse_args()
    if a.modo == "generar":
        generar_datos(a.carpeta, a.materias, a.semilla)
        print("Datos generados en", a.carpeta)
    elif a.modo == "ejecutar":
        ejecutar(a)
    else:
        experimento(a)
