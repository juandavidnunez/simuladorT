import json
from pathlib import Path

from AVL import AVL
from asociaciones import candidatos_de, referencia_de
from cola_reportes import ColaReportes
from estado import (
	EstadoOperativo,
	_reconstruir_evento,
	_reconstruir_valor,
	reconstruir_estado,
	serializar_estado,
)
from evento import calcular_prioridad
from escenario import Escenario
from gestor_eventos import GestorEventos
from historico import GestorHistorico
from metricas import Metricas
from reportes import Reporte, validar_reporte


def exportar(
	escenario: Escenario,
	arbol: AVL,
	historico: GestorHistorico,
	cola: ColaReportes,
	pila_o_metricas,
	ruta: str | Path = "estado.json",
	nombre_version: str | None = None,
) -> Path:
	if hasattr(pila_o_metricas, "estado"):
		estado = pila_o_metricas.estado
		metricas = estado.metricas
		referencias = estado.referencias
	elif hasattr(pila_o_metricas, "metricas"):
		metricas = pila_o_metricas.metricas
		referencias = pila_o_metricas.referencias
	elif isinstance(pila_o_metricas, Metricas):
		metricas = pila_o_metricas
		referencias = {}
	else:
		metricas = pila_o_metricas if isinstance(pila_o_metricas, dict) else {}
		referencias = {}
	estado_serializado = serializar_estado(
		arbol,
		historico,
		cola,
		escenario,
		metricas,
		referencias,
	)
	documento = {
		"formato": "sismolab-json-v1",
		"nombre_version": nombre_version,
		"estado": estado_serializado,
	}
	destino = Path(ruta)
	with destino.open("w", encoding="utf-8") as archivo:
		json.dump(documento, archivo, ensure_ascii=False, indent=2)
	return destino


def _leer_documento(datos_o_ruta):
	if isinstance(datos_o_ruta, (str, Path)):
		with Path(datos_o_ruta).open("r", encoding="utf-8") as archivo:
			return json.load(archivo)
	return datos_o_ruta


def _extraer_estado(documento):
	if isinstance(documento, dict) and "estado" in documento:
		if documento.get("formato") != "sismolab-json-v1":
			raise ValueError("Formato de persistencia no soportado")
		return documento["estado"]
	return documento


def _problemas_prioridad_archivada(eventos_archivados):
	problemas = []
	for evento in eventos_archivados:
		try:
			prioridad_calculada = calcular_prioridad(
				evento["magnitud"],
				evento["profundidad"],
				evento["en_zona_poblada"],
			)
			if evento.get("prioridad") != prioridad_calculada:
				problemas.append(
					f"Prioridad guardada incorrecta en evento archivado {evento['identificador']}"
				)
		except (KeyError, TypeError, ValueError):
			problemas.append(
				f"Datos incompletos para calcular prioridad en evento archivado {evento.get('identificador')}"
			)
	return problemas


