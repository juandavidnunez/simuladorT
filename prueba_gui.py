import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from pygame_app import crear_aplicacion_demo
from persistencia import cargar_por_inserciones
from escenario import Escenario


def click_comando(pantalla, superficie, comando):
	pantalla.dibujar(superficie)
	rect = next(rect for rect, actual in pantalla.botones if actual == comando)
	pantalla.manejar_evento(
		pygame.event.Event(
			pygame.MOUSEBUTTONDOWN,
			{"button": 1, "pos": rect.center},
		)
	)


def escribir_campo(pantalla, nombre, texto):
	pantalla.dibujar(superficie)
	rect = next(rect for actual, rect in pantalla.campos if actual == nombre)
	pantalla.manejar_evento(
		pygame.event.Event(
			pygame.MOUSEBUTTONDOWN,
			{"button": 1, "pos": rect.center},
		)
	)
	pantalla.manejar_evento(
		pygame.event.Event(
			pygame.KEYDOWN,
			{"key": pygame.K_a, "unicode": "\x01", "mod": pygame.KMOD_CTRL},
		)
	)
	for caracter in texto:
		pantalla.manejar_evento(
			pygame.event.Event(
				pygame.KEYDOWN,
				{"key": ord(caracter), "unicode": caracter, "mod": 0},
			)
		)


pygame.init()
aplicacion = crear_aplicacion_demo()
pantalla = aplicacion.pantallas["simulador"]
superficie = pygame.Surface(aplicacion.dimensiones)
layout = pantalla.vista_arbol.calcular_layout((1068, 704))

assert len(layout) == aplicacion.contexto.arbol.peso()
assert [item["nodo"].clave for item in layout] == aplicacion.contexto.arbol.claves_in_order()
assert [item["x"] for item in layout] == sorted(item["x"] for item in layout)
assert aplicacion.contexto.arbol.metricas.casos_LR >= 1
assert all(
	item["nodo"].acceso_costoso
	== (item["nodo"].clave.prioridad == 3 and item["profundidad"] > aplicacion.contexto.escenario.L)
	for item in layout
)
aplicacion.contexto.arbol.actualizar_accesos_costosos(0)
assert any(item["nodo"].acceso_costoso for item in layout)
aplicacion.contexto.arbol.actualizar_accesos_costosos(aplicacion.contexto.escenario.L)

pantalla.dibujar(superficie)
captura_arbol = Path(tempfile.gettempdir()) / "sismolab_simulador_arbol.png"
pygame.image.save(superficie, captura_arbol)
click_comando(pantalla, superficie, "seccion:mapa")
pantalla.dibujar(superficie)
captura_mapa = Path(tempfile.gettempdir()) / "sismolab_simulador_mapa.png"
pygame.image.save(superficie, captura_mapa)
assert len(pantalla._rect_nodos) == len(aplicacion.contexto.historico.indice_activos)
rect_marcador, id_marcador = pantalla._rect_nodos[0]
pantalla.manejar_evento(
	pygame.event.Event(
		pygame.MOUSEBUTTONDOWN,
		{"button": 1, "pos": rect_marcador.center},
	)
)
assert pantalla.seleccionado == id_marcador
pantalla.dibujar(superficie)
assert pantalla.contexto.historico.indice_activos[id_marcador].identificador == id_marcador

click_comando(pantalla, superficie, "seccion:comparacion")
pantalla.orden_comparacion = "ascendente"
pantalla.dibujar(superficie)
avl_comparativo, bst_comparativo, claves_comparadas = pantalla._crear_arboles_comparacion()
assert claves_comparadas == sorted(claves_comparadas)
assert avl_comparativo.claves_in_order() == bst_comparativo.claves_in_order()
assert bst_comparativo.raiz.clave == claves_comparadas[0]
assert bst_comparativo.altura() >= avl_comparativo.altura()
pantalla.orden_comparacion = "recepcion"
avl_comparativo, bst_comparativo, claves_comparadas = pantalla._crear_arboles_comparacion()
assert avl_comparativo.claves_in_order() == bst_comparativo.claves_in_order()

