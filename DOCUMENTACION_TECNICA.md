# Documentación técnica del proyecto SismoLab

## 1. Objetivo general del sistema

Este proyecto simula un sistema de gestión de eventos sísmicos con estas responsabilidades principales:

- guardar eventos activos en un árbol ordenado por prioridad,
- aceptar correcciones o reportes de estaciones,
- detectar conflictos entre revisiones,
- archivar ramas antiguas cuando cumplen condiciones,
- calcular asociaciones entre eventos relacionados,
- exportar/importar el estado del sistema,
- ofrecer una interfaz gráfica con pygame para visualizar y manipular el árbol.

La pieza central es un árbol AVL que ordena los eventos según una clave compuesta por:

- prioridad del evento,
- magnitud,
- identificador.

Esto permite mantener un acceso eficiente, buscar un evento por clave y mantener el árbol balanceado.

---

## 2. Arquitectura general

El sistema se compone de varias capas:

1. Modelo de datos
   - `Evento`
   - `Clave`
   - `Reporte`
   - `Zona`
   - `Escenario`

2. Estructura de almacenamiento
   - `AVL` y `BST`
   - `Nodo`
   - `GestorHistorico`
   - `ColaReportes`

3. Lógica de negocio
   - `GestorEventos`
   - `procesar_reporte`
   - `asociaciones.py`
   - `auditoria.py`

4. Persistencia y estado
   - `EstadoOperativo`
   - `serializar_estado` / `reconstruir_estado`
   - `persistencia.py`
   - `PilaDeshacer`

5. Interfaz gráfica
   - `pygame_app.py`
   - `gui/app.py`
   - `gui/contexto.py`
   - `gui/simulador.py`
   - `gui/vista_arbol.py`

A nivel conceptual, el flujo típico es:

- un evento llega como dato crudo,
- se valida,
- se crea la clave y se inserta en el AVL,
- el árbol ordena y equilibra automáticamente,
- los reportes se acumulan en una cola,
- se procesan para aprobar, descartar o actualizar eventos,
- la rama antigua puede archivarse,
- el estado se puede guardar o deshacer.

---

## 3. Módulos principales y qué hace cada uno

### 3.1 `AVL.py`

Es la implementación principal del árbol balanceado.

Funciones principales:

- `__init__`: inicializa la raíz, el índice de nodos y métricas.
- `_obtener_altura`: devuelve la altura del nodo.
- `_actualizar_altura`: recalcula altura y factor de balance.
- `_factor_balance`: calcula la diferencia entre subárbol izquierdo y derecho.
- `_rotacion_derecha` / `_rotacion_izquierda`: rotaciones AVL para restaurar equilibrio.
- `insertar`: inserta una clave y reequilibra si el modo es `normal`.
- `_insertar`: inserción recursiva con soporte para desbalance y balanceo.
- `_balancear`: aplica los casos LL, RR, LR, RL.
- `eliminar`: elimina una clave y rebalancea.
- `_balancear_despues_de_eliminar`: gestiona rotaciones tras borrado.
- `recuperar_equilibrio`: intenta reconstruir el árbol sin pérdida de orden.

Qué aporta al sistema:

- mantiene los eventos ordenados por prioridad/magnitud/ID,
- garantiza altura logarítmica en modo normal,
- registra métricas de rotaciones y casos de balance.

Es el núcleo del proyecto, porque casi todo gira alrededor de este árbol.

---

### 3.2 `BST.py`

Define una variante sin rebalanceo.

- hereda de `AVL`, pero fuerza el modo `estres`.
- `modo` solo acepta `estres`.
- `recuperar_equilibrio` no está implementado porque no hay balanceo AVL.

Qué aporta:

- permite simular el mismo árbol bajo carga, sin rotaciones,
- útil para pruebas o escenarios de estrés donde se quiere ver cómo responde una estructura no balanceada.

---

### 3.3 `Nodo.py`

Representa un nodo del árbol.

Atributos:

- `clave`: objeto de tipo `Clave`.
- `izquierda`, `derecha`: hijos del árbol.
- `altura`: altura del subárbol.
- `factor_balance`: diferencia de alturas.
- `acceso_costoso`: marca nodos con acceso más costoso para visualización o auditoría.

Métodos:

- `es_hoja`: indica si el nodo no tiene hijos.
- `__repr__`: representación útil para depuración.

Es la unidad concreta que el árbol guarda.

---

### 3.4 `clave.py`