def cargar_por_inserciones(
	lista_eventos,
	escenario: Escenario | None = None,
	modo: str = "normal",
	metricas: Metricas | dict | None = None,
) -> EstadoOperativo:
	if modo not in {"normal", "estres"}:
		raise ValueError("El modo debe ser 'normal' o 'estres'")
	ids = [
		evento.identificador if hasattr(evento, "identificador") else evento.get("identificador")
		for evento in lista_eventos
	]
	if len(ids) != len(set(ids)):
		raise ValueError("El archivo contiene identificadores duplicados")

	escenario = escenario if escenario is not None else Escenario(modo=modo)
	escenario.modo = modo
	metricas_estado = metricas if metricas is not None else Metricas()
	metricas_arbol = (
		metricas_estado
		if isinstance(metricas_estado, Metricas)
		else Metricas()
	)
	arbol = AVL(metricas_arbol)
	arbol.modo = modo
	indice_activos = {}
	historico = GestorHistorico(indice_activos)
	gestor = GestorEventos(
		arbol,
		indice_activos,
		escenario,
		historico,
	)
	for registro in lista_eventos:
		if hasattr(registro, "identificador"):
			datos = {
				"identificador": registro.identificador,
				"magnitud": registro.magnitud,
				"profundidad": registro.profundidad,
				"epicentro": registro.epicentro,
				"fecha": registro.fecha,
				"en_zona_poblada": registro.en_zona_poblada,
				"estaciones": getattr(registro, "estaciones", set()),
			}
		else:
			datos = {
				nombre: _reconstruir_valor(registro[nombre])
				for nombre in (
					"identificador",
					"magnitud",
					"profundidad",
					"epicentro",
					"fecha",
					"en_zona_poblada",
					"estaciones",
				)
				if nombre in registro
			}
		evento = gestor.crear_evento(datos)
		if evento is False:
			raise ValueError(
				f"No se pudo crear el evento {datos.get('identificador')} durante la carga"
			)

	cola = ColaReportes(indice_activos, arbol, escenario, historico)
	return EstadoOperativo(
		arbol,
		historico,
		cola,
		escenario,
		metricas_estado,
		{},
		gestor,
	)


