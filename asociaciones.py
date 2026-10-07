from dataclasses import dataclass
from datetime import date, datetime, time
from math import hypot, isfinite
from typing import Iterable

from AVL import AVL
from evento import Evento
from historico import GestorHistorico
from escenario import Escenario


@dataclass
class FuentesEventos:
	arbol: AVL
	indice_activos: dict
	historico: GestorHistorico


def distancia_euclidiana(epicentro_a, epicentro_b) -> float:
	"""Distancia euclidiana en km entre epicentros cartesianos (x, y)."""
	if not all(
		isinstance(epicentro, (tuple, list)) and len(epicentro) == 2
		for epicentro in (epicentro_a, epicentro_b)
	):
		raise ValueError("Los epicentros deben ser pares de coordenadas")
	coordenadas = (*epicentro_a, *epicentro_b)
	if any(
		isinstance(valor, bool)
		or not isinstance(valor, (int, float))
		or not isfinite(valor)
		for valor in coordenadas
	):
		raise ValueError("Las coordenadas deben ser números finitos")
	return hypot(
		epicentro_a[0] - epicentro_b[0],
		epicentro_a[1] - epicentro_b[1],
	)


def _fecha_hora(fecha) -> datetime | None:
	if isinstance(fecha, datetime):
		return fecha
	if isinstance(fecha, date):
		return datetime.combine(fecha, time.min)
	if isinstance(fecha, str):
		try:
			return datetime.fromisoformat(fecha)
		except ValueError:
			return None
	return None


def _eventos_disponibles(todos_los_eventos) -> list[Evento]:
	if isinstance(todos_los_eventos, FuentesEventos):
		activos = (
			todos_los_eventos.indice_activos[clave.identificador]
			for clave in todos_los_eventos.arbol.claves_in_order()
			if clave.identificador in todos_los_eventos.indice_activos
		)
		archivados = todos_los_eventos.historico.eventos_archivados.values()
		ids_archivados = set(todos_los_eventos.historico.eventos_archivados)
		eliminados = (
			todos_los_eventos.historico.identificadores_eliminados
			- ids_archivados
		)
		return _unicos_por_id((*activos, *archivados), eliminados)

	if (
		isinstance(todos_los_eventos, tuple)
		and len(todos_los_eventos) == 2
		and isinstance(todos_los_eventos[0], AVL)
		and isinstance(todos_los_eventos[1], GestorHistorico)
	):
		arbol, historico = todos_los_eventos
		activos = (
			historico.indice_activos[clave.identificador]
			for clave in arbol.claves_in_order()
			if clave.identificador in historico.indice_activos
		)
		archivados = historico.eventos_archivados.values()
		ids_archivados = set(historico.eventos_archivados)
		return _unicos_por_id(
			(*activos, *archivados),
			historico.identificadores_eliminados - ids_archivados,
		)

	return _unicos_por_id(todos_los_eventos)


def _unicos_por_id(eventos: Iterable[Evento], eliminados=()) -> list[Evento]:
	por_id = {}
	for evento in eventos:
		if evento.identificador not in eliminados:
			por_id[evento.identificador] = evento
	return list(por_id.values())


def candidatos_de(
	evento_b: Evento,
	todos_los_eventos,
	escenario: Escenario,
) -> list[Evento]:
	fecha_b = _fecha_hora(evento_b.fecha)
	if fecha_b is None:
		return []

	candidatos = []
	for evento_a in _eventos_disponibles(todos_los_eventos):
		if evento_a.identificador == evento_b.identificador:
			continue
		if evento_a.magnitud <= evento_b.magnitud:
			continue
		fecha_a = _fecha_hora(evento_a.fecha)
		if fecha_a is None:
			continue
		try:
			diferencia = fecha_b - fecha_a
		except TypeError:
			continue
		if diferencia.total_seconds() <= 0:
			continue
		if diferencia.total_seconds() > escenario.W * 3600:
			continue
		try:
			distancia = distancia_euclidiana(
				evento_a.epicentro,
				evento_b.epicentro,
			)
		except ValueError:
			continue
		if distancia <= escenario.R:
			candidatos.append((evento_a, diferencia.total_seconds()))

	# Desempate de referencia: mayor magnitud, menor diferencia temporal, menor identificador.
	candidatos.sort(
		key=lambda par: (
			-par[0].magnitud,
			par[1],
			par[0].identificador,
		)
	)
	return [evento for evento, _ in candidatos]


def referencia_de(evento_b: Evento, candidatos: Iterable[Evento]) -> Evento | None:
	fecha_b = _fecha_hora(evento_b.fecha)
	validos = []
	for candidato in candidatos:
		fecha_candidato = _fecha_hora(candidato.fecha)
		if fecha_b is None or fecha_candidato is None:
			diferencia = float("inf")
		else:
			try:
				diferencia = abs((fecha_b - fecha_candidato).total_seconds())
			except TypeError:
				diferencia = float("inf")
		validos.append((candidato, diferencia))
	if not validos:
		return None
	return min(
		validos,
		key=lambda par: (
			-par[0].magnitud,
			par[1],
			par[0].identificador,
		),
	)[0]


def recuperar_afectadas(
	evento: Evento,
	todos_los_eventos,
	escenario: Escenario,
	referencias: dict[int, int],
) -> dict[int, int | None]:
	eventos = _eventos_disponibles(todos_los_eventos)
	fecha_evento = _fecha_hora(evento.fecha)
	if fecha_evento is None:
		return {}

	afectados = []
	for otro in eventos:
		fecha_otro = _fecha_hora(otro.fecha)
		if fecha_otro is None:
			continue
		try:
			posterior = fecha_otro > fecha_evento
		except TypeError:
			continue
		if otro.identificador == evento.identificador or posterior:
			afectados.append(otro)

	actualizados = {}
	for evento_b in afectados:
		referencia = referencia_de(
			evento_b,
			candidatos_de(evento_b, eventos, escenario),
		)
		id_referencia = referencia.identificador if referencia is not None else None
		if id_referencia is None:
			referencias.pop(evento_b.identificador, None)
		else:
			referencias[evento_b.identificador] = id_referencia
		actualizados[evento_b.identificador] = id_referencia
	return actualizados