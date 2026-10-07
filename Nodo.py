from clave import Clave


class Nodo:
	def __init__(self, clave: Clave):
		self.clave = clave
		self.izquierda = None
		self.derecha = None
		self.altura = 0
		self.factor_balance = 0
		self.acceso_costoso = False

	def es_hoja(self) -> bool:
		return self.izquierda is None and self.derecha is None

	def __repr__(self) -> str:
		return (
			f"Nodo(clave={self.clave}, altura={self.altura}, "
			f"factor_balance={self.factor_balance}, "
			f"acceso_costoso={self.acceso_costoso})"
		)
