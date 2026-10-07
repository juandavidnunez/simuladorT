from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from math import isfinite
import re

from AVL import AVL
from clave import Clave
from evento import Evento, calcular_prioridad
from escenario import Escenario
from historico import GestorHistorico


class GestorEventos:
	MAGNITUD_MINIMA = -2.0
	MAGNITUD_MAXIMA = 10.0
	PROFUNDIDAD_MINIMA = 0.0
	PROFUNDIDAD_MAXIMA = 700.0

	def __init__(
		self,
		arbol: AVL,
		indice_identificadores: dict | None = None,
		escenario: Escenario | None = None,
		gestor_historico: GestorHistorico | None = None,
	):
		self.arbol = arbol
		self.escenario = escenario
		self.indice_identificadores = (
			indice_identificadores if indice_identificadores is not None else {}
		)
		self.gestor_historico = gestor_historico or GestorHistorico(
			self.indice_identificadores
		)
		self.gestor_historico.indice_activos = self.indice_identificadores
		if self.escenario is not None and (
			self.indice_identificadores
			or self.gestor_historico.eventos_archivados
			or self.gestor_historico.identificadores_eliminados
		):
			self.escenario.bloquear_geometria()

	@property
	def identificadores_retirados(self) -> set:
		return self.gestor_historico.identificadores_eliminados

	def _actualizar_clasificacion_zona(self, datos: dict) -> dict:
		if self.escenario is not None and isinstance(
			datos["epicentro"], (tuple, list)
		):
			datos["en_zona_poblada"] = self.escenario.zona_de(
				*datos["epicentro"]
			)
		return datos

	def _validar_reloj_simulado(self, datos: dict) -> None:
		if self.escenario is None:
			return
		reloj = self.escenario.reloj
		if isinstance(reloj, datetime) and reloj.microsecond:
			reloj = reloj.replace(microsecond=0)
		if self._normalizar_fecha_utc(datos["fecha"]) > self._normalizar_fecha_utc(reloj):
			raise ValueError("La fecha de ocurrencia no puede superar el reloj simulado")

	@staticmethod
	def _leer_dato(datos, nombre, predeterminado=None):
		if isinstance(datos, Mapping):
			return datos.get(nombre, predeterminado)
		return getattr(datos, nombre, predeterminado)

	@staticmethod
	def _validar_precision(nombre, valor):
		try:
			decimal = Decimal(str(valor))
		except InvalidOperation as error:
			raise ValueError(f"{nombre} debe tener máximo un decimal") from error
		if decimal.as_tuple().exponent < -1:
			raise ValueError(f"{nombre} debe tener máximo un decimal")

	@staticmethod
	def _normalizar_fecha_utc(valor):
		if isinstance(valor, datetime):
			fecha = valor
		elif isinstance(valor, str):
			texto = valor.strip()
			if not re.fullmatch(
				r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?",
				texto,
				re.IGNORECASE,
			):
				raise ValueError("La fecha debe incluir hora, minutos y segundos ISO 8601")
			try:
				fecha = datetime.fromisoformat(texto.replace("Z", "+00:00").replace("z", "+00:00"))
			except ValueError as error:
				raise ValueError("La fecha debe ser un instante ISO 8601 válido") from error
		else:
			raise ValueError("La fecha debe ser un instante ISO 8601 válido")
		if fecha.microsecond:
			raise ValueError("La fecha debe tener precisión de segundos")
		if fecha.tzinfo is None:
			fecha = fecha.replace(tzinfo=timezone.utc)
		else:
			fecha = fecha.astimezone(timezone.utc)
		return fecha

	@classmethod
	def _validar_datos(cls, datos):
		identificador = cls._leer_dato(datos, "identificador")
		magnitud = cls._leer_dato(datos, "magnitud")
		profundidad = cls._leer_dato(datos, "profundidad")
		epicentro = cls._leer_dato(datos, "epicentro")
		fecha = cls._leer_dato(datos, "fecha")
		en_zona_poblada = cls._leer_dato(datos, "en_zona_poblada", False)

		if (
			isinstance(identificador, bool)
			or not isinstance(identificador, int)
			or not 1 <= identificador <= 999999
		):
			raise ValueError("El identificador debe ser un entero entre 1 y 999999")
		if isinstance(magnitud, bool) or not isinstance(magnitud, (int, float)):
			raise ValueError("La magnitud debe ser numérica")
		if not isfinite(magnitud) or not cls.MAGNITUD_MINIMA <= magnitud <= cls.MAGNITUD_MAXIMA:
			raise ValueError("La magnitud debe estar entre -2 y 10")
		cls._validar_precision("La magnitud", magnitud)
		if isinstance(profundidad, bool) or not isinstance(profundidad, (int, float)):
			raise ValueError("La profundidad debe ser numérica")
		if not isfinite(profundidad) or not cls.PROFUNDIDAD_MINIMA <= profundidad <= cls.PROFUNDIDAD_MAXIMA:
			raise ValueError("La profundidad debe estar entre 0 y 700 km")
		cls._validar_precision("La profundidad", profundidad)

		if isinstance(epicentro, (tuple, list)) and len(epicentro) == 2:
			x, y = epicentro
			if any(
				isinstance(valor, bool)
				or not isinstance(valor, (int, float))
				or not isfinite(valor)
				for valor in (x, y)
			):
				raise ValueError("Las coordenadas del epicentro deben ser numéricas")
			if not 0 <= x <= 1000 or not 0 <= y <= 1000:
				raise ValueError("Las coordenadas deben estar entre 0 y 1000 km")
			cls._validar_precision("Las coordenadas", x)
			cls._validar_precision("Las coordenadas", y)
			epicentro = (x, y)
		else:
			raise ValueError("El epicentro debe ser un par de coordenadas cartesianas")

		fecha = cls._normalizar_fecha_utc(fecha)
		if not isinstance(en_zona_poblada, bool):
			raise ValueError("en_zona_poblada debe ser booleano")

		return {
			"identificador": identificador,
			"magnitud": magnitud,
			"profundidad": profundidad,
			"epicentro": epicentro,
			"fecha": fecha,
			"en_zona_poblada": en_zona_poblada,
		}

	@staticmethod
	def _crear_clave(evento: Evento) -> Clave:
		prioridad = calcular_prioridad(
			evento.magnitud,
			evento.profundidad,
			evento.en_zona_poblada,
		)
		return Clave(prioridad, evento.magnitud, evento.identificador)

	@staticmethod
	def _crear_clave_datos(datos: dict) -> Clave:
		prioridad = calcular_prioridad(
			datos["magnitud"],
			datos["profundidad"],
			datos["en_zona_poblada"],
		)
		return Clave(prioridad, datos["magnitud"], datos["identificador"])

	def crear_evento(self, datos):
		datos_validados = self._actualizar_clasificacion_zona(
			self._validar_datos(datos)
		)
		self._validar_reloj_simulado(datos_validados)
		identificador = datos_validados["identificador"]
		if (
			identificador in self.indice_identificadores
			or identificador in self.identificadores_retirados
		):
			self.arbol.metricas.incrementar("conflictos")
			return False
		estaciones = self._leer_dato(datos, "estaciones", ())
		if not isinstance(estaciones, (set, list, tuple)):
			raise ValueError("Las estaciones del evento deben ser una colección")
		estacion_origen = self._leer_dato(datos, "estacion")
		if estacion_origen is not None:
			estaciones = (*estaciones, estacion_origen)
		if self.escenario is not None and not estaciones:
			raise ValueError("El evento debe tener al menos una estación de procedencia")
		if any(
			not isinstance(estacion, str)
			or not estacion.strip()
			or self.escenario is not None and estacion.strip() not in self.escenario.estaciones
			for estacion in estaciones
		):
			raise ValueError("El evento contiene una estación no configurada en el escenario")

		evento = Evento(
			identificador,
			datos_validados["magnitud"],
			datos_validados["profundidad"],
			datos_validados["epicentro"],
			datos_validados["fecha"],
			1,
			"pendiente",
			datos_validados["en_zona_poblada"],
		)
		if not self.arbol.insertar(self._crear_clave(evento)):
			self.arbol.metricas.incrementar("conflictos")
			return False
		for estacion in estaciones:
			evento.agregar_estacion(estacion)
		self.indice_identificadores[identificador] = evento
		if self.escenario is not None:
			self.escenario.bloquear_geometria()
		self.arbol.metricas.incrementar("correcciones_aceptadas")
		if self.escenario is not None:
			self.arbol.actualizar_accesos_costosos(self.escenario.L)
		return evento

	def marcar_revisado(self, identificador: int) -> bool:
		evento = self.indice_identificadores.get(identificador)
		if evento is None:
			return False
		evento.estado = "revisado"
		return True

	def corregir_evento(self, identificador: int, nuevos_datos):
		evento = self.indice_identificadores.get(identificador)
		if evento is None:
			return None

		if self._leer_dato(nuevos_datos, "identificador", identificador) != identificador:
			raise ValueError("No se puede cambiar el identificador del evento")

		combinados = {
			"identificador": identificador,
			"magnitud": evento.magnitud,
			"profundidad": evento.profundidad,
			"epicentro": evento.epicentro,
			"fecha": evento.fecha,
			"en_zona_poblada": evento.en_zona_poblada,
		}
		for nombre in (
			"magnitud",
			"profundidad",
			"epicentro",
			"fecha",
			"en_zona_poblada",
		):
			valor = self._leer_dato(nuevos_datos, nombre)
			if valor is not None:
				combinados[nombre] = valor

		validados = self._actualizar_clasificacion_zona(
			self._validar_datos(combinados)
		)
		self._validar_reloj_simulado(validados)
		clave_anterior = self._crear_clave(evento)
		clave_nueva = self._crear_clave_datos(validados)
		clave_cambio = clave_anterior != clave_nueva

		if clave_cambio and not self.arbol.eliminar(clave_anterior):
			self.arbol.metricas.incrementar("conflictos")
			return None

		estado_anterior = (
			evento.magnitud,
			evento.profundidad,
			evento.epicentro,
			evento.fecha,
			evento.en_zona_poblada,
			evento.revision,
			evento.estado,
		)
		evento.magnitud = validados["magnitud"]
		evento.profundidad = validados["profundidad"]
		evento.epicentro = validados["epicentro"]
		evento.fecha = validados["fecha"]
		evento.en_zona_poblada = validados["en_zona_poblada"]
		evento.revision += 1
		evento.estado = "pendiente"

		if clave_cambio and not self.arbol.insertar(clave_nueva):
			(
				evento.magnitud,
				evento.profundidad,
				evento.epicentro,
				evento.fecha,
				evento.en_zona_poblada,
				evento.revision,
				evento.estado,
			) = estado_anterior
			self.arbol.insertar(clave_anterior)
			self.arbol.metricas.incrementar("conflictos")
			return None

		if self.escenario is not None:
			self.arbol.actualizar_accesos_costosos(self.escenario.L)
		return evento

	def eliminar_evento(self, identificador: int) -> bool:
		evento = self.indice_identificadores.get(identificador)
		if evento is None:
			return False
		if not self.arbol.eliminar(self._crear_clave(evento)):
			return False
		self.indice_identificadores.pop(identificador)
		self.identificadores_retirados.add(identificador)
		if self.escenario is not None:
			self.arbol.actualizar_accesos_costosos(self.escenario.L)
		return True