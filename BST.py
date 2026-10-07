from AVL import AVL
from metricas import Metricas


class BST(AVL):
	def __init__(self, metricas: Metricas | None = None):
		self.raiz = None
		self._nodos_por_identificador = {}
		self.metricas = metricas if metricas is not None else Metricas()
		self._modo = "estres"

	@property
	def modo(self) -> str:
		return "estres"

	@modo.setter
	def modo(self, modo: str) -> None:
		if modo != "estres":
			raise ValueError("Un BST puro no admite modo balanceado")
		self._modo = "estres"

	def recuperar_equilibrio(self) -> list[str]:
		raise NotImplementedError("Un BST puro no aplica rotaciones AVL")