Define el criterio de orden del árbol.

- `Clave(prioridad, magnitud, identificador)`
- `__lt__`: compara primero prioridad, luego magnitud, luego id.
- `__eq__`: compara la misma terna.

Esto es crucial porque permite que el AVL mantenga orden total y estable.

Un árbol ordenado por prioridad suele preferir primero los eventos más críticos. La comparación sigue el orden:

1. prioridad más baja primero,
2. luego mayor magnitud,
3. luego menor id como desempate.

---

### 3.5 `evento.py`

Define el modelo de un evento sísmico.

Atributos principales:

- `identificador`
- `magnitud`
- `profundidad`
- `epicentro`
- `fecha`
- `revision`
- `estado`
- `en_zona_poblada`
- `estaciones`: conjunto de estaciones que han reportado el evento.

Métodos importantes:

- `__str__`: cadena legible del evento.
- `_normalizar_dato`: normaliza valores para comparar fechas, coordenadas y magnitudes con precisión controlada.
- `datos_iguales`: compara si dos eventos tienen el mismo contenido esencial.
- `agregar_estacion`: añade una estación emisora al evento.

La función `calcular_prioridad` devuelve un valor 1, 2 o 3 según la severidad del sismo:

- 3: magnitud muy alta o combinación grave con profundidad baja y zona poblada.
- 2: magnitud moderada.
- 1: menor prioridad.

Este valor es la base para la clave del árbol.

---

### 3.6 `escenario.py`

Representa el entorno del simulador.

Clases:

- `Zona`: dataclass con límites x/y y bandera `poblada`.
- `Escenario`: contiene reloj, zonas y parámetros globales W, R, L, T.

Funciones y responsabilidad:

- validar parámetros numéricos,
- normalizar zonas desde dicts, tuplas o `Zona`,
- avanzar el reloj,
- determinar si un punto pertenece a una zona poblada,
- controlar el modo `normal` o `estres` del escenario.

Parámetros clave:

- `W`: ancho temporal de ventana para asociaciones,
- `R`: radio máximo de proximidad del epicentro,
- `L`: límite de eventos,
- `T`: tiempo de antigüedad usado por el histórico.

---

### 3.7 `reportes.py`

Define el tipo `Reporte`, que es la forma de entrada del sistema.

`Reporte` contiene:

- identificador,
- revisión,
- magnitud,
- profundidad,
- epicentro,
- fecha,
- `en_zona_poblada`,
- `estacion`.

También incluye la lógica central `procesar_reporte`:

- si el evento no existe -> lo crea y lo inserta en el árbol,
- si la revisión es mayor -> actualiza el evento,
- si la revisión es menor -> lo descarta,
- si es igual pero con mismo contenido -> confirma,
- si hay conflicto -> rechaza la operación.

Es la capa que convierte un mensaje externo en cambio válido del estado del sistema.

---

### 3.8 `gestor_eventos.py`

Es el componente de gestión de alta calidad para eventos.

Responsabilidades:

- validar datos de entrada,
- comprobar identificadores únicos,
- crear eventos nuevos,
- corregir eventos existentes,
- marcar revisados,
- eliminar eventos.

Métodos principales:

- `_validar_datos`: asegura que magnitud, profundidad, fecha y coordenadas sean correctas.
- `_crear_clave`: construye la clave a partir del evento.
- `crear_evento`: inserta un evento y contabiliza conflictos.
- `corregir_evento`: reemplaza un evento con versión actualizada y reinserta en el AVL.
- `eliminar_evento`: elimina del árbol y marca el identificador como retirado.

Este módulo centraliza la lógica de negocio del dominio sísmico.

---

### 3.9 `historico.py`

Guarda eventos que ya no están activos y que han sido archivados porque una rama fue considerada antigua o no relevante.

Métodos relevantes:

- `_fecha_ocurrencia`: normaliza fechas a `datetime`.
- `es_elegible`: comprueba si un nodo cumple criterios para archivado.
- `buscar_rama_a_archivar`: busca la rama más apropiada para archivar.
- `archivar_rama`: mueve todos los nodos de la rama a `eventos_archivados` y los elimina del árbol.

Es una especie de gestor de “viejo estado” o “historial masivo”.

---

### 3.10 `asociaciones.py`

Se encarga de relacionar eventos según proximidad temporal y espacial.

Funciones principales:

- `distancia_euclidiana`: calcula la distancia entre epicentros.
- `candidatos_de`: encuentra otros eventos que podrían estar relacionados con un evento concreto.
- `referencia_de`: determina cuál es la referencia más probable para un evento.
- `recuperar_afectadas`: recalcula relaciones afectadas por un cambio.

Este módulo no solo trata con almacenamiento, sino con contexto extra: qué eventos son potencialmente la “fuente” o el “seguimiento” de otro.

La estrategia es:

- requisitos: otro evento más fuerte,
- fecha posterior en un rango temporal W,
- distancia geográfica <= R,
- desempate por magnitud mayor y diferencia temporal menor.

---

### 3.11 `metricas.py`

Es un contenedor de métricas del sistema. Es un dataclass con contadores como:

- `correcciones_aceptadas`
- `reportes_descartados`
- `conflictos`
- `archivos_masivos`
- `eventos_archivados`
- `casos_LL`, `casos_RR`, `casos_LR`, `casos_RL`
- `giros_izquierda`, `giros_derecha`

Métodos:

- `incrementar`: suma un valor a un contador.
- `a_dict`: serializa a diccionario.
- `desde_dict`: reconstruye desde dict.

La idea es rastrear continuamente la salud del sistema y la estructura de datos.

---

### 3.12 `cola_reportes.py`

Es una cola FIFO para reportes pendientes.

- `encolar`: los añade al final,
- `reportes_pendientes`: devuelve la lista actual,
- `procesar_uno`: procesa el siguiente reporte usando `procesar_reporte`,
- `procesar_todos`: recorre la cola entera.

Esto permite desacoplar la recepción de reportes de su procesamiento real.

---

### 3.13 `pila_deshacer.py`

Implementa una pila de snapshots para deshacer acciones.

- `registrar`: guarda el estado del sistema serializado.
- `deshacer`: recupera el estado anterior.
- `ejecutar_accion`: guarda el snapshot y ejecuta la acción.
- `cantidad`: cuenta cuántos pasos de undo quedan.

Es una herramienta de recuperación muy útil para la interfaz gráfica.

---

### 3.14 `estado.py`

Es el modelo central de estado operativo del sistema.

`EstadoOperativo` contiene:

- `arbol`
- `historico`
- `cola`
- `escenario`
- `metricas`
- `referencias`
- `gestor_eventos`

Además ofrece:

- `fuentes_eventos`: devuelve la vista combinada de activos + históricos.

Las funciones de serialización:

- `_serializar_valor`: convierte datos a formato JSON-safe.
- `_reconstruir_valor`: hace el proceso inverso.
- `_serializar_evento`, `_reconstruir_evento`
- `_serializar_reporte`, `_reconstruir_reporte`
- `_serializar_nodo`, `_reconstruir_nodo`
- `serializar_estado`, `reconstruir_estado`

Esto es crucial porque permite guardar y restaurar el árbol, los eventos, la cola, el escenario y las métricas en un JSON consistente.

---

### 3.15 `persistencia.py`

Es la capa de I/O del sistema.

Funciones principales:

- `exportar`: escribe el estado actual a un archivo JSON.
- `_leer_documento`: abre archivo o acepta un dict.
- `_extraer_estado`: saca el bloque de estado del documento final.
- `_problemas_prioridad_archivada`: valida priorización interna de eventos archivados.
- `cargar_por_inserciones`: reconstruye un estado desde una lista de eventos.
- `validar_topologia`: comprueba si una topología guardada es válida.
- `cargar_por_topologia`: intenta cargar un snapshot completo y devuelve un estado o errores.

Su papel es asegurarse de que el estado guardado sea consistente y pueda restaurarse sin romper el árbol ni la lógica del sistema.

---

### 3.16 `auditoria.py`

Se encarga de revisar si el árbol está bien construido.

La función `verificar_estructura()` recorre el árbol para comprobar:

- nodos repetidos o ciclos,
- ordenamiento correcto,
- altura calculada vs. altura almacenada,
- factor de balance correcto,
- si el árbol en modo normal mantiene desbalance <= 1.

Devuelve una lista de incidencias con:

- `identificador`,
- `tipo`,
- `errores`,
- `desbalances`,
- `es_error_integridad`.

Esto sirve como prueba de integridad para validar que la estructura sigue siendo correcta.

---

### 3.17 `pygame_app.py`

Es el punto de entrada para ejecutar una demo de la app.

