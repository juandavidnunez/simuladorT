import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from AVL import AVL
from escenario import Escenario
from persistencia import (
	cargar_por_inserciones,
	cargar_por_topologia,
	exportar,
)


eventos = [
	{
		"identificador": identificador,
		"magnitud": magnitud,
		"profundidad": 50.0,
		"epicentro": (float(identificador), 0.0),
		"fecha": datetime(2026, 9, 28, 10, identificador),
		"en_zona_poblada": False,
		"estaciones": {"STA-01"},
	}
	for identificador, magnitud in ((10, 2.0), (20, 2.5), (30, 3.0), (40, 3.5), (50, 4.0))
]
reloj = datetime(2026, 9, 29, 12, 0)

with tempfile.TemporaryDirectory() as temporal:
	ruta_normal = Path(temporal) / "normal.json"
	estado_normal = cargar_por_inserciones(
		eventos,
		Escenario(reloj=reloj),
		modo="normal",
	)
	exportar(
		estado_normal.escenario,
		estado_normal.arbol,
		estado_normal.historico,
		estado_normal.cola,
		estado_normal,
		ruta_normal,
		"versión normal",
	)
	documento_normal = json.loads(ruta_normal.read_text(encoding="utf-8"))
	cargado_normal, problemas = cargar_por_topologia(ruta_normal)
	assert not problemas
	assert cargado_normal is not None
	assert cargado_normal.arbol.modo == "normal"
	assert cargado_normal.arbol.claves_in_order() == estado_normal.arbol.claves_in_order()
	assert cargado_normal.arbol.altura() <= 2
	assert documento_normal["nombre_version"] == "versión normal"

	ruta_estres = Path(temporal) / "estres.json"
	estado_estres = cargar_por_inserciones(
		eventos,
		Escenario(reloj=reloj, estaciones=("STA-01", "STA-X", "STA-Y")),
		modo="estres",
	)
	assert estado_estres.arbol.altura() == len(eventos) - 1
	exportar(
		estado_estres.escenario,
		estado_estres.arbol,
		estado_estres.historico,
		estado_estres.cola,
		estado_estres,
		ruta_estres,
	)
	cargado_estres, problemas = cargar_por_topologia(ruta_estres)
	assert not problemas
	assert cargado_estres is not None
	assert type(cargado_estres.arbol) is AVL
	assert cargado_estres.arbol.modo == "estres"
	assert cargado_estres.arbol.altura() == len(eventos) - 1
	assert cargado_estres.arbol.claves_in_order() == estado_estres.arbol.claves_in_order()
	assert cargado_estres.escenario.estaciones == ("STA-01", "STA-X", "STA-Y")
	orden_estres = cargado_estres.arbol.claves_in_order()
	cargado_estres.arbol.recuperar_equilibrio()
	assert cargado_estres.arbol.modo == "normal"
	assert cargado_estres.arbol.claves_in_order() == orden_estres

	estado_vigente = cargado_normal
	raiz_vigente = estado_vigente.arbol.raiz
	reloj_vigente = estado_vigente.escenario.reloj
	documento_invalido = copy.deepcopy(documento_normal)
	documento_invalido["estado"]["eventos_activos"][0]["prioridad"] = 3
	estado_resultante, problemas = cargar_por_topologia(
		documento_invalido,
		estado_vigente,
	)
	assert estado_resultante is estado_vigente
	assert estado_resultante.arbol.raiz is raiz_vigente
	assert estado_resultante.escenario.reloj == reloj_vigente
	assert any("Prioridad guardada incorrecta" in problema for problema in problemas)

	documento_reporte_invalido = copy.deepcopy(documento_normal)
	documento_reporte_invalido["estado"]["cola_reportes"].append({
		"identificador": 99,
		"revision": 0,
		"magnitud": 4.0,
		"profundidad": 10.0,
		"epicentro": {"tipo": "tuple", "elementos": [0.0, 0.0]},
		"fecha": {"tipo": "datetime", "valor": "2026-09-28T10:00:00"},
		"en_zona_poblada": False,
		"estacion": "EST-99",
	})
	estado_resultante, problemas = cargar_por_topologia(
		documento_reporte_invalido,
		estado_vigente,
	)
	assert estado_resultante is estado_vigente
	assert any("Reporte pendiente 1 inválido" in problema for problema in problemas)

	documento_referencia_invalida = copy.deepcopy(documento_normal)
	documento_referencia_invalida["estado"]["referencias"] = [[10, 20]]
	_, problemas = cargar_por_topologia(documento_referencia_invalida, estado_vigente)
	assert any("política determinista" in problema for problema in problemas)

	documento_precision_invalida = copy.deepcopy(documento_normal)
	documento_precision_invalida["estado"]["eventos_activos"][0]["magnitud"] = 2.55
	_, problemas = cargar_por_topologia(documento_precision_invalida, estado_vigente)
	assert any("máximo un decimal" in problema for problema in problemas)

	documento_con_ciclo = copy.deepcopy(documento_normal)
	indice_raiz = documento_con_ciclo["estado"]["arbol"]["raiz"]["raiz"]
	documento_con_ciclo["estado"]["arbol"]["raiz"]["nodos"][indice_raiz][
		"izquierda"
	] = indice_raiz
	estado_resultante, problemas = cargar_por_topologia(
		documento_con_ciclo,
		estado_vigente,
	)
	assert estado_resultante is estado_vigente
	assert any("ciclo" in problema for problema in problemas)

	documento_balance_invalido = copy.deepcopy(documento_normal)
	documento_balance_invalido["estado"]["arbol"]["raiz"]["nodos"][indice_raiz][
		"factor_balance"
	] = 9
	_, problemas = cargar_por_topologia(
		documento_balance_invalido,
		estado_vigente,
	)
	assert any("Factor de balance incorrecto" in problema for problema in problemas)

	documento_bst_invalido = copy.deepcopy(documento_normal)
	raiz_normal = documento_bst_invalido["estado"]["arbol"]["raiz"]["raiz"]
	indice_izquierdo = documento_bst_invalido["estado"]["arbol"]["raiz"]["nodos"][
		raiz_normal
	]["izquierda"]
	documento_bst_invalido["estado"]["arbol"]["raiz"]["nodos"][indice_izquierdo][
		"clave"
	]["magnitud"] = 9.0
	_, problemas = cargar_por_topologia(
		documento_bst_invalido,
		estado_vigente,
	)
	assert any("Orden BST inválido" in problema for problema in problemas)

	documento_modo_incorrecto = copy.deepcopy(
		json.loads(ruta_estres.read_text(encoding="utf-8"))
	)
	documento_modo_incorrecto["estado"]["arbol"]["modo"] = "normal"
	_, problemas = cargar_por_topologia(
		documento_modo_incorrecto,
		estado_vigente,
	)
	assert any("desbalanceado en modo normal" in problema for problema in problemas)

	documento_ids_duplicados = copy.deepcopy(documento_normal)
	evento_activo = documento_ids_duplicados["estado"]["eventos_activos"][0]
	documento_ids_duplicados["estado"]["eventos_archivados"].append(
		copy.deepcopy(evento_activo)
	)
	_, problemas = cargar_por_topologia(
		documento_ids_duplicados,
		estado_vigente,
	)
	assert any("repetidos entre activos e históricos" in problema for problema in problemas)

