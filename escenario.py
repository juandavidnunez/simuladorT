from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Zona:
	x_min: float
	x_max: float
	y_min: float
	y_max: float
	poblada: bool


class Escenario:
	ESTACIONES_POR_DEFECTO = tuple(f"STA-{indice:02d}" for indice in range(1, 9))

	def __init__(
		self,
		reloj: datetime | None = None,
		zonas: Iterable[Zona | Mapping | tuple] | None = None,
		W: float = 48,
		R: float = 40,
		L: int = 3,
		T: float = 72,
		modo: str = "normal",
		estaciones=None,
	):
		self.reloj = reloj if reloj is not None else datetime.now(timezone.utc).replace(microsecond=0)
		if not isinstance(self.reloj, datetime):
			raise TypeError("reloj debe ser un datetime")
		self.W = W
		self.R = R
		self.L = L
		self.T = T
		self.modo = modo
		self._zonas = tuple(self._normalizar_zona(zona) for zona in (zonas or []))
		self._geometria_bloqueada = False
		if isinstance(estaciones, str):
			raise ValueError("El catálogo de estaciones debe ser una colección de identificadores")
		catalogo = tuple(estaciones) if estaciones is not None else self.ESTACIONES_POR_DEFECTO
		if not catalogo or any(not isinstance(estacion, str) or not estacion.strip() for estacion in catalogo):
			raise ValueError("El escenario requiere estaciones con identificadores no vacíos")
		catalogo = tuple(estacion.strip() for estacion in catalogo)
		if len(catalogo) != len(set(catalogo)):
			raise ValueError("Los identificadores de estación deben ser únicos")
		self._estaciones = catalogo

	@property
	def estaciones(self) -> tuple[str, ...]:
		return self._estaciones

	@property
	def zonas(self) -> tuple[Zona, ...]:
		return self._zonas

	@property
	def geometria_bloqueada(self) -> bool:
		return self._geometria_bloqueada

	def bloquear_geometria(self) -> None:
		self._geometria_bloqueada = True

	@staticmethod
	def _validar_parametro(nombre: str, valor):
		if isinstance(valor, bool) or not isinstance(valor, (int, float)):
			raise ValueError(f"{nombre} debe ser numérico")
		if not isfinite(valor) or valor <= 0:
			raise ValueError(f"{nombre} debe ser positivo")
		return valor

	@staticmethod
	def _normalizar_zona(zona) -> Zona:
		if isinstance(zona, Zona):
			valores = (
				zona.x_min,
				zona.x_max,
				zona.y_min,
				zona.y_max,
				zona.poblada,
			)
		elif isinstance(zona, Mapping):
			valores = (
				zona["x_min"],
				zona["x_max"],
				zona["y_min"],
				zona["y_max"],
				zona["poblada"],
			)
		else:
			valores = tuple(zona)
		if len(valores) != 5:
			raise ValueError("Cada zona requiere x_min, x_max, y_min, y_max y poblada")
		x_min, x_max, y_min, y_max, poblada = valores
		coordenadas = (x_min, x_max, y_min, y_max)
		if any(
			isinstance(valor, bool)
			or not isinstance(valor, (int, float))
			or not isfinite(valor)
			for valor in coordenadas
		):
			raise ValueError("Los límites de la zona deben ser números finitos")
		if x_min >= x_max or y_min >= y_max:
			raise ValueError("Cada zona debe tener ancho y alto positivos")
		if any(not 0 <= valor <= 1000 for valor in coordenadas):
			raise ValueError("Las zonas deben permanecer dentro del plano de 0 a 1000 km")
		if not isinstance(poblada, bool):
			raise ValueError("poblada debe ser booleano")
		return Zona(x_min, x_max, y_min, y_max, poblada)

	def avanzar_reloj(self, nuevo_tiempo: datetime) -> None:
		if not isinstance(nuevo_tiempo, datetime):
			raise TypeError("nuevo_tiempo debe ser un datetime")
		try:
			posterior = nuevo_tiempo > self.reloj
		except TypeError as error:
			raise ValueError("Los datetime deben tener zonas horarias compatibles") from error
		if not posterior:
			raise ValueError("El nuevo tiempo debe ser posterior al reloj actual")
		self.reloj = nuevo_tiempo

	def zona_de(self, x: float, y: float) -> bool:
		if any(
			isinstance(valor, bool)
			or not isinstance(valor, (int, float))
			or not isfinite(valor)
			for valor in (x, y)
		):
			raise ValueError("Las coordenadas deben ser números finitos")
		return any(
			zona.poblada
			and zona.x_min <= x <= zona.x_max
			and zona.y_min <= y <= zona.y_max
			for zona in self.zonas
		)

	def agregar_zona(self, zona: Zona | Mapping | tuple) -> None:
		if self._geometria_bloqueada:
			raise ValueError("La geometría de zonas es inmutable después de iniciar el escenario")
		self._zonas = (*self._zonas, self._normalizar_zona(zona))

	@property
	def modo(self) -> str:
		return self._modo

	@modo.setter
	def modo(self, modo: str) -> None:
		if modo not in {"normal", "estres"}:
			raise ValueError("El modo debe ser 'normal' o 'estres'")
		self._modo = modo

	@property
	def W(self) -> float:
		return self._W

	@W.setter
	def W(self, valor: float) -> None:
		self._W = self._validar_parametro("W", valor)

	@property
	def R(self) -> float:
		return self._R

	@R.setter
	def R(self, valor: float) -> None:
		self._R = self._validar_parametro("R", valor)

	@property
	def L(self) -> int:
		return self._L

	@L.setter
	def L(self, valor: int) -> None:
		if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
			raise ValueError("L debe ser un entero no negativo")
		self._L = valor

	@property
	def T(self) -> float:
		return self._T

	@T.setter
	def T(self, valor: float) -> None:
		self._T = self._validar_parametro("T", valor)