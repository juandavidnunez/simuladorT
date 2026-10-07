from datetime import date, datetime, time

from AVL import AVL
from Nodo import Nodo
from escenario import Escenario


class GestorHistorico:
	def __init__(self, indice_activos: dict, identificadores_eliminados: set | None = None):
		self.eventos_archivados = {}
		self.identificadores_eliminados = (
			identificadores_eliminados
			if identificadores_eliminados is not None
			else set()
		)
		self.indice_activos = indice_activos
		self.rotaciones_ultimo_archivo = []

	@staticmethod
	def _fecha_ocurrencia(fecha) -> datetime | None:
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

	def _eventos_de_rama(self, nodo: Nodo) -> list:
		eventos = []
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			evento = self.indice_activos.get(actual.clave.identificador)
			if evento is None:
				return []
			eventos.append(evento)
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)
		return eventos

	def es_elegible(self, nodo: Nodo, escenario: Escenario) -> bool:
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			evento = self.indice_activos.get(actual.clave.identificador)
			if evento is None or actual.clave.prioridad != 1:
				return False
			fecha = self._fecha_ocurrencia(evento.fecha)
			if fecha is None:
				return False
			try:
				antiguedad = escenario.reloj - fecha
			except TypeError:
				return False
			if antiguedad.total_seconds() <= escenario.T * 3600:
				return False
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)
		return True

	@staticmethod
	def _profundidad(nodo: Nodo, arbol: AVL) -> int | None:
		pendientes = [(arbol.raiz, 0)]
		while pendientes:
			actual, profundidad = pendientes.pop()
			if actual is nodo:
				return profundidad
			if actual.izquierda is not None:
				pendientes.append((actual.izquierda, profundidad + 1))
			if actual.derecha is not None:
				pendientes.append((actual.derecha, profundidad + 1))
		return None

	@staticmethod
	def _cantidad_nodos(nodo: Nodo) -> int:
		cantidad = 0
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			cantidad += 1
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)
		return cantidad

	def buscar_rama_a_archivar(
		self,
		arbol: AVL,
		escenario: Escenario,
	) -> Nodo | None:
		candidatos = []
		pendientes = [(arbol.raiz, 0)] if arbol.raiz is not None else []
		while pendientes:
			nodo, profundidad = pendientes.pop()
			if self.es_elegible(nodo, escenario):
				candidatos.append(
					(
						self._cantidad_nodos(nodo),
						profundidad,
						nodo.clave.identificador,
						nodo,
					)
				)
			if nodo.izquierda is not None:
				pendientes.append((nodo.izquierda, profundidad + 1))
			if nodo.derecha is not None:
				pendientes.append((nodo.derecha, profundidad + 1))
		if not candidatos:
			return None
		return max(candidatos, key=lambda candidato: candidato[:3])[3]

	@staticmethod
	def _buscar_ruta(arbol: AVL, objetivo: Nodo) -> list[tuple[Nodo, str]] | None:
		if arbol.raiz is None:
			return None
		pendientes = [arbol.raiz]
		anterior = {arbol.raiz: None}
		while pendientes:
			actual = pendientes.pop()
			if actual is objetivo:
				break
			for atributo in ("izquierda", "derecha"):
				hijo = getattr(actual, atributo)
				if hijo is not None and hijo not in anterior:
					anterior[hijo] = (actual, atributo)
					pendientes.append(hijo)
		else:
			return None

		ruta = []
		actual = objetivo
		while actual is not arbol.raiz:
			paso = anterior.get(actual)
			if paso is None:
				return None
			padre, atributo = paso
			ruta.append((padre, atributo))
			actual = padre
		ruta.reverse()
		return ruta

	def archivar_rama(self, nodo: Nodo, arbol: AVL) -> list:
		ruta = self._buscar_ruta(arbol, nodo)
		if ruta is None:
			return []

		ids_a_archivar = []
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			ids_a_archivar.append(actual.clave.identificador)
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)
		eventos = {
			identificador: self.indice_activos[identificador]
			for identificador in ids_a_archivar
		}
		nodos = {}
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			nodos[actual.clave.identificador] = actual
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)

		if not ruta:
			arbol.raiz = None
		else:
			padre, lado = ruta[-1]
			setattr(padre, lado, None)
			ancestros = [
				(ruta[-1][0], None),
				*reversed(ruta[:-1]),
			]
			self.rotaciones_ultimo_archivo = []
			reconstruido = None
			for antecesor, lado in ancestros:
				if lado is not None:
					setattr(antecesor, lado, reconstruido)
				arbol._actualizar_altura(antecesor)
				if arbol.modo == "normal":
					reconstruido = arbol._recuperar_subarbol(
						antecesor,
						self.rotaciones_ultimo_archivo,
					)
				else:
					reconstruido = antecesor
			arbol.raiz = reconstruido
		if not ruta:
			self.rotaciones_ultimo_archivo = []

		for identificador, evento in eventos.items():
			self.eventos_archivados[identificador] = evento
			self.indice_activos.pop(identificador)
			arbol._nodos_por_identificador.pop(identificador, None)
			self.identificadores_eliminados.add(identificador)
		arbol.metricas.incrementar("archivos_masivos")
		arbol.metricas.incrementar("eventos_archivados", len(eventos))

		return list(eventos.values())