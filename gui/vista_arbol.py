import pygame

from gui.contexto import ContextoGUI


class VistaArbol:
	FONDO = (17, 23, 29)
	PANEL = (25, 34, 41)
	TEXTO = (232, 239, 241)
	TEXTO_SUAVE = (147, 163, 170)
	LINEA = (75, 92, 99)
	COLOR_PRIORIDAD = {
		1: (36, 120, 100),
		2: (158, 106, 39),
		3: (164, 62, 70),
	}
	BORDE_COSTOSO = (55, 204, 211)
	BORDE_NORMAL = (207, 219, 222)

	def __init__(self, contexto: ContextoGUI):
		self.contexto = contexto
		self._fuentes = None

	def _obtener_fuentes(self):
		if not pygame.font.get_init():
			pygame.font.init()
		if self._fuentes is None:
			self._fuentes = {
				"titulo": pygame.font.SysFont("segoeui", 27, bold=True),
				"subtitulo": pygame.font.SysFont("segoeui", 14),
				"estadistica": pygame.font.SysFont("segoeui", 14, bold=True),
				"leyenda": pygame.font.SysFont("segoeui", 13),
			}
		return self._fuentes

	def manejar_evento(self, evento: pygame.event.Event) -> None:
		return None

	def actualizar(self) -> None:
		return None

	def _nodos_in_order_con_profundidad(self):
		resultado = []
		pila = []
		nodo = self.contexto.arbol.raiz
		profundidad = 0
		while pila or nodo is not None:
			while nodo is not None:
				pila.append((nodo, profundidad))
				nodo = nodo.izquierda
				profundidad += 1
			nodo, profundidad = pila.pop()
			resultado.append((nodo, profundidad))
			nodo = nodo.derecha
			profundidad += 1
		return resultado

	def calcular_layout(self, dimensiones):
		ancho, alto = dimensiones
		nodos = self._nodos_in_order_con_profundidad()
		if not nodos:
			return []

		margen = 48
		ancho_util = max(1, ancho - margen * 2)
		paso_x = ancho_util / len(nodos)
		ancho_nodo = max(66, min(184, int(paso_x * 0.86)))
		profundidad_maxima = max(profundidad for _, profundidad in nodos)
		techo = 164
		pie = 96
		if profundidad_maxima == 0:
			paso_y = 0
		else:
			paso_y = max(76, min(132, (alto - techo - pie) / profundidad_maxima))

		return [
			{
				"nodo": nodo,
				"profundidad": profundidad,
				"x": margen + paso_x * (indice + 0.5),
				"y": techo + paso_y * profundidad,
				"ancho": ancho_nodo,
				"alto": 66,
			}
			for indice, (nodo, profundidad) in enumerate(nodos)
		]

	@staticmethod
	def _texto_ajustado(texto, ancho_maximo, color, negrita=False):
		for tamano in range(16, 9, -1):
			fuente = pygame.font.SysFont("segoeui", tamano, bold=negrita)
			if fuente.size(texto)[0] <= ancho_maximo:
				return fuente.render(texto, True, color)
		fuente = pygame.font.SysFont("segoeui", 9, bold=negrita)
		return fuente.render(texto, True, color)

	def dibujar(self, superficie: pygame.Surface) -> None:
		fuentes = self._obtener_fuentes()
		ancho, alto = superficie.get_size()
		superficie.fill(self.FONDO)

		pygame.draw.rect(superficie, self.PANEL, (24, 22, ancho - 48, 94), border_radius=14)
		superficie.blit(fuentes["titulo"].render("Árbol de eventos", True, self.TEXTO), (46, 36))
		modo = self.contexto.arbol.modo.upper()
		estadistica = (
			f"{self.contexto.arbol.peso()} nodos    "
			f"altura {self.contexto.arbol.altura()}    {modo}"
		)
		superficie.blit(fuentes["subtitulo"].render("Orden in-order · profundidad vertical", True, self.TEXTO_SUAVE), (48, 76))
		estadistica_render = fuentes["estadistica"].render(estadistica, True, (191, 204, 207))
		superficie.blit(estadistica_render, (ancho - estadistica_render.get_width() - 48, 52))

		layout = self.calcular_layout((ancho, alto))
		por_nodo = {id(item["nodo"]): item for item in layout}
		for item in layout:
			nodo = item["nodo"]
			for hijo in (nodo.izquierda, nodo.derecha):
				if hijo is None or id(hijo) not in por_nodo:
					continue
				posicion_hijo = por_nodo[id(hijo)]
				pygame.draw.line(
					superficie,
					self.LINEA,
					(item["x"], item["y"] + item["alto"] * 0.42),
					(posicion_hijo["x"], posicion_hijo["y"] - posicion_hijo["alto"] * 0.42),
					2,
				)

		for item in layout:
			nodo = item["nodo"]
			clave = nodo.clave
			rectangulo = pygame.Rect(0, 0, item["ancho"], item["alto"])
			rectangulo.center = (round(item["x"]), round(item["y"]))
			relleno = self.COLOR_PRIORIDAD.get(clave.prioridad, (75, 82, 87))
			costoso = bool(getattr(nodo, "acceso_costoso", False))
			borde = self.BORDE_COSTOSO if costoso else self.BORDE_NORMAL
			pygame.draw.rect(superficie, relleno, rectangulo, border_radius=13)
			pygame.draw.rect(superficie, borde, rectangulo, width=3 if costoso else 1, border_radius=13)

			id_texto = f"SIS-{clave.identificador:06d}"
			clave_texto = f"({clave.prioridad}, {clave.magnitud:g}, {clave.identificador})"
			render_id = self._texto_ajustado(id_texto, rectangulo.width - 12, self.TEXTO, True)
			render_clave = self._texto_ajustado(clave_texto, rectangulo.width - 12, (239, 225, 193))
			superficie.blit(render_id, render_id.get_rect(center=(rectangulo.centerx, rectangulo.centery - 10)))
			superficie.blit(render_clave, render_clave.get_rect(center=(rectangulo.centerx, rectangulo.centery + 12)))
			if costoso:
				centro_marca = (rectangulo.right - 2, rectangulo.top + 2)
				pygame.draw.circle(superficie, self.BORDE_COSTOSO, centro_marca, 10)
				marca = pygame.font.SysFont("segoeui", 13, bold=True).render("!", True, self.FONDO)
				superficie.blit(marca, marca.get_rect(center=centro_marca))

		self._dibujar_leyenda(superficie, alto, fuentes["leyenda"])

	def _dibujar_leyenda(self, superficie, alto, fuente):
		ancho = superficie.get_width()
		pygame.draw.line(superficie, (47, 59, 66), (32, alto - 62), (ancho - 32, alto - 62), 1)
		x = 48
		for prioridad, etiqueta in ((1, "P1 baja"), (2, "P2 media"), (3, "P3 alta")):
			pygame.draw.rect(
				superficie,
				self.COLOR_PRIORIDAD[prioridad],
				(x, alto - 43, 15, 15),
				border_radius=4,
			)
			superficie.blit(fuente.render(etiqueta, True, self.TEXTO_SUAVE), (x + 23, alto - 45))
			x += 126
		pygame.draw.rect(
			superficie,
			self.PANEL,
			(x, alto - 46, 24, 20),
			border_radius=5,
		)
		pygame.draw.rect(
			superficie,
			self.BORDE_COSTOSO,
			(x, alto - 46, 24, 20),
			width=2,
			border_radius=5,
		)
		superficie.blit(fuente.render("acceso costoso", True, self.TEXTO_SUAVE), (x + 32, alto - 45))