click_comando(pantalla, superficie, "seccion:consultas")
pantalla._consultar_top_k(3)
assert len(pantalla.resultados_consulta) == 3
assert pantalla.nodos_consultados <= aplicacion.contexto.arbol.peso()
pantalla._consultar_magnitud(4.5, 7.0)
assert len(pantalla.resultados_consulta) == 5
assert pantalla.nodos_consultados == aplicacion.contexto.arbol.peso()
reloj_simulado = aplicacion.contexto.escenario.reloj
inicio_dia = reloj_simulado.replace(hour=0, minute=0, second=0, microsecond=0)
pantalla._consultar_profundidad_fecha(700.0, inicio_dia, reloj_simulado)
assert len(pantalla.resultados_consulta) == aplicacion.contexto.arbol.peso()
fecha_exacta = aplicacion.contexto.historico.indice_activos[30].fecha.replace(tzinfo=None)
pantalla._consultar_profundidad_fecha(45.0, fecha_exacta, fecha_exacta)
assert len(pantalla.resultados_consulta) == aplicacion.contexto.arbol.peso()

for consulta_invalida, argumentos in (
	(pantalla._consultar_identificador, (0,)),
	(pantalla._consultar_magnitud, (float("nan"), 5.0)),
	(pantalla._consultar_profundidad_fecha, (float("inf"), inicio_dia, reloj_simulado)),
):
	try:
		consulta_invalida(*argumentos)
	except ValueError:
		pass
	else:
		raise AssertionError("La consulta debe rechazar criterios fuera de dominio")
pantalla._consultar_identificador(30)
assert any("búsqueda por clave" in fila for fila in pantalla.resultados_consulta)
assert any("Zona poblada" in fila for fila in pantalla.resultados_consulta)
assert any("Referencia elegida" in fila for fila in pantalla.resultados_consulta)
assert any("Prioridad" in fila for fila in pantalla.resultados_consulta)
pantalla._consultar_acceso_costoso()
assert pantalla.nodos_consultados == aplicacion.contexto.arbol.peso()
pantalla.dibujar(superficie)
click_comando(pantalla, superficie, "seccion:arbol")
ids_iniciales = set(aplicacion.contexto.historico.indice_activos)
pantalla.seleccionado = 30
click_comando(pantalla, superficie, "eliminar")
assert pantalla.confirmacion["tipo"] == "eliminar"
assert 30 in aplicacion.contexto.historico.indice_activos
click_comando(pantalla, superficie, "cancelar_confirmacion")
assert 30 in aplicacion.contexto.historico.indice_activos
click_comando(pantalla, superficie, "eliminar")
click_comando(pantalla, superficie, "confirmar_confirmacion")
assert 30 not in aplicacion.contexto.historico.indice_activos
assert set(aplicacion.contexto.historico.indice_activos) == ids_iniciales - {30}
click_comando(pantalla, superficie, "deshacer")
assert set(aplicacion.contexto.historico.indice_activos) == ids_iniciales

click_comando(pantalla, superficie, "crear")
for nombre, valor in (
	("ID", "996"),
	("Magnitud", "4.2"),
	("Profundidad km", "50"),
	("Coordenada X", "10"),
	("Coordenada Y", "10"),
	("Fecha UTC ISO", aplicacion.contexto.escenario.reloj.isoformat(timespec="seconds")),
	("Estación", "STA-99"),
):
	escribir_campo(pantalla, nombre, valor)
click_comando(pantalla, superficie, "confirmar_form")
assert pantalla.formulario is not None
assert pantalla.mensaje_error
assert 996 not in aplicacion.contexto.historico.indice_activos
assert aplicacion.contexto.pila_deshacer.cantidad() == 0
click_comando(pantalla, superficie, "cerrar_form")

click_comando(pantalla, superficie, "crear")
for nombre, valor in (
	("ID", "999"),
	("Magnitud", "4.6"),
	("Profundidad km", "18"),
	("Coordenada X", "12.5"),
	("Coordenada Y", "13.5"),
	("Fecha UTC ISO", "2026-09-29T11:30:00Z"),
):
	escribir_campo(pantalla, nombre, valor)
click_comando(pantalla, superficie, "confirmar_form")
assert 999 in aplicacion.contexto.historico.indice_activos
assert aplicacion.contexto.historico.indice_activos[999].estaciones == {"STA-01"}
assert aplicacion.contexto.pila_deshacer.cantidad() == 1
click_comando(pantalla, superficie, "deshacer")
assert 999 not in aplicacion.contexto.historico.indice_activos

