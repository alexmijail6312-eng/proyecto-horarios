"""
Sistema de agentes.

Cada agente sigue el ciclo percibir -> decidir -> actuar sobre el entorno compartido.

  AgentePlanificador  basado en utilidad: genera el horario (PSR -> genetico -> busqueda local)
                      minimizando la penalizacion total.
  AgenteVerificador   basado en reglas: acepta, rechaza o senala el conflicto.
  AgenteReparador     basado en objetivos: ante un cambio del entorno, restituye la
                      consistencia con busqueda informada (A* ponderado) y, si no basta,
                      con re-planificacion parcial o total mediante PSR.
  Orquestador         coordina el ciclo de mantenimiento: evento -> verificacion -> reparacion.
"""
import time

from . import busqueda, genetico, local, psr
from .modelo import DIAS, HD, HORAS, NF, etiqueta_franja


def _etapa(nombre, ent, g, tiempo, **extra):
    d = {"etapa": nombre, "tiempo": round(tiempo, 3)}
    d.update(ent.detalle(g))
    d.update(extra)
    return d


# ---------------------------------------------------------------------------- verificador
class AgenteVerificador:
    nombre = "Verificador"

    def percibir(self, ent, g):
        self.ent, self.g = ent, g

    def actuar(self):
        diag = self.ent.diagnostico(self.g)
        if not diag:
            return {"veredicto": "aceptar", "conflictos": [], "detalle": self.ent.detalle(self.g)}
        return {"veredicto": "rechazar", "conflictos": [m for m, _ in diag],
                "detalle": self.ent.detalle(self.g)}

    def verificar(self, ent, g):
        self.percibir(ent, g)
        return self.actuar()


# ---------------------------------------------------------------------------- planificador
class AgentePlanificador:
    nombre = "Planificador"

    def __init__(self, poblacion=30, generaciones=80, metodo_local="sa", semilla=0):
        self.poblacion, self.generaciones = poblacion, generaciones
        self.metodo_local, self.semilla = metodo_local, semilla

    def percibir(self, ent):
        self.ent = ent

    def actuar(self):
        ent, etapas = self.ent, []
        g0, e = psr.resolver(ent, semilla=self.semilla)
        if g0 is None:
            return None, {"etapas": [], "error": "El PSR no encontro un horario completo."}
        etapas.append(_etapa("PSR (primera solucion)", ent, g0, e["tiempo"], nodos=e["nodos"]))
        g1, h_ga, e = genetico.evolucionar(ent, self.poblacion, self.generaciones, semilla=self.semilla)
        etapas.append(_etapa("Algoritmo genetico", ent, g1, e["tiempo"], evaluaciones=e["evaluaciones"]))
        if self.metodo_local == "hc":
            g2, h_ls, e = local.hill_climbing(ent, g1, semilla=self.semilla)
            nombre = "Hill climbing con reinicios"
        else:
            g2, h_ls, e = local.recocido(ent, g1, semilla=self.semilla)
            nombre = "Recocido simulado"
        etapas.append(_etapa(nombre, ent, g2, e["tiempo"], pasos=e["pasos"]))
        return g2, {"etapas": etapas, "historia_ga": h_ga, "historia_local": h_ls}

    def planificar(self, ent):
        self.percibir(ent)
        return self.actuar()


# ---------------------------------------------------------------------------- reparador
class AgenteReparador:
    nombre = "Reparador"

    def percibir(self, ent, g):
        self.ent, self.g = ent, list(g)

    def actuar(self, pulir=True):
        ent, g = self.ent, self.g
        t0 = time.time()
        info = {"metodo": None, "nodos": 0, "resuelto": False}
        nueva, e = busqueda.reparar(ent, g)
        info.update(metodo="A* ponderado", nodos=e["nodos"], h_inicial=e.get("h_inicial"))
        if nueva is None:
            malas = {i for _, ids in ent.diagnostico(g) for i in ids}
            libres = set(malas)
            for i in malas:
                libres.update(ent.vec[i].keys())
            fijos = {i: g[i] for i in range(ent.n) if i not in libres}
            nueva, e = psr.resolver(ent, fijos=fijos)
            info.update(metodo="PSR parcial", nodos=info["nodos"] + e["nodos"])
        if nueva is None:
            nueva, e = psr.resolver(ent)
            info.update(metodo="PSR completo", nodos=info["nodos"] + e["nodos"])
        if nueva is None:
            info.update(tiempo=time.time() - t0, movidas=0)
            return g, info
        movidas = [i for i in range(ent.n) if g[i] != nueva[i]]
        if pulir and 0 < len(movidas) <= 8:                    # mejora solo lo que se movio
            nueva = busqueda.pulir_sesiones(ent, nueva, movidas)
        info.update(resuelto=True, tiempo=time.time() - t0,
                    movidas=sum(1 for a, b in zip(g, nueva) if a != b))
        return nueva, info

    def reparar(self, ent, g, pulir=True):
        self.percibir(ent, g)
        return self.actuar(pulir)


