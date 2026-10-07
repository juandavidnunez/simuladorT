from datetime import datetime, timezone

from AVL import AVL
from clave import Clave
from cola_reportes import ColaReportes
from estado import EstadoOperativo
from evento import Evento
from escenario import Escenario
from historico import GestorHistorico
from gestor_eventos import GestorEventos
from pila_deshacer import PilaDeshacer
from reportes import Reporte


arbol = AVL()
evento_activo = Evento(
	120,
	4.8,
	70.0,
	(10.0, 10.0),
	datetime(2026, 9, 29, 10, 0),
	2,
	"revisado",
)
clave_activa = Clave(2, evento_activo.magnitud, evento_activo.identificador)
assert arbol.insertar(clave_activa)
indice_activos = {evento_activo.identificador: evento_activo}
historico = GestorHistorico(indice_activos)
escenario = Escenario(reloj=datetime(2026, 9, 29, 12, 0))
cola = ColaReportes(indice_activos, arbol)
reporte_antiguo = Reporte(
	120,
	1,
	3.2,
	100.0,
	(10.0, 10.0),
	datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc),
	False,
	"STA-01",
)
cola.encolar(reporte_antiguo)
gestor_eventos = GestorEventos(arbol, indice_activos, escenario, historico)
estado = EstadoOperativo(
	arbol,
	historico,
	cola,
	escenario,
	{"reportes_descartados": 0},
	{},
	gestor_eventos,
)
pila = PilaDeshacer(estado)

resultado = pila.ejecutar_accion(
	"procesar un reporte",
	lambda: pila.estado.cola.procesar_uno(),
)
assert resultado is not None
assert resultado.decision == "descartado"
assert pila.estado.cola.reportes_pendientes() == []
assert pila.cantidad() == 1

estado_restaurado = pila.deshacer()
assert estado_restaurado is estado
assert pila.estado.cola.reportes_pendientes() == [reporte_antiguo]
assert pila.estado.arbol.claves_in_order() == [clave_activa]
assert pila.estado.historico.indice_activos[120].revision == 2
assert pila.estado.cola._arbol is pila.estado.arbol
assert pila.estado.cola._indice_identificadores is pila.estado.historico.indice_activos

resultado_repetido = pila.estado.cola.procesar_uno()
assert resultado_repetido is not None
assert resultado_repetido.decision == "descartado"
assert pila.estado.cola.reportes_pendientes() == []
assert pila.deshacer() is None

ventana_anterior = pila.estado.escenario.W

def fallar_despues_de_mutar():
	pila.estado.escenario.W = 12
	raise ValueError("fallo intencional de prueba")

try:
	pila.ejecutar_accion("acción fallida", fallar_despues_de_mutar)
except ValueError:
	pass
else:
	raise AssertionError("La acción fallida debía propagar su error")
assert pila.estado.escenario.W == ventana_anterior
assert pila.cantidad() == 0

print("El reporte antiguo se descartó, se repuso en FIFO al deshacer y volvió a descartarse")
print("La prueba de deshacer pasó")