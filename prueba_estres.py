from datetime import datetime, timezone

from AVL import AVL
from clave import Clave
from cola_reportes import ColaReportes
from reportes import Reporte


arbol = AVL()
arbol.modo = "estres"
claves_insertadas = [Clave(1, valor, valor) for valor in range(1, 17)]

for clave in claves_insertadas:
	assert arbol.insertar(clave)

claves_antes = arbol.claves_in_order()
assert claves_antes == claves_insertadas
assert arbol.altura() == len(claves_insertadas) - 1

print(f"Antes de recuperar: altura={arbol.altura()}, modo={arbol.modo}")
for clave in claves_antes:
	print(
		f"{clave}: altura={arbol._nodos_por_identificador[clave.identificador].altura}, "
		f"factor={arbol.factor_balance_de(clave)}"
	)

rotaciones = arbol.recuperar_equilibrio()
claves_despues = arbol.claves_in_order()

print(f"Rotaciones aplicadas ({len(rotaciones)}):")
for rotacion in rotaciones:
	print(rotacion)
print(f"Después de recuperar: altura={arbol.altura()}, modo={arbol.modo}")
for clave in claves_despues:
	print(
		f"{clave}: altura={arbol._nodos_por_identificador[clave.identificador].altura}, "
		f"factor={arbol.factor_balance_de(clave)}"
	)

assert claves_despues == claves_antes
assert arbol.modo == "normal"
assert arbol.altura() <= 4


def verificar_avl(nodo):
	if nodo is None:
		return -1

	altura_izquierda = verificar_avl(nodo.izquierda)
	altura_derecha = verificar_avl(nodo.derecha)
	altura_real = 1 + max(altura_izquierda, altura_derecha)
	assert nodo.altura == altura_real
	assert abs(altura_izquierda - altura_derecha) <= 1
	return altura_real


verificar_avl(arbol.raiz)
arbol.in_order()

arbol_borrado = AVL()
arbol_borrado.modo = "estres"
claves_borrado = [Clave(1, valor, valor) for valor in (10, 20, 30, 40, 50)]
for clave in claves_borrado:
	assert arbol_borrado.insertar(clave)
assert arbol_borrado.eliminar(claves_borrado[-1])
assert arbol_borrado.modo == "estres"
assert arbol_borrado.altura() == 3
assert arbol_borrado.factor_balance_de(claves_borrado[0]) == -3

arbol_cola = AVL()
cola = ColaReportes({}, arbol_cola)
cola.modo = "estres"
reportes = [
	Reporte(
		901 + posicion,
		1,
		6.0 + posicion / 10,
		100.0,
		(100.0 + posicion, 200.0),
		datetime(2026, 9, 29, 10, posicion, tzinfo=timezone.utc),
		False,
		f"EST-{posicion + 1:02d}",
	)
	for posicion in range(5)
]
for reporte in reportes:
	cola.encolar(reporte)
resultados = cola.procesar_todos()
assert [resultado.identificador for resultado in resultados] == [
	reporte.identificador for reporte in reportes
]
assert arbol_cola.modo == "estres"
assert arbol_cola.altura() == 4

print("La prueba de estrés y recuperación pasó")