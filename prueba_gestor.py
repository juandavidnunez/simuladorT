from AVL import AVL
from gestor_eventos import GestorEventos
from datetime import timezone


def datos_evento(
	identificador,
	magnitud,
	profundidad,
	fecha="2026-09-29T12:00:00",
	epicentro=(10.0, 10.0),
	en_zona_poblada=False,
):
	return {
		"identificador": identificador,
		"magnitud": magnitud,
		"profundidad": profundidad,
		"epicentro": epicentro,
		"fecha": fecha,
		"en_zona_poblada": en_zona_poblada,
	}


arbol = AVL()
gestor = GestorEventos(arbol)

evento = gestor.crear_evento(datos_evento(501, 4.8, 70.0))
assert evento is not False
assert evento.revision == 1
assert evento.estado == "pendiente"
clave_anterior = gestor._crear_clave(evento)
assert clave_anterior.prioridad == 2
assert arbol.buscar(clave_anterior) is not None

clave_vieja = arbol.buscar(clave_anterior)
assert clave_vieja is not None
evento_corregido = gestor.corregir_evento(
	501,
	datos_evento(501, 6.2, 15.0, fecha=evento.fecha, epicentro=evento.epicentro),
)
assert evento_corregido is evento
assert evento.revision == 2
assert evento.estado == "pendiente"
assert arbol.metricas.correcciones_aceptadas == 1
clave_nueva = gestor._crear_clave(evento)
assert clave_nueva.prioridad == 3
assert arbol.buscar(clave_anterior) is None
assert arbol.buscar(clave_nueva) is not None
assert arbol._nodos_por_identificador[501].clave == clave_nueva

nodo_antes_de_revisar = arbol.buscar(clave_nueva)
assert nodo_antes_de_revisar is not None
raiz_antes_de_revisar = arbol.raiz
izquierda_antes_de_revisar = nodo_antes_de_revisar.izquierda
derecha_antes_de_revisar = nodo_antes_de_revisar.derecha
assert gestor.marcar_revisado(501)
assert evento.estado == "revisado"
assert arbol.raiz is raiz_antes_de_revisar
assert nodo_antes_de_revisar.izquierda is izquierda_antes_de_revisar
assert nodo_antes_de_revisar.derecha is derecha_antes_de_revisar
assert arbol.buscar(clave_nueva) is nodo_antes_de_revisar
assert arbol.claves_in_order() == [clave_nueva]

evento_sin_cambio_clave = gestor.crear_evento(datos_evento(502, 3.2, 200.0))
assert evento_sin_cambio_clave is not False
nodo_sin_cambio = arbol.buscar(gestor._crear_clave(evento_sin_cambio_clave))
assert nodo_sin_cambio is not None
resultado_sin_cambio = gestor.corregir_evento(
	502,
	datos_evento(
		502,
		3.2,
		210.0,
		fecha="2026-09-29T12:05:00",
		epicentro=(11.0, 11.0),
	),
)
assert resultado_sin_cambio is evento_sin_cambio_clave
assert arbol.buscar(gestor._crear_clave(resultado_sin_cambio)) is nodo_sin_cambio
assert resultado_sin_cambio.revision == 2

evento_limite_escenario = gestor.crear_evento(
	datos_evento(504, -2.0, 0.0, epicentro=(1000.0, 1000.0))
)
assert evento_limite_escenario is not False
assert evento_limite_escenario.magnitud == -2.0
assert evento_limite_escenario.epicentro == (1000.0, 1000.0)

assert gestor.eliminar_evento(501)
assert 501 not in gestor.indice_identificadores
assert 501 in gestor.identificadores_retirados
assert gestor.identificadores_retirados is gestor.gestor_historico.identificadores_eliminados
assert gestor.crear_evento(datos_evento(501, 5.0, 30.0)) is False
assert arbol.metricas.conflictos == 1

try:
	gestor.crear_evento(datos_evento(503, 11.0, 20.0))
except ValueError:
	pass
else:
	raise AssertionError("La magnitud fuera de rango debía rechazarse")

for fecha_invalida in (
	"2026-09-29",
	"2026-09-29T12:00",
	"2026-09-29T12:00:00.001Z",
):
	try:
		gestor.crear_evento(
			datos_evento(505, 3.0, 20.0, fecha=fecha_invalida, epicentro=(1.0, 1.0))
		)
	except ValueError:
		pass
	else:
		raise AssertionError("La fecha debe incluir segundos enteros y no admitir fracciones")

evento_offset = gestor.crear_evento(
	datos_evento(
		506,
		3.0,
		20.0,
		fecha="2026-09-29T12:00:00-04:00",
		epicentro=(1.0, 1.0),
	)
)
assert evento_offset.fecha.hour == 16
assert evento_offset.fecha.tzinfo is timezone.utc

print("Corrección: prioridad 2 -> 3; clave anterior retirada")
print("Revisado: estado cambiado sin reemplazar el nodo AVL")
print("Corrección sin cambio de clave: el nodo AVL se conservó")
print("Eliminación: el ID retirado no puede reutilizarse")
print("La prueba del gestor de eventos pasó")