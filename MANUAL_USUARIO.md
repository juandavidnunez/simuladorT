# Manual de usuario SismoLab AVL

## Inicio

Desde PowerShell, en la carpeta del proyecto, ejecuta:

```powershell
.\.venv\Scripts\python.exe pygame_app.py
```

La ventana inicia con un escenario de demostración. El catálogo inicial de estaciones es `STA-01` a `STA-08`; sus identificadores son inmutables durante la ejecución.

## Mapa

Abre **Mapa de zonas**. El plano mantiene X e Y entre 0 y 1000 km; las líneas principales representan 200 km. Verde identifica zona poblada, azul grisáceo zona no poblada. El color del epicentro representa prioridad y el contorno cian identifica un evento archivado. Selecciona un punto para consultar sus datos. **+ Agregar zona** permite definir límites y tipo antes del primer evento o reporte aceptado; luego la geometría permanece fija.

Para configurar un territorio propio, abre **Escenario**, usa **Nuevo escenario vacío** y confirma el resumen. El escenario conserva reloj, parámetros y estaciones, pero retira los eventos y reportes actuales. Después podrás agregar zonas en el mapa y deshacer la operación completa.

## Eventos

En **Árbol activo** o **Eventos**, selecciona un nodo y usa **+ Crear evento**, **Corregir seleccionado**, **Marcar revisado** o **Eliminar seleccionado**. Las altas requieren una estación configurada. Magnitud, profundidad y coordenadas admiten máximo un decimal; la fecha debe incluir hora, minutos y segundos UTC y no ser posterior al reloj del escenario.

La eliminación muestra primero el evento afectado. Confirma para retirar solo ese ID o cancela para conservar el estado.

## Reportes

En **Cola FIFO**, usa **+ Encolar reporte** para añadir un reporte completo o **Cargar ráfaga JSON** para encolar un lote FIFO de forma atómica. **Procesar siguiente** resuelve un paso. **Iniciar continuo** procesa un reporte cada 900 ms y se detiene cuando la cola queda vacía; **Pausar continuo** lo interrumpe. El mensaje de resultado incluye estación, evento, revisión, decisión y giros AVL. Cada preparación de lote y cada paso pueden deshacerse.

## Consultas y comparación

En **AVL vs BST**, alterna entre orden de recepción y claves ascendentes. Ambos árboles se construyen con las mismas claves; la vista compara raíz, altura, hojas y comparaciones de búsqueda.

En **Consultas**, elige búsqueda por identificador, top-k pendientes, intervalo de magnitud, profundidad/fechas o acceso costoso. Cada resultado informa cuántos nodos del AVL fueron examinados. Las listas extensas admiten desplazamiento con la rueda del ratón.

## Histórico y auditoría

En **Histórico**, **Archivar rama elegible** calcula y muestra la raíz, cantidad, criterio e IDs antes de confirmar. El conjunto queda fijado para la operación. **Auditoría** revisa orden, metadatos del árbol, eventos, marcas de acceso y referencias.

## Guardado, carga y deshacer

**Exportar** abre un explorador para guardar el estado estructural. En **Escenario**, **Cargar JSON** abre un snapshot con topología explícita y **Cargar por inserciones** abre una lista de eventos JSON. Una carga inválida se rechaza sin reemplazar el escenario actual.

Hay archivos de demostración en `datos_prueba/`: `carga_inserciones.json`, `carga_topologia.json` y `rafaga_reportes.json`.

En **Versiones**, guarda una versión con nombre y restáurala desde la lista. Los archivos se guardan en `.sismolab/versiones` dentro de la carpeta personal del usuario; los nombres existentes no se sobrescriben. **Deshacer** restaura la acción anterior, incluida la topología, cola y métricas.

## Escenario

En **Escenario** consulta reloj, estaciones, zonas, modo y parámetros W, R, L y T. **Editar reloj y W/R/L/T** modifica los valores permitidos; **Alternar modo** aplaza o activa el balanceo, y en modo estrés aparece **Recuperar equilibrio**.