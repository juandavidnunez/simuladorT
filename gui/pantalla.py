from typing import Protocol

import pygame


class Pantalla(Protocol):
	def manejar_evento(self, evento: pygame.event.Event) -> None:
		...

	def actualizar(self) -> None:
		...

	def dibujar(self, superficie: pygame.Surface) -> None:
		...