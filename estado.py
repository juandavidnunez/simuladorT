from collections.abc import Mapping
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite

from AVL import AVL
from Nodo import Nodo
from asociaciones import FuentesEventos
from cola_reportes import ColaReportes
from escenario import Escenario
from evento import Evento, calcular_prioridad
from gestor_eventos import GestorEventos
from historico import GestorHistorico
from reportes import Reporte
from clave import Clave
from metricas import Metricas


@dataclass
class EstadoOperativo:
	arbol: AVL
	historico: GestorHistorico
	cola: ColaReportes
	escenario: Escenario
	metricas: Metricas | dict
	referencias: dict
	gestor_eventos: GestorEventos

	@property
	def fuentes_eventos(self) -> FuentesEventos:
		return FuentesEventos(
			self.arbol,
			self.historico.indice_activos,
			self.historico,
		)


def _serializar_valor(valor):
	if isinstance(valor, Metricas):
		return {"tipo": "metricas", "valores": valor.a_dict()}
	if isinstance(valor, datetime):
		return {"tipo": "datetime", "valor": valor.isoformat()}
	if isinstance(valor, date):
		return {"tipo": "date", "valor": valor.isoformat()}
	if isinstance(valor, tuple):
		return {"tipo": "tuple", "elementos": [_serializar_valor(item) for item in valor]}
	if isinstance(valor, list):
		return [_serializar_valor(item) for item in valor]
	if isinstance(valor, set):
		return {
			"tipo": "set",
			"elementos": [_serializar_valor(item) for item in sorted(valor, key=repr)],
		}
	if isinstance(valor, Mapping):
		return {
			"tipo": "dict",
			"elementos": [
				[_serializar_valor(clave), _serializar_valor(item)]
				for clave, item in valor.items()
			],
		}
	if valor is None or isinstance(valor, (str, int, bool)):
		return valor
	if isinstance(valor, float) and isfinite(valor):
		return valor
	raise TypeError(f"Valor no serializable: {type(valor).__name__}")


def _reconstruir_valor(valor):
	if isinstance(valor, list):
		return [_reconstruir_valor(item) for item in valor]
	if not isinstance(valor, dict):
		return valor
	tipo = valor.get("tipo")
	if tipo == "metricas":
		return Metricas.desde_dict(valor["valores"])
	if tipo == "datetime":
		return datetime.fromisoformat(valor["valor"])
	if tipo == "date":
		return date.fromisoformat(valor["valor"])
	if tipo == "tuple":
		return tuple(_reconstruir_valor(item) for item in valor["elementos"])
	if tipo == "set":
		return {_reconstruir_valor(item) for item in valor["elementos"]}
	if tipo == "dict":
		return {
			_reconstruir_valor(clave): _reconstruir_valor(item)
			for clave, item in valor["elementos"]
		}
	return {clave: _reconstruir_valor(item) for clave, item in valor.items()}


def _serializar_evento(evento: Evento) -> dict:
	return {
		"identificador": evento.identificador,
		"magnitud": evento.magnitud,
		"profundidad": evento.profundidad,
		"epicentro": _serializar_valor(evento.epicentro),
		"fecha": _serializar_valor(evento.fecha),
		"revision": evento.revision,
		"estado": evento.estado,
		"en_zona_poblada": evento.en_zona_poblada,
		"prioridad": calcular_prioridad(
			evento.magnitud,
			evento.profundidad,
			evento.en_zona_poblada,
		),
		"estaciones": _serializar_valor(evento.estaciones),
	}


def _reconstruir_evento(datos: dict) -> Evento:
	evento = Evento(
		datos["identificador"],
		datos["magnitud"],
		datos["profundidad"],
		_reconstruir_valor(datos["epicentro"]),
		_reconstruir_valor(datos["fecha"]),
		datos["revision"],
		datos["estado"],
		datos["en_zona_poblada"],
	)
	evento.estaciones = _reconstruir_valor(datos["estaciones"])
	return evento


