from datetime import datetime, timezone

from AVL import AVL
from evento import Evento
from historico import GestorHistorico
from reportes import Reporte, procesar_reporte


arbol = AVL()
indice_identificadores = {}

casos = [
	(
		"Identificador desconocido",
		"alta",
		Reporte(801, 1, 4.5, 20.0, (100.0, 100.0), "2026-09-29T10:00:00Z", True, "EST-01"),
	),
	(
		"Revisión mayor que la vigente",
		"sustitucion",
		Reporte(801, 2, 5.1, 80.0, (110.0, 110.0), "2026-09-29T10:01:00Z", False, "EST-02"),
	),
	(
		"Revisión igual, datos iguales",
		"confirmacion",
		Reporte(801, 2, 5.1, 80.0, (110.0, 110.0), "2026-09-29T10:01:00Z", False, "EST-03"),
	),
	(
		"Revisión igual, datos distintos",
		"conflicto",
		Reporte(801, 2, 5.1, 80.0, (120.0, 120.0), "2026-09-29T10:01:00Z", False, "EST-04"),
	),
	(
		"Revisión menor que la vigente",
		"descartado",
		Reporte(801, 1, 4.5, 20.0, (100.0, 100.0), "2026-09-29T10:00:00Z", True, "EST-05"),
	),
]

for situacion, esperado, reporte in casos:
	resultado = procesar_reporte(reporte, indice_identificadores, arbol)
	print(f"{situacion}: {resultado}")
	assert resultado == esperado

evento = indice_identificadores[801]
assert evento.revision == 2
assert evento.magnitud == 5.1
assert evento.epicentro == (110.0, 110.0)
assert evento.estaciones == {"EST-01", "EST-02", "EST-03"}
assert arbol.peso() == 1
assert arbol.claves_in_order()[0].prioridad == 2
assert arbol.claves_in_order()[0].magnitud == 5.1

arbol_historico = AVL()
indice_activos = {}
historico = GestorHistorico(indice_activos)
archivado = Evento(
	902,
	4.0,
	40.0,
	(300.0, 300.0),
	datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc),
	2,
	"archivado",
)
historico.eventos_archivados[902] = archivado
historico.identificadores_eliminados.add(902)
assert procesar_reporte(
	Reporte(902, 2, 4.0, 40.0, (300.0, 300.0), "2026-09-29T10:00:00Z", False, "EST-06"),
	indice_activos,
	arbol_historico,
	historico,
) == "confirmacion"
assert 902 not in indice_activos
assert procesar_reporte(
	Reporte(902, 1, 3.0, 50.0, (300.0, 300.0), "2026-09-29T09:00:00Z", False, "EST-07"),
	indice_activos,
	arbol_historico,
	historico,
) == "descartado"
assert procesar_reporte(
	Reporte(902, 3, 4.2, 35.0, (310.0, 310.0), "2026-09-29T10:01:00Z", False, "EST-08"),
	indice_activos,
	arbol_historico,
	historico,
) == "reactivacion"
assert indice_activos[902] is archivado
assert 902 not in historico.eventos_archivados
assert 902 not in historico.identificadores_eliminados
assert archivado.estado == "pendiente"

historico.identificadores_eliminados.add(903)
assert procesar_reporte(
	Reporte(903, 1, 4.0, 40.0, (300.0, 300.0), "2026-09-29T10:00:00Z", False, "EST-09"),
	indice_activos,
	arbol_historico,
	historico,
) == "retirado"
assert 903 not in indice_activos
print("La prueba de los cinco estados de reportes pasó")
print("Reactivación de archivado y rechazo de IDs eliminados verificados")