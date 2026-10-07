import pygame

from gui.contexto import ContextoGUI
from gui.pantalla import Pantalla
from gui.simulador import VistaSimulador
from estado import EstadoOperativo
from pila_deshacer import PilaDeshacer


class Aplicacion:
	def __init__(
		self,
		escenario,
		arbol,
		historico,
		cola,
		gestor_eventos=None,
		gestor_asociaciones=None,
		pila_deshacer=None,
		metricas=None,
		referencias=None,
		dimensiones=(1280, 820),
		titulo="SismoLab | Árbol de eventos",
	):
		self.contexto = ContextoGUI(
			escenario=escenario,
			arbol=arbol,
			historico=historico,
			cola=cola,
			gestor_eventos=gestor_eventos,
			gestor_asociaciones=gestor_asociaciones,
			pila_deshacer=pila_deshacer,
			metricas=metricas,
			referencias=referencias,
		)
		self.dimensiones = dimensiones
		self.titulo = titulo
		self.pantallas: dict[str, Pantalla] = {}
		self.registrar_pantalla("simulador", VistaSimulador(self.contexto, self))
		self.pantalla_activa = "simulador"
		self.corriendo = False
		self.superficie = None

	def registrar_pantalla(self, nombre: str, pantalla: Pantalla) -> None:
		self.pantallas[nombre] = pantalla

	def activar_pantalla(self, nombre: str) -> None:
		if nombre not in self.pantallas:
			raise KeyError(f"Pantalla no registrada: {nombre}")
		self.pantalla_activa = nombre

	def cerrar(self) -> None:
		self.corriendo = False

	def sincronizar_estado(self, estado) -> None:
		self.contexto.escenario = estado.escenario
		self.contexto.arbol = estado.arbol
		self.contexto.historico = estado.historico
		self.contexto.cola = estado.cola
		self.contexto.gestor_eventos = estado.gestor_eventos
		self.contexto.metricas = estado.metricas
		self.contexto.referencias = estado.referencias
		if self.contexto.pila_deshacer is not None:
			self.contexto.pila_deshacer.estado = estado
		for pantalla in self.pantallas.values():
			if hasattr(pantalla, "contexto"):
				pantalla.contexto = self.contexto
			if hasattr(pantalla, "vista_arbol"):
				pantalla.vista_arbol.contexto = self.contexto

	def estado_operativo(self) -> EstadoOperativo:
		return EstadoOperativo(
			self.contexto.arbol,
			self.contexto.historico,
			self.contexto.cola,
			self.contexto.escenario,
			self.contexto.metricas,
			self.contexto.referencias or {},
			self.contexto.gestor_eventos,
		)

	def instalar_estado(self, estado) -> None:
		self.sincronizar_estado(estado)
		self.contexto.pila_deshacer = PilaDeshacer(estado)
		for pantalla in self.pantallas.values():
			if hasattr(pantalla, "contexto"):
				pantalla.contexto = self.contexto

	def ejecutar(self, max_frames: int | None = None) -> None:
		pygame.init()
		self.superficie = pygame.display.set_mode(self.dimensiones)
		pygame.display.set_caption(self.titulo)
		reloj = pygame.time.Clock()
		self.corriendo = True
		frames = 0

		try:
			while self.corriendo:
				pantalla = self.pantallas[self.pantalla_activa]
				for evento in pygame.event.get():
					if evento.type == pygame.QUIT:
						self.corriendo = False
					else:
						pantalla.manejar_evento(evento)
				pantalla.actualizar()
				pantalla.dibujar(self.superficie)
				pygame.display.flip()
				reloj.tick(60)
				frames += 1
				if max_frames is not None and frames >= max_frames:
					self.corriendo = False
		finally:
			pygame.quit()