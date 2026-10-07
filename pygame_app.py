from datetime import datetime, timezone

from AVL import AVL
from cola_reportes import ColaReportes
from estado import EstadoOperativo
from escenario import Escenario, Zona
from gestor_eventos import GestorEventos
from historico import GestorHistorico
from pila_deshacer import PilaDeshacer
from gui.app import Aplicacion


def crear_aplicacion_demo() -> Aplicacion:
	escenario = Escenario(
		reloj=datetime.now(timezone.utc).replace(microsecond=0),
		zonas=[
			Zona(120, 360, 120, 380, True),
			Zona(440, 650, 130, 390, False),
			Zona(620, 870, 600, 850, True),
		],
	)
	arbol = AVL()
	indice_activos = {}
	historico = GestorHistorico(indice_activos)
	gestor_eventos = GestorEventos(
		arbol,
		indice_activos,
		escenario,
		historico,
	)
	cola = ColaReportes(indice_activos, arbol, escenario, historico)

	for identificador, magnitud, epicentro in (
		(30, 3.9, (245, 310)),
		(20, 2.5, (100, 100)),
		(25, 3.2, (380, 260)),
		(48, 4.8, (545, 220)),
		(51, 5.1, (735, 450)),
		(61, 6.1, (845, 760)),
		(43, 4.3, (490, 610)),
		(70, 7.0, (690, 680)),
		(47, 4.7, (270, 760)),
	):
		gestor_eventos.crear_evento(
			{
				"identificador": identificador,
				"magnitud": magnitud,
				"profundidad": 45.0,
				"epicentro": epicentro,
				"fecha": escenario.reloj,
				"estacion": "STA-01",
			}
		)

	arbol.actualizar_accesos_costosos(escenario.L)

	estado = EstadoOperativo(
		arbol,
		historico,
		cola,
		escenario,
		arbol.metricas,
		{},
		gestor_eventos,
	)
	pila = PilaDeshacer(estado)
	return Aplicacion(
		escenario=escenario,
		arbol=arbol,
		historico=historico,
		cola=cola,
		gestor_eventos=gestor_eventos,
		pila_deshacer=pila,
		metricas=arbol.metricas,
	)


if __name__ == "__main__":
	crear_aplicacion_demo().ejecutar()