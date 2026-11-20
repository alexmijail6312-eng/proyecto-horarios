"""Presentacion del horario en texto plano (grilla por grupo, docente o aula)."""
from .modelo import DIAS, HD, HORAS


def grilla_texto(ent, g, tipo="grupo", item=None):
    """Devuelve la grilla de un grupo, docente o aula como texto."""
    clave = {"grupo": ent.grp, "docente": ent.doc, "aula": [ent.aulas[a] for _, a in g]}[tipo]
    if item is None:
        item = {"grupo": ent.grupos, "docente": ent.docentes, "aula": ent.aulas}[tipo][0]
    celdas = {}
    for i, (f, a) in enumerate(g):
        if clave[i] == item:
            extra = ent.aulas[a] if tipo != "aula" else ent.grp[i]
            celdas.setdefault((f // HD, f % HD), []).append(f"{ent.mat[i]} {extra}")
    ancho = 12
    lineas = [f"{tipo.capitalize()} {item}",
              "Hora  | " + " | ".join(f"{d:^{ancho}}" for d in DIAS),
              "------+-" + "-+-".join("-" * ancho for _ in DIAS)]
    for h in range(HD):
        lineas.append(f"{HORAS[h]} | " + " | ".join(
            f"{'/'.join(celdas.get((d, h), [])):^{ancho}}" for d in range(len(DIAS))))
    return "\n".join(lineas)


def tabla_etapas(etapas):
    out = [f'{"Etapa":<32}{"Conf":>5}{"Vent":>6}{"Conc":>6}{"Sep":>5}{"Penaliz.":>10}{"Tiempo s":>10}']
    for e in etapas:
        out.append(f'{e["etapa"]:<32}{e["conflictos"]:>5}{e["ventanas"]:>6}{e["concentracion"]:>6}'
                   f'{e["separacion"]:>5}{e["penalizacion"]:>10.2f}{e["tiempo"]:>10.3f}')
    return "\n".join(out)