# ---------------------------------------------------------------------------- orquestador
class Orquestador:
    def __init__(self, ent, semilla=0):
        self.ent, self.semilla = ent, semilla
        self.g = None
        self.anterior = None
        self.log, self.eventos, self.etapas = [], [], []
        self.historia_ga, self.historia_local = [], []
        self.verificador, self.reparador = AgenteVerificador(), AgenteReparador()

    def registrar(self, agente, texto):
        self.log.append({"t": time.strftime("%H:%M:%S"), "agente": agente, "texto": texto})

    def planificar(self, metodo_local="sa", generaciones=80, poblacion=30, semilla=None):
        plan = AgentePlanificador(poblacion, generaciones, metodo_local,
                                  self.semilla if semilla is None else semilla)
        self.registrar(plan.nombre, f"Planificando {self.ent.n} sesiones con {self.ent.na} aulas")
        g, info = plan.planificar(self.ent)
        if g is None:
            self.registrar(plan.nombre, info["error"])
            return False
        self.g, self.anterior = g, None
        self.etapas = info["etapas"]
        self.historia_ga, self.historia_local = info["historia_ga"], info["historia_local"]
        for e in self.etapas:
            self.registrar(plan.nombre, f'{e["etapa"]}: penalizacion {e["penalizacion"]}, '
                                        f'conflictos {e["conflictos"]}, {e["tiempo"]} s')
        v = self.verificador.verificar(self.ent, self.g)
        self.registrar(self.verificador.nombre, f'Veredicto: {v["veredicto"]}')
        return True

    def sugerir_sorpresa(self):
        """Un docente con carga alta pierde dos de las franjas en las que dicta clase."""
        ent = self.ent
        docente = max(ent.docentes, key=lambda d: sum(1 for x in ent.doc if x == d))
        franjas = sorted(f for i, (f, _) in enumerate(self.g) if ent.doc[i] == docente)[:2]
        return {"tipo": "docente_no_disponible", "docente": docente, "franjas": franjas}

    def aplicar_evento(self, tipo, **p):
        ent = self.ent
        if self.g is None:
            raise ValueError("Primero se debe planificar el horario.")
        self.anterior = list(self.g)
        if tipo == "docente_no_disponible":
            ent.docente_no_disponible(p["docente"], p["franjas"])
            desc = f'Docente {p["docente"]} no disponible en ' + ", ".join(etiqueta_franja(f) for f in p["franjas"])
        elif tipo == "aula_fuera_de_servicio":
            ent.aula_fuera_de_servicio(p["aula"], p.get("franjas"))
            desc = f'Aula {p["aula"]} fuera de servicio' + ("" if p.get("franjas") is None else
                   " en " + ", ".join(etiqueta_franja(f) for f in p["franjas"]))
        elif tipo == "cambio_matricula":
            ent.cambiar_matricula(p["materia"], p["matricula"])
            desc = f'Matricula de {p["materia"]} cambia a {p["matricula"]}'
        else:
            raise ValueError(f"Evento desconocido: {tipo}")
        self.registrar("Entorno", f"Evento: {desc}")
        v = self.verificador.verificar(ent, self.g)
        res = {"evento": desc, "conflictos_tras_evento": len(v["conflictos"]), "metodo": None,
               "tiempo": 0.0, "movidas": 0, "nodos": 0, "resuelto": True}
        if v["veredicto"] == "aceptar":
            self.registrar(self.verificador.nombre, "El horario sigue siendo consistente; no se requieren cambios")
        else:
            self.registrar(self.verificador.nombre,
                           f'Rechazado: {len(v["conflictos"])} conflicto(s). ' + "; ".join(v["conflictos"][:3]))
            self.g, info = self.reparador.reparar(ent, self.g)
            res.update(metodo=info["metodo"], tiempo=round(info["tiempo"], 4), movidas=info["movidas"],
                       nodos=info["nodos"], resuelto=info["resuelto"])
            if info["resuelto"]:
                self.registrar(self.reparador.nombre, f'Reparado con {info["metodo"]}: {info["movidas"]} sesion(es) '
                               f'movida(s), {info["nodos"]} nodos, {info["tiempo"]:.3f} s')
            else:
                self.registrar(self.reparador.nombre, "No fue posible restituir la consistencia con los datos actuales")
        res["detalle"] = ent.detalle(self.g)
        self.eventos.append(res)
        return res

    def estado(self):
        e, g = self.ent, self.g
        nombres = {m["id"]: m["nombre"] for m in e.materias}
        malas, mensajes = set(), []
        if g:
            diag = e.diagnostico(g)
            malas = {i for _, ids in diag for i in ids}
            mensajes = [m for m, _ in diag][:30]
        sesiones = []
        for i in range(e.n):
            s = {"id": i, "sesion": e.nombre[i], "materia": e.mat[i], "nombre": nombres[e.mat[i]],
                 "grupo": e.grp[i], "carrera": e.carr[i], "docente": e.doc[i], "matricula": e.tam[i]}
            if g:
                f, a = g[i]
                s.update(franja=f, dia=f // HD, hora=f % HD, aula=e.aulas[a], conflicto=i in malas,
                         movida=self.anterior is not None and self.anterior[i] != g[i])
            sesiones.append(s)
        return {
            "dias": DIAS, "horas": HORAS,
            "resumen": {"materias": len(e.materias), "sesiones": e.n, "aulas": e.na, "docentes": len(e.docentes),
                        "grupos": len(e.grupos), "franjas": NF},
            "docentes": e.docentes, "grupos": e.grupos,
            "aulas": [{"aula": a, "capacidad": c} for a, c in zip(e.aulas, e.cap)],
            "materias": [{"id": m["id"], "nombre": m["nombre"], "matricula": int(m["matricula"])} for m in e.materias],
            "nd_docente": {d: sorted(s) for d, s in e.nd_doc.items() if s},
            "nd_aula": {e.aulas[a]: sorted(s) for a, s in e.nd_aula.items() if s},
            "planificado": g is not None, "sesiones": sesiones,
            "metricas": e.detalle(g) if g else None,
            "veredicto": ("aceptar" if not mensajes else "rechazar") if g else None, "mensajes": mensajes,
            "etapas": self.etapas, "historia_ga": self.historia_ga, "historia_local": self.historia_local,
            "eventos": self.eventos, "log": self.log[-120:],
        }
