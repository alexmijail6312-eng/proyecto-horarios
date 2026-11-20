"""Generacion, lectura y escritura de datos en formato CSV."""
import csv
import math
import os
import random

from .modelo import DIAS, HORAS, HD, NF, Entorno

TAMANOS = {"pocas": 8, "medianas": 20, "muchas": 40}
CARRERAS = ["Sistemas", "Industrial", "Civil"]


def escribir(ruta, campos, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(campos)
        w.writerows(filas)


def leer(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def generar_tablas(n_materias, semilla=1, tension=False):
    """
    Devuelve (materias, docentes, aulas) como listas de listas, listas para escribir en CSV.
    tension=True genera un problema ajustado: pocas aulas y docentes con mucha indisponibilidad.
    """
    rng = random.Random(semilla)
    n_grupos = max(2, math.ceil(n_materias / 5))
    n_docentes = max(3, math.ceil(n_materias * 0.6))
    materias = []
    for m in range(n_materias):
        g = m % n_grupos
        materias.append([f"M{m + 1:02d}", f"Materia {m + 1}", CARRERAS[g % 3], f"G{g + 1}",
                         f"D{rng.randrange(n_docentes) + 1:02d}", rng.choice([2, 2, 3]),
                         rng.choice([20, 25, 30, 35, 40, 45, 50, 60, 70])])
    docentes = [[f"D{d + 1:02d}", ";".join(map(str, sorted(rng.sample(range(NF), 12 if tension else 3))))]
                for d in range(n_docentes)]
    total = sum(m[5] for m in materias)
    n_aulas = max(3, math.ceil(total / NF * (1.2 if tension else 2.2)))
    caps = [100, 60, 50, 80, 40, 30, 60]   # siempre hay un aula para la matricula maxima
    aulas = [[f"A{a + 1:02d}", caps[a % len(caps)]] for a in range(n_aulas)]
    return materias, docentes, aulas


CAMPOS = {
    "materias": ["id", "nombre", "carrera", "grupo", "docente", "sesiones", "matricula"],
    "docentes": ["docente", "no_disponible"],
    "aulas": ["aula", "capacidad"],
}


def generar(carpeta, n_materias, semilla=1):
    os.makedirs(carpeta, exist_ok=True)
    materias, docentes, aulas = generar_tablas(n_materias, semilla)
    escribir(os.path.join(carpeta, "materias.csv"), CAMPOS["materias"], materias)
    escribir(os.path.join(carpeta, "docentes.csv"), CAMPOS["docentes"], docentes)
    escribir(os.path.join(carpeta, "aulas.csv"), CAMPOS["aulas"], aulas)
    escribir(os.path.join(carpeta, "franjas.csv"), ["franja", "dia", "hora"],
             [[f, DIAS[f // HD], HORAS[f % HD]] for f in range(NF)])


def entorno_desde_tablas(materias, docentes, aulas):
    return Entorno(
        [dict(zip(CAMPOS["materias"], m)) for m in materias],
        {d[0]: {int(x) for x in str(d[1]).split(";") if x != ""} for d in docentes},
        [dict(zip(CAMPOS["aulas"], a)) for a in aulas])


def generar_entorno(n_materias, semilla=1, tension=False):
    return entorno_desde_tablas(*generar_tablas(n_materias, semilla, tension))


def _leer_validado(carpeta, nombre):
    ruta = os.path.join(carpeta, f"{nombre}.csv")
    filas = leer(ruta)
    faltan = [c for c in CAMPOS[nombre] if filas and c not in filas[0]]
    if faltan:
        raise ValueError(
            f"{ruta} no tiene las columnas: {', '.join(faltan)}. Es probable que sea de una version anterior. "
            f"Regenere los datos con: python main.py generar --carpeta {carpeta} --materias 20")
    return filas


def cargar(carpeta):
    docentes = _leer_validado(carpeta, "docentes")
    nd = {r["docente"]: {int(x) for x in r["no_disponible"].split(";") if x} for r in docentes}
    return Entorno(_leer_validado(carpeta, "materias"), nd, _leer_validado(carpeta, "aulas"))


def guardar_horario(ent, g, ruta):
    filas = [[ent.nombre[i], ent.mat[i], ent.grp[i], ent.carr[i], ent.doc[i], DIAS[f // HD],
              HORAS[f % HD], f, ent.aulas[a]] for i, (f, a) in enumerate(g)]
    escribir(ruta, ["sesion", "materia", "grupo", "carrera", "docente", "dia", "hora", "franja", "aula"],
             filas)


def cargar_horario(ent, ruta):
    """Lee un horario (por ejemplo, uno armado a mano) con columnas sesion, franja y aula."""
    datos = {r["sesion"]: (int(r["franja"]), ent.aulas.index(r["aula"])) for r in leer(ruta)}
    return [datos[nombre] for nombre in ent.nombre]


def horario_referencia(ent):
    """Referencia manual simulada: cada sesion va a la primera franja y aula libres, sin optimizar."""
    g = []
    for i in range(ent.n):
        elegido = ent.dominio[i][0] if ent.dominio[i] else (0, 0)
        for v in ent.dominio[i]:
            if all(g[j] != v
                   and not ((ent.doc[i] == ent.doc[j] or ent.grp[i] == ent.grp[j]) and g[j][0] == v[0])
                   and not (ent.mat[i] == ent.mat[j] and g[j][0] // HD == v[0] // HD)
                   for j in range(len(g))):
                elegido = v
                break
        g.append(elegido)
    return g