click_comando(pantalla, superficie, "seccion:cola")
click_comando(pantalla, superficie, "reporte")
aplicacion.contexto.historico.indice_activos[30].revision = 2
for nombre, valor in (
	("ID", "30"),
	("Revisión", "1"),
	("Magnitud", "3.0"),
	("Profundidad km", "50"),
	("Coordenada X", "1"),
	("Coordenada Y", "1"),
	("Fecha UTC ISO", "2026-09-28T10:00:00Z"),
	("Estación", "STA-02"),
):
	escribir_campo(pantalla, nombre, valor)
click_comando(pantalla, superficie, "confirmar_form")
assert len(aplicacion.contexto.cola.reportes_pendientes()) == 1
click_comando(pantalla, superficie, "procesar_uno")
assert len(aplicacion.contexto.cola.reportes_pendientes()) == 0
assert aplicacion.contexto.arbol.metricas.reportes_descartados == 1
click_comando(pantalla, superficie, "deshacer")
assert len(aplicacion.contexto.cola.reportes_pendientes()) == 1
assert aplicacion.contexto.arbol.metricas.reportes_descartados == 0
click_comando(pantalla, superficie, "seccion:cola")
click_comando(pantalla, superficie, "procesar_todos")
pantalla.siguiente_paso_ms = 0
pantalla.actualizar()
assert len(aplicacion.contexto.cola.reportes_pendientes()) == 0
assert "decisión: descartado" in pantalla.mensaje
pantalla.siguiente_paso_ms = 0
pantalla.actualizar()
assert not pantalla.continuo_activo
click_comando(pantalla, superficie, "deshacer")
assert len(aplicacion.contexto.cola.reportes_pendientes()) == 1

click_comando(pantalla, superficie, "seccion:mapa")
pantalla.dibujar(superficie)
assert len(aplicacion.contexto.escenario.zonas) == 3
assert any(isinstance(evento.epicentro, tuple) for evento in aplicacion.contexto.historico.indice_activos.values())
assert aplicacion.contexto.escenario.geometria_bloqueada
assert not any(comando == "zona" for _, comando in pantalla.botones)
pantalla._accion("zona")
assert pantalla.formulario is None
assert pantalla.mensaje_error
assert len(aplicacion.contexto.escenario.zonas) == 3

click_comando(pantalla, superficie, "seccion:escenario")
click_comando(pantalla, superficie, "alternar_modo")
assert aplicacion.contexto.arbol.modo == "estres"
assert aplicacion.contexto.escenario.modo == "estres"
click_comando(pantalla, superficie, "recuperar")
assert aplicacion.contexto.arbol.modo == "normal"
assert aplicacion.contexto.escenario.modo == "normal"
assert "Recuperación auditada" in pantalla.mensaje
click_comando(pantalla, superficie, "deshacer")
assert aplicacion.contexto.arbol.modo == "estres"
assert aplicacion.contexto.escenario.modo == "estres"
click_comando(pantalla, superficie, "deshacer")
assert aplicacion.contexto.arbol.modo == "normal"
assert aplicacion.contexto.escenario.modo == "normal"

escenario_estres = Escenario(reloj=aplicacion.contexto.escenario.reloj)
eventos_estres = [
	{
		"identificador": identificador,
		"magnitud": 2.0 + identificador / 10,
		"profundidad": 80.0,
		"epicentro": (100.0 + identificador, 200.0),
		"fecha": escenario_estres.reloj,
		"en_zona_poblada": False,
		"estaciones": ["STA-01"],
	}
	for identificador in range(1, 13)
]
estado_estres = cargar_por_inserciones(eventos_estres, escenario_estres, modo="estres")
aplicacion_estres = crear_aplicacion_demo()
aplicacion_estres.instalar_estado(estado_estres)
pantalla_estres = aplicacion_estres.pantallas["simulador"]
claves_estres = aplicacion_estres.contexto.arbol.claves_in_order()
altura_estres = aplicacion_estres.contexto.arbol.altura()
assert type(aplicacion_estres.contexto.arbol).__name__ == "AVL"
assert altura_estres == 11
click_comando(pantalla_estres, superficie, "seccion:escenario")
click_comando(pantalla_estres, superficie, "alternar_modo")
assert aplicacion_estres.contexto.arbol.modo == "estres"
assert "Recuperar equilibrio" in pantalla_estres.mensaje
assert aplicacion_estres.contexto.pila_deshacer.cantidad() == 0
click_comando(pantalla_estres, superficie, "recuperar")
assert aplicacion_estres.contexto.arbol.modo == "normal"
assert aplicacion_estres.contexto.escenario.modo == "normal"
assert aplicacion_estres.contexto.arbol.claves_in_order() == claves_estres
assert aplicacion_estres.contexto.arbol.altura() < altura_estres
assert "Recuperación auditada" in pantalla_estres.mensaje
click_comando(pantalla_estres, superficie, "deshacer")
assert aplicacion_estres.contexto.arbol.modo == "estres"
assert aplicacion_estres.contexto.escenario.modo == "estres"
assert aplicacion_estres.contexto.arbol.altura() == altura_estres

