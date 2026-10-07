from datetime import datetime
import json
from math import isfinite
from pathlib import Path
import re

import pygame

from AVL import AVL
from BST import BST
from auditoria import verificar_estructura
from asociaciones import candidatos_de, referencia_de
from gui.contexto import ContextoGUI
from gui.vista_arbol import VistaArbol
from persistencia import cargar_por_inserciones, cargar_por_topologia, exportar
from reportes import Reporte
from escenario import Escenario


class VistaSimulador:
	FONDO = (16, 23, 29)
	PANEL = (25, 34, 41)
	PANEL_CLARO = (32, 43, 51)
	TEXTO = (234, 240, 241)
	SUAVE = (148, 164, 171)
	ACENTO = (55, 204, 211)
	ROJO = (177, 67, 73)
	VERDE = (42, 143, 111)

	SECCIONES = (
		("arbol", "Árbol activo"),
		("eventos", "Eventos"),
		("cola", "Cola FIFO"),
		("comparacion", "AVL vs BST"),
		("consultas", "Consultas"),
		("historico", "Histórico"),
		("asociaciones", "Asociaciones"),
		("mapa", "Mapa de zonas"),
		("auditoria", "Auditoría"),
		("metricas", "Indicadores"),
		("escenario", "Escenario"),
		("versiones", "Versiones"),
	)

	def __init__(self, contexto: ContextoGUI, aplicacion):
		self.contexto = contexto
		self.aplicacion = aplicacion
		self.vista_arbol = VistaArbol(contexto)
		self.seccion = "arbol"
		self.botones = []
		self.campos = []
		self.formulario = None
		self.campo_activo = None
		self.seleccionado = None
		self.mensaje = "Simulación lista. Selecciona un evento o inicia una acción."
		self.mensaje_error = False
		self._fuentes = None
		self._rect_nodos = []
		self.continuo_activo = False
		self.siguiente_paso_ms = 0
		self.resultados_consulta = []
		self.titulo_consulta = "Consulta"
		self.nodos_consultados = 0
		self.orden_comparacion = "recepcion"
		self.confirmacion = None
		self.desplazamiento = 0
		self.rotaciones_recuperacion = []
		self._recalcular_referencias()

	def _fuente(self, tamano=16, negrita=False):
		if not pygame.font.get_init():
			pygame.font.init()
		return pygame.font.SysFont("segoeui", tamano, bold=negrita)

	def manejar_evento(self, evento):
		if self.confirmacion is not None:
			if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
				self.confirmacion = None
				return
			if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
				for rect, comando in reversed(self.botones):
					if rect.collidepoint(evento.pos) and comando in {"cancelar_confirmacion", "confirmar_confirmacion"}:
						self._accion(comando)
						return
			return
		if evento.type == pygame.MOUSEWHEEL:
			self.desplazamiento = max(0, self.desplazamiento - evento.y * 3)
			return
		if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
			posicion = evento.pos
			for rect, comando in reversed(self.botones):
				if rect.collidepoint(posicion):
					self._accion(comando)
					return
			if self.formulario:
				for nombre, rect in self.campos:
					if rect.collidepoint(posicion):
						self.campo_activo = nombre
						return
			for rect, identificador in reversed(self._rect_nodos):
				if rect.collidepoint(posicion):
					self.seleccionado = identificador
					return
			self.campo_activo = None
		elif evento.type == pygame.KEYDOWN and self.formulario:
			if evento.key == pygame.K_ESCAPE:
				self.formulario = None
				self.campo_activo = None
			elif evento.key == pygame.K_a and evento.mod & pygame.KMOD_CTRL and self.campo_activo:
				self.formulario[self.campo_activo] = ""
			elif evento.key == pygame.K_TAB and self.campos:
				nombres = [nombre for nombre, _ in self.campos]
				indice = nombres.index(self.campo_activo) if self.campo_activo in nombres else -1
				self.campo_activo = nombres[(indice + 1) % len(nombres)]
			elif evento.key == pygame.K_RETURN:
				self._confirmar_formulario()
			elif self.campo_activo:
				valor = self.formulario.get(self.campo_activo, "")
				if evento.key == pygame.K_BACKSPACE:
					self.formulario[self.campo_activo] = valor[:-1]
				elif evento.unicode and evento.unicode.isprintable():
					self.formulario[self.campo_activo] = valor + evento.unicode

	def actualizar(self):
		if not self.continuo_activo:
			return
		ahora = pygame.time.get_ticks()
		if ahora < self.siguiente_paso_ms:
			return
		if not self.contexto.cola.reportes_pendientes():
			self.continuo_activo = False
			self._mensaje("Cola vacía; procesamiento continuo finalizado")
			return
		self._procesar_uno()
		self.siguiente_paso_ms = ahora + 900

	def _accion(self, comando):
		if comando.startswith("seccion:"):
			self.seccion = comando.split(":", 1)[1]
			self.desplazamiento = 0
			self.formulario = None
			self.campo_activo = None
			return
		if comando == "cerrar":
			self.aplicacion.cerrar()
		elif comando == "deshacer":
			if self.contexto.pila_deshacer is None:
				self._mensaje("Pila de deshacer no configurada", True)
				return
			estado = self.contexto.pila_deshacer.deshacer()
			if estado is None:
				self._mensaje("No hay acciones para deshacer", True)
			else:
				self.aplicacion.sincronizar_estado(estado)
				self._mensaje("Última acción deshecha")
		elif comando == "exportar":
			self._exportar_con_dialogo()
		elif comando == "crear":
			self._abrir_formulario("crear")
		elif comando == "corregir":
			self._abrir_formulario("corregir")
		elif comando == "reporte":
			self._abrir_formulario("reporte")
		elif comando == "cargar_rafaga":
			self._cargar_rafaga_con_dialogo()
		elif comando == "escenario":
			self._abrir_formulario("escenario")
		elif comando == "revisado":
			self._ejecutar("Marcar revisado", self._marcar_revisado)
		elif comando == "eliminar":
			self._previsualizar_eliminacion()
		elif comando == "procesar_uno":
			self._procesar_uno()
		elif comando == "procesar_todos":
			self.continuo_activo = not self.continuo_activo
			self.siguiente_paso_ms = pygame.time.get_ticks()
			self._mensaje(
				"Procesamiento continuo iniciado" if self.continuo_activo else "Procesamiento continuo en pausa"
			)
		elif comando == "recuperar":
			self._ejecutar("Recuperar equilibrio", self._recuperar_equilibrio)
		elif comando == "archivar":
			self._previsualizar_archivo()
		elif comando == "nuevo_escenario":
			self._previsualizar_nuevo_escenario()
		elif comando == "confirmar_confirmacion":
			self._confirmar_operacion()
		elif comando == "cancelar_confirmacion":
			self.confirmacion = None
			self._mensaje("Operación cancelada")
		elif comando == "alternar_modo":
			self._ejecutar("Cambiar modo", self._alternar_modo)
		elif comando == "cargar":
			self._cargar_con_dialogo()
		elif comando == "cargar_inserciones":
			self._cargar_inserciones_con_dialogo()
		elif comando == "zona":
			if self.contexto.escenario.geometria_bloqueada:
				self._mensaje("La geometría de zonas quedó fija al iniciar el escenario", True)
			else:
				self._abrir_formulario("zona")
		elif comando == "guardar_version":
			self._abrir_formulario("version_guardar")
		elif comando.startswith("restaurar_version:"):
			self._restaurar_version(comando.split(":", 1)[1])
		elif comando.startswith("consulta:"):
			self._accion_consulta(comando.split(":", 1)[1])
		elif comando.startswith("comparacion_orden:"):
			self.orden_comparacion = comando.split(":", 1)[1]
		elif comando == "cerrar_form":
			self.formulario = None
			self.campo_activo = None
		elif comando == "confirmar_form":
			self._confirmar_formulario()

	def _directorio_versiones(self):
		return Path.home() / ".sismolab" / "versiones"

	@staticmethod
	def _elegir_archivo(guardar=False, ruta_inicial=None):
		import tkinter as tk
		from tkinter import filedialog

		raiz = tk.Tk()
		raiz.withdraw()
		raiz.attributes("-topmost", True)
		try:
			if guardar:
				return filedialog.asksaveasfilename(
					parent=raiz,
					initialdir=str(ruta_inicial.parent) if ruta_inicial else str(Path.home()),
					initialfile=ruta_inicial.name if ruta_inicial else "sismolab_estado.json",
					defaultextension=".json",
					filetypes=(("Archivos JSON", "*.json"),),
				)
			return filedialog.askopenfilename(
				parent=raiz,
				initialdir=str(ruta_inicial) if ruta_inicial else str(Path.home()),
				filetypes=(("Archivos JSON", "*.json"),),
			)
		finally:
			raiz.destroy()

	def _exportar_con_dialogo(self):
		try:
			ruta = self._elegir_archivo(guardar=True)
			if not ruta:
				return
			exportar(
				self.contexto.escenario,
				self.contexto.arbol,
				self.contexto.historico,
				self.contexto.cola,
				self.aplicacion.estado_operativo(),
				ruta,
			)
			self._mensaje(f"Estado exportado: {Path(ruta).name}")
		except (OSError, TypeError, ValueError) as error:
			self._mensaje(f"No se pudo exportar: {error}", True)

	def _cargar_con_dialogo(self):
		try:
			ruta = self._elegir_archivo()
			if not ruta:
				return
			estado, problemas = cargar_por_topologia(
				ruta,
				self.aplicacion.estado_operativo(),
			)
			if problemas:
				self._mensaje("Carga rechazada: " + "; ".join(problemas[:3]), True)
				return
			self._ejecutar(
				"Cargar escenario",
				lambda: self.aplicacion.sincronizar_estado(estado),
			)
		except (OSError, TypeError, ValueError) as error:
			self._mensaje(f"No se pudo cargar: {error}", True)

	def _cargar_inserciones_con_dialogo(self):
		try:
			ruta = self._elegir_archivo()
			if not ruta:
				return
			with Path(ruta).open("r", encoding="utf-8") as archivo:
				datos = json.load(archivo)
			if isinstance(datos, dict):
				datos = datos.get("eventos")
			if not isinstance(datos, list):
				raise ValueError("La carga por inserciones requiere una lista JSON de eventos")
			estado = cargar_por_inserciones(datos, modo=self.contexto.arbol.modo)
			self._ejecutar(
				"Cargar por inserciones",
				lambda: self.aplicacion.sincronizar_estado(estado),
			)
		except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
			self._mensaje(f"No se pudo cargar por inserciones: {error}", True)

	def _cargar_rafaga_con_dialogo(self):
		try:
			ruta = self._elegir_archivo()
			if not ruta:
				return
			with Path(ruta).open("r", encoding="utf-8") as archivo:
				datos = json.load(archivo)
			if isinstance(datos, dict):
				datos = datos.get("reportes")
			if not isinstance(datos, list) or not datos:
				raise ValueError("La ráfaga debe ser una lista JSON no vacía de reportes")
			reportes = [
				Reporte(
					registro["identificador"],
					registro["revision"],
					registro["magnitud"],
					registro["profundidad"],
					tuple(registro["epicentro"]),
					registro["fecha"],
					registro.get("en_zona_poblada", False),
					registro["estacion"],
				)
				for registro in datos
			]
			resultado = self._ejecutar(
				"Encolar ráfaga",
				lambda: [self.contexto.cola.encolar(reporte) for reporte in reportes],
			)
			if resultado is not None:
				self._mensaje(f"Ráfaga FIFO aceptada: {len(reportes)} reportes")
		except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
			self._mensaje(f"No se pudo cargar la ráfaga: {error}", True)

	def _procesar_uno(self):
		if not self.contexto.cola.reportes_pendientes():
			self._mensaje("No hay reportes pendientes", True)
			return
		metricas_antes = self.contexto.arbol.metricas.a_dict()
		resultado = self._ejecutar("Procesar reporte", self.contexto.cola.procesar_uno)
		if resultado is None:
			return
		metricas_despues = self.contexto.arbol.metricas.a_dict()
		giros_izquierda = metricas_despues.get("giros_izquierda", 0) - metricas_antes.get("giros_izquierda", 0)
		giros_derecha = metricas_despues.get("giros_derecha", 0) - metricas_antes.get("giros_derecha", 0)
		rotaciones = f"giros izq./der. {giros_izquierda}/{giros_derecha}"
		self._mensaje(
			f"{resultado.estacion}: SIS-{resultado.identificador:06d}, "
			f"rev. {resultado.revision}, decisión: {resultado.decision}, {rotaciones}"
		)

	def _guardar_version(self, nombre):
		nombre = nombre.strip()
		nombre_archivo = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre).strip("._-")
		if not nombre_archivo:
			raise ValueError("Escribe un nombre de versión válido")
		carpeta = self._directorio_versiones()
		carpeta.mkdir(parents=True, exist_ok=True)
		ruta = carpeta / f"{nombre_archivo}.json"
		if ruta.exists():
			raise ValueError("Ya existe una versión con ese nombre")
		exportar(
			self.contexto.escenario,
			self.contexto.arbol,
			self.contexto.historico,
			self.contexto.cola,
			self.aplicacion.estado_operativo(),
			ruta,
			nombre,
		)
		return ruta

	def _restaurar_version(self, nombre_archivo):
		if Path(nombre_archivo).name != nombre_archivo or not nombre_archivo.endswith(".json"):
			self._mensaje("Nombre de versión inválido", True)
			return
		ruta = self._directorio_versiones() / nombre_archivo
		estado, problemas = cargar_por_topologia(
			ruta,
			self.aplicacion.estado_operativo(),
		)
		if problemas:
			self._mensaje("Restauración rechazada: " + "; ".join(problemas[:3]), True)
			return
		self._ejecutar(
			"Restaurar versión",
			lambda: self.aplicacion.sincronizar_estado(estado),
		)

	def _accion_consulta(self, tipo):
		formularios = {
			"id": "consulta_id",
			"top_k": "consulta_top_k",
			"magnitud": "consulta_magnitud",
			"profundidad_fecha": "consulta_profundidad_fecha",
		}
		if tipo == "costoso":
			self._consultar_acceso_costoso()
		else:
			self._abrir_formulario(formularios[tipo])

	def _registrar_resultado_consulta(self, titulo, resultados, examinados):
		self.titulo_consulta = titulo
		self.resultados_consulta = resultados or ["Sin resultados para los criterios indicados."]
		self.nodos_consultados = examinados

	def _consultar_identificador(self, identificador):
		if isinstance(identificador, bool) or not isinstance(identificador, int) or not 1 <= identificador <= 999999:
			raise ValueError("El identificador debe ser un entero entre 1 y 999999")
		evento = self.contexto.historico.indice_activos.get(identificador)
		nodo = self.contexto.arbol._nodos_por_identificador.get(identificador)
		if evento is not None and nodo is not None:
			profundidad = self._profundidad_de_nodo(nodo)
			clave = nodo.clave
			eventos = (
				list(self.contexto.historico.indice_activos.values())
				+ list(self.contexto.historico.eventos_archivados.values())
			)
			candidatos = candidatos_de(evento, eventos, self.contexto.escenario)
			referencia = self.contexto.referencias.get(identificador) if self.contexto.referencias else None
			referenciado_por = [
				origen
				for origen, destino in (self.contexto.referencias or {}).items()
				if destino == identificador
			]
			lineas = [
				f"Activo · SIS-{identificador:06d}",
				f"Prioridad {clave.prioridad} · clave K=({clave.prioridad}, {clave.magnitud:g}, {clave.identificador})",
				f"Revisión {evento.revision} · {evento.estado} · estaciones: {', '.join(sorted(evento.estaciones)) or 'ninguna'}",
				f"Zona poblada: {'sí' if evento.en_zona_poblada else 'no'}",
				f"Ocurrencia UTC: {evento.fecha.isoformat() if isinstance(evento.fecha, datetime) else evento.fecha}",
				f"Profundidad de nodo {profundidad} · búsqueda por clave {profundidad + 1} nodos",
				f"Altura {nodo.altura} · factor {nodo.factor_balance}",
				f"Epicentro {evento.epicentro} · hipocentro {evento.profundidad:g} km",
				"Candidatos: " + (", ".join(
					f"SIS-{c.identificador:06d} ({'activo' if c.identificador in self.contexto.historico.indice_activos else 'archivado'})"
					for c in candidatos
				) or "ninguno"),
				f"Referencia elegida: {f'SIS-{referencia:06d}' if referencia else 'ninguna'}",
				"Usado como referencia por: " + (", ".join(
					f"SIS-{origen:06d} ({'activo' if origen in self.contexto.historico.indice_activos else 'archivado'})"
					for origen in referenciado_por
				) or "ninguno"),
			]
		elif identificador in self.contexto.historico.eventos_archivados:
			evento = self.contexto.historico.eventos_archivados[identificador]
			lineas = [
				f"Archivado · SIS-{identificador:06d}",
				f"Magnitud {evento.magnitud:g} · revisión {evento.revision} · fecha {evento.fecha}",
			]
		elif identificador in self.contexto.historico.identificadores_eliminados:
			lineas = [f"Eliminado · SIS-{identificador:06d}; no puede reutilizarse."]
		else:
			lineas = [f"SIS-{identificador:06d} no existe en el escenario."]
		self._registrar_resultado_consulta("Consulta por identificador", lineas, 0)

	def _consultar_top_k(self, k):
		resultados = []
		examinados = 0
		pila = []
		nodo = self.contexto.arbol.raiz
		while pila or nodo is not None:
			while nodo is not None:
				pila.append(nodo)
				nodo = nodo.derecha
			nodo = pila.pop()
			examinados += 1
			evento = self.contexto.historico.indice_activos.get(nodo.clave.identificador)
			if evento is not None and evento.estado == "pendiente":
				resultados.append(
					f"SIS-{evento.identificador:06d} · K=({nodo.clave.prioridad}, "
					f"{nodo.clave.magnitud:g}, {nodo.clave.identificador})"
				)
				if len(resultados) == k:
					break
			nodo = nodo.izquierda
		self._registrar_resultado_consulta(f"Top {k} pendientes por K descendente", resultados, examinados)

	def _nodos_con_profundidad(self):
		resultado = []
		pendientes = [(self.contexto.arbol.raiz, 0)] if self.contexto.arbol.raiz else []
		while pendientes:
			nodo, profundidad = pendientes.pop()
			resultado.append((nodo, profundidad))
			if nodo.derecha is not None:
				pendientes.append((nodo.derecha, profundidad + 1))
			if nodo.izquierda is not None:
				pendientes.append((nodo.izquierda, profundidad + 1))
		return resultado

	def _profundidad_de_nodo(self, objetivo):
		for nodo, profundidad in self._nodos_con_profundidad():
			if nodo is objetivo:
				return profundidad
		return -1

	def _consultar_magnitud(self, minimo, maximo):
		if (
			isinstance(minimo, bool)
			or isinstance(maximo, bool)
			or not isinstance(minimo, (int, float))
			or not isinstance(maximo, (int, float))
			or not isfinite(minimo)
			or not isfinite(maximo)
			or minimo > maximo
		):
			raise ValueError("La magnitud mínima no puede superar la máxima")
		resultados = []
		examinados = 0
		for nodo, _ in self._nodos_con_profundidad():
			examinados += 1
			if minimo <= nodo.clave.magnitud <= maximo:
				resultados.append(
					f"SIS-{nodo.clave.identificador:06d} · M {nodo.clave.magnitud:g} · P{nodo.clave.prioridad}"
				)
		self._registrar_resultado_consulta(f"Magnitud inclusiva [{minimo:g}, {maximo:g}]", resultados, examinados)

	def _consultar_profundidad_fecha(self, profundidad_maxima, inicio, fin):
		if (
			isinstance(profundidad_maxima, bool)
			or not isinstance(profundidad_maxima, (int, float))
			or not isfinite(profundidad_maxima)
			or profundidad_maxima < 0
		):
			raise ValueError("El límite de profundidad debe ser un número finito no negativo")
		inicio = self.contexto.gestor_eventos._normalizar_fecha_utc(inicio)
		fin = self.contexto.gestor_eventos._normalizar_fecha_utc(fin)
		if inicio > fin:
			raise ValueError("Rango de profundidad o fechas inválido")
		resultados = []
		examinados = 0
		for nodo, _ in self._nodos_con_profundidad():
			examinados += 1
			evento = self.contexto.historico.indice_activos[nodo.clave.identificador]
			fecha = evento.fecha
			if isinstance(fecha, str):
				fecha = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
			if isinstance(fecha, datetime):
				fecha = self.contexto.gestor_eventos._normalizar_fecha_utc(fecha)
				coincide_fecha = inicio <= fecha <= fin
			else:
				coincide_fecha = False
			if evento.profundidad <= profundidad_maxima and coincide_fecha:
				resultados.append(
					f"SIS-{evento.identificador:06d} · H {evento.profundidad:g} km · {fecha.isoformat()}"
				)
		self._registrar_resultado_consulta("Profundidad y fechas inclusivas", resultados, examinados)

	def _consultar_acceso_costoso(self):
		resultados = []
		nodos = self._nodos_con_profundidad()
		for nodo, profundidad in nodos:
			if nodo.clave.prioridad == 3 and nodo.acceso_costoso:
				resultados.append(
					f"SIS-{nodo.clave.identificador:06d} · profundidad {profundidad} "
					f"> L={self.contexto.escenario.L} · búsqueda {profundidad + 1} nodos"
				)
		self._registrar_resultado_consulta("Eventos de prioridad alta con acceso costoso", resultados, len(nodos))

	@staticmethod
	def _contar_hojas(arbol):
		if arbol.raiz is None:
			return 0
		pendientes = [arbol.raiz]
		hojas = 0
		while pendientes:
			nodo = pendientes.pop()
			if nodo.izquierda is None and nodo.derecha is None:
				hojas += 1
			if nodo.izquierda is not None:
				pendientes.append(nodo.izquierda)
			if nodo.derecha is not None:
				pendientes.append(nodo.derecha)
		return hojas

	@staticmethod
	def _comparaciones_busqueda(arbol, claves):
		comparaciones = 0
		for clave in claves:
			nodo = arbol.raiz
			while nodo is not None:
				comparaciones += 1
				if clave == nodo.clave:
					break
				nodo = nodo.izquierda if clave < nodo.clave else nodo.derecha
		return comparaciones

	def _crear_arboles_comparacion(self):
		claves = [
			self.contexto.gestor_eventos._crear_clave(evento)
			for evento in self.contexto.historico.indice_activos.values()
		]
		if self.orden_comparacion == "ascendente":
			claves.sort()
		avl = AVL()
		bst = BST()
		for clave in claves:
			avl.insertar(clave)
			bst.insertar(clave)
		return avl, bst, claves

	def _dibujar_comparacion(self, superficie, area):
		avl, bst, claves = self._crear_arboles_comparacion()
		orden = "claves ascendentes" if self.orden_comparacion == "ascendente" else "orden de recepción"
		superficie.blit(self._fuente(22, True).render("Comparación de estructuras", True, self.TEXTO), (area.x + 24, area.y + 18))
		superficie.blit(
			self._fuente(13).render(f"Mismas claves y {orden} · el BST no realiza rotaciones", True, self.SUAVE),
			(area.x + 26, area.y + 48),
		)
		ancho = (area.width - 60) // 2
		alto_panel = area.height - 104
		for indice, (arbol, nombre, tono) in enumerate(((avl, "AVL", (35, 111, 103)), (bst, "BST", (154, 94, 48)))):
			panel = pygame.Rect(area.x + 20 + indice * (ancho + 20), area.y + 78, ancho, alto_panel)
			pygame.draw.rect(superficie, (28, 39, 45), panel, border_radius=8)
			x, y = panel.x + 16, panel.y + 14
			superficie.blit(self._fuente(18, True).render(nombre, True, self.TEXTO), (x, y))
			y += 30
			raiz = arbol.raiz.clave.identificador if arbol.raiz else "—"
			comparaciones = self._comparaciones_busqueda(arbol, claves)
			promedio = comparaciones / len(claves) if claves else 0
			metricas = (
				f"Nodos {arbol.peso()} · raíz SIS-{raiz}",
				f"Altura {arbol.altura()} · profundidad máxima {arbol.altura()}",
				f"Hojas {self._contar_hojas(arbol)} · búsquedas {comparaciones}",
				f"Promedio de comparaciones: {promedio:.2f}",
			)
			for texto in metricas:
				superficie.blit(self._fuente(12).render(texto, True, (201, 213, 212)), (x, y))
				y += 20
			pygame.draw.line(superficie, tono, (x, y + 5), (panel.right - 16, y + 5), 2)
			y += 18
			self._dibujar_arbol_comparativo(superficie, arbol, panel, y)
		self._dibujar_mensaje(superficie, area)

	def _dibujar_arbol_comparativo(self, superficie, arbol, panel, y_inicio):
		if arbol.raiz is None:
			superficie.blit(self._fuente(14).render("Sin eventos activos", True, self.SUAVE), (panel.x + 18, y_inicio))
			return
		orden = []
		pila = []
		pendientes = [(arbol.raiz, 0)]
		por_nodo = {}
		while pendientes:
			nodo, profundidad = pendientes.pop()
			por_nodo[id(nodo)] = (nodo, profundidad)
			if nodo.derecha is not None:
				pendientes.append((nodo.derecha, profundidad + 1))
			if nodo.izquierda is not None:
				pendientes.append((nodo.izquierda, profundidad + 1))
		nodo = arbol.raiz
		while pila or nodo is not None:
			while nodo is not None:
				pila.append(nodo)
				nodo = nodo.izquierda
			nodo = pila.pop()
			orden.append(nodo)
			nodo = nodo.derecha
		max_profundidad = max(profundidad for _, profundidad in por_nodo.values())
		ancho_util = panel.width - 36
		alto_util = panel.bottom - y_inicio - 22
		paso_y = min(58, max(36, alto_util // (max_profundidad + 1)))
		posiciones = {}
		for indice, nodo in enumerate(orden):
			profundidad = por_nodo[id(nodo)][1]
			x = panel.x + 18 + round((indice + 0.5) * ancho_util / len(orden))
			y = y_inicio + profundidad * paso_y
			posiciones[id(nodo)] = (x, y)
		for nodo, _ in por_nodo.values():
			for hijo in (nodo.izquierda, nodo.derecha):
				if hijo is not None:
					pygame.draw.line(superficie, (94, 112, 114), posiciones[id(nodo)], posiciones[id(hijo)], 1)
		for nodo in orden:
			x, y = posiciones[id(nodo)]
			color = self.vista_arbol.COLOR_PRIORIDAD.get(nodo.clave.prioridad, self.PANEL)
			rect = pygame.Rect(0, 0, 48, 28)
			rect.center = (x, y)
			pygame.draw.rect(superficie, color, rect, border_radius=4)
			pygame.draw.rect(superficie, (220, 230, 228), rect, 1, border_radius=4)
			texto = self._fuente(10, True).render(str(nodo.clave.identificador), True, self.TEXTO)
			superficie.blit(texto, texto.get_rect(center=rect.center))

	def _dibujar_consultas(self, superficie, area):
		superficie.blit(self._fuente(22, True).render(self.titulo_consulta, True, self.TEXTO), (area.x + 24, area.y + 18))
		superficie.blit(
			self._fuente(13).render(f"Nodos del AVL examinados: {self.nodos_consultados}", True, self.ACENTO),
			(area.x + 26, area.y + 50),
		)
		pygame.draw.line(superficie, (66, 82, 88), (area.x + 24, area.y + 78), (area.right - 24, area.y + 78), 1)
		filas_visibles = max(1, (area.height - 140) // 28)
		offset = min(self.desplazamiento, max(0, len(self.resultados_consulta) - filas_visibles))
		y = area.y + 98
		for linea in self.resultados_consulta[offset:offset + filas_visibles]:
			superficie.blit(self._fuente(14).render(linea, True, (205, 216, 214)), (area.x + 28, y))
			y += 28
		if len(self.resultados_consulta) > filas_visibles:
			rango = f"Mostrando {offset + 1}–{min(offset + filas_visibles, len(self.resultados_consulta))} de {len(self.resultados_consulta)}"
			superficie.blit(self._fuente(11).render(rango, True, self.SUAVE), (area.right - 230, area.bottom - 50))
		self._dibujar_mensaje(superficie, area)

	def _dibujar_versiones(self, superficie, area):
		superficie.blit(self._fuente(22, True).render("Versiones persistentes", True, self.TEXTO), (area.x + 24, area.y + 18))
		superficie.blit(
			self._fuente(13).render("Snapshots estructurales · restaurar crea una acción reversible", True, self.SUAVE),
			(area.x + 26, area.y + 48),
		)
		carpeta = self._directorio_versiones()
		archivos = sorted(carpeta.glob("*.json"), key=lambda ruta: ruta.name.casefold()) if carpeta.exists() else []
		if not archivos:
			superficie.blit(self._fuente(15).render("Aún no hay versiones guardadas.", True, self.SUAVE), (area.x + 28, area.y + 94))
		else:
			filas_visibles = max(1, (area.height - 140) // 48)
			offset = min(self.desplazamiento, max(0, len(archivos) - filas_visibles))
			y = area.y + 82
			for ruta in archivos[offset:offset + filas_visibles]:
				boton = pygame.Rect(area.x + 24, y, 290, 38)
				self._boton(superficie, boton, f"Restaurar · {ruta.stem[:24]}", f"restaurar_version:{ruta.name}")
				superficie.blit(self._fuente(12).render(ruta.name, True, self.SUAVE), (boton.right + 14, y + 11))
				y += 48
			if len(archivos) > filas_visibles:
				rango = f"Mostrando {offset + 1}–{min(offset + filas_visibles, len(archivos))} de {len(archivos)}"
				superficie.blit(self._fuente(11).render(rango, True, self.SUAVE), (area.right - 230, area.bottom - 50))
		self._dibujar_mensaje(superficie, area)

	def _ejecutar(self, nombre, funcion):
		pila = self.contexto.pila_deshacer
		try:
			resultado = pila.ejecutar_accion(nombre, funcion) if pila else funcion()
			if resultado is False:
				self._mensaje(f"{nombre}: operación rechazada", True)
				return resultado
			if self.contexto.escenario is not None:
				self.contexto.arbol.actualizar_accesos_costosos(self.contexto.escenario.L)
			self._recalcular_referencias()
			if nombre == "Recuperar equilibrio":
				self._mensaje(
					f"Recuperación auditada: {len(resultado)} rotaciones; modo normal"
				)
			else:
				self._mensaje(f"{nombre}: completado")
			return resultado
		except (ValueError, KeyError, TypeError) as error:
			if pila is not None:
				self.aplicacion.sincronizar_estado(pila.estado)
			self._mensaje(str(error), True)
			return None

	def _recalcular_referencias(self):
		eventos = (
			list(self.contexto.historico.indice_activos.values())
			+ list(self.contexto.historico.eventos_archivados.values())
		)
		referencias = {}
		for evento in eventos:
			candidatos = candidatos_de(evento, eventos, self.contexto.escenario)
			referencia = referencia_de(evento, candidatos)
			if referencia is not None:
				referencias[evento.identificador] = referencia.identificador
		if self.contexto.referencias is None:
			self.contexto.referencias = {}
		self.contexto.referencias.clear()
		self.contexto.referencias.update(referencias)
		if self.contexto.pila_deshacer is not None:
			self.contexto.pila_deshacer.estado.referencias = self.contexto.referencias

	def _marcar_revisado(self):
		return self.contexto.gestor_eventos.marcar_revisado(self.seleccionado) if self.seleccionado else False

	def _eliminar_evento(self):
		if self.seleccionado is None:
			raise ValueError("Selecciona un evento del árbol primero")
		return self.contexto.gestor_eventos.eliminar_evento(self.seleccionado)

	def _archivar_elegible(self):
		nodo = self.contexto.historico.buscar_rama_a_archivar(
			self.contexto.arbol,
			self.contexto.escenario,
		)
		if nodo is None:
			raise ValueError("No hay ramas completas que cumplan antigüedad y prioridad")
		return self.contexto.historico.archivar_rama(nodo, self.contexto.arbol)

	@staticmethod
	def _ids_subarbol(nodo):
		ids = []
		pendientes = [nodo]
		while pendientes:
			actual = pendientes.pop()
			ids.append(actual.clave.identificador)
			if actual.izquierda is not None:
				pendientes.append(actual.izquierda)
			if actual.derecha is not None:
				pendientes.append(actual.derecha)
		return sorted(ids)

	def _previsualizar_eliminacion(self):
		evento = self.contexto.historico.indice_activos.get(self.seleccionado)
		if evento is None:
			self._mensaje("Selecciona un evento activo antes de eliminar", True)
			return
		clave = self.contexto.gestor_eventos._crear_clave(evento)
		self.confirmacion = {
			"tipo": "eliminar",
			"titulo": "Confirmar eliminación individual",
			"lineas": [
				f"Se retirará únicamente SIS-{evento.identificador:06d}.",
				f"Magnitud {evento.magnitud:g} · prioridad {clave.prioridad} · estado {evento.estado}",
				"El identificador quedará retirado y no podrá reutilizarse.",
			],
		}

	def _previsualizar_archivo(self):
		nodo = self.contexto.historico.buscar_rama_a_archivar(
			self.contexto.arbol,
			self.contexto.escenario,
		)
		if nodo is None:
			self._mensaje("No hay ramas completas que cumplan antigüedad y prioridad", True)
			return
		ids = self._ids_subarbol(nodo)
		ids_texto = ", ".join(f"SIS-{identificador:06d}" for identificador in ids)
		self.continuo_activo = False
		self.confirmacion = {
			"tipo": "archivar",
			"nodo": nodo,
			"ids": ids,
			"titulo": "Previsualizar archivo de rama",
			"lineas": [
				f"Raíz SIS-{nodo.clave.identificador:06d} · {len(ids)} eventos.",
				f"Elegible: todos son de prioridad baja y tienen antigüedad > {self.contexto.escenario.T:g} h.",
				"Selección: mayor cantidad de nodos; desempates por mayor profundidad y mayor ID de raíz.",
				ids_texto,
				"El conjunto queda fijado antes de las rotaciones del archivo.",
			],
		}

	def _previsualizar_nuevo_escenario(self):
		self.continuo_activo = False
		self.confirmacion = {
			"tipo": "nuevo_escenario",
			"titulo": "Iniciar escenario vacío",
			"lineas": [
				f"Se retirarán del escenario {len(self.contexto.historico.indice_activos)} eventos activos, "
				f"{len(self.contexto.historico.eventos_archivados)} archivados y "
				f"{len(self.contexto.cola.reportes_pendientes())} reportes pendientes.",
			"Se conservarán W/R/L/T, estaciones y reloj; la nueva geometría quedará editable.",
			"La acción completa puede deshacerse.",
			],
		}

	def _iniciar_escenario_vacio(self):
		escenario = Escenario(
			reloj=self.contexto.escenario.reloj,
			W=self.contexto.escenario.W,
			R=self.contexto.escenario.R,
			L=self.contexto.escenario.L,
			T=self.contexto.escenario.T,
			modo="normal",
			estaciones=self.contexto.escenario.estaciones,
		)
		estado = cargar_por_inserciones([], escenario, modo="normal")
		self.continuo_activo = False
		self.seleccionado = None
		return self.aplicacion.sincronizar_estado(estado)

	def _confirmar_operacion(self):
		confirmacion = self.confirmacion
		self.confirmacion = None
		if confirmacion is None:
			return
		if confirmacion["tipo"] == "eliminar":
			self._ejecutar("Eliminar evento", self._eliminar_evento)
			return
		if confirmacion["tipo"] == "nuevo_escenario":
			self._ejecutar("Iniciar escenario vacío", self._iniciar_escenario_vacio)
			return
		nodo = confirmacion["nodo"]
		if self._ids_subarbol(nodo) != confirmacion["ids"]:
			self._mensaje("La rama cambió desde la previsualización; vuelve a calcularla", True)
			return
		self._ejecutar(
			"Archivar rama elegible",
			lambda: self.contexto.historico.archivar_rama(nodo, self.contexto.arbol),
		)

	def _alternar_modo(self):
		if self.contexto.arbol.modo == "estres":
			incidencias = verificar_estructura(
				self.contexto.arbol,
				self.contexto.escenario,
				self.contexto.historico.indice_activos,
				self.contexto.historico,
				self.contexto.referencias,
			)
			if any(
				incidencia["es_error_integridad"] or incidencia["desbalances"]
				for incidencia in incidencias
			):
				raise ValueError("El árbol está desbalanceado; ejecute Recuperar equilibrio antes de volver a normal")
			modo = "normal"
		else:
			modo = "estres"
		self.contexto.arbol.modo = modo
		self.contexto.escenario.modo = modo
		return modo

	def _recuperar_equilibrio(self):
		self.rotaciones_recuperacion = self.contexto.arbol.recuperar_equilibrio()
		self.contexto.escenario.modo = self.contexto.arbol.modo
		self.contexto.arbol.actualizar_accesos_costosos(self.contexto.escenario.L)
		incidencias = verificar_estructura(
			self.contexto.arbol,
			self.contexto.escenario,
			self.contexto.historico.indice_activos,
			self.contexto.historico,
			self.contexto.referencias,
		)
		if any(incidencia["es_error_integridad"] for incidencia in incidencias):
			raise ValueError("La auditoría no confirmó la recuperación; revise la sección Auditoría")
		return self.rotaciones_recuperacion

	def _mensaje(self, texto, error=False):
		self.mensaje = texto
		self.mensaje_error = error

	def _abrir_formulario(self, tipo):
		self.mensaje_error = False
		seleccion = self.contexto.historico.indice_activos.get(self.seleccionado)
		if tipo == "corregir" and seleccion is None:
			self._mensaje("Selecciona primero un evento activo", True)
			return
		if tipo == "crear":
			self.formulario = {
				"ID": "", "Magnitud": "", "Profundidad km": "",
				"Coordenada X": "", "Coordenada Y": "",
				"Fecha UTC ISO": self.contexto.escenario.reloj.isoformat(timespec="seconds"),
				"Estación": "STA-01",
			}
		elif tipo == "corregir":
			self.formulario = {
				"ID": str(seleccion.identificador),
				"Magnitud": str(seleccion.magnitud),
				"Profundidad km": str(seleccion.profundidad),
				"Coordenada X": str(seleccion.epicentro[0]) if isinstance(seleccion.epicentro, (tuple, list)) else "0",
				"Coordenada Y": str(seleccion.epicentro[1]) if isinstance(seleccion.epicentro, (tuple, list)) else "0",
				"Fecha UTC ISO": seleccion.fecha.isoformat() if isinstance(seleccion.fecha, datetime) else str(seleccion.fecha),
			}
		elif tipo == "reporte":
			self.formulario = {
				"ID": "", "Revisión": "1", "Magnitud": "", "Profundidad km": "",
				"Coordenada X": "", "Coordenada Y": "",
				"Fecha UTC ISO": self.contexto.escenario.reloj.isoformat(timespec="seconds"),
				"Estación": "STA-01",
			}
		elif tipo == "zona":
			self.formulario = {
				"X mínimo": "100",
				"X máximo": "250",
				"Y mínimo": "100",
				"Y máximo": "250",
				"Poblada true/false": "true",
			}
		elif tipo == "version_guardar":
			self.formulario = {"Nombre de versión": ""}
		elif tipo == "consulta_id":
			self.formulario = {"Identificador": ""}
		elif tipo == "consulta_top_k":
			self.formulario = {"Cantidad k": "5"}
		elif tipo == "consulta_magnitud":
			self.formulario = {"Magnitud mínima": "-2.0", "Magnitud máxima": "10.0"}
		elif tipo == "consulta_profundidad_fecha":
			self.formulario = {
				"Profundidad máxima km": "100",
				"Fecha UTC inicial ISO": self.contexto.escenario.reloj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds"),
				"Fecha UTC final ISO": self.contexto.escenario.reloj.isoformat(timespec="seconds"),
			}
		else:
			self.formulario = {
				"W horas": str(self.contexto.escenario.W),
				"R km": str(self.contexto.escenario.R),
				"L eventos": str(self.contexto.escenario.L),
				"T horas": str(self.contexto.escenario.T),
				"Reloj UTC ISO": self.contexto.escenario.reloj.isoformat(timespec="seconds"),
			}
		self.formulario["_tipo"] = tipo
		self.campo_activo = next(key for key in self.formulario if not key.startswith("_"))

	def _confirmar_formulario(self):
		if not self.formulario:
			return
		tipo = self.formulario.pop("_tipo")
		valores = dict(self.formulario)
		try:
			if tipo in {"crear", "corregir", "reporte"}:
				id_evento = int(valores["ID"])
				magnitud = float(valores["Magnitud"])
				profundidad = float(valores["Profundidad km"])
				epicentro = (float(valores["Coordenada X"]), float(valores["Coordenada Y"]))
				fecha = self.contexto.gestor_eventos._normalizar_fecha_utc(valores["Fecha UTC ISO"])
				if tipo == "crear":
					if not valores["Estación"].strip():
						raise ValueError("El evento debe indicar la estación de origen")
					def crear_evento():
						evento = self.contexto.gestor_eventos.crear_evento({
							"identificador": id_evento,
							"magnitud": magnitud,
							"profundidad": profundidad,
							"epicentro": epicentro,
							"fecha": fecha,
							"estacion": valores["Estación"].strip(),
						})
						return evento
					funcion = crear_evento
					self._ejecutar("Crear evento", funcion)
				elif tipo == "corregir":
					funcion = lambda: self.contexto.gestor_eventos.corregir_evento(id_evento, {
						"magnitud": magnitud,
						"profundidad": profundidad,
						"epicentro": epicentro,
						"fecha": fecha,
					})
					self._ejecutar("Corregir evento", funcion)
				else:
					reporte = Reporte(
						id_evento,
						int(valores["Revisión"]),
						magnitud,
						profundidad,
						epicentro,
						fecha,
						self.contexto.escenario.zona_de(*epicentro),
						valores["Estación"],
					)
					self._ejecutar("Encolar reporte", lambda: self.contexto.cola.encolar(reporte))
			elif tipo == "escenario":
				W = float(valores["W horas"])
				R = float(valores["R km"])
				L = int(valores["L eventos"])
				T = float(valores["T horas"])
				nuevo_reloj = self.contexto.gestor_eventos._normalizar_fecha_utc(
					valores["Reloj UTC ISO"]
				)
				if nuevo_reloj <= self.contexto.escenario.reloj:
					raise ValueError("El reloj nuevo debe ser posterior al actual")
				Escenario(
					reloj=self.contexto.escenario.reloj,
					zonas=self.contexto.escenario.zonas,
					W=W,
					R=R,
					L=L,
					T=T,
					modo=self.contexto.escenario.modo,
				)
				def cambiar_escenario():
					self.contexto.escenario.W = W
					self.contexto.escenario.R = R
					self.contexto.escenario.L = L
					self.contexto.escenario.T = T
					self.contexto.escenario.avanzar_reloj(nuevo_reloj)
				self.contexto.arbol.modo = self.contexto.escenario.modo
				self._ejecutar("Actualizar escenario", cambiar_escenario)
			elif tipo == "cargar":
				estado, problemas = cargar_por_topologia(
					valores["Ruta JSON"],
					self.aplicacion.estado_operativo(),
				)
				if problemas:
					self._mensaje("Carga rechazada: " + problemas[0], True)
					self.formulario["_tipo"] = tipo
					return
				self.aplicacion.instalar_estado(estado)
				self._mensaje("Estado cargado y validado")
			elif tipo == "zona":
				texto_poblada = valores["Poblada true/false"].strip().lower()
				if texto_poblada not in {"true", "false"}:
					raise ValueError("Poblada debe ser true o false")
				zona = (
					float(valores["X mínimo"]),
					float(valores["X máximo"]),
					float(valores["Y mínimo"]),
					float(valores["Y máximo"]),
					texto_poblada == "true",
				)
				self._ejecutar(
					"Agregar zona",
					lambda: self.contexto.escenario.agregar_zona(zona),
				)
			elif tipo == "version_guardar":
				ruta = self._guardar_version(valores["Nombre de versión"])
				self._mensaje(f"Versión guardada: {ruta.stem}")
			elif tipo == "consulta_id":
				self._consultar_identificador(int(valores["Identificador"]))
			elif tipo == "consulta_top_k":
				k = int(valores["Cantidad k"])
				if k <= 0:
					raise ValueError("k debe ser un entero positivo")
				self._consultar_top_k(k)
			elif tipo == "consulta_magnitud":
				self._consultar_magnitud(
					float(valores["Magnitud mínima"]),
					float(valores["Magnitud máxima"]),
				)
			elif tipo == "consulta_profundidad_fecha":
				self._consultar_profundidad_fecha(
					float(valores["Profundidad máxima km"]),
					valores["Fecha UTC inicial ISO"],
					valores["Fecha UTC final ISO"],
				)
			if self.mensaje_error:
				self.formulario["_tipo"] = tipo
				return
			self.formulario = None
			self.campo_activo = None
		except (ValueError, TypeError, KeyError) as error:
			self.formulario["_tipo"] = tipo
			self._mensaje(f"Datos no válidos: {error}", True)

	def dibujar(self, superficie):
		ancho, alto = superficie.get_size()
		superficie.fill(self.FONDO)
		self.botones = []
		self._rect_nodos = []
		self._dibujar_cabecera(superficie)
		self._dibujar_navegacion(superficie)
		contenido = pygame.Rect(212, 96, ancho - 232, alto - 116)
		pygame.draw.rect(superficie, (20, 28, 34), contenido, border_radius=12)
		if self.seccion == "arbol":
			self._dibujar_arbol(superficie, contenido)
		elif self.seccion == "mapa":
			self._dibujar_mapa(superficie, contenido)
		elif self.seccion == "comparacion":
			self._dibujar_comparacion(superficie, contenido)
		elif self.seccion == "consultas":
			self._dibujar_consultas(superficie, contenido)
		elif self.seccion == "versiones":
			self._dibujar_versiones(superficie, contenido)
		elif self.seccion in {"eventos", "cola", "historico", "asociaciones", "auditoria", "metricas", "escenario"}:
			self._dibujar_seccion(superficie, contenido)
		if self.formulario:
			self._dibujar_modal(superficie)
		elif self.confirmacion is not None:
			self._dibujar_modal_confirmacion(superficie)

	def _boton(self, superficie, rect, texto, comando, tono="normal"):
		colores = {
			"normal": (39, 52, 61), "principal": (25, 115, 105),
			"peligro": (142, 48, 56), "cerrar": (173, 50, 59),
			"activo": (40, 91, 101),
		}
		pygame.draw.rect(superficie, colores[tono], rect, border_radius=8)
		pygame.draw.rect(superficie, (72, 91, 99), rect, 1, border_radius=8)
		render = self._fuente(14, True).render(texto, True, self.TEXTO)
		superficie.blit(render, render.get_rect(center=rect.center))
		self.botones.append((pygame.Rect(rect), comando))

	def _dibujar_cabecera(self, superficie):
		ancho = superficie.get_width()
		pygame.draw.rect(superficie, self.PANEL, (0, 0, ancho, 76))
		superficie.blit(self._fuente(23, True).render("SismoLab", True, self.TEXTO), (24, 16))
		superficie.blit(self._fuente(13).render("SIMULADOR DE EVENTOS SÍSMICOS", True, self.SUAVE), (25, 46))
		self._boton(superficie, pygame.Rect(ancho - 318, 18, 96, 40), "DESHACER", "deshacer")
		self._boton(superficie, pygame.Rect(ancho - 212, 18, 94, 40), "EXPORTAR", "exportar")
		self._boton(superficie, pygame.Rect(ancho - 106, 18, 88, 40), "CERRAR", "cerrar", "cerrar")

	def _dibujar_navegacion(self, superficie):
		x, y, ancho = 18, 96, 178
		for clave, etiqueta in self.SECCIONES:
			tono = "activo" if self.seccion == clave else "normal"
			self._boton(superficie, pygame.Rect(x, y, ancho, 32), etiqueta, f"seccion:{clave}", tono)
			y += 36
		superficie.blit(self._fuente(11, True).render("ACCIONES", True, self.SUAVE), (x + 4, y + 7))
		y += 26
		if self.seccion in {"arbol", "eventos"}:
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "+ Crear evento", "crear", "principal")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Corregir seleccionado", "corregir")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Marcar revisado", "revisado")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Eliminar seleccionado", "eliminar", "peligro")
		elif self.seccion == "cola":
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "+ Encolar reporte", "reporte", "principal")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Cargar ráfaga JSON", "cargar_rafaga")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Procesar siguiente", "procesar_uno")
			y += 40
			texto = "Pausar continuo" if self.continuo_activo else "Iniciar continuo"
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), texto, "procesar_todos")
		elif self.seccion == "escenario":
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Editar reloj y W/R/L/T", "escenario", "principal")
			if self.contexto.arbol.modo == "estres":
				y += 40
				self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Recuperar equilibrio", "recuperar")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Alternar modo", "alternar_modo")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Cargar JSON", "cargar")
			y += 40
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Cargar por inserciones", "cargar_inserciones")
		elif self.seccion == "historico":
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Archivar rama elegible", "archivar", "principal")
		elif self.seccion == "mapa" and not self.contexto.escenario.geometria_bloqueada:
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "+ Agregar zona", "zona", "principal")
		elif self.seccion == "consultas":
			for etiqueta, tipo in (
				("Buscar identificador", "id"),
				("Top-k pendientes", "top_k"),
				("Rango magnitud", "magnitud"),
				("Profundidad / fechas", "profundidad_fecha"),
				("Acceso costoso", "costoso"),
			):
				self._boton(superficie, pygame.Rect(x, y, ancho, 34), etiqueta, f"consulta:{tipo}")
				y += 40
		elif self.seccion == "versiones":
			self._boton(superficie, pygame.Rect(x, y, ancho, 34), "Guardar versión", "guardar_version", "principal")
		elif self.seccion == "comparacion":
			for etiqueta, orden in (("Orden de recepción", "recepcion"), ("Claves ascendentes", "ascendente")):
				tono = "activo" if self.orden_comparacion == orden else "normal"
				self._boton(superficie, pygame.Rect(x, y, ancho, 34), etiqueta, f"comparacion_orden:{orden}", tono)
				y += 40

	def _dibujar_arbol(self, superficie, area):
		vista = self.vista_arbol
		layout = vista.calcular_layout((area.width, area.height))
		if not layout:
			superficie.blit(self._fuente(20).render("No hay eventos activos. Usa + Crear evento para iniciar.", True, self.SUAVE), (area.x + 24, area.y + 28))
			return
		por_nodo = {id(item["nodo"]): item for item in layout}
		for item in layout:
			nodo = item["nodo"]
			for hijo in (nodo.izquierda, nodo.derecha):
				if hijo is not None and id(hijo) in por_nodo:
					pos = por_nodo[id(hijo)]
					pygame.draw.line(superficie, vista.LINEA,
						(area.x + item["x"], area.y + item["y"] + 28),
						(area.x + pos["x"], area.y + pos["y"] - 28), 2)
		for item in layout:
			nodo = item["nodo"]
			r = pygame.Rect(0, 0, item["ancho"], 62)
			r.center = (round(area.x + item["x"]), round(area.y + item["y"]))
			seleccionado = nodo.clave.identificador == self.seleccionado
			costoso = bool(nodo.acceso_costoso)
			pygame.draw.rect(superficie, vista.COLOR_PRIORIDAD.get(nodo.clave.prioridad, vista.PANEL), r, border_radius=10)
			pygame.draw.rect(superficie, vista.BORDE_COSTOSO if costoso else (203, 215, 219), r, 3 if costoso or seleccionado else 1, border_radius=10)
			superficie.blit(self._fuente(13, True).render(f"SIS-{nodo.clave.identificador:06d}", True, vista.TEXTO), (r.x + 7, r.y + 8))
			superficie.blit(self._fuente(11).render(f"({nodo.clave.prioridad}, {nodo.clave.magnitud:g}, {nodo.clave.identificador})", True, (245, 231, 199)), (r.x + 7, r.y + 34))
			if costoso:
				superficie.blit(self._fuente(11, True).render("!", True, vista.BORDE_COSTOSO), (r.right - 17, r.top + 4))
			self._rect_nodos.append((r, nodo.clave.identificador))
		evento = self.contexto.historico.indice_activos.get(self.seleccionado)
		if evento:
			texto = f"Seleccionado: SIS-{evento.identificador:06d} · M {evento.magnitud:g} · {evento.estado}"
			superficie.blit(self._fuente(14).render(texto, True, self.TEXTO), (area.x + 20, area.bottom - 34))

	def _dibujar_mapa(self, superficie, area):
		pygame.draw.rect(superficie, (19, 29, 34), area, border_radius=12)
		activos = self.contexto.historico.indice_activos
		archivados = self.contexto.historico.eventos_archivados
		eventos = list(activos.values()) + list(archivados.values())
		zonas = self.contexto.escenario.zonas
		seleccionado = activos.get(self.seleccionado) or archivados.get(self.seleccionado)

		superficie.blit(self._fuente(22, True).render("Mapa del escenario", True, self.TEXTO), (area.x + 24, area.y + 17))
		descripcion = "Plano cartesiano · dominio fijo de 0 a 1000 km"
		if self.contexto.escenario.geometria_bloqueada:
			descripcion += " · geometría fijada"
		superficie.blit(
			self._fuente(13).render(descripcion, True, self.SUAVE),
			(area.x + 26, area.y + 47),
		)

		panel = pygame.Rect(area.x + 18, area.y + 72, area.width - 36, area.height - 92)
		lienzo_size = min(548, panel.height - 52, panel.width - 430)
		lienzo_size = max(240, lienzo_size)
		lienzo = pygame.Rect(panel.x + 48, panel.y + 18, lienzo_size, lienzo_size)
		lienzo.bottom = min(lienzo.bottom, panel.bottom - 24)

		def a_pantalla(x, y):
			return (
				round(lienzo.left + x / 1000 * lienzo.width),
				round(lienzo.bottom - y / 1000 * lienzo.height),
			)

		pygame.draw.rect(superficie, (237, 242, 239), lienzo)
		clip_anterior = superficie.get_clip()
		superficie.set_clip(lienzo)
		for marca in range(0, 1001, 100):
			pos_x = a_pantalla(marca, 0)[0]
			pos_y = a_pantalla(0, marca)[1]
			color = (181, 194, 191) if marca % 200 == 0 else (215, 224, 221)
			ancho_linea = 1 if marca % 200 else 2
			pygame.draw.line(superficie, color, (pos_x, lienzo.top), (pos_x, lienzo.bottom), ancho_linea)
			pygame.draw.line(superficie, color, (lienzo.left, pos_y), (lienzo.right, pos_y), ancho_linea)

		for indice, zona in enumerate(zonas, 1):
			x_min = max(0, min(1000, zona.x_min))
			x_max = max(0, min(1000, zona.x_max))
			y_min = max(0, min(1000, zona.y_min))
			y_max = max(0, min(1000, zona.y_max))
			if x_min >= x_max or y_min >= y_max:
				continue
			izquierda, abajo = a_pantalla(x_min, y_min)
			derecha, arriba = a_pantalla(x_max, y_max)
			rect_zona = pygame.Rect(izquierda, arriba, derecha - izquierda, abajo - arriba)
			color_zona = (36, 133, 105) if zona.poblada else (91, 119, 137)
			capa = pygame.Surface(rect_zona.size, pygame.SRCALPHA)
			capa.fill((*color_zona, 66))
			superficie.blit(capa, rect_zona.topleft)
			pygame.draw.rect(superficie, color_zona, rect_zona, 2)
			if rect_zona.width > 70 and rect_zona.height > 28:
				tipo_zona = "Poblada" if zona.poblada else "No poblada"
				etiqueta = self._fuente(11, True).render(f"Z{indice} · {tipo_zona}", True, (31, 64, 58))
				superficie.blit(etiqueta, (rect_zona.x + 6, rect_zona.y + 5))

		colores_prioridad = {1: (31, 132, 101), 2: (190, 111, 34), 3: (184, 58, 70)}
		self._rect_nodos = []
		for evento in eventos:
			if not isinstance(evento.epicentro, (tuple, list)) or len(evento.epicentro) != 2:
				continue
			x, y = map(float, evento.epicentro)
			if not 0 <= x <= 1000 or not 0 <= y <= 1000:
				continue
			posicion = a_pantalla(x, y)
			prioridad = self.contexto.gestor_eventos._crear_clave(evento).prioridad
			color = colores_prioridad[prioridad]
			identificador = evento.identificador
			archivado = identificador in archivados
			if archivado:
				pygame.draw.circle(superficie, (32, 119, 129), posicion, 13, 2)
			if identificador == self.seleccionado:
				pygame.draw.circle(superficie, (32, 42, 45), posicion, 12, 3)
			pygame.draw.circle(superficie, color, posicion, 8)
			pygame.draw.circle(superficie, (255, 255, 255), posicion, 8, 2)
			rect_marcador = pygame.Rect(0, 0, 24, 24)
			rect_marcador.center = posicion
			self._rect_nodos.append((rect_marcador, identificador))
			etiqueta = self._fuente(11, True).render(f"{identificador:06d}", True, (36, 51, 53))
			superficie.blit(etiqueta, (posicion[0] + 11, posicion[1] - 9))

		superficie.set_clip(clip_anterior)
		for marca in range(0, 1001, 200):
			pos_x = a_pantalla(marca, 0)[0]
			pos_y = a_pantalla(0, marca)[1]
			tick_x = self._fuente(11).render(str(marca), True, (190, 204, 200))
			tick_y = self._fuente(11).render(str(marca), True, (190, 204, 200))
			superficie.blit(tick_x, tick_x.get_rect(center=(pos_x, lienzo.bottom + 14)))
			superficie.blit(tick_y, tick_y.get_rect(midright=(lienzo.left - 8, pos_y)))
		pygame.draw.rect(superficie, (76, 100, 99), lienzo, 1)

		panel_x = lienzo.right + 34
		panel_rect = pygame.Rect(panel_x, panel.y + 18, panel.right - panel_x, panel.height - 36)
		pygame.draw.rect(superficie, (29, 42, 47), panel_rect, border_radius=8)
		px, py = panel_rect.x + 18, panel_rect.y + 18
		superficie.blit(self._fuente(15, True).render("LECTURA DEL MAPA", True, self.TEXTO), (px, py))
		py += 34
		superficie.blit(self._fuente(13).render(f"{len(activos)} activos  ·  {len(archivados)} archivados", True, self.SUAVE), (px, py))
		py += 37
		superficie.blit(self._fuente(13, True).render("Zonas", True, self.TEXTO), (px, py))
		py += 23
		for poblada, etiqueta in ((True, "Poblada"), (False, "No poblada")):
			color_zona = (36, 133, 105) if poblada else (91, 119, 137)
			pygame.draw.rect(superficie, color_zona, (px, py + 2, 14, 14), border_radius=2)
			superficie.blit(self._fuente(12).render(etiqueta, True, (205, 216, 214)), (px + 23, py))
			py += 22
		py += 8
		superficie.blit(self._fuente(13, True).render("Prioridad", True, self.TEXTO), (px, py))
		py += 23
		for prioridad, etiqueta in ((3, "Alta"), (2, "Media"), (1, "Baja")):
			color = colores_prioridad[prioridad]
			pygame.draw.circle(superficie, color, (px + 7, py + 9), 7)
			superficie.blit(self._fuente(12).render(f"P{prioridad} · {etiqueta}", True, (205, 216, 214)), (px + 23, py))
			py += 22
		pygame.draw.circle(superficie, (32, 119, 129), (px + 7, py + 9), 9, 2)
		superficie.blit(self._fuente(12).render("Archivado", True, (205, 216, 214)), (px + 23, py))
		py += 34
		pygame.draw.line(superficie, (70, 87, 91), (px, py), (panel_rect.right - 16, py), 1)
		py += 14
		superficie.blit(self._fuente(13, True).render("Evento seleccionado", True, self.TEXTO), (px, py))
		py += 26
		if seleccionado is None:
			lineas = ["Haz clic en un epicentro", "para consultar sus datos."]
		else:
			archivado = seleccionado.identificador in archivados
			prioridad = self.contexto.gestor_eventos._crear_clave(seleccionado).prioridad
			x, y = seleccionado.epicentro
			lineas = [
				f"SIS-{seleccionado.identificador:06d} · {'Archivado' if archivado else 'Activo'}",
				f"Magnitud: {seleccionado.magnitud:g}  ·  P{prioridad}",
				f"Epicentro: ({x:g}, {y:g}) km",
				f"Hipocentro: {seleccionado.profundidad:g} km",
				f"Zona poblada: {'Sí' if self.contexto.escenario.zona_de(x, y) else 'No'}",
				f"Atención: {seleccionado.estado}",
			]
		for linea in lineas:
			superficie.blit(self._fuente(12).render(linea, True, (213, 222, 219)), (px, py))
			py += 21

		pie = self._fuente(11).render("X e Y en km · cada división principal representa 200 km", True, self.SUAVE)
		superficie.blit(pie, (area.x + 24, area.bottom - 18 - pie.get_height()))

	def _dibujar_seccion(self, superficie, area):
		titulo = dict(self.SECCIONES)[self.seccion]
		superficie.blit(self._fuente(22, True).render(titulo, True, self.TEXTO), (area.x + 24, area.y + 18))
		if self.seccion == "escenario":
			self._boton(
				superficie,
				pygame.Rect(area.right - 222, area.y + 13, 196, 36),
				"Nuevo escenario vacío",
				"nuevo_escenario",
			)
		if self.seccion == "eventos":
			filas = [f"SIS-{e.identificador:06d} | P{self.contexto.gestor_eventos._crear_clave(e).prioridad} | M {e.magnitud:g} | H {e.profundidad:g} km | rev. {e.revision} | {e.estado}" for e in self.contexto.historico.indice_activos.values()]
		elif self.seccion == "cola":
			filas = [f"{i + 1:02d} · SIS-{r.identificador:06d} | rev. {r.revision} | M {r.magnitud:g} | estación {r.estacion}" for i, r in enumerate(self.contexto.cola.reportes_pendientes())]
			filas.append(f"Pendientes: {len(self.contexto.cola.reportes_pendientes())}")
		elif self.seccion == "historico":
			filas = [f"SIS-{e.identificador:06d} | M {e.magnitud:g} | {e.fecha} | archivado" for e in self.contexto.historico.eventos_archivados.values()]
			filas.extend(f"ID {identificador} | eliminado" for identificador in sorted(self.contexto.historico.identificadores_eliminados - set(self.contexto.historico.eventos_archivados)))
		elif self.seccion == "asociaciones":
			activos = self.contexto.historico.indice_activos
			archivados = self.contexto.historico.eventos_archivados
			eventos = list(activos.values()) + list(archivados.values())
			referenciados_por = {evento.identificador: [] for evento in eventos}
			for origen, destino in (self.contexto.referencias or {}).items():
				if destino in referenciados_por:
					referenciados_por[destino].append(origen)
			filas = [
				f"Eventos activos examinados en AVL: {len(activos)} · eventos archivados examinados: {len(archivados)}"
			]
			for evento in eventos:
				candidatos = candidatos_de(evento, eventos, self.contexto.escenario)
				referencia = referencia_de(evento, candidatos)
				estado = "activo" if evento.identificador in activos else "archivado"
				id_referencia = f"SIS-{referencia.identificador:06d}" if referencia else "ninguna"
				filas.extend((
					f"SIS-{evento.identificador:06d} · {estado} · referencia elegida: {id_referencia}",
					"  Candidatos: " + (", ".join(
						f"SIS-{c.identificador:06d} ({'activo' if c.identificador in activos else 'archivado'})"
						for c in candidatos
					) or "ninguno"),
					"  Referencia de: " + (", ".join(
						f"SIS-{identificador:06d}"
						for identificador in referenciados_por[evento.identificador]
					) or "ninguno"),
				))
		elif self.seccion == "auditoria":
			incidencias = verificar_estructura(
				self.contexto.arbol,
				self.contexto.escenario,
				self.contexto.historico.indice_activos,
				self.contexto.historico,
				self.contexto.referencias,
			)
			filas = [f"SIS-{i['identificador']:06d} | {i['tipo']} | {'; '.join(i['errores']) or 'desbalance informativo: ' + str(i['desbalances'])}" for i in incidencias]
			if not filas:
				filas = ["Estructura íntegra. No se detectaron inconsistencias."]
		elif self.seccion == "metricas":
			arbol = self.contexto.arbol
			metricas = self.contexto.arbol.metricas.a_dict()
			activos = self.contexto.historico.indice_activos
			archivados = self.contexto.historico.eventos_archivados
			nodos = self._nodos_con_profundidad()
			niveles = [nodo for nodo, _ in nodos]
			eventos_prioridad = {prioridad: 0 for prioridad in (1, 2, 3)}
			pendientes_atencion = 0
			for evento in activos.values():
				prioridad = self.contexto.gestor_eventos._crear_clave(evento).prioridad
				eventos_prioridad[prioridad] += 1
				pendientes_atencion += evento.estado == "pendiente"
			costosos = sum(nodo.acceso_costoso for nodo, _ in nodos)
			nivel_actual = []
			cola_niveles = [arbol.raiz] if arbol.raiz is not None else []
			while cola_niveles:
				nodo = cola_niveles.pop(0)
				nivel_actual.append(nodo.clave.identificador)
				if nodo.izquierda is not None:
					cola_niveles.append(nodo.izquierda)
				if nodo.derecha is not None:
					cola_niveles.append(nodo.derecha)
			inorden = arbol.claves_in_order()
			preorden = arbol._recorrido_pre_order(arbol.raiz)
			postorden = arbol._recorrido_post_order(arbol.raiz)
			formatear = lambda claves: " ".join(f"{clave.identificador:06d}" for clave in claves) or "vacío"
			filas = [
				f"Eventos activos: {len(activos)} · históricos: {len(archivados)}",
				f"Altura AVL: {arbol.altura()} · hojas: {self._contar_hojas(arbol)} · modo: {arbol.modo}",
				f"Eventos por prioridad: P1 {eventos_prioridad[1]} · P2 {eventos_prioridad[2]} · P3 {eventos_prioridad[3]}",
				f"Pendientes de atención: {pendientes_atencion} · acceso costoso: {costosos} · límite L={self.contexto.escenario.L}",
				f"Inorden: {formatear(inorden)}",
				f"Preorden: {formatear(preorden)}",
				f"Postorden: {formatear(postorden)}",
				f"Por niveles: {' '.join(f'{identificador:06d}' for identificador in nivel_actual) or 'vacío'}",
			]
			filas.extend(f"{nombre.replace('_', ' ').capitalize()}: {valor}" for nombre, valor in metricas.items())
			if self.rotaciones_recuperacion:
				filas.append("Última recuperación AVL:")
				filas.extend(self.rotaciones_recuperacion)
		else:
			escenario = self.contexto.escenario
			filas = [
				f"Reloj simulado: {escenario.reloj.isoformat(sep=' ', timespec='minutes')}",
				f"Modo: {self.contexto.arbol.modo}",
				f"W ventana de asociación: {escenario.W} h",
				f"R distancia máxima: {escenario.R} km",
				f"L umbral de eventos: {escenario.L}",
				f"T antigüedad de archivo: {escenario.T} h",
				f"Zonas configuradas: {len(escenario.zonas)}",
				f"Estaciones inmutables: {', '.join(escenario.estaciones)}",
			]
			y = area.y + 68
			for fila in filas:
				superficie.blit(self._fuente(15).render(fila, True, (198, 211, 214)), (area.x + 28, y))
				y += 36
			self._dibujar_mensaje(superficie, area)
			return
		filas = self._envolver_filas(filas, self._fuente(14), area.width - 56)
		filas_visibles = max(1, (area.height - 120) // 30)
		offset = min(self.desplazamiento, max(0, len(filas) - filas_visibles))
		y = area.y + 66
		for fila in filas[offset:offset + filas_visibles]:
			superficie.blit(self._fuente(14).render(fila, True, (198, 211, 214)), (area.x + 28, y))
			y += 30
		if len(filas) > filas_visibles:
			rango = f"Mostrando {offset + 1}–{min(offset + filas_visibles, len(filas))} de {len(filas)}"
			superficie.blit(self._fuente(11).render(rango, True, self.SUAVE), (area.right - 230, area.bottom - 50))
		self._dibujar_mensaje(superficie, area)

	@staticmethod
	def _envolver_filas(filas, fuente, ancho_maximo):
		resultado = []
		for fila in filas:
			actual = ""
			for palabra in str(fila).split():
				candidato = f"{actual} {palabra}".strip()
				if actual and fuente.size(candidato)[0] > ancho_maximo:
					resultado.append(actual)
					actual = palabra
				else:
					actual = candidato
			if actual:
				resultado.append(actual)
		return resultado

	def _dibujar_mensaje(self, superficie, area):
		color = (255, 151, 133) if self.mensaje_error else self.ACENTO
		superficie.blit(self._fuente(13).render(self.mensaje[:130], True, color), (area.x + 20, area.bottom - 27))

	def _dibujar_modal(self, superficie):
		ancho, alto = superficie.get_size()
		capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)
		capa.fill((0, 0, 0, 155))
		superficie.blit(capa, (0, 0))
		modal = pygame.Rect(0, 0, min(620, ancho - 60), min(640, alto - 90))
		modal.center = (ancho // 2, alto // 2)
		pygame.draw.rect(superficie, (29, 40, 47), modal, border_radius=14)
		tipo = self.formulario["_tipo"]
		titulos = {
			"crear": "Crear evento sísmico",
			"corregir": "Corregir evento seleccionado",
			"reporte": "Encolar reporte",
			"escenario": "Parámetros del escenario",
			"cargar": "Cargar estado JSON",
			"zona": "Agregar zona rectangular",
			"version_guardar": "Guardar versión persistente",
			"consulta_id": "Consultar identificador",
			"consulta_top_k": "Pendientes por prioridad",
			"consulta_magnitud": "Intervalo de magnitud",
			"consulta_profundidad_fecha": "Profundidad y fechas",
		}
		superficie.blit(self._fuente(21, True).render(titulos[tipo], True, self.TEXTO), (modal.x + 24, modal.y + 20))
		self.campos = []
		y = modal.y + 68
		if self.mensaje_error:
			error = self._fuente(12, True).render(self.mensaje[:84], True, (255, 151, 133))
			superficie.blit(error, (modal.x + 24, y))
			y += 22
		for nombre, valor in self.formulario.items():
			if nombre.startswith("_"):
				continue
			label = self._fuente(13).render(nombre, True, self.SUAVE)
			superficie.blit(label, (modal.x + 24, y))
			rect = pygame.Rect(modal.x + 24, y + 20, modal.width - 48, 36)
			activo = nombre == self.campo_activo
			pygame.draw.rect(superficie, (18, 27, 33), rect, border_radius=6)
			pygame.draw.rect(superficie, self.ACENTO if activo else (67, 82, 89), rect, 2 if activo else 1, border_radius=6)
			superficie.blit(self._fuente(14).render(str(valor), True, self.TEXTO), (rect.x + 10, rect.y + 8))
			self.campos.append((nombre, rect))
			y += 64
			if y > modal.bottom - 98:
				break
		self._boton(superficie, pygame.Rect(modal.right - 224, modal.bottom - 58, 94, 38), "CANCELAR", "cerrar_form")
		self._boton(superficie, pygame.Rect(modal.right - 118, modal.bottom - 58, 94, 38), "GUARDAR", "confirmar_form", "principal")

	def _dibujar_modal_confirmacion(self, superficie):
		ancho, alto = superficie.get_size()
		capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)
		capa.fill((0, 0, 0, 175))
		superficie.blit(capa, (0, 0))
		modal = pygame.Rect(0, 0, min(700, ancho - 60), min(430, alto - 90))
		modal.center = (ancho // 2, alto // 2)
		pygame.draw.rect(superficie, (29, 40, 47), modal, border_radius=12)
		pygame.draw.rect(superficie, (93, 111, 116), modal, 1, border_radius=12)
		superficie.blit(
			self._fuente(20, True).render(self.confirmacion["titulo"], True, self.TEXTO),
			(modal.x + 24, modal.y + 22),
		)
		fuente = self._fuente(14)
		lineas = []
		for texto in self.confirmacion["lineas"]:
			actual = ""
			for palabra in texto.split():
				candidato = f"{actual} {palabra}".strip()
				if actual and fuente.size(candidato)[0] > modal.width - 48:
					lineas.append(actual)
					actual = palabra
				else:
					actual = candidato
			if actual:
				lineas.append(actual)
		y = modal.y + 72
		for linea in lineas[:7]:
			superficie.blit(fuente.render(linea, True, (207, 218, 216)), (modal.x + 24, y))
			y += 27
		self._boton(
			superficie,
			pygame.Rect(modal.right - 228, modal.bottom - 58, 96, 38),
			"CANCELAR",
			"cancelar_confirmacion",
		)
		self._boton(
			superficie,
			pygame.Rect(modal.right - 120, modal.bottom - 58, 96, 38),
			"CONFIRMAR",
			"confirmar_confirmacion",
			"peligro" if self.confirmacion["tipo"] == "eliminar" else "principal",
		)