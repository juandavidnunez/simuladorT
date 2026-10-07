from collections import deque
from collections.abc import Callable
from typing import Any

from estado import EstadoOperativo, reconstruir_estado, serializar_estado


class PilaDeshacer:
	def __init__(self, estado: EstadoOperativo):
		self.estado = estado
		self._snapshots = deque()

	def registrar(self, nombre: str = "acción") -> None:
		snapshot = serializar_estado(
			self.estado.arbol,
			self.estado.historico,
			self.estado.cola,
			self.estado.escenario,
			self.estado.metricas,
			self.estado.referencias,
		)
		self._snapshots.append((nombre, snapshot))

	def deshacer(self) -> EstadoOperativo | None:
		if not self._snapshots:
			return None
		_, snapshot = self._snapshots.pop()
		restaurado = reconstruir_estado(snapshot)
		self._aplicar_estado(restaurado)
		return self.estado

	def ejecutar_accion(
		self,
		nombre: str,
		funcion: Callable[..., Any],
		*args,
		**kwargs,
	):
		snapshot = serializar_estado(
			self.estado.arbol,
			self.estado.historico,
			self.estado.cola,
			self.estado.escenario,
			self.estado.metricas,
			self.estado.referencias,
		)
		self._snapshots.append((nombre, snapshot))
		try:
			return funcion(*args, **kwargs)
		except Exception:
			self._snapshots.pop()
			self._aplicar_estado(reconstruir_estado(snapshot))
			raise

	def _aplicar_estado(self, restaurado: EstadoOperativo) -> None:
		self.estado.arbol = restaurado.arbol
		self.estado.historico = restaurado.historico
		self.estado.cola = restaurado.cola
		self.estado.escenario = restaurado.escenario
		self.estado.metricas = restaurado.metricas
		self.estado.referencias = restaurado.referencias
		self.estado.gestor_eventos = restaurado.gestor_eventos

	def cantidad(self) -> int:
		return len(self._snapshots)