aplicacion_nueva = crear_aplicacion_demo()
pantalla_nueva = aplicacion_nueva.pantallas["simulador"]
ids_demo = set(aplicacion_nueva.contexto.historico.indice_activos)
click_comando(pantalla_nueva, superficie, "seccion:escenario")
click_comando(pantalla_nueva, superficie, "nuevo_escenario")
assert pantalla_nueva.confirmacion["tipo"] == "nuevo_escenario"
click_comando(pantalla_nueva, superficie, "confirmar_confirmacion")
assert aplicacion_nueva.contexto.arbol.peso() == 0
assert not aplicacion_nueva.contexto.escenario.geometria_bloqueada
click_comando(pantalla_nueva, superficie, "seccion:mapa")
pantalla_nueva.dibujar(superficie)
assert any(comando == "zona" for _, comando in pantalla_nueva.botones)
click_comando(pantalla_nueva, superficie, "zona")
for nombre, valor in (
	("X mínimo", "100"),
	("X máximo", "200"),
	("Y mínimo", "100"),
	("Y máximo", "200"),
	("Poblada true/false", "true"),
):
	escribir_campo(pantalla_nueva, nombre, valor)
click_comando(pantalla_nueva, superficie, "confirmar_form")
assert len(aplicacion_nueva.contexto.escenario.zonas) == 1
assert not aplicacion_nueva.contexto.escenario.geometria_bloqueada
click_comando(pantalla_nueva, superficie, "seccion:eventos")
click_comando(pantalla_nueva, superficie, "crear")
for nombre, valor in (
	("ID", "1400"),
	("Magnitud", "4.5"),
	("Profundidad km", "20"),
	("Coordenada X", "150"),
	("Coordenada Y", "150"),
	("Fecha UTC ISO", aplicacion_nueva.contexto.escenario.reloj.isoformat(timespec="seconds")),
	("Estación", "STA-01"),
):
	escribir_campo(pantalla_nueva, nombre, valor)
click_comando(pantalla_nueva, superficie, "confirmar_form")
assert aplicacion_nueva.contexto.escenario.geometria_bloqueada
assert aplicacion_nueva.contexto.historico.indice_activos[1400].en_zona_poblada
click_comando(pantalla_nueva, superficie, "deshacer")
assert not aplicacion_nueva.contexto.escenario.geometria_bloqueada
assert aplicacion_nueva.contexto.arbol.peso() == 0
click_comando(pantalla_nueva, superficie, "deshacer")
assert len(aplicacion_nueva.contexto.escenario.zonas) == 0
click_comando(pantalla_nueva, superficie, "deshacer")
assert set(aplicacion_nueva.contexto.historico.indice_activos) == ids_demo
assert aplicacion_nueva.contexto.escenario.geometria_bloqueada

aplicacion_archivo = crear_aplicacion_demo()
pantalla_archivo = aplicacion_archivo.pantallas["simulador"]
pantalla_archivo.contexto.escenario.T = 1
pantalla_archivo.contexto.escenario.reloj += timedelta(hours=2)
ids_antes_archivo = set(pantalla_archivo.contexto.historico.indice_activos)
click_comando(pantalla_archivo, superficie, "seccion:historico")
click_comando(pantalla_archivo, superficie, "archivar")
assert pantalla_archivo.confirmacion["tipo"] == "archivar"
ids_previsualizados = set(pantalla_archivo.confirmacion["ids"])
assert ids_previsualizados
assert set(pantalla_archivo.contexto.historico.indice_activos) == ids_antes_archivo
click_comando(pantalla_archivo, superficie, "confirmar_confirmacion")
assert ids_previsualizados.issubset(pantalla_archivo.contexto.historico.eventos_archivados)
assert not ids_previsualizados & set(pantalla_archivo.contexto.historico.indice_activos)
click_comando(pantalla_archivo, superficie, "deshacer")
assert set(pantalla_archivo.contexto.historico.indice_activos) == ids_antes_archivo