def _serializar_reporte(reporte: Reporte) -> dict:
	return {
		"identificador": reporte.identificador,
		"revision": reporte.revision,
		"magnitud": reporte.magnitud,
		"profundidad": reporte.profundidad,
		"epicentro": _serializar_valor(reporte.epicentro),
		"fecha": _serializar_valor(reporte.fecha),
		"en_zona_poblada": reporte.en_zona_poblada,
		"estacion": _serializar_valor(reporte.estacion),
	}


def _reconstruir_reporte(datos: dict) -> Reporte:
	return Reporte(
		datos["identificador"],
		datos["revision"],
		datos["magnitud"],
		datos["profundidad"],
		_reconstruir_valor(datos["epicentro"]),
		_reconstruir_valor(datos["fecha"]),
		datos["en_zona_poblada"],
		_reconstruir_valor(datos["estacion"]),
	)


def _serializar_nodo(nodo: Nodo | None):
	if nodo is None:
		return {"raiz": None, "nodos": []}
	indices = {id(nodo): 0}
	pendientes = deque([nodo])
	nodos = []
	while pendientes:
		actual = pendientes.popleft()
		registro = {
			"clave": {
			"prioridad": actual.clave.prioridad,
			"magnitud": actual.clave.magnitud,
			"identificador": actual.clave.identificador,
			},
			"altura": actual.altura,
			"factor_balance": actual.factor_balance,
			"acceso_costoso": actual.acceso_costoso,
			"izquierda": None,
			"derecha": None,
		}
		for atributo in ("izquierda", "derecha"):
			hijo = getattr(actual, atributo)
			if hijo is not None:
				indice_hijo = indices.get(id(hijo))
				if indice_hijo is None:
					indice_hijo = len(indices)
					indices[id(hijo)] = indice_hijo
					pendientes.append(hijo)
				registro[atributo] = indice_hijo
		nodos.append(registro)
	return {"raiz": 0, "nodos": nodos}


def _reconstruir_nodo(datos, indice_nodos: dict[int, Nodo]) -> Nodo | None:
	if datos["raiz"] is None:
		return None
	nodos = []
	for datos_nodo in datos["nodos"]:
		datos_clave = datos_nodo["clave"]
		clave = Clave(
			datos_clave["prioridad"],
			datos_clave["magnitud"],
			datos_clave["identificador"],
		)
		if clave.identificador in indice_nodos:
			raise ValueError("El snapshot contiene identificadores activos duplicados")
		nodo_nuevo = Nodo(clave)
		nodo_nuevo.altura = datos_nodo["altura"]
		nodo_nuevo.factor_balance = datos_nodo.get("factor_balance", 0)
		nodo_nuevo.acceso_costoso = datos_nodo.get("acceso_costoso", False)
		indice_nodos[clave.identificador] = nodo_nuevo
		nodos.append(nodo_nuevo)

	indice_raiz = datos["raiz"]
	if not isinstance(indice_raiz, int) or not 0 <= indice_raiz < len(nodos):
		raise ValueError("Snapshot inconsistente: índice de raíz inválido")
	for indice, datos_nodo in enumerate(datos["nodos"]):
		for atributo in ("izquierda", "derecha"):
			indice_hijo = datos_nodo[atributo]
			if indice_hijo is None:
				continue
			if not isinstance(indice_hijo, int) or not 0 <= indice_hijo < len(nodos):
				raise ValueError("Snapshot inconsistente: índice de hijo inválido")
			setattr(nodos[indice], atributo, nodos[indice_hijo])
	return nodos[indice_raiz]


