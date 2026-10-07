from datetime import datetime, timedelta

from AVL import AVL
from evento import calcular_prioridad
from gestor_eventos import GestorEventos
from escenario import Escenario, Zona


ahora = datetime(2026, 9, 29, 12, 0)
escenario = Escenario(
	ahora,
	[
		Zona(0, 5, 0, 10, False),
		Zona(5, 10, 0, 10, True),
	],
)

for zona_invalida in (
	Zona(-1, 5, 0, 10, True),
	Zona(0, 1001, 0, 10, True),
	Zona(5, 5, 0, 10, True),
):
	try:
		Escenario(ahora, [zona_invalida])
	except ValueError:
		pass
	else:
		raise AssertionError("Una zona fuera del dominio o degenerada debe rechazarse")

assert escenario.zona_de(5, 5) is True
assert escenario.zona_de(0, 0) is False
assert escenario.zona_de(8, 5) is True
assert (escenario.W, escenario.R, escenario.L, escenario.T) == (48, 40, 3, 72)
assert escenario.estaciones == Escenario.ESTACIONES_POR_DEFECTO
try:
	escenario.estaciones = ("STA-99",)
except AttributeError:
	pass
else:
	raise AssertionError("El catálogo de estaciones debe ser inmutable")

escenario.W = 24
escenario.R = 25
escenario.L = 4
escenario.T = 36
assert (escenario.W, escenario.R, escenario.L, escenario.T) == (24, 25, 4, 36)

escenario.avanzar_reloj(ahora + timedelta(hours=1))
assert escenario.reloj == ahora + timedelta(hours=1)
try:
	escenario.avanzar_reloj(ahora)
except ValueError:
	pass
else:
	raise AssertionError("El reloj no debe retroceder")

poblada = escenario.zona_de(5, 5)
assert calcular_prioridad(4.8, 15.0, poblada) == 3

gestor = GestorEventos(AVL(), escenario=escenario)
evento = gestor.crear_evento(
	{
		"identificador": 1201,
		"magnitud": 4.8,
		"profundidad": 15.0,
		"epicentro": (5, 5),
		"fecha": ahora,
		"estacion": "STA-01",
	}
)
assert evento is not False
assert evento.en_zona_poblada is True
clave = gestor._crear_clave(evento)
assert clave.prioridad == 3

escenario_geometria = Escenario(ahora)
escenario_geometria.agregar_zona(Zona(100, 200, 100, 200, True))
assert not escenario_geometria.geometria_bloqueada
gestor_geometria = GestorEventos(AVL(), escenario=escenario_geometria)
evento_geometria = gestor_geometria.crear_evento({
	"identificador": 1301,
	"magnitud": 3.0,
	"profundidad": 40.0,
	"epicentro": (150.0, 150.0),
	"fecha": ahora,
	"estacion": "STA-01",
})
assert evento_geometria is not False
assert escenario_geometria.geometria_bloqueada
assert evento_geometria.en_zona_poblada
escenario_sin_estacion = Escenario(ahora)
gestor_sin_estacion = GestorEventos(AVL(), escenario=escenario_sin_estacion)
try:
	gestor_sin_estacion.crear_evento({
		"identificador": 1401,
		"magnitud": 3.0,
		"profundidad": 40.0,
		"epicentro": (10.0, 10.0),
		"fecha": ahora,
	})
except ValueError:
	pass
else:
	raise AssertionError("Un evento del escenario debe incluir estación de procedencia")
assert gestor_sin_estacion.arbol.peso() == 0
assert not escenario_sin_estacion.geometria_bloqueada
assert gestor_geometria.eliminar_evento(1301)
try:
	escenario_geometria.agregar_zona(Zona(300, 400, 300, 400, False))
except ValueError:
	pass
else:
	raise AssertionError("La geometría debe continuar fija tras eliminar el último evento")

print("El borde entre zona no poblada y poblada se clasifica como poblado")
print("Reloj, parámetros modificables e integración de prioridad verificados")