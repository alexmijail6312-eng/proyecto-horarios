# Capturas previstas para el documento

Cada captura indica la seccion del formato, que mostrar y como obtenerla.
Comando de la interfaz: `python main.py gui`. Archivo sugerido entre parentesis.

| Seccion | Captura | Como obtenerla |
|---|---|---|
| III.D Arquitectura | Diagrama del agente (sensores, mecanismo de decision, actuadores y entorno) | Se elabora aparte a partir de la tabla de agentes del README |
| VI. Evidencias | Estructura de carpetas del proyecto (cap_01_estructura) | Explorador de archivos o comando `tree` |
| VI. Evidencias | Ejecucion de las pruebas automaticas, 9 pruebas correctas (cap_02_pruebas) | `python main.py pruebas` |
| VI. Evidencias | Ejecucion en consola del pipeline (cap_03_consola) | `python main.py resolver --materias 20 --sorpresa` |
| VI. Evidencias | Interfaz con el entorno generado, antes de planificar (cap_04_gui_entorno) | Abrir la interfaz y pulsar "Generar datos" |
| VI. Evidencias | Interfaz con el horario planificado, vista por grupo (cap_05_gui_horario) | Pulsar "Planificar horario" |
| VI. Evidencias | Vista por docente con celdas no disponibles (cap_06_gui_docente) | Cambiar "Vista" a docente tras aplicar un evento de docente |
| VI. Evidencias | Vista por aula (cap_07_gui_aula) | Cambiar "Vista" a aula |
| VI. Evidencias | Archivos CSV de entrada abiertos (cap_08_csv) | Carpeta `datos` tras `python main.py generar` |
| VII. Escenario pocas | Metricas y etapas con 8 materias (cap_09_esc_pocas) | Materias = 8, Generar datos, Planificar |
| VII. Escenario medianas | Metricas y etapas con 20 materias (cap_10_esc_medianas) | Materias = 20 |
| VII. Escenario muchas | Metricas y etapas con 40 materias (cap_11_esc_muchas) | Materias = 40 |
| VII. Convergencia | Paneles de convergencia del genetico y de la busqueda local (cap_12_convergencia) | Tras planificar, paneles inferiores |
| VII. Cambio sorpresa | Horario tras la reparacion, con sesiones movidas en gris y registro de los agentes (cap_13_sorpresa) | Pulsar "Cambio sorpresa" |
| VII. Otros eventos | Evento de aula fuera de servicio y su reparacion (cap_14_evento_aula) | Evento "Aula fuera de servicio" |
| VII. Otros eventos | Cambio de matricula imposible de atender, con el mensaje del registro (cap_15_evento_imposible) | Evento "Cambio de matricula" con un valor mayor a la capacidad maxima |
| VII. Comparacion | Tablas de calidad, PSR y cambio sorpresa (cap_16_tablas) | "Ejecutar experimentos" |
| VII. Comparacion | Grafico de convergencia y grafico comparativo por metodo (cap_17_graficos) | Archivos `resultados/convergencia.png` y `resultados/comparacion.png` |
| Anexos | Cuaderno ejecutado (cap_18_notebook) | Abrir `proyecto_agente.ipynb` y ejecutar todas las celdas |