try:
	cargar_por_inserciones([eventos[0], eventos[0]])
except ValueError as error:
	assert "identificadores duplicados" in str(error)
else:
	raise AssertionError("La carga por inserciones debía rechazar IDs duplicados")

carpeta_datos = Path(__file__).parent / "datos_prueba"
estado_topologia_demo, problemas = cargar_por_topologia(
	carpeta_datos / "carga_topologia.json"
)
assert not problemas
assert estado_topologia_demo.arbol.peso() == 1
with (carpeta_datos / "carga_inserciones.json").open(encoding="utf-8") as archivo:
	fixture_inserciones = json.load(archivo)
estado_inserciones_demo = cargar_por_inserciones(
	fixture_inserciones["eventos"],
	Escenario(reloj=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)),
)
assert estado_inserciones_demo.arbol.peso() == len(fixture_inserciones["eventos"])
assert estado_inserciones_demo.arbol.claves_in_order() == sorted(
	estado_inserciones_demo.arbol.claves_in_order()
)

print("Carga por topología normal y por estrés verificadas")
print("Fixtures JSON de topología e inserciones verificadas")
print("Prioridad inconsistente rechazada sin sustituir el estado actual")
print("Carga por inserciones prevalidó identificadores duplicados")
print("La prueba de persistencia pasó")