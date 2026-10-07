from collections import deque
from typing import Optional

from clave import Clave
from Nodo import Nodo
from metricas import Metricas


class AVL:
	def __init__(self, metricas: Optional[Metricas] = None):
		self.raiz = None
		self._nodos_por_identificador = {}
		self.metricas = metricas if metricas is not None else Metricas()
		self.modo = "normal"

	@property
	def modo(self) -> str:
		return self._modo

	@modo.setter
	def modo(self, modo: str) -> None:
		if modo not in {"normal", "estres"}:
			raise ValueError("El modo debe ser 'normal' o 'estres'")
		self._modo = modo

	def _obtener_altura(self, nodo: Optional[Nodo]) -> int:
		if nodo is None:
			return -1
		return nodo.altura

	def _actualizar_altura(self, nodo: Nodo) -> None:
		nodo.altura = 1 + max(
			self._obtener_altura(nodo.izquierda),
			self._obtener_altura(nodo.derecha),
		)
		nodo.factor_balance = self._factor_balance(nodo)

	def _factor_balance(self, nodo: Optional[Nodo]) -> int:
		if nodo is None:
			return 0
		return (
			self._obtener_altura(nodo.izquierda)
			- self._obtener_altura(nodo.derecha)
		)

	def _rotacion_derecha(self, nodo: Nodo) -> Nodo:
		self.metricas.incrementar("giros_derecha")
		nuevo_raiz = nodo.izquierda
		subarbol_temporal = nuevo_raiz.derecha

		nuevo_raiz.derecha = nodo
		nodo.izquierda = subarbol_temporal

		self._actualizar_altura(nodo)
		self._actualizar_altura(nuevo_raiz)
		return nuevo_raiz

	def _rotacion_izquierda(self, nodo: Nodo) -> Nodo:
		self.metricas.incrementar("giros_izquierda")
		nuevo_raiz = nodo.derecha
		subarbol_temporal = nuevo_raiz.izquierda

		nuevo_raiz.izquierda = nodo
		nodo.derecha = subarbol_temporal

		self._actualizar_altura(nodo)
		self._actualizar_altura(nuevo_raiz)
		return nuevo_raiz

	def insertar(self, clave: Clave) -> bool:
		if clave.identificador in self._nodos_por_identificador:
			return False

		self.raiz, insertado = self._insertar(
			self.raiz,
			clave,
			balancear=self.modo == "normal",
		)
		if insertado:
			nodo = self.buscar(clave)
			if nodo is not None:
				self._nodos_por_identificador[clave.identificador] = nodo
		return insertado

	def _insertar(
		self,
		nodo: Optional[Nodo],
		clave: Clave,
		balancear: bool = True,
	) -> tuple[Optional[Nodo], bool]:
		if nodo is None:
			return Nodo(clave), True

		if clave < nodo.clave:
			nodo.izquierda, insertado = self._insertar(
				nodo.izquierda,
				clave,
				balancear,
			)
		elif clave > nodo.clave:
			nodo.derecha, insertado = self._insertar(
				nodo.derecha,
				clave,
				balancear,
			)
		else:
			return nodo, False

		if not insertado:
			return nodo, False

		self._actualizar_altura(nodo)
		if not balancear:
			return nodo, True
		return self._balancear(nodo, clave)

	def _balancear(
		self,
		nodo: Nodo,
		clave: Clave,
	) -> tuple[Nodo, bool]:
		balance = self._factor_balance(nodo)

		if balance > 1 and clave < nodo.izquierda.clave:
			self.metricas.incrementar("casos_LL")
			return self._rotacion_derecha(nodo), True

		if balance < -1 and clave > nodo.derecha.clave:
			self.metricas.incrementar("casos_RR")
			return self._rotacion_izquierda(nodo), True

		if balance > 1 and clave > nodo.izquierda.clave:
			self.metricas.incrementar("casos_LR")
			nodo.izquierda = self._rotacion_izquierda(nodo.izquierda)
			return self._rotacion_derecha(nodo), True

		if balance < -1 and clave < nodo.derecha.clave:
			self.metricas.incrementar("casos_RL")
			nodo.derecha = self._rotacion_derecha(nodo.derecha)
			return self._rotacion_izquierda(nodo), True

		return nodo, True

	def eliminar(self, clave: Clave) -> bool:
		nodo_objetivo = self.buscar(clave)
		if nodo_objetivo is None:
			return False

		identificador_eliminado = nodo_objetivo.clave.identificador
		sucesor = None
		if nodo_objetivo.izquierda is not None and nodo_objetivo.derecha is not None:
			sucesor = self._buscar_minimo(nodo_objetivo.derecha)

		self.raiz, eliminado = self._eliminar(
			self.raiz,
			clave,
			balancear=self.modo == "normal",
		)
		if eliminado:
			self._nodos_por_identificador.pop(identificador_eliminado, None)
			if sucesor is not None:
				self._nodos_por_identificador[sucesor.clave.identificador] = nodo_objetivo
		return eliminado

	def _eliminar(
		self,
		nodo: Optional[Nodo],
		clave: Clave,
		balancear: bool = True,
	) -> tuple[Optional[Nodo], bool]:
		if nodo is None:
			return None, False

		if clave < nodo.clave:
			nodo.izquierda, eliminado = self._eliminar(
				nodo.izquierda,
				clave,
				balancear,
			)
		elif clave > nodo.clave:
			nodo.derecha, eliminado = self._eliminar(
				nodo.derecha,
				clave,
				balancear,
			)
		else:
			if nodo.izquierda is None:
				return nodo.derecha, True
			if nodo.derecha is None:
				return nodo.izquierda, True

			sucesor = self._buscar_minimo(nodo.derecha)
			nodo.clave = sucesor.clave
			nodo.derecha, _ = self._eliminar(
				nodo.derecha,
				sucesor.clave,
				balancear,
			)
			eliminado = True

		if not eliminado:
			return nodo, False

		self._actualizar_altura(nodo)
		if not balancear:
			return nodo, True
		return self._balancear_despues_de_eliminar(nodo)

	def _balancear_despues_de_eliminar(
		self,
		nodo: Nodo,
	) -> tuple[Nodo, bool]:
		balance = self._factor_balance(nodo)

		if balance > 1 and self._factor_balance(nodo.izquierda) >= 0:
			self.metricas.incrementar("casos_LL")
			return self._rotacion_derecha(nodo), True

		if balance > 1:
			self.metricas.incrementar("casos_LR")
			nodo.izquierda = self._rotacion_izquierda(nodo.izquierda)
			return self._rotacion_derecha(nodo), True

		if balance < -1 and self._factor_balance(nodo.derecha) <= 0:
			self.metricas.incrementar("casos_RR")
			return self._rotacion_izquierda(nodo), True

		if balance < -1:
			self.metricas.incrementar("casos_RL")
			nodo.derecha = self._rotacion_derecha(nodo.derecha)
			return self._rotacion_izquierda(nodo), True

		return nodo, True

	def recuperar_equilibrio(self) -> list[str]:
		rotaciones = []
		self.raiz = self._recuperar_subarbol(self.raiz, rotaciones)
		self.modo = "normal"
		return rotaciones

	def _recuperar_subarbol(
		self,
		nodo: Optional[Nodo],
		rotaciones: list[str],
	) -> Optional[Nodo]:
		if nodo is None:
			return None

		nodo.izquierda = self._recuperar_subarbol(nodo.izquierda, rotaciones)
		nodo.derecha = self._recuperar_subarbol(nodo.derecha, rotaciones)
		self._actualizar_altura(nodo)

		while abs(self._factor_balance(nodo)) > 1:
			balance = self._factor_balance(nodo)
			if balance > 1:
				if self._factor_balance(nodo.izquierda) < 0:
					self.metricas.incrementar("casos_LR")
					rotaciones.append(f"Rotación izquierda (LR) en {nodo.clave}")
					nodo.izquierda = self._rotacion_izquierda(nodo.izquierda)
				else:
					self.metricas.incrementar("casos_LL")
				rotaciones.append(f"Rotación derecha en {nodo.clave}")
				nodo = self._rotacion_derecha(nodo)
			else:
				if self._factor_balance(nodo.derecha) > 0:
					self.metricas.incrementar("casos_RL")
					rotaciones.append(f"Rotación derecha (RL) en {nodo.clave}")
					nodo.derecha = self._rotacion_derecha(nodo.derecha)
				else:
					self.metricas.incrementar("casos_RR")
				rotaciones.append(f"Rotación izquierda en {nodo.clave}")
				nodo = self._rotacion_izquierda(nodo)

			nodo.izquierda = self._recuperar_subarbol(nodo.izquierda, rotaciones)
			nodo.derecha = self._recuperar_subarbol(nodo.derecha, rotaciones)
			self._actualizar_altura(nodo)

		return nodo

	def _buscar_minimo(self, nodo: Nodo) -> Nodo:
		actual = nodo
		while actual.izquierda is not None:
			actual = actual.izquierda
		return actual

	def buscar(self, clave: Clave) -> Optional[Nodo]:
		actual = self.raiz
		while actual is not None:
			if clave == actual.clave:
				return actual
			if clave < actual.clave:
				actual = actual.izquierda
			else:
				actual = actual.derecha
		return None

	def in_order(self) -> None:
		print(" ".join(str(clave) for clave in self.claves_in_order()))

	def claves_in_order(self) -> list[Clave]:
		claves = []
		self._in_order(self.raiz, claves)
		return claves

	def _in_order(self, nodo: Optional[Nodo], claves: list[Clave]) -> None:
		if nodo is None:
			return
		self._in_order(nodo.izquierda, claves)
		claves.append(nodo.clave)
		self._in_order(nodo.derecha, claves)

	def pre_order(self) -> None:
		print(" ".join(str(clave) for clave in self._recorrido_pre_order(self.raiz)))

	def _recorrido_pre_order(self, nodo: Optional[Nodo]) -> list[Clave]:
		if nodo is None:
			return []
		return [nodo.clave] + self._recorrido_pre_order(nodo.izquierda) + self._recorrido_pre_order(nodo.derecha)

	def post_order(self) -> None:
		print(" ".join(str(clave) for clave in self._recorrido_post_order(self.raiz)))

	def _recorrido_post_order(self, nodo: Optional[Nodo]) -> list[Clave]:
		if nodo is None:
			return []
		return self._recorrido_post_order(nodo.izquierda) + self._recorrido_post_order(nodo.derecha) + [nodo.clave]

	def anchura(self) -> None:
		if self.raiz is None:
			print("")
			return
		cola = deque([self.raiz])
		claves = []
		while cola:
			nodo = cola.popleft()
			claves.append(nodo.clave)
			if nodo.izquierda is not None:
				cola.append(nodo.izquierda)
			if nodo.derecha is not None:
				cola.append(nodo.derecha)
		print(" ".join(str(clave) for clave in claves))

	def altura(self) -> int:
		return self._obtener_altura(self.raiz)

	def actualizar_accesos_costosos(self, limite: int) -> None:
		if isinstance(limite, bool) or not isinstance(limite, int) or limite < 0:
			raise ValueError("El límite de acceso debe ser un entero no negativo")
		pendientes = [(self.raiz, 0)] if self.raiz is not None else []
		while pendientes:
			nodo, profundidad = pendientes.pop()
			nodo.acceso_costoso = nodo.clave.prioridad == 3 and profundidad > limite
			if nodo.izquierda is not None:
				pendientes.append((nodo.izquierda, profundidad + 1))
			if nodo.derecha is not None:
				pendientes.append((nodo.derecha, profundidad + 1))

	def factor_balance_de(self, clave: Clave) -> Optional[int]:
		nodo = self.buscar(clave)
		if nodo is None:
			return None
		return self._factor_balance(nodo)

	def peso(self) -> int:
		return self._peso(self.raiz)

	def _peso(self, nodo: Optional[Nodo]) -> int:
		if nodo is None:
			return 0
		return 1 + self._peso(nodo.izquierda) + self._peso(nodo.derecha)