def validar_topologia(
	raiz: dict,
	eventos_activos: list[dict],
	eventos_archivados: list[dict],
	escenario_datos: dict,
	modo: str,
	identificadores_eliminados=None,
	referencias=None,
	cola_reportes=None,
) -> list[str]:
	problemas = []
	try:
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
	except (KeyError, TypeError, ValueError) as error:
		return [f"Escenario inválido: {error}"]
	geometria_bloqueada = escenario_datos.get("geometria_bloqueada", False)
	if not isinstance(geometria_bloqueada, bool):
		problemas.append("El estado de geometría bloqueada debe ser booleano")
	elif (
		eventos_activos
		or eventos_archivados
		or identificadores_eliminados
		or cola_reportes
	) and not geometria_bloqueada:
		problemas.append("La geometría debe estar bloqueada cuando el escenario ya tiene datos")
	if geometria_bloqueada:
		escenario.bloquear_geometria()
	for indice, datos_reporte in enumerate(cola_reportes or []):
		try:
			validar_reporte(
				Reporte(
					datos_reporte["identificador"],
					datos_reporte["revision"],
					datos_reporte["magnitud"],
					datos_reporte["profundidad"],
					_reconstruir_valor(datos_reporte["epicentro"]),
					_reconstruir_valor(datos_reporte["fecha"]),
					datos_reporte["en_zona_poblada"],
					_reconstruir_valor(datos_reporte["estacion"]),
				),
				escenario,
			)
		except (KeyError, TypeError, ValueError) as error:
			problemas.append(f"Reporte pendiente {indice + 1} inválido: {error}")

	for tipo_eventos, registros in (("activo", eventos_activos), ("archivado", eventos_archivados)):
		for evento in registros:
			identificador = evento.get("identificador")
			try:
				datos_evento = GestorEventos._validar_datos({
					"identificador": identificador,
					"magnitud": evento["magnitud"],
					"profundidad": evento["profundidad"],
					"epicentro": _reconstruir_valor(evento["epicentro"]),
					"fecha": _reconstruir_valor(evento["fecha"]),
					"en_zona_poblada": evento["en_zona_poblada"],
				})
				revision = evento["revision"]
				if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
					raise ValueError("la revisión debe ser un entero positivo")
				estaciones = _reconstruir_valor(evento["estaciones"])
				if not isinstance(estaciones, set) or any(
					not isinstance(estacion, str) or not estacion.strip()
					for estacion in estaciones
				):
					raise ValueError("el conjunto de estaciones no es válido")
				if not estaciones.issubset(set(escenario.estaciones)):
					raise ValueError("el evento contiene estaciones fuera del catálogo guardado")
				if datos_evento["fecha"] > GestorEventos._normalizar_fecha_utc(escenario.reloj):
					raise ValueError("la ocurrencia supera el reloj simulado")
				if escenario.zona_de(*datos_evento["epicentro"]) != datos_evento["en_zona_poblada"]:
					raise ValueError("la clasificación de zona poblada no coincide con las zonas guardadas")
			except (KeyError, TypeError, ValueError) as error:
				problemas.append(f"Evento {tipo_eventos} {identificador} inválido: {error}")

	nodos = raiz.get("nodos") if isinstance(raiz, dict) else None
	indice_raiz = raiz.get("raiz") if isinstance(raiz, dict) else None
	if not isinstance(nodos, list):
		return ["La topología no contiene una lista de nodos"]
	if modo not in {"normal", "estres"}:
		problemas.append("El modo del árbol debe ser normal o estres")
	limite_acceso = escenario_datos.get("L", 3)
	if isinstance(limite_acceso, bool) or not isinstance(limite_acceso, int) or limite_acceso < 0:
		problemas.append("El límite L de acceso debe ser un entero no negativo")
		limite_acceso = 3
	if not nodos:
		if indice_raiz is not None:
			problemas.append("La raíz debe ser nula cuando no hay nodos")
		if eventos_activos:
			problemas.append("Hay eventos activos pero la topología no tiene raíz")
		problemas.extend(_problemas_prioridad_archivada(eventos_archivados))
		return problemas
	else:
		if (
			isinstance(indice_raiz, bool)
			or not isinstance(indice_raiz, int)
			or not 0 <= indice_raiz < len(nodos)
		):
			problemas.append("El índice de raíz es inválido")

	ids_activos = [item.get("identificador") for item in eventos_activos]
	ids_archivados = [item.get("identificador") for item in eventos_archivados]
	ids_retirados = set(identificadores_eliminados or ())
	for identificador in (*ids_activos, *ids_archivados, *ids_retirados):
		if isinstance(identificador, bool) or not isinstance(identificador, int) or not 1 <= identificador <= 999999:
			problemas.append(f"Identificador inválido en el snapshot: {identificador}")
	if len(ids_activos) != len(set(ids_activos)):
		problemas.append("Hay identificadores activos duplicados")
	if len(ids_archivados) != len(set(ids_archivados)):
		problemas.append("Hay identificadores archivados duplicados")
	if set(ids_activos) & set(ids_archivados):
		problemas.append("Hay identificadores repetidos entre activos e históricos")
	if set(ids_activos) & (ids_retirados - set(ids_archivados)):
		problemas.append("Hay identificadores activos marcados como eliminados")

	if referencias is not None:
		pares_referencia = referencias if isinstance(referencias, list) else []
		mapa_referencias = {}
		for par in pares_referencia:
			if not isinstance(par, list) or len(par) != 2:
				problemas.append("Formato de referencias inválido")
				continue
			origen, destino = par
			if origen in mapa_referencias:
				problemas.append(f"Referencia duplicada para el evento {origen}")
			mapa_referencias[origen] = destino
		ids_disponibles = set(ids_activos) | set(ids_archivados)
		for origen, destino in mapa_referencias.items():
			if origen not in ids_disponibles or destino not in ids_disponibles or origen == destino:
				problemas.append(f"Referencia inválida entre {origen} y {destino}")
		for origen in mapa_referencias:
			vistos = set()
			actual = origen
			while actual in mapa_referencias:
				if actual in vistos:
					problemas.append(f"Ciclo en referencias desde el evento {origen}")
					break
				vistos.add(actual)
				actual = mapa_referencias[actual]
		eventos_modelo = [
			_reconstruir_evento(evento)
			for evento in (*eventos_activos, *eventos_archivados)
		]
		referencias_esperadas = {}
		for evento in eventos_modelo:
			referencia = referencia_de(
				evento,
				candidatos_de(evento, eventos_modelo, escenario),
			)
			if referencia is not None:
				referencias_esperadas[evento.identificador] = referencia.identificador
		if mapa_referencias != referencias_esperadas:
			problemas.append("Las referencias almacenadas no coinciden con la política determinista")

	if (
		isinstance(indice_raiz, bool)
		or not isinstance(indice_raiz, int)
		or not 0 <= indice_raiz < len(nodos)
	):
		if ids_activos:
			problemas.append("Hay eventos activos pero la topología no tiene raíz")
		return problemas

	indegree = [0] * len(nodos)
	for registro in nodos:
		for lado in ("izquierda", "derecha"):
			indice_hijo = registro.get(lado)
			if (
				not isinstance(indice_hijo, bool)
				and isinstance(indice_hijo, int)
				and 0 <= indice_hijo < len(nodos)
			):
				indegree[indice_hijo] += 1
	if any(valor > 1 for valor in indegree):
		problemas.append("La topología contiene nodos con más de un padre")
	if indegree[indice_raiz] != 0:
		problemas.append("La raíz participa en un ciclo o tiene un padre")

	claves = []
	for indice, registro in enumerate(nodos):
		try:
			clave_datos = registro["clave"]
			claves.append(
				(
					clave_datos["prioridad"],
					clave_datos["magnitud"],
					clave_datos["identificador"],
				)
			)
		except (KeyError, TypeError):
			claves.append(None)
			problemas.append(f"El nodo {indice} no tiene una clave válida")

		hijos = []
		for lado in ("izquierda", "derecha"):
			indice_hijo = registro.get(lado)
			if indice_hijo is not None:
				if (
					isinstance(indice_hijo, bool)
					or not isinstance(indice_hijo, int)
					or not 0 <= indice_hijo < len(nodos)
				):
					problemas.append(f"Índice de hijo inválido en nodo {indice}")
				else:
					hijos.append(indice_hijo)
		if len(hijos) != len(set(hijos)):
			problemas.append(f"Un nodo no puede ser hijo izquierdo y derecho del nodo {indice}")

		try:
			altura = registro["altura"]
			factor = registro["factor_balance"]
			if isinstance(altura, bool) or not isinstance(altura, int):
				raise ValueError
			if isinstance(factor, bool) or not isinstance(factor, int):
				raise ValueError
		except (KeyError, ValueError):
			problemas.append(f"Altura o factor declarado inválido en nodo {indice}")

	visitados = set()
	profundidades = {}
	ciclo_o_referencia_repetida = False
	pendientes = [(indice_raiz, None, None, 0)]
	while pendientes:
		indice, limite_inferior, limite_superior, profundidad_nodo = pendientes.pop()
		if indice in visitados:
			problemas.append("La topología contiene un ciclo o referencia repetida")
			ciclo_o_referencia_repetida = True
			continue
		visitados.add(indice)
		profundidades[indice] = profundidad_nodo
		clave = claves[indice]
		if clave is not None:
			if limite_inferior is not None and not limite_inferior < clave:
				problemas.append(f"Orden BST inválido en nodo {indice}")
			if limite_superior is not None and not clave < limite_superior:
				problemas.append(f"Orden BST inválido en nodo {indice}")
		for lado, inferior, superior in (
			("derecha", clave, limite_superior),
			("izquierda", limite_inferior, clave),
		):
			indice_hijo = nodos[indice].get(lado)
			if (
				not isinstance(indice_hijo, bool)
				and isinstance(indice_hijo, int)
				and 0 <= indice_hijo < len(nodos)
			):
				pendientes.append((indice_hijo, inferior, superior, profundidad_nodo + 1))
	if len(visitados) != len(nodos):
		problemas.append("La topología contiene nodos desconectados de la raíz")
	if any(valor > 1 for valor in indegree) or indegree[indice_raiz] != 0:
		ciclo_o_referencia_repetida = True
	if ciclo_o_referencia_repetida or len(visitados) != len(nodos):
		return problemas

	alturas_reales = {}
	pendientes_postorden = [(indice_raiz, False)]
	while pendientes_postorden:
		indice, procesado = pendientes_postorden.pop()
		if indice not in visitados:
			continue
		if not procesado:
			pendientes_postorden.append((indice, True))
			for lado in ("derecha", "izquierda"):
				indice_hijo = nodos[indice].get(lado)
				if (
					not isinstance(indice_hijo, bool)
					and isinstance(indice_hijo, int)
					and 0 <= indice_hijo < len(nodos)
				):
					pendientes_postorden.append((indice_hijo, False))
			continue
		izquierda = nodos[indice].get("izquierda")
		derecha = nodos[indice].get("derecha")
		altura_izquierda = alturas_reales.get(izquierda, -1)
		altura_derecha = alturas_reales.get(derecha, -1)
		altura_real = 1 + max(altura_izquierda, altura_derecha)
		factor_real = altura_izquierda - altura_derecha
		alturas_reales[indice] = altura_real
		if nodos[indice].get("altura") != altura_real:
			problemas.append(f"Altura incorrecta en nodo {indice}")
		if nodos[indice].get("factor_balance") != factor_real:
			problemas.append(f"Factor de balance incorrecto en nodo {indice}")
		if modo != "estres" and abs(factor_real) > 1:
			problemas.append(f"El nodo {indice} está desbalanceado en modo normal")

	eventos_activos_por_id = {item.get("identificador"): item for item in eventos_activos}
	ids_nodos = {clave[2] for clave in claves if clave is not None}
	if ids_nodos != set(ids_activos):
		problemas.append("Los nodos activos y los eventos activos no coinciden")
	for indice, clave in enumerate(claves):
		if clave is None:
			continue
		acceso_declarado = nodos[indice].get("acceso_costoso")
		if not isinstance(acceso_declarado, bool):
			problemas.append(f"Marca de acceso costoso inválida en nodo {indice}")
		else:
			acceso_esperado = clave[0] == 3 and profundidades.get(indice, 0) > limite_acceso
			if acceso_declarado != acceso_esperado:
				problemas.append(f"Marca de acceso costoso inconsistente en nodo {indice}")
		evento = eventos_activos_por_id.get(clave[2])
		if evento is None:
			continue
		try:
			prioridad_calculada = calcular_prioridad(
				evento["magnitud"],
				evento["profundidad"],
				evento["en_zona_poblada"],
			)
			if clave[0] != prioridad_calculada:
				problemas.append(f"Prioridad de clave incorrecta en nodo {indice}")
			if evento.get("prioridad") != prioridad_calculada:
				problemas.append(f"Prioridad guardada incorrecta en evento {clave[2]}")
			if clave[1] != evento["magnitud"]:
				problemas.append(f"Magnitud de clave inconsistente en evento {clave[2]}")
		except (KeyError, TypeError, ValueError):
			problemas.append(f"Datos incompletos para calcular prioridad en evento {clave[2]}")

	problemas.extend(_problemas_prioridad_archivada(eventos_archivados))
	return problemas


def cargar_por_topologia(datos, estado_actual: EstadoOperativo | None = None):
	try:
		documento = _leer_documento(datos)
		estado_datos = _extraer_estado(documento)
		if estado_datos.get("version_esquema") != 1:
			return estado_actual, ["Versión de snapshot no soportada"]
		problemas = validar_topologia(
			estado_datos["arbol"]["raiz"],
			estado_datos["eventos_activos"],
			estado_datos["eventos_archivados"],
			estado_datos["escenario"],
			estado_datos["arbol"]["modo"],
			_reconstruir_valor(estado_datos["identificadores_eliminados"]),
			estado_datos.get("referencias", []),
			estado_datos.get("cola_reportes", []),
		)
		if problemas:
			return estado_actual, problemas
		return reconstruir_estado(estado_datos), []
	except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
		return estado_actual, [f"No se pudo cargar la topología: {error}"]