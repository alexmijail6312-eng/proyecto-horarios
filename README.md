# Sistema de agentes para horarios academicos

Genera, verifica y mantiene el horario de clases de una institucion. Python 3.8 o superior, sin dependencias obligatorias.

## Uso

```
python main.py gui                                  interfaz visual en http://127.0.0.1:8000
python main.py resolver --materias 20 --sorpresa    pipeline completo y cambio sorpresa en consola
python main.py resolver --carpeta datos --local hc  datos propios en CSV y hill climbing
python main.py experimentos --repeticiones 3        tres tamanos, comparaciones y graficos
python main.py pruebas                              pruebas automaticas
python main.py generar --materias 40 --carpeta datos
python main.py resolver --materias 20 --regenerar   sobrescribe los CSV de la carpeta datos
```

Si aparece un error de columnas faltantes en `datos`, la carpeta es de una version anterior: use `--regenerar`
o borre la carpeta `datos`.

Los graficos de `experimentos` y del notebook requieren `pip install matplotlib` (opcional).
El cuaderno `proyecto_agente.ipynb` ejecuta el mismo flujo paso a paso.

## Entorno

| Propiedad | Clasificacion | Justificacion |
|---|---|---|
| Observabilidad | Totalmente observable | Materias, docentes, aulas, franjas y matricula se cargan desde CSV antes de planificar. |
| Determinismo | Determinista | Cada accion (asignar o mover una sesion) tiene un unico resultado. |
| Dinamica | Estatico durante la planificacion | Cambia solo con eventos externos: docente o aula no disponible, cambio de matricula. |
| Valores | Discreto | Sesiones, franjas y aulas son conjuntos finitos. |
| Secuencialidad | Secuencial | Cada asignacion limita las siguientes. |

## Agentes

| Agente | Tipo | Percibe | Actua |
|---|---|---|---|
| Planificador | Basado en utilidad | Restricciones, matricula, disponibilidad | Propone el horario completo (PSR, genetico, busqueda local) |
| Verificador | Basado en reglas | Un horario propuesto | Acepta, rechaza o senala el conflicto |
| Reparador | Basado en objetivos | Horario y cambio del entorno | Repara con A* ponderado; si no basta, replanifica con PSR |
| Orquestador | Coordinador | Eventos del entorno | Ciclo evento, verificacion, reparacion |

## Tecnicas seleccionadas

| Tecnica | Uso | Motivo |
|---|---|---|
| D. PSR | Modelo de las reglas obligatorias; AC-3, backtracking, MRV y comprobacion hacia adelante | Las reglas del horario son restricciones sobre variables discretas |
| C. Busqueda local y geneticos | Optimizacion de la calidad (ventanas, concentracion, separacion, desperdicio) | Existen muchas soluciones validas de distinta calidad |
| B. Busqueda informada | Reparacion tras un evento con A* ponderado; heuristica = restricciones violadas | Se busca la reparacion con pocos movimientos y rapida |
| A. Busqueda no informada | No se usa | El espacio es demasiado grande para exploracion ciega |
| E. Redes bayesianas | No se usa | El entorno es totalmente observable: no hay incertidumbre que modelar |
| F. PDM | No se usa | No hay dinamica estocastica ni recompensas acumuladas |

## Estructura

```
main.py                   comandos
pruebas.py                9 pruebas automaticas
proyecto_agente.ipynb     cuaderno de ejecucion
horarios/modelo.py        entorno, restricciones y penalizacion
horarios/datos.py         generacion y lectura de CSV, horario de referencia
horarios/psr.py           AC-3 y backtracking con MRV
horarios/genetico.py      algoritmo genetico
horarios/local.py         recocido simulado y hill climbing
horarios/busqueda.py      A* ponderado para reparar
horarios/agentes.py       planificador, verificador, reparador y orquestador
horarios/experimentos.py  experimentacion y graficos
horarios/servidor.py      servidor de la interfaz visual
horarios/salida.py        grillas en texto
web/index.html            interfaz visual
CAPTURAS.md               lista de capturas para el documento
```

## Notas

- Los datos de ejemplo son sinteticos. Para datos reales basta reemplazar los CSV de la carpeta `datos`
  (materias, docentes, aulas) con las mismas columnas.
- La referencia manual es una simulacion (cada sesion a la primera franja y aula libres). Si se dispone de un horario
  real armado a mano, `datos.cargar_horario` lo lee desde un CSV con columnas `sesion`, `franja` y `aula`.
- Funcion de penalizacion: 1000 por conflicto, 5 por ventana, 3 por concentracion excesiva, 2 por sesiones de una
  materia en dias consecutivos y 2 por fraccion de capacidad de aula desperdiciada.
