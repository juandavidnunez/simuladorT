from dataclasses import dataclass
from datetime import datetime
from typing import Any

from AVL import AVL
from clave import Clave
from evento import Evento, calcular_prioridad
from gestor_eventos import GestorEventos


@dataclass(frozen=True)
class Reporte:
	identificador: int
	revision: int
	magnitud: float
	profundidad: float
	epicentro: Any
	fecha: Any
	en_zona_poblada: bool = False
	estacion: Any = None


def validar_reporte(reporte: Reporte, escenario=None) -> Reporte:
	if not isinstance(reporte, Reporte):
		raise TypeError("Se esperaba un reporte")
	if (
		isinstance(reporte.revision, bool)
		or not isinstance(reporte.revision, int)
		or reporte.revision < 1
	):
		raise ValueError("La revisión del reporte debe ser un entero positivo")
	if not isinstance(reporte.estacion, str) or not reporte.estacion.strip():
		raise ValueError("El reporte debe indicar una estación emisora")
	if escenario is not None and reporte.estacion.strip() not in escenario.estaciones:
		raise ValueError("La estación no pertenece al catálogo inmutable del escenario")
	datos = GestorEventos._validar_datos({
		"identificador": reporte.identificador,
		"magnitud": reporte.magnitud,
		"profundidad": reporte.profundidad,
		"epicentro": reporte.epicentro,
		"fecha": reporte.fecha,
		"en_zona_poblada": reporte.en_zona_poblada,
	})
	if escenario is not None:
		if isinstance(datos["epicentro"], (tuple, list)):
			datos["en_zona_poblada"] = escenario.zona_de(*datos["epicentro"])
		reloj = escenario.reloj
		if isinstance(reloj, datetime) and reloj.microsecond:
			reloj = reloj.replace(microsecond=0)
		if datos["fecha"] > GestorEventos._normalizar_fecha_utc(reloj):
			raise ValueError("La fecha del reporte no puede superar el reloj simulado")
	return Reporte(
		datos["identificador"],
		reporte.revision,
		datos["magnitud"],
		datos["profundidad"],
		datos["epicentro"],
		datos["fecha"],
		datos["en_zona_poblada"],
		reporte.estacion.strip(),
	)


def _crear_clave(evento: Evento) -> Clave:
	prioridad = calcular_prioridad(
		evento.magnitud,
		evento.profundidad,
		evento.en_zona_poblada,
	)
	return Clave(prioridad, evento.magnitud, evento.identificador)


def _crear_evento(reporte: Reporte) -> Evento:
	evento = Evento(
		reporte.identificador,
		reporte.magnitud,
		reporte.profundidad,
		reporte.epicentro,
		reporte.fecha,
		reporte.revision,
		"pendiente",
		reporte.en_zona_poblada,
	)
	evento.agregar_estacion(reporte.estacion)
	return evento


