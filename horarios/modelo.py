"""
Modelo del entorno de asignacion de horarios.

El entorno es totalmente observable: materias, docentes, aulas, franjas y matricula
son datos conocidos antes de planificar. Es determinista (cada accion tiene un unico
resultado), discreto, secuencial y estatico durante la planificacion; cambia solo cuando
llega un evento externo (docente o aula no disponible, cambio de matricula).

Un horario es una lista g donde g[i] = (franja, aula) para la sesion i.
"""
from collections import Counter, defaultdict

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie"]
HORAS = ["07:00", "08:30", "10:00", "11:30", "14:00", "15:30"]
HD = len(HORAS)                  # franjas por dia
NF = len(DIAS) * HD              # franjas por semana
MAX_DIA = 3                      # mas de 3 sesiones al dia de un grupo es concentracion excesiva
PESO = {"conflicto": 1000, "ventana": 5, "concentracion": 3, "separacion": 2, "desperdicio": 2}


def etiqueta_franja(f):
    return f"{DIAS[f // HD]} {HORAS[f % HD]}"


class Entorno:
    def __init__(self, materias, no_disp_docente, aulas):
        """
        materias: lista de dict con id, nombre, carrera, grupo, docente, sesiones, matricula
        no_disp_docente: dict docente -> conjunto de franjas no disponibles
        aulas: lista de dict con aula, capacidad
        """
        self.materias = [dict(m) for m in materias]
        self.aulas = [a["aula"] for a in aulas]
        self.cap = [int(a["capacidad"]) for a in aulas]
        self.na = len(self.aulas)
        self.nd_doc = defaultdict(set, {d: set(s) for d, s in no_disp_docente.items()})
        self.nd_aula = defaultdict(set)
        self.construir()

    # ------------------------------------------------------------------ estructura
    def construir(self):
        """Variables = sesiones; dominios = pares (franja, aula); vecinos del PSR."""
        self.mat, self.doc, self.grp, self.carr, self.nombre, self.tam = [], [], [], [], [], []
        self.sesiones_de = defaultdict(list)
        for m in self.materias:
            for s in range(int(m["sesiones"])):
                self.sesiones_de[m["id"]].append(len(self.mat))
                self.mat.append(m["id"])
                self.doc.append(m["docente"])
                self.grp.append(m["grupo"])
                self.carr.append(m["carrera"])
                self.nombre.append(f'{m["id"]}.{s + 1}')
                self.tam.append(int(m["matricula"]))
        self.n = len(self.mat)
        self.docentes = sorted(set(self.doc))
        self.grupos = sorted(set(self.grp), key=lambda x: (len(x), x))
        self.vec = defaultdict(dict)
        for i in range(self.n):
            for j in range(i + 1, self.n):
                dF = self.doc[i] == self.doc[j] or self.grp[i] == self.grp[j]
                dD = self.mat[i] == self.mat[j]
                if dF or dD:
                    self.vec[i][j] = self.vec[j][i] = (dF, dD)
        self.actualizar_dominios()

    def actualizar_dominios(self):
        self.dominio = []
        for i in range(self.n):
            self.dominio.append([(f, a) for f in range(NF) if f not in self.nd_doc[self.doc[i]]
                                 for a in range(self.na)
                                 if self.cap[a] >= self.tam[i] and f not in self.nd_aula[a]])

    # ------------------------------------------------------------------ eventos
    def docente_no_disponible(self, docente, franjas):
        self.nd_doc[docente].update(franjas)
        self.actualizar_dominios()

    def aula_fuera_de_servicio(self, aula, franjas=None):
        self.nd_aula[self.aulas.index(aula)].update(range(NF) if franjas is None else franjas)
        self.actualizar_dominios()

    def cambiar_matricula(self, id_materia, nueva):
        for m in self.materias:
            if m["id"] == id_materia:
                m["matricula"] = int(nueva)
        for i in self.sesiones_de[id_materia]:
            self.tam[i] = int(nueva)
        self.actualizar_dominios()

    # ------------------------------------------------------------------ evaluacion
    def diagnostico(self, g):
        """Lista de (mensaje, sesiones) con cada restriccion obligatoria violada."""
        grupos = defaultdict(list)
        out = []
        for i, (f, a) in enumerate(g):
            grupos[("Docente", self.doc[i], f)].append(i)
            grupos[("Grupo", self.grp[i], f)].append(i)
            grupos[("Aula", self.aulas[a], f)].append(i)
            grupos[("Materia repetida en el dia", self.mat[i], f // HD)].append(i)
            if self.cap[a] < self.tam[i]:
                out.append((f"Capacidad insuficiente: {self.nombre[i]} ({self.tam[i]}) en "
                            f"{self.aulas[a]} ({self.cap[a]})", [i]))
            if f in self.nd_doc[self.doc[i]]:
                out.append((f"Docente {self.doc[i]} no disponible: {self.nombre[i]} en "
                            f"{etiqueta_franja(f)}", [i]))
            if f in self.nd_aula[a]:
                out.append((f"Aula {self.aulas[a]} fuera de servicio: {self.nombre[i]} en "
                            f"{etiqueta_franja(f)}", [i]))
        for (tipo, clave, f), lst in grupos.items():
            if len(lst) > 1:
                donde = DIAS[f] if tipo.startswith("Materia") else etiqueta_franja(f)
                out.append((f"{tipo} {clave} repetido en {donde}: "
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
            if self.cap[a] < self.tam[i]:
                n += 1
            if f in self.nd_doc[self.doc[i]]:
                n += 1
            if f in self.nd_aula[a]:
                n += 1
        return n + sum(v - 1 for cc in c for v in cc.values() if v > 1)

    def blandas(self, g):
        """Ventanas, concentracion excesiva y sesiones de una materia en dias consecutivos."""
        por = defaultdict(list)
        dias_mat = defaultdict(set)
        for i, (f, a) in enumerate(g):
            por[(self.grp[i], f // HD)].append(f % HD)
            dias_mat[self.mat[i]].add(f // HD)
        v = k = 0
        for horas in por.values():
            h = set(horas)
            v += max(h) - min(h) + 1 - len(h)
            k += max(0, len(horas) - MAX_DIA)
        s = sum(1 for ds in dias_mat.values() for d in ds if d + 1 in ds)
        return v, k, s

    def desperdicio(self, g):
        return sum((self.cap[a] - self.tam[i]) / self.cap[a]
                   for i, (f, a) in enumerate(g) if self.cap[a] >= self.tam[i])

    def penalizacion(self, g):
        v, k, s = self.blandas(g)
        return (PESO["conflicto"] * self.conflictos(g) + PESO["ventana"] * v
                + PESO["concentracion"] * k + PESO["separacion"] * s
                + PESO["desperdicio"] * self.desperdicio(g))

    def detalle(self, g):
        v, k, s = self.blandas(g)
        return {"conflictos": self.conflictos(g), "ventanas": v, "concentracion": k,
                "separacion": s, "desperdicio": round(self.desperdicio(g), 2),
                "penalizacion": round(self.penalizacion(g), 2)}
