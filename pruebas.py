"""Pruebas automaticas del sistema (python main.py pruebas)."""
import unittest

from horarios import busqueda, datos, genetico, local, psr
from horarios.agentes import AgenteVerificador, Orquestador


class PruebasHorarios(unittest.TestCase):
    def setUp(self):
        self.ent = datos.generar_entorno(10, 3)

    def test_psr_sin_conflictos(self):
        g, est = psr.resolver(self.ent)
        self.assertIsNotNone(g)
        self.assertEqual(self.ent.conflictos(g), 0)
        self.assertTrue(est["resuelto"])

    def test_verificador_detecta_conflicto(self):
        g, _ = psr.resolver(self.ent)
        self.assertEqual(AgenteVerificador().verificar(self.ent, g)["veredicto"], "aceptar")
        mala = list(g)
        mala[1] = mala[0]                                   # misma franja y aula para dos sesiones
        inf = AgenteVerificador().verificar(self.ent, mala)
        self.assertEqual(inf["veredicto"], "rechazar")
        self.assertTrue(inf["conflictos"])

    def test_genetico_no_empeora_y_es_factible(self):
        g0, _ = psr.resolver(self.ent, semilla=3000)
        g, hist, _ = genetico.evolucionar(self.ent, generaciones=20, semilla=3)
        self.assertEqual(self.ent.conflictos(g), 0)
        self.assertLessEqual(hist[-1]["mejor"], hist[0]["mejor"])

    def test_busqueda_local_mantiene_factibilidad(self):
        g, _ = psr.resolver(self.ent)
        for metodo in (local.recocido, local.hill_climbing):
            h = metodo(self.ent, g)[0]
            self.assertEqual(self.ent.conflictos(h), 0)
            self.assertLessEqual(self.ent.penalizacion(h), self.ent.penalizacion(g))

    def test_reparacion_astar(self):
        o = Orquestador(self.ent)
        self.assertTrue(o.planificar(generaciones=15))
        r = o.aplicar_evento(**o.sugerir_sorpresa())
        self.assertGreater(r["conflictos_tras_evento"], 0)
        self.assertTrue(r["resuelto"])
        self.assertEqual(self.ent.conflictos(o.g), 0)
        self.assertLessEqual(r["movidas"], r["conflictos_tras_evento"] + 2)

    def test_evento_sin_efecto(self):
        o = Orquestador(self.ent)
        o.planificar(generaciones=10)
        libre = [f for f in range(30) if all(o.g[i][0] != f for i in range(self.ent.n))]
        if libre:
            r = o.aplicar_evento("docente_no_disponible", docente=self.ent.docentes[0], franjas=libre[:1])
            self.assertEqual(r["conflictos_tras_evento"], 0)

    def test_matricula_imposible_se_informa(self):
        o = Orquestador(self.ent)
        o.planificar(generaciones=10)
        r = o.aplicar_evento("cambio_matricula", materia="M01", matricula=500)
        self.assertFalse(r["resuelto"])

    def test_replanificacion_parcial_conserva_sesiones(self):
        g, _ = psr.resolver(self.ent)
        fijos = {i: g[i] for i in range(2, self.ent.n)}
        h, est = psr.resolver(self.ent, fijos=fijos)
        self.assertIsNotNone(h)
        self.assertTrue(all(h[i] == g[i] for i in fijos))

    def test_horario_csv(self):
        import os, tempfile
        g, _ = psr.resolver(self.ent)
        ruta = os.path.join(tempfile.mkdtemp(), "h.csv")
        datos.guardar_horario(self.ent, g, ruta)
        self.assertEqual(datos.cargar_horario(self.ent, ruta), g)


if __name__ == "__main__":
    unittest.main()
