from datetime import datetime

from AVL import AVL
from auditoria import verificar_estructura
from clave import Clave
from cola_reportes import ColaReportes
from estado import EstadoOperativo
from evento import Evento
from escenario import Escenario
from historico import GestorHistorico
from gestor_eventos import GestorEventos
from metricas import Metricas
from pila_deshacer import PilaDeshacer
from reportes import Reporte, procesar_reporte


escenario_normal = Escenario(reloj=datetime(2026, 9, 29), modo="normal")
arbol_correcto = AVL()
for magnitud, identificador in ((20, 20), (10, 10), (30, 30), (5, 5), (15, 15)):
	assert arbol_correcto.insertar(Clave(1, magnitud, identificador))
assert verificar_estructura(arbol_correcto, escenario_normal) == []

nodo_raiz = arbol_correcto.raiz
altura_correcta = nodo_raiz.altura
nodo_raiz.altura += 5
incidencias = verificar_estructura(arbol_correcto, escenario_normal)
incidencia_raiz = next(
	incidencia
	for incidencia in incidencias
	if incidencia["identificador"] == nodo_raiz.clave.identificador
)
assert incidencia_raiz["tipo"] == "metadatos"
assert incidencia_raiz["es_error_integridad"]
assert any("altura almacenada" in error for error in incidencia_raiz["errores"])
assert all(incidencia["tipo"] != "orden" for incidencia in incidencias)
nodo_raiz.altura = altura_correcta

escenario_referencias = Escenario(reloj=datetime(2026, 9, 29, 12, 0))
arbol_referencias = AVL()
evento_principal = Evento(
	201, 6.0, 20.0, (100.0, 100.0), datetime(2026, 9, 29, 9, 0), 1, "pendiente"
)
evento_secundario = Evento(
	202, 4.0, 20.0, (101.0, 100.0), datetime(2026, 9, 29, 10, 0), 1, "pendiente"
)
indice_referencias = {201: evento_principal, 202: evento_secundario}
historico_referencias = GestorHistorico(indice_referencias)
assert arbol_referencias.insertar(Clave(3, 6.0, 201))
assert arbol_referencias.insertar(Clave(1, 4.0, 202))
incidencias_referencias = verificar_estructura(
	arbol_referencias,
	escenario_referencias,
	indice_referencias,
	historico_referencias,
	{202: 999},
)
assert any(
	incidencia["identificador"] == 202 and incidencia["tipo"] == "referencia"
	for incidencia in incidencias_referencias
)

arbol_orden = AVL()
for magnitud, identificador in ((20, 20), (10, 10), (30, 30), (5, 5), (15, 15)):
	assert arbol_orden.insertar(Clave(1, magnitud, identificador))
nodo_fuera_de_rango = arbol_orden._nodos_por_identificador[15]
nodo_fuera_de_rango.clave = Clave(1, 25, 15)
incidencias_orden = verificar_estructura(arbol_orden, escenario_normal)
assert any(incidencia["tipo"] == "orden" for incidencia in incidencias_orden)

escenario_estres = Escenario(reloj=datetime(2026, 9, 29), modo="estres")
arbol_estres = AVL()
arbol_estres.modo = "estres"
for valor in range(1, 7):
	assert arbol_estres.insertar(Clave(1, valor, valor))
incidencias_estres = verificar_estructura(arbol_estres, escenario_estres)
assert incidencias_estres
assert all(
	incidencia["tipo"] == "desbalance_informativo"
	and not incidencia["es_error_integridad"]
	for incidencia in incidencias_estres
)

arbol_rotacion = AVL()
for valor in (30, 10, 20):
	assert arbol_rotacion.insertar(Clave(1, valor, valor))
assert arbol_rotacion.metricas.casos_LR == 1
assert arbol_rotacion.metricas.giros_izquierda == 1
assert arbol_rotacion.metricas.giros_derecha == 1

ahora = datetime(2026, 9, 29, 10, 0)
arbol_reportes = AVL()
evento_actual = Evento(601, 4.0, 50.0, (0.0, 0.0), ahora, 2, "activo")
assert arbol_reportes.insertar(Clave(1, 4.0, 601))
indice_reportes = {601: evento_actual}
assert procesar_reporte(
	Reporte(601, 1, 3.0, 60.0, (0.0, 0.0), ahora, False, "EST-01"),
	indice_reportes,
	arbol_reportes,
) == "descartado"
assert procesar_reporte(
	Reporte(601, 2, 4.1, 50.0, (0.0, 0.0), ahora, False, "EST-02"),
	indice_reportes,
	arbol_reportes,
) == "conflicto"
assert procesar_reporte(
	Reporte(601, 3, 4.2, 50.0, (0.0, 0.0), ahora, False, "EST-03"),
	indice_reportes,
	arbol_reportes,
) == "sustitucion"
assert arbol_reportes.metricas.reportes_descartados == 1
assert arbol_reportes.metricas.conflictos == 1
assert arbol_reportes.metricas.correcciones_aceptadas == 1

metricas = Metricas(conflictos=4)
arbol_snapshot = AVL(metricas)
indice_activos = {}
historico = GestorHistorico(indice_activos)
cola = ColaReportes(indice_activos, arbol_snapshot)
escenario = Escenario(reloj=datetime(2026, 9, 29))
gestor = GestorEventos(arbol_snapshot, indice_activos, escenario, historico)
estado = EstadoOperativo(
	arbol_snapshot,
	historico,
	cola,
	escenario,
	metricas,
	{},
	gestor,
)
pila = PilaDeshacer(estado)
pila.ejecutar_accion(
	"incrementar conflicto de prueba",
	lambda: pila.estado.arbol.metricas.incrementar("conflictos"),
)
assert pila.estado.metricas.conflictos == 5
restaurado = pila.deshacer()
assert restaurado is estado
assert pila.estado.metricas.conflictos == 4
assert pila.estado.arbol.metricas is pila.estado.metricas

print("Altura corrupta detectada como metadatos, sin falso error de orden")
print("Orden global y desbalance informativo de estrés verificados")
print("Contadores de doble giro y restauración de métricas verificados")
print("La prueba de auditoría y métricas pasó")