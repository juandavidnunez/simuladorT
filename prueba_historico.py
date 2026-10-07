from datetime import datetime

from AVL import AVL
from clave import Clave
from evento import Evento
from escenario import Escenario
from historico import GestorHistorico
from gestor_eventos import GestorEventos


reloj = datetime(2026, 9, 29, 12, 0)
escenario = Escenario(reloj=reloj, T=72)
fecha_antigua = datetime(2026, 9, 20, 12, 0)

arbol_mixto = AVL()
indice_mixto = {}
evento_bajo = Evento(100, 3.0, 100.0, "Zona A", fecha_antigua, 1, "revisado")
evento_alto = Evento(200, 6.2, 100.0, "Zona B", fecha_antigua, 1, "revisado")
for evento, prioridad in ((evento_bajo, 1), (evento_alto, 3)):
	assert arbol_mixto.insertar(
		Clave(prioridad, evento.magnitud, evento.identificador)
	)
	indice_mixto[evento.identificador] = evento

historico_mixto = GestorHistorico(indice_mixto)
assert arbol_mixto.raiz.clave.identificador == 100
assert arbol_mixto.raiz.derecha.clave.identificador == 200
assert not historico_mixto.es_elegible(arbol_mixto.raiz, escenario)
assert historico_mixto.buscar_rama_a_archivar(arbol_mixto, escenario) is None
print("Rama con descendiente de prioridad alta: no elegible")

arbol_archivable = AVL()
indice_archivable = {}
eventos = [
	Evento(
		identificador,
		magnitud,
		100.0,
		f"Zona {identificador}",
		fecha_antigua,
		1,
		"revisado",
	)
	for identificador, magnitud in ((310, 3.0), (320, 2.0), (330, 4.0))
]
for evento in eventos:
	assert arbol_archivable.insertar(Clave(1, evento.magnitud, evento.identificador))
	indice_archivable[evento.identificador] = evento

historico = GestorHistorico(indice_archivable)
raiz_archivable = arbol_archivable.raiz
assert raiz_archivable is not None
assert historico.es_elegible(raiz_archivable, escenario)
assert historico.buscar_rama_a_archivar(arbol_archivable, escenario) is raiz_archivable
archivados = historico.archivar_rama(raiz_archivable, arbol_archivable)

assert {evento.identificador for evento in archivados} == {310, 320, 330}
assert set(historico.eventos_archivados) == {310, 320, 330}
assert not indice_archivable
assert arbol_archivable.raiz is None
assert arbol_archivable.peso() == 0
assert not arbol_archivable._nodos_por_identificador
assert historico.identificadores_eliminados == {310, 320, 330}
assert arbol_archivable.metricas.archivos_masivos == 1
assert arbol_archivable.metricas.eventos_archivados == 3
print("Rama antigua de prioridad baja archivada en una sola desconexión")

arbol_rebalanceo = AVL()
indice_rebalanceo = {}
eventos_rebalanceo = []
for prioridad, magnitud, identificador in [
	(2, 4.0, 404),
	(1, 2.0, 402),
	(2, 6.0, 406),
	(1, 1.0, 401),
	(1, 3.0, 403),
	(2, 5.0, 405),
	(2, 7.0, 407),
]:
	evento = Evento(
		identificador,
		magnitud,
		100.0,
		f"Zona {identificador}",
		fecha_antigua,
		1,
		"revisado",
	)
	assert arbol_rebalanceo.insertar(Clave(prioridad, magnitud, identificador))
	indice_rebalanceo[identificador] = evento
	eventos_rebalanceo.append(evento)

historico_rebalanceo = GestorHistorico(indice_rebalanceo)
gestor_eventos = GestorEventos(
	arbol_rebalanceo,
	indice_rebalanceo,
	gestor_historico=historico_rebalanceo,
)
rama_elegible = historico_rebalanceo.buscar_rama_a_archivar(
	arbol_rebalanceo,
	escenario,
)
assert rama_elegible is not None
assert {evento.identificador for evento in historico_rebalanceo.archivar_rama(
	rama_elegible,
	arbol_rebalanceo,
)} == {401, 402, 403}
assert set(indice_rebalanceo) == {404, 405, 406, 407}
assert gestor_eventos.identificadores_retirados == {401, 402, 403}
assert arbol_rebalanceo.peso() == 4
assert [
	clave.identificador for clave in arbol_rebalanceo.claves_in_order()
] == [404, 405, 406, 407]


def verificar_balance(nodo):
	if nodo is None:
		return -1
	altura_izquierda = verificar_balance(nodo.izquierda)
	altura_derecha = verificar_balance(nodo.derecha)
	assert nodo.altura == 1 + max(altura_izquierda, altura_derecha)
	assert abs(altura_izquierda - altura_derecha) <= 1
	return nodo.altura


verificar_balance(arbol_rebalanceo.raiz)
print("Desconexión no raíz: antecesores reequilibrados y activos sincronizados")

print("La prueba del histórico pasó")