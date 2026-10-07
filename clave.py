class Clave:
	def __init__(self, prioridad, magnitud, identificador):
		self.prioridad = prioridad
		self.magnitud = magnitud
		self.identificador = identificador

	def __lt__(self, otra):
		return (
			self.prioridad,
			self.magnitud,
			self.identificador,
		) < (
			otra.prioridad,
			otra.magnitud,
			otra.identificador,
		)

	def __eq__(self, otra):
		if not isinstance(otra, Clave):
			return NotImplemented

		return (
			self.prioridad,
			self.magnitud,
			self.identificador,
		) == (
			otra.prioridad,
			otra.magnitud,
			otra.identificador,
		)

	def __repr__(self):
		return (
			f"Clave({self.prioridad}, {self.magnitud}, "
			f"{self.identificador})"
		)


if __name__ == "__main__":
	claves = [
		Clave(3, 5.2, 25),
		Clave(2, 5.8, 20),
		Clave(3, 5.2, 10),
		Clave(1, 9.0, 1),
		Clave(3, 6.1, 30),
		Clave(2, 4.5, 8),
	]

	esperado = [
		Clave(1, 9.0, 1),
		Clave(2, 4.5, 8),
		Clave(2, 5.8, 20),
		Clave(3, 5.2, 10),
		Clave(3, 5.2, 25),
		Clave(3, 6.1, 30),
	]

	ordenado = sorted(claves)
	print("Claves originales:", claves)
	print("Claves ordenadas:", ordenado)
	assert ordenado == esperado
	assert claves[2] < claves[0]
	assert claves[0] > claves[2]
	assert claves[0] == claves[0]
	print("La comparación de claves pasó")
