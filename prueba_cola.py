import json
from datetime import datetime, timezone
from pathlib import Path

from AVL import AVL
from cola_reportes import ColaReportes
from reportes import Reporte
from escenario import Escenario
from historico import GestorHistorico


arbol = AVL()
indice_identificadores = {}
cola = ColaReportes(indice_identificadores, arbol)

reportes = [
	Reporte(702, 2, 6.5, 10.0, (100.0, 100.0), "2026-09-29T10:00:00Z", False, "EST-ALTA"),
	Reporte(701, 1, 3.5, 50.0, (200.0, 200.0), "2026-09-29T10:01:00Z", False, "EST-BAJA"),
	Reporte(702, 2, 6.5, 10.0, (100.0, 100.0), "2026-09-29T10:00:00Z", False, "EST-CONFIRMA"),
	Reporte(702, 1, 4.0, 70.0, (100.0, 100.0), "2026-09-29T09:50:00Z", False, "EST-ANTIGUA"),
	Reporte(702, 3, 3.8, 40.0, (110.0, 110.0), "2026-09-29T10:02:00Z", False, "EST-CORRECCION"),
]
for reporte in reportes:
	cola.encolar(reporte)

primer_resultado = cola.procesar_uno()
assert primer_resultado is not None
resultados = [primer_resultado] + cola.procesar_todos()

decisiones_esperadas = [
	"alta",
	"alta",
	"confirmacion",
	"descartado",
	"sustitucion",
]
estaciones_esperadas = [
	"EST-ALTA",
	"EST-BAJA",
	"EST-CONFIRMA",
	"EST-ANTIGUA",
	"EST-CORRECCION",
]

assert [resultado.decision for resultado in resultados] == decisiones_esperadas
assert [resultado.estacion for resultado in resultados] == estaciones_esperadas
assert [resultado.revision for resultado in resultados] == [2, 1, 2, 1, 3]
assert [resultado.identificador for resultado in resultados] == [702, 701, 702, 702, 702]

assert resultados[0].evento is not None
assert resultados[0].evento.magnitud == 6.5
assert resultados[-1].evento is not None
assert resultados[-1].evento.magnitud == 3.8
assert resultados[0].evento.revision == 2
assert resultados[-1].evento.revision == 3

ids_en_orden_del_arbol = [
	clave.identificador for clave in arbol.claves_in_order()
]
assert ids_en_orden_del_arbol == [701, 702]
assert [resultado.identificador for resultado in resultados[:2]] == [702, 701]
assert cola.procesar_uno() is None
assert cola.procesar_todos() == []

for resultado in resultados:
	print(
		f"{resultado.estacion}: SIS-{resultado.identificador:06d}, "
		f"revisión {resultado.revision}, {resultado.decision}"
	)
print("La prueba de orden FIFO pasó")

with (Path(__file__).parent / "datos_prueba" / "rafaga_reportes.json").open(encoding="utf-8") as archivo:
	fixture_rafaga = json.load(archivo)["reportes"]
indice_rafaga = {}
arbol_rafaga = AVL()
historico_rafaga = GestorHistorico(indice_rafaga)
cola_rafaga = ColaReportes(
	indice_rafaga,
	arbol_rafaga,
	Escenario(reloj=datetime(2026, 10, 5, tzinfo=timezone.utc)),
	historico_rafaga,
)
for datos in fixture_rafaga:
	cola_rafaga.encolar(Reporte(
		datos["identificador"],
		datos["revision"],
		datos["magnitud"],
		datos["profundidad"],
		tuple(datos["epicentro"]),
		datos["fecha"],
		datos.get("en_zona_poblada", False),
		datos["estacion"],
	))
resultados_rafaga = cola_rafaga.procesar_todos()
assert [resultado.decision for resultado in resultados_rafaga] == [
	"alta", "alta", "confirmacion", "descartado", "conflicto", "sustitucion"
]
print("Fixture de ráfaga: seis decisiones FIFO verificadas")