def procesar_reporte(
	reporte: Reporte,
	indice_identificadores: dict,
	arbol: AVL,
	historico=None,
	escenario=None,
) -> str:
	reporte = validar_reporte(reporte, escenario)
	if escenario is not None:
		escenario.bloquear_geometria()
	evento_actual = indice_identificadores.get(reporte.identificador)

	if evento_actual is None:
		evento_archivado = (
			historico.eventos_archivados.get(reporte.identificador)
			if historico is not None
			else None
		)
		if evento_archivado is not None:
			if reporte.revision < evento_archivado.revision:
				arbol.metricas.incrementar("reportes_descartados")
				return "descartado"
			if reporte.revision == evento_archivado.revision:
				if evento_archivado.datos_iguales(reporte):
					evento_archivado.agregar_estacion(reporte.estacion)
					return "confirmacion"
				arbol.metricas.incrementar("conflictos")
				return "conflicto"
			estado_anterior = (
				evento_archivado.magnitud,
				evento_archivado.profundidad,
				evento_archivado.epicentro,
				evento_archivado.fecha,
				evento_archivado.revision,
				evento_archivado.en_zona_poblada,
				evento_archivado.estado,
				evento_archivado.estaciones.copy(),
			)
			evento_archivado.magnitud = reporte.magnitud
			evento_archivado.profundidad = reporte.profundidad
			evento_archivado.epicentro = reporte.epicentro
			evento_archivado.fecha = reporte.fecha
			evento_archivado.revision = reporte.revision
			evento_archivado.en_zona_poblada = reporte.en_zona_poblada
			evento_archivado.estado = "pendiente"
			evento_archivado.agregar_estacion(reporte.estacion)
			if not arbol.insertar(_crear_clave(evento_archivado)):
				(
					evento_archivado.magnitud,
					evento_archivado.profundidad,
					evento_archivado.epicentro,
					evento_archivado.fecha,
					evento_archivado.revision,
					evento_archivado.en_zona_poblada,
					evento_archivado.estado,
					evento_archivado.estaciones,
				) = estado_anterior
				arbol.metricas.incrementar("conflictos")
				return "conflicto"
			indice_identificadores[reporte.identificador] = evento_archivado
			historico.eventos_archivados.pop(reporte.identificador)
			historico.identificadores_eliminados.discard(reporte.identificador)
			arbol.metricas.incrementar("correcciones_aceptadas")
			if escenario is not None:
				arbol.actualizar_accesos_costosos(escenario.L)
			return "reactivacion"
		if (
			historico is not None
			and reporte.identificador in historico.identificadores_eliminados
		):
			arbol.metricas.incrementar("conflictos")
			return "retirado"
		nuevo_evento = _crear_evento(reporte)
		if not arbol.insertar(_crear_clave(nuevo_evento)):
			arbol.metricas.incrementar("conflictos")
			return "conflicto"
		indice_identificadores[reporte.identificador] = nuevo_evento
		if escenario is not None:
			arbol.actualizar_accesos_costosos(escenario.L)
		return "alta"

	if reporte.revision > evento_actual.revision:
		clave_anterior = _crear_clave(evento_actual)
		if not arbol.eliminar(clave_anterior):
			arbol.metricas.incrementar("conflictos")
			return "conflicto"

		estado_anterior = (
			evento_actual.magnitud,
			evento_actual.profundidad,
			evento_actual.epicentro,
			evento_actual.fecha,
			evento_actual.revision,
			evento_actual.en_zona_poblada,
				evento_actual.estado,
			evento_actual.estaciones.copy(),
			)
		evento_actual.magnitud = reporte.magnitud
		evento_actual.profundidad = reporte.profundidad
		evento_actual.epicentro = reporte.epicentro
		evento_actual.fecha = reporte.fecha
		evento_actual.revision = reporte.revision
		evento_actual.en_zona_poblada = reporte.en_zona_poblada
		evento_actual.estado = "pendiente"
		evento_actual.agregar_estacion(reporte.estacion)

		if not arbol.insertar(_crear_clave(evento_actual)):
			(
				evento_actual.magnitud,
				evento_actual.profundidad,
				evento_actual.epicentro,
				evento_actual.fecha,
				evento_actual.revision,
				evento_actual.en_zona_poblada,
				evento_actual.estado,
				evento_actual.estaciones,
			) = estado_anterior
			arbol.insertar(clave_anterior)
			arbol.metricas.incrementar("conflictos")
			return "conflicto"
		arbol.metricas.incrementar("correcciones_aceptadas")
		if escenario is not None:
			arbol.actualizar_accesos_costosos(escenario.L)
		return "sustitucion"

	if reporte.revision < evento_actual.revision:
		arbol.metricas.incrementar("reportes_descartados")
		return "descartado"

	if evento_actual.datos_iguales(reporte):
		evento_actual.agregar_estacion(reporte.estacion)
		return "confirmacion"

	arbol.metricas.incrementar("conflictos")
	return "conflicto"