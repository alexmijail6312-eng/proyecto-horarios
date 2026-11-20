"""
Sistema de agentes para generar y mantener horarios academicos.

  python main.py generar --materias 20 --carpeta datos
  python main.py resolver --carpeta datos --sorpresa
  python main.py resolver --materias 40 --local hc --no-disp D03:4,8
  python main.py experimentos --repeticiones 3
  python main.py gui
  python main.py pruebas
"""
import argparse
import os
import sys
import unittest

from horarios import datos, experimentos, salida
from horarios.agentes import Orquestador


def cmd_generar(a):
    datos.generar(a.carpeta, a.materias, a.semilla)
    print(f"Datos generados en {a.carpeta}/ (materias, docentes, aulas y franjas)")


def cmd_resolver(a):
    if a.regenerar or not os.path.exists(os.path.join(a.carpeta, "materias.csv")):
        datos.generar(a.carpeta, a.materias, a.semilla)
        print(f"Datos generados en {a.carpeta}/")
    try:
        ent = datos.cargar(a.carpeta)
    except ValueError as e:
        print("Error en los datos:", e)
        print("Tambien puede usar la opcion --regenerar para sobrescribir la carpeta.")
        return 1
    print(f"Entorno: {len(ent.materias)} materias, {ent.n} sesiones, {len(ent.docentes)} docentes, "
          f"{ent.na} aulas, {len(ent.grupos)} grupos")
    ref = datos.horario_referencia(ent)
    print("Referencia manual simulada:", ent.detalle(ref))
    o = Orquestador(ent, a.semilla)
    if not o.planificar(a.local):
        print("No se encontro un horario completo.")
        return 1
    print("\n" + salida.tabla_etapas(o.etapas))
    for g in ent.grupos[:a.grupos]:
        print("\n" + salida.grilla_texto(ent, o.g, "grupo", g))
    os.makedirs(a.salida, exist_ok=True)
    datos.guardar_horario(ent, o.g, os.path.join(a.salida, "horario.csv"))
    print(f"\nHorario guardado en {a.salida}/horario.csv")
    ev = None
    if a.sorpresa:
        ev = o.sugerir_sorpresa()
    elif a.no_disp:
        d, f = a.no_disp.split(":")
        ev = {"tipo": "docente_no_disponible", "docente": d, "franjas": [int(x) for x in f.split(",")]}
    if ev:
        r = o.aplicar_evento(**ev)
        print(f"\nEvento: {r['evento']}")
        print(f"Conflictos tras el evento: {r['conflictos_tras_evento']}")
        print(f"Reparacion con {r['metodo']}: {r['movidas']} sesiones movidas, {r['nodos']} nodos, "
              f"{r['tiempo']} s, resuelto: {r['resuelto']}")
        print("Metricas finales:", r["detalle"])
    print("\nRegistro de los agentes:")
    for l in o.log:
        print(f"  {l['t']} [{l['agente']}] {l['texto']}")
    return 0


def cmd_experimentos(a):
    res = experimentos.correr(a.repeticiones, a.semilla, a.salida, callback=lambda m: print(" ", m))
    experimentos.imprimir(res)
    print(f"\nResultados guardados en {a.salida}/ (JSON, CSV y graficos)")


def cmd_gui(a):
    from horarios import servidor
    servidor.servir(a.puerto, not a.sin_navegador)


def cmd_pruebas(a):
    suite = unittest.defaultTestLoader.discover(os.path.dirname(os.path.abspath(__file__)), pattern="pruebas.py")
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar"); g.set_defaults(f=cmd_generar)
    g.add_argument("--materias", type=int, default=20); g.add_argument("--carpeta", default="datos")
    g.add_argument("--semilla", type=int, default=1)
    r = sub.add_parser("resolver"); r.set_defaults(f=cmd_resolver)
    r.add_argument("--carpeta", default="datos"); r.add_argument("--materias", type=int, default=20)
    r.add_argument("--semilla", type=int, default=1); r.add_argument("--local", choices=["sa", "hc"], default="sa")
    r.add_argument("--grupos", type=int, default=2, help="cantidad de grillas de grupo a mostrar")
    r.add_argument("--salida", default="resultados")
    r.add_argument("--regenerar", action="store_true", help="vuelve a generar los CSV de la carpeta de datos")
    r.add_argument("--sorpresa", action="store_true", help="un docente con carga alta deja de estar disponible")
    r.add_argument("--no-disp", help="docente y franjas no disponibles, ejemplo D03:4,8")
    e = sub.add_parser("experimentos"); e.set_defaults(f=cmd_experimentos)
    e.add_argument("--repeticiones", type=int, default=3); e.add_argument("--semilla", type=int, default=1)
    e.add_argument("--salida", default="resultados")
    u = sub.add_parser("gui"); u.set_defaults(f=cmd_gui)
    u.add_argument("--puerto", type=int, default=8000); u.add_argument("--sin-navegador", action="store_true")
    p = sub.add_parser("pruebas"); p.set_defaults(f=cmd_pruebas)
    a = ap.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
