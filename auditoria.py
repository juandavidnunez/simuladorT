from AVL import AVL
from Nodo import Nodo
from asociaciones import candidatos_de, referencia_de
from evento import calcular_prioridad
from escenario import Escenario


def verificar_estructura(
	arbol: AVL,
	escenario: Escenario,
	indice_activos: dict | None = None,
	historico=None,
	referencias: dict | None = None,
) -> list[dict]:
	incidencias = {}
	incidencias_por_id = {}

	def obtener_incidencia(nodo: Nodo) -> dict:
		clave_interna = id(nodo)
		if clave_interna not in incidencias:
			incidencias[clave_interna] = {
				"identificador": nodo.clave.identificador,
				"tipos": set(),
				"errores": [],
				"desbalances": [],
			}
		return incidencias[clave_interna]

	def registrar_error(nodo: Nodo, tipo: str, mensaje: str) -> None:
		incidencia = obtener_incidencia(nodo)
		incidencia["tipos"].add(tipo)
		incidencia["errores"].append(mensaje)

	def registrar_error_id(identificador: int, tipo: str, mensaje: str) -> None:
		incidencia = incidencias_por_id.setdefault(
			identificador,
			{"identificador": identificador, "tipos": set(), "errores": [], "desbalances": []},
		)
		incidencia["tipos"].add(tipo)
		incidencia["errores"].append(mensaje)

	visitados = set()
	nodos_en_orden = []
	profundidades = {}
	ids_vistos = set()
	pendientes = [(arbol.raiz, None, None, 0)] if arbol.raiz is not None else []
	while pendientes:
		nodo, limite_inferior, limite_superior, profundidad = pendientes.pop()
		if id(nodo) in visitados:
			registrar_error(nodo, "estructura", "Nodo repetido o ciclo en la estructura")
			continue
		visitados.add(id(nodo))
		profundidades[id(nodo)] = profundidad
		nodos_en_orden.append(nodo)
		if nodo.clave.identificador in ids_vistos:
			registrar_error(nodo, "unicidad", "Identificador duplicado en el AVL")
		ids_vistos.add(nodo.clave.identificador)
		if indice_activos is not None:
			evento = indice_activos.get(nodo.clave.identificador)
			if evento is None:
				registrar_error(nodo, "referencia", "El nodo no tiene evento activo asociado")
			else:
				prioridad = calcular_prioridad(
					evento.magnitud,
					evento.profundidad,
					evento.en_zona_poblada,
				)
				if prioridad != nodo.clave.prioridad or evento.magnitud != nodo.clave.magnitud:
					registrar_error(nodo, "clave", "La clave no coincide con los datos vigentes del evento")
		if limite_inferior is not None and not limite_inferior < nodo.clave:
			registrar_error(
				nodo,
				"orden",
				"Clave no es mayor que el límite inferior de su subárbol",
			)
		if limite_superior is not None and not nodo.clave < limite_superior:
			registrar_error(
				nodo,
				"orden",
				"Clave no es menor que el límite superior de su subárbol",
			)
		if nodo.derecha is not None:
			pendientes.append((nodo.derecha, nodo.clave, limite_superior, profundidad + 1))
		if nodo.izquierda is not None:
			pendientes.append((nodo.izquierda, limite_inferior, nodo.clave, profundidad + 1))

	alturas_reales = {}
	for nodo in reversed(nodos_en_orden):
		altura_izquierda = (
			alturas_reales.get(id(nodo.izquierda), -1)
			if nodo.izquierda is not None
			else -1
		)
		altura_derecha = (
			alturas_reales.get(id(nodo.derecha), -1)
			if nodo.derecha is not None
			else -1
		)
		altura_real = 1 + max(altura_izquierda, altura_derecha)
		factor_real = altura_izquierda - altura_derecha
		alturas_reales[id(nodo)] = altura_real

		errores_metadata = []
		if nodo.altura != altura_real:
			errores_metadata.append(
				f"altura almacenada {nodo.altura}, calculada {altura_real}"
			)
		if getattr(nodo, "factor_balance", None) != factor_real:
			errores_metadata.append(
				"factor almacenado "
			f"{getattr(nodo, 'factor_balance', None)}, calculado {factor_real}"
			)
		if escenario.modo == "normal" and abs(factor_real) > 1:
			errores_metadata.append(
				f"factor {factor_real} fuera de {{-1, 0, 1}} en modo normal"
			)
		if nodo.acceso_costoso != (
			nodo.clave.prioridad == 3 and profundidades[id(nodo)] > escenario.L
		):
			errores_metadata.append("marca de acceso costoso inconsistente")
		if errores_metadata:
			for mensaje in errores_metadata:
				registrar_error(nodo, "metadatos", mensaje)
		elif escenario.modo == "estres" and abs(factor_real) > 1:
			obtener_incidencia(nodo)["desbalances"].append(factor_real)

	if indice_activos is not None:
		for identificador in set(indice_activos) - ids_vistos:
			registrar_error_id(identificador, "referencia", "El evento activo no tiene nodo en el AVL")

	if referencias is not None and indice_activos is not None:
		eventos = list(indice_activos.values())
		if historico is not None:
			eventos.extend(historico.eventos_archivados.values())
		referencias_esperadas = {}
		for evento in eventos:
			referencia = referencia_de(
				evento,
				candidatos_de(evento, eventos, escenario),
			)
			if referencia is not None:
				referencias_esperadas[evento.identificador] = referencia.identificador
		for identificador in set(referencias) | set(referencias_esperadas):
			if referencias.get(identificador) != referencias_esperadas.get(identificador):
				registrar_error_id(
					identificador,
					"referencia",
					"La referencia guardada no coincide con la política determinista",
				)

	resultados = []
	for incidencia in (*incidencias.values(), *incidencias_por_id.values()):
		tipos = sorted(incidencia["tipos"])
		if incidencia["desbalances"] and not tipos:
			tipo = "desbalance_informativo"
		elif len(tipos) == 1:
			tipo = tipos[0]
		else:
			tipo = "_y_".join(tipos)
		resultados.append(
			{
				"identificador": incidencia["identificador"],
				"tipo": tipo,
				"errores": incidencia["errores"],
				"desbalances": incidencia["desbalances"],
				"es_error_integridad": bool(incidencia["errores"]),
			}
		)
	return resultados