from decimal import Decimal, ROUND_HALF_UP


class Evento:
	DECIMALES_COMPARACION = 2

	def __init__(
		self,
		identificador,
		magnitud,
		profundidad,
		epicentro,
		fecha,
		revision,
		estado,
		en_zona_poblada=False,
	):
		self.identificador = identificador
		self.magnitud = magnitud
		self.profundidad = profundidad
		self.epicentro = epicentro
		self.fecha = fecha
		self.revision = revision
		self.estado = estado
		self.en_zona_poblada = en_zona_poblada
		self.estaciones = set()

	def __str__(self):
		return (
			f"Evento(id={self.identificador}, magnitud={self.magnitud}, "
			f"profundidad={self.profundidad}, epicentro={self.epicentro}, "
			f"fecha={self.fecha}, revision={self.revision}, "
			f"estado={self.estado})"
		)

	@classmethod
	def _normalizar_dato(cls, dato):
		if isinstance(dato, float):
			cuantizador = Decimal("1").scaleb(-cls.DECIMALES_COMPARACION)
			return Decimal(str(dato)).quantize(
				cuantizador,
				rounding=ROUND_HALF_UP,
			)
		if isinstance(dato, (tuple, list)):
			return tuple(cls._normalizar_dato(valor) for valor in dato)
		return dato

	def datos_iguales(self, otro):
		campos = ("magnitud", "profundidad", "epicentro", "fecha")
		if not all(hasattr(otro, campo) for campo in campos):
			return False

		return all(
			self._normalizar_dato(getattr(self, campo))
			== self._normalizar_dato(getattr(otro, campo))
			for campo in campos
		)

	def agregar_estacion(self, estacion):
		if estacion is not None:
			self.estaciones.add(estacion)


def calcular_prioridad(magnitud, profundidad, en_zona_poblada):
	if magnitud >= 6.0:
		return 3

	if magnitud >= 4.5 and profundidad <= 30.0 and en_zona_poblada:
		return 3

	if magnitud >= 4.5:
		return 2

	return 1