- crea un escenario con varias zonas,
- genera un árbol `AVL`,
- carga algunos eventos demo,
- calcula las marcas `acceso_costoso` desde prioridad, profundidad y límite `L`,
- construye `EstadoOperativo` y `PilaDeshacer`,
- crea la instancia de `Aplicacion` y la ejecuta.

Es una forma de arrancar la aplicación con datos reales aunque no haya entrada externa.

---

### 3.18 `gui/contexto.py`

Define el contexto compartido por la interfaz.

Contiene:

- escenario,
- árbol,
- histórico,
- cola,
- gestor_eventos,
- métricas,
- referencias.

Es la pieza que conecta la vista con los datos reales del sistema sin acoplar cada panel a un único objeto.

---

### 3.19 `gui/pantalla.py`

Define el protocolo para cualquier pantalla visual.

Cada pantalla debe implementar:

- `manejar_evento`
- `actualizar`
- `dibujar`

Esto permite que la aplicación pueda cambiar de pantalla sin romper el diseño.

---

### 3.20 `gui/app.py`

Es la aplicación principal en pygame.

Responsabilidades:

- crear y registrar pantallas,
- activar una pantalla concreta,
- sincronizar el contexto cuando cambia el estado,
- construir un `EstadoOperativo` desde el contexto,
- instalar un estado nuevo,
- ejecutar el bucle principal del juego.

Es el equivalente a la capa de control de la interfaz.

---

### 3.21 `gui/simulador.py`

Es la pantalla de simulación principal.

Maneja:

- menús y botones,
- formularios para crear, corregir o reportar eventos,
- exportación/importación de estado,
- selección de nodos,
- cambio de modo normal/estres,
- deshacer última acción,
- procesamiento de cola,
- comparación AVL/BST y consultas del catálogo,
- gestión de versiones persistentes,
- recuperación del equilibrio,
- archivado de ramas,
- revisión de auditoría y métrica.

Es donde se hace visible la lógica de negocio en la interfaz.

---

### 3.22 `gui/vista_arbol.py`

Se encarga de dibujar el árbol visualmente en pantalla.

- calcula el layout de los nodos,
- dibuja líneas entre nodos,
- colorea según prioridad,
- resalta nodos costosos,
- renderiza el texto del identificador y la clave.

---

## 4. Flujos y reglas visibles de la interfaz

### 4.1 Plano geográfico

La vista del mapa conserva el dominio del escenario de 0 a 1000 km en ambos ejes; no autoescala según los datos que haya cargados. La cuadrícula principal está marcada cada 200 km. Las zonas pobladas y no pobladas tienen colores distintos; los epicentros usan el color de prioridad y un contorno adicional para eventos archivados. Al seleccionar un punto se muestran sus datos y estado. Las zonas se validan dentro del dominio y deben tener ancho y alto positivos.

### 4.2 Eventos y reportes

El catálogo de estaciones es una tupla inmutable del escenario. Por defecto contiene `STA-01` a `STA-08`; un escenario puede recibir otro catálogo al construirse y lo conserva en snapshots. Altas manuales y reportes deben referenciar una estación configurada.

El identificador está entre 1 y 999999; magnitud entre -2.0 y 10.0; profundidad entre 0.0 y 700.0 km; coordenadas entre 0.0 y 1000.0 km. Los campos numéricos admiten máximo un decimal. Las fechas deben incluir hora, minutos y segundos enteros; se normalizan a UTC y no pueden superar el reloj simulado. Una entrada ISO sin zona horaria se interpreta como UTC; fechas sin hora, con solo minutos o con fracciones de segundo se rechazan.

Toda alta de evento requiere al menos una estación configurada. La geometría se define antes del primer evento o reporte aceptado y permanece bloqueada incluso si se eliminan todos los eventos activos. El bloqueo se conserva al deshacer y restaurar snapshots. La GUI permite iniciar un escenario vacío, conservando reloj, parámetros y catálogo de estaciones, para configurar zonas antes de cargar datos.

Los reportes se validan antes de entrar en la cola FIFO. El procesamiento continuo consume un reporte por paso, con pausa de 900 ms; cada paso constituye una acción de deshacer. Una revisión mayor de un evento archivado lo reactiva conservando la identidad. Confirmaciones y reportes antiguos no lo reactivan; los identificadores eliminados se rechazan.

El borrado individual y el archivo de rama requieren confirmación. La previsualización de archivo muestra raíz, cantidad, criterio e identificadores y mantiene bloqueadas otras acciones hasta confirmar o cancelar.

### 4.3 Consultas, comparación y persistencia