def serializar_estado(
	arbol: AVL,
	historico: GestorHistorico,
	cola: ColaReportes,
	escenario: Escenario,
	metricas: dict,
	referencias: dict | None = None,
) -> dict:
	return {
		"version_esquema": 1,
		"arbol": {
			"modo": arbol.modo,
			"raiz": _serializar_nodo(arbol.raiz),
		},
		"eventos_activos": [
			_serializar_evento(evento)
			for evento in historico.indice_activos.values()
		],
		"eventos_archivados": [
			_serializar_evento(evento)
			for evento in historico.eventos_archivados.values()
		],
		"identificadores_eliminados": _serializar_valor(
			historico.identificadores_eliminados
		),
		"cola_reportes": [
			_serializar_reporte(reporte)
			for reporte in cola.reportes_pendientes()
		],
		"escenario": {
			"reloj": _serializar_valor(escenario.reloj),
			"estaciones": list(escenario.estaciones),
			"geometria_bloqueada": bool(
				escenario.geometria_bloqueada
				or historico.indice_activos
				or historico.eventos_archivados
			or historico.identificadores_eliminados
			or cola.reportes_pendientes()
			),
			"zonas": [
				{
					"x_min": zona.x_min,
					"x_max": zona.x_max,
					"y_min": zona.y_min,
					"y_max": zona.y_max,
					"poblada": zona.poblada,
				}
				for zona in escenario.zonas
			],
			"W": escenario.W,
			"R": escenario.R,
			"L": escenario.L,
			"T": escenario.T,
			"modo": escenario.modo,
		},
		"metricas": _serializar_valor(metricas),
		"metricas_arbol": _serializar_valor(arbol.metricas),
		"referencias": [
			[identificador, referencia]
			for identificador, referencia in (referencias or {}).items()
		],
		"rotaciones_ultimo_archivo": list(historico.rotaciones_ultimo_archivo),
	}


def reconstruir_estado(datos: dict) -> EstadoOperativo:
	if datos.get("version_esquema") != 1:
		raise ValueError("Versión de snapshot no soportada")

	modo_arbol = datos["arbol"]["modo"]
	if modo_arbol not in {"normal", "estres"}:
		raise ValueError("El modo guardado debe ser normal o estres")
	metricas_arbol = _reconstruir_valor(
		datos.get("metricas_arbol", {"tipo": "metricas", "valores": {}})
	)
	if not isinstance(metricas_arbol, Metricas):
		metricas_arbol = Metricas()
	arbol = AVL(metricas_arbol)
	arbol.modo = modo_arbol
	indice_nodos = {}
	arbol.raiz = _reconstruir_nodo(datos["arbol"]["raiz"], indice_nodos)
	arbol._nodos_por_identificador = indice_nodos

	indice_activos = {
		evento.identificador: evento
		for evento in (
			_reconstruir_evento(item) for item in datos["eventos_activos"]
		)
	}
	if set(indice_activos) != set(indice_nodos):
		raise ValueError("Snapshot inconsistente: nodos y eventos activos difieren")
	for identificador, nodo in indice_nodos.items():
		if nodo.clave.identificador != identificador:
			raise ValueError("Snapshot inconsistente en el índice de nodos")

	ids_eliminados = _reconstruir_valor(datos["identificadores_eliminados"])
	historico = GestorHistorico(indice_activos, ids_eliminados)
	historico.eventos_archivados = {
		evento.identificador: evento
		for evento in (
			_reconstruir_evento(item) for item in datos["eventos_archivados"]
		)
	}
	historico.rotaciones_ultimo_archivo = list(
		datos.get("rotaciones_ultimo_archivo", [])
	)

	escenario_datos = datos["escenario"]
	escenario = Escenario(
		reloj=_reconstruir_valor(escenario_datos["reloj"]),
		zonas=escenario_datos["zonas"],
		W=escenario_datos["W"],
		R=escenario_datos["R"],
		L=escenario_datos["L"],
		T=escenario_datos["T"],
		modo=escenario_datos["modo"],
		estaciones=escenario_datos.get("estaciones"),
	)
	if escenario_datos.get("geometria_bloqueada", False):
		escenario.bloquear_geometria()
	cola = ColaReportes(indice_activos, arbol, escenario, historico)
	cola.restaurar_pendientes(
		_reconstruir_reporte(item) for item in datos["cola_reportes"]
	)
	metricas = _reconstruir_valor(datos["metricas"])
	if isinstance(metricas, Metricas):
		arbol.metricas = metricas
	referencias = {
		identificador: referencia
		for identificador, referencia in datos.get("referencias", [])
	}
	gestor_eventos = GestorEventos(
		arbol,
		indice_activos,
		escenario,
		historico,
	)
	return EstadoOperativo(
		arbol,
		historico,
		cola,
		escenario,
		metricas,
		referencias,
		gestor_eventos,
	)