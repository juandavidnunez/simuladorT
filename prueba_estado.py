import json
from datetime import datetime, timezone

from AVL import AVL
from clave import Clave
from cola_reportes import ColaReportes
from estado import reconstruir_estado, serializar_estado
from evento import Evento
from escenario import Escenario, Zona
from historico import GestorHistorico
from reportes import Reporte


arbol = AVL()
arbol.modo = "estres"
indice_activos = {}
for identificador in range(1, 5):
	magnitud = float(identificador)
	evento = Evento(
		identificador,
		magnitud,
		20.0 + identificador,
		(float(identificador), float(identificador + 1)),
		datetime(2026, 9, 28, 10, identificador),
		identificador,
		"pendiente",
		True,
	)
	evento.estaciones = {f"EST-{identificador:02d}"}
	assert arbol.insertar(Clave(1, magnitud, identificador))
	indice_activos[identificador] = evento

historico = GestorHistorico(indice_activos)
evento_archivado = Evento(
	90,
	2.5,
	50.0,
	(7.0, 8.0),
	datetime(2026, 9, 20, 8, 30),
	3,
	"archivado",
)
historico.eventos_archivados[90] = evento_archivado
historico.identificadores_eliminados.update({90, 99})

cola = ColaReportes(indice_activos, arbol)
reporte_pendiente = Reporte(
	1,
	5,
	4.5,
	18.0,
	(1.5, 2.5),
	datetime(2026, 9, 29, 9, 15, tzinfo=timezone.utc),
	True,
	"EST-PENDIENTE",
)
cola.encolar(reporte_pendiente)
escenario = Escenario(
	reloj=datetime(2026, 9, 29, 12, 0),
	zonas=[Zona(0, 10, 0, 10, True)],
	W=24,
	R=30,
	L=4,
	T=48,
	modo="estres",
)
metricas = {"procesados": 12, "tasas": [1.25, 2.5], "detalle": {"correctos": 10}}
referencias = {2: 1, 90: 1}

snapshot = serializar_estado(
	arbol,
	historico,
	cola,
	escenario,
	metricas,
	referencias,
)
json.dumps(snapshot)
restaurado = reconstruir_estado(snapshot)
snapshot_restaurado = serializar_estado(
	restaurado.arbol,
	restaurado.historico,
	restaurado.cola,
	restaurado.escenario,
	restaurado.metricas,
	restaurado.referencias,
)

assert snapshot_restaurado == snapshot
assert restaurado.arbol.modo == "estres"
assert restaurado.arbol.altura() == 3
assert restaurado.arbol._nodos_por_identificador[1].derecha is not None
assert restaurado.historico.eventos_archivados[90].estado == "archivado"
assert restaurado.historico.identificadores_eliminados == {90, 99}
assert restaurado.cola.reportes_pendientes() == [reporte_pendiente]
assert restaurado.escenario.reloj == escenario.reloj
assert restaurado.escenario.geometria_bloqueada
assert restaurado.escenario.zona_de(5, 5)
assert restaurado.metricas == metricas
assert restaurado.referencias == referencias
assert restaurado.gestor_eventos.gestor_historico is restaurado.historico
assert restaurado.cola._arbol is restaurado.arbol
assert restaurado.cola._indice_identificadores is restaurado.historico.indice_activos

print("Snapshot JSON-compatible y round-trip completo verificados")