aplicacion_rafaga = crear_aplicacion_demo()
pantalla_rafaga = aplicacion_rafaga.pantallas["simulador"]
pantalla_rafaga._elegir_archivo = lambda guardar=False, ruta_inicial=None: str(
	Path(__file__).parent / "datos_prueba" / "rafaga_reportes.json"
)
click_comando(pantalla_rafaga, superficie, "seccion:cola")
click_comando(pantalla_rafaga, superficie, "cargar_rafaga")
assert [
	reporte.identificador
	for reporte in aplicacion_rafaga.contexto.cola.reportes_pendientes()
] == [82001, 82002, 82001, 82001, 82001, 82001]
assert aplicacion_rafaga.contexto.pila_deshacer.cantidad() == 1
click_comando(pantalla_rafaga, superficie, "deshacer")
assert aplicacion_rafaga.contexto.cola.reportes_pendientes() == []

with tempfile.TemporaryDirectory() as temporal:
	carpeta_versiones = Path(temporal) / "versiones"
	pantalla._directorio_versiones = lambda: carpeta_versiones
	ruta_version = pantalla._guardar_version("baseline laboratorio")
	documento_version = json.loads(ruta_version.read_text(encoding="utf-8"))
	assert documento_version["nombre_version"] == "baseline laboratorio"
	assert ruta_version.exists()
	try:
		pantalla._guardar_version("baseline laboratorio")
	except ValueError:
		pass
	else:
		raise AssertionError("Una versión existente no debe sobrescribirse")
	crear_despues = lambda: aplicacion.contexto.gestor_eventos.crear_evento({
		"identificador": 998,
		"magnitud": 2.0,
		"profundidad": 80.0,
		"epicentro": (300.0, 300.0),
		"fecha": aplicacion.contexto.escenario.reloj,
		"estacion": "STA-01",
	})
	pantalla._ejecutar("Crear evento posterior", crear_despues)
	assert 998 in aplicacion.contexto.historico.indice_activos
	pantalla._restaurar_version(ruta_version.name)
	assert 998 not in aplicacion.contexto.historico.indice_activos
	estado_deshacer = aplicacion.contexto.pila_deshacer.deshacer()
	aplicacion.sincronizar_estado(estado_deshacer)
	assert 998 in aplicacion.contexto.historico.indice_activos

	ruta_inserciones = Path(temporal) / "eventos.json"
	ruta_inserciones.write_text(json.dumps({
		"eventos": [{
			"identificador": 777,
			"magnitud": 3.0,
			"profundidad": 20.0,
			"epicentro": [500.0, 500.0],
			"fecha": datetime.now().astimezone().replace(microsecond=0).isoformat(),
			"estaciones": ["STA-01"],
		}]
	}), encoding="utf-8")
	pantalla._elegir_archivo = lambda guardar=False, ruta_inicial=None: str(ruta_inserciones)
	pantalla._cargar_inserciones_con_dialogo()
	assert set(aplicacion.contexto.historico.indice_activos) == {777}
	estado_deshacer = aplicacion.contexto.pila_deshacer.deshacer()
	aplicacion.sincronizar_estado(estado_deshacer)
	assert 777 not in aplicacion.contexto.historico.indice_activos

pantalla.dibujar(superficie)
assert any(comando == "cerrar" for _, comando in pantalla.botones)
click_comando(pantalla, superficie, "cerrar")
assert not aplicacion.corriendo

pygame.event.post(pygame.event.Event(pygame.QUIT))
otra_aplicacion = crear_aplicacion_demo()
otra_aplicacion.ejecutar(max_frames=10)
assert not otra_aplicacion.corriendo
pygame.quit()

print(f"Capturas: {captura_arbol}; {captura_mapa}")
print("Alta, formularios, cola, descarte, undo y ambos cierres verificados")