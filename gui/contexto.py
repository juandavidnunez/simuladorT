from dataclasses import dataclass
from typing import Any

from AVL import AVL
from cola_reportes import ColaReportes
from escenario import Escenario
from gestor_eventos import GestorEventos
from historico import GestorHistorico


@dataclass
class ContextoGUI:
	escenario: Escenario
	arbol: AVL
	historico: GestorHistorico
	cola: ColaReportes
	gestor_eventos: GestorEventos | None = None
	gestor_asociaciones: Any = None
	pila_deshacer: Any = None
	metricas: Any = None
	referencias: dict | None = None