from collections import deque
from copy import copy
from dataclasses import dataclass
from typing import Any

from AVL import AVL
from evento import Evento
from reportes import Reporte, procesar_reporte, validar_reporte


@dataclass(frozen=True)
class ResultadoReporte:
	estacion: Any
	identificador: int
	revision: int
	decision: str
	evento: Evento | None


class ColaReportes:
	def __init__(self, indice_identificadores: dict, arbol: AVL, escenario=None, historico=None):
		self._cola = deque()
		self._indice_identificadores = indice_identificadores
		self._arbol = arbol
		self._escenario = escenario
		self._historico = historico

	@property
	def modo(self) -> str:
		return self._arbol.modo

	@modo.setter
	def modo(self, modo: str) -> None:
		self._arbol.modo = modo

	def encolar(self, reporte: Reporte) -> None:
		reporte_validado = validar_reporte(reporte, self._escenario)
		self._cola.append(reporte_validado)
		if self._escenario is not None:
			self._escenario.bloquear_geometria()

	def reportes_pendientes(self) -> list[Reporte]:
		return list(self._cola)

	def restaurar_pendientes(self, reportes) -> None:
		self._cola = deque(reportes)
		if self._cola and self._escenario is not None:
			self._escenario.bloquear_geometria()

	def procesar_uno(self) -> ResultadoReporte | None:
		if not self._cola:
			return None

		reporte = self._cola.popleft()
		decision = procesar_reporte(
			reporte,
			self._indice_identificadores,
			self._arbol,
			self._historico,
			self._escenario,
		)
		evento_actual = self._indice_identificadores.get(
			reporte.identificador
		)
		evento_resultado = None
		if evento_actual is not None:
			evento_resultado = copy(evento_actual)
			evento_resultado.estaciones = evento_actual.estaciones.copy()

		return ResultadoReporte(
			reporte.estacion,
			reporte.identificador,
			reporte.revision,
			decision,
			evento_resultado,
		)

	def procesar_todos(self) -> list[ResultadoReporte]:
		resultados = []
		while self._cola:
			resultado = self.procesar_uno()
			if resultado is not None:
				resultados.append(resultado)
		return resultados