La vista de comparación construye un AVL y un BST puro con las mismas claves, usando el orden de recepción o claves ascendentes. Presenta raíz, altura, hojas, búsquedas y comparaciones acumuladas.

Las consultas incluyen búsqueda por ID, top-k pendientes en orden descendente, intervalos inclusivos de magnitud y de profundidad/fecha, y eventos de prioridad alta con acceso costoso. Cada resultado informa cuántos nodos del AVL examinó; el acceso por ID usa el índice auxiliar y examina cero nodos del árbol.

La carga por topología se selecciona mediante un explorador de archivos y valida eventos, estaciones, referencias, identificadores retirados, orden BST, metadatos, marcas de acceso costoso y reportes pendientes antes de instalar el estado. La carga por inserciones acepta una lista JSON de eventos o un objeto con la propiedad `eventos`; cada evento debe incluir estaciones configuradas. El árbol activo siempre es AVL: en modo estrés conserva el orden BST y aplaza rotaciones, pero permanece recuperable. La clase `BST` sin balance se reserva para la comparación.

Las versiones se guardan como snapshots JSON en `.sismolab/versiones` dentro del directorio personal del usuario. No se sobrescriben nombres existentes. Restaurar valida el snapshot y registra una acción reversible.

### 4.4 Esquema estructural JSON

El documento exportado usa el sobre `{"formato":"sismolab-json-v1","nombre_version":null,"estado":{...}}`. El bloque `estado` contiene:

- `version_esquema`, `arbol.modo` y `arbol.raiz`; `raiz` guarda el índice de raíz y una lista de nodos con clave, altura, factor, marca de acceso costoso e índices `izquierda`/`derecha`.
- `eventos_activos`, `eventos_archivados` e `identificadores_eliminados`, con identidad, revisión, datos físicos, estaciones aceptadas, estado y prioridad derivada.
- `cola_reportes` en orden FIFO y `referencias` como pares `[evento, referencia]`.
- `escenario` con reloj UTC, estaciones, zonas, `W`, `R`, `L`, `T` y modo.
- `metricas`, `metricas_arbol` y `rotaciones_ultimo_archivo`.

La carga estructural comprueba referencias, unicidad y rangos de datos, clasificación de zona, fechas contra el reloj, estaciones, prioridad, orden BST global, ciclos, alturas, factores, marcas derivadas y contenido de la cola. Ante cualquier problema devuelve incidencias y conserva el estado operativo anterior.

Los fixtures reproducibles `datos_prueba/carga_inserciones.json`, `datos_prueba/carga_topologia.json` y `datos_prueba/rafaga_reportes.json` cubren los dos modos de carga y decisiones FIFO de alta, confirmación, reporte antiguo, conflicto y corrección.

## 5. Costos y decisiones

- Búsqueda por ID: O(1) promedio con el índice de identificadores; la profundidad del evento se obtiene recorriendo la topología para presentar su costo simulado.
- Inserción y búsqueda por clave en AVL: O(log n) en modo normal; en modo estrés pueden llegar a O(n). El BST comparativo tiene peor caso O(n).
- Top-k pendientes: recorrido inverso del AVL, O(n) en el peor caso y puede detenerse al reunir k pendientes.
- Filtros por magnitud, profundidad/fecha y acceso costoso: O(n) en el peor caso. No se atribuye costo logarítmico cuando el predicado no permite descartar subárboles.
- Asociaciones: se evalúan sobre eventos activos y archivados; el cálculo directo es O(n²) por comparación de candidatos. La regla de desempate es determinista: mayor magnitud, menor diferencia temporal y menor identificador.
- Comparación: reconstruir cada árbol cuesta O(n log n) para AVL y O(n²) para BST en el peor caso. Buscar todas las claves acumula el número de nodos visitados en cada búsqueda.
- Deshacer y versiones guardan snapshots completos: O(n) tiempo y memoria por estado guardado. Esta elección simplifica recuperar la topología exacta y evita que cambios posteriores muten estados anteriores.

## 6. Uso de IA

Se utilizó IA como apoyo de programación para revisar requisitos, implementar la visualización del mapa, completar flujos de comparación/consulta/persistencia, reforzar validaciones y crear pruebas de regresión. La IA no sustituye la revisión del equipo: antes de la entrega, los integrantes deben verificar las decisiones, ejecutar y explicar el código, y conservar este reporte junto con el manual técnico según las instrucciones del curso.

Es una vista puramente gráfica del contenido del árbol, pero usa datos reales del `AVL`.

---

## 4. Cómo interactúan las piezas entre sí

El flujo más importante del sistema es este:

1. Los datos de un sismo llegan como `Reporte` o un dict con `identificador`, `magnitud`, `profundidad`, `epicentro`, etc.
2. `GestorEventos` valida la información y genera un `Evento`.
3. Se calcula la prioridad con `calcular_prioridad`.
4. Se crea `Clave` y se inserta en el `AVL`.
5. El árbol reordena y balancea automáticamente.
6. Se actualiza el índice activo de eventos.
7. Los reportes pendientes se pueden procesar en cola con `ColaReportes`.
8. Si una rama es antigua y elegible, `GestorHistorico` la archiva.
9. `persistencia.py` puede exportar o restaurar el estado completo.
10. `PilaDeshacer` permite volver atrás en el tiempo.
11. La GUI observa el estado y dibuja el árbol y los indicadores.

---

## 5. Qué es lo más importante del proyecto

Si tuviera que resumir la idea central en una sola frase:

El proyecto es un simulador de gestión de eventos sísmicos con un árbol AVL como núcleo, un sistema de reportes y revisiones, un histórico de ramas archivadas y una interfaz gráfica para operar todo el estado.

Las piezas más importantes son:

- `AVL.py`: estructura de datos central.
- `GestorEventos`: lógica de alta y edición de eventos.
- `reportes.py`: decisiones de aceptación/rechazo.
- `historico.py`: archivado de tramos antiguos.
- `estado.py` + `persistencia.py`: salvar y restaurar el sistema.
- `gui/simulador.py`: capa de interacción con el usuario.

---

## 6. Archivos de prueba

El proyecto incluye varios archivos de prueba, de los cuales destacan:

- `prueba_avl.py`: prueba del árbol AVL y sus rotaciones.
- `prueba_estado.py`: validación del estado serializable.
- `prueba_gestor.py`: validación del gestor de eventos.
- `prueba_persistencia.py`: prueba de exportación e importación.
- `prueba_historico.py`: validación del archivado histórico.
- `prueba_gui.py`: pruebas de la interfaz.
- `prueba_cola.py`: validación de cola de reportes.
- `prueba_deshacer.py`: pruebas de estados y undo.
- `prueba_escenario.py`: validación del escenario y zonas.
- `prueba_asociaciones.py`: pruebas de asociaciones entre eventos.
- `prueba_estres.py`: pruebas bajo carga y estrés.
- `prueba_auditoria.py`: comprobación de integridad estructural.
- `prueba_reportes.py`: validación del procesamiento de reportes.

Aunque estos archivos son de prueba, ayudan a verificar que cada módulo cumple su función de forma aislada y coherente con el sistema completo.

---

## 7. En una línea: qué hace cada archivo

- `AVL.py`: árbol balanceado principal.
- `BST.py`: versión sin balanceo.
- `Nodo.py`: nodo del árbol.
- `clave.py`: clave de orden.
- `evento.py`: definición del evento y prioridad.
- `escenario.py`: entorno, zonas y reloj.
- `reportes.py`: lógica de entrada de datos.
- `gestor_eventos.py`: gestión de eventos activos.
- `historico.py`: archivado de ramas.
- `asociaciones.py`: relaciones entre eventos.
- `metricas.py`: contadores del sistema.
- `cola_reportes.py`: cola FIFO de correcciones.
- `pila_deshacer.py`: sistema de undo.
- `estado.py`: snapshot completo del sistema.
- `persistencia.py`: exportación/importación.
- `auditoria.py`: validación estructural.
- `pygame_app.py`: arrancador del demo.
- `gui/*`: interfaz gráfica y visualización.

---

## 8. Conclusión

La lógica central del proyecto es una mezcla de tres ideas:

1. estructura de datos avanzada (`AVL`),
2. dominio de eventos sísmicos (validez, prioridad, ubicación, fechas),
3. simulación operativa con cola, auditoría, persistencia y GUI.

Por eso se ve como un sistema “realista” aunque está basado en un ejercicio de programación estructural y orientada a objetos.

Si quieres, el siguiente paso natural es hacer una segunda versión del documento con:

- diagrama de flujo de datos,
- explicación de cómo se procesan los reportes paso a paso,
- recorrido práctico de un ejemplo real con eventos,
- explicación detallada de cada método de `AVL` con pseudo-código.
