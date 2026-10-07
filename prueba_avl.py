from AVL import AVL
from clave import Clave
from evento import calcular_prioridad


def verificar_estado(arbol, caso, insertada):
	nodos = []

	def recorrer(nodo):
		if nodo is None:
			return -1

		nodos.append(nodo)
		altura_izquierda = recorrer(nodo.izquierda)
		altura_derecha = recorrer(nodo.derecha)
		altura_calculada = 1 + max(altura_izquierda, altura_derecha)
		factor_balance = altura_izquierda - altura_derecha

		assert nodo.altura == altura_calculada
		assert factor_balance in {-1, 0, 1}
		return altura_calculada

	altura_arbol = recorrer(arbol.raiz)
	estado = ", ".join(
		f"{nodo.clave.magnitud:g}(h={nodo.altura}, "
		f"fb={arbol.factor_balance_de(nodo.clave)})"
		for nodo in nodos
	)
	print(
		f"{caso} tras insertar {insertada}: "
		f"altura_arbol={altura_arbol}; nodos: {estado}"
	)


def probar_rotaciones():
	casos = {
		"LL": [30, 20, 10],
		"RR": [10, 20, 30],
		"LR": [30, 10, 20],
		"RL": [10, 30, 20],
	}

	for nombre, valores in casos.items():
		arbol_rotacion = AVL()
		for valor in valores:
			assert arbol_rotacion.insertar(Clave(1, valor, valor))
			verificar_estado(arbol_rotacion, nombre, valor)

		assert arbol_rotacion.raiz.clave.magnitud == 20
		assert arbol_rotacion.altura() == 1
	print("Las cuatro pruebas de rotación AVL pasaron")


def probar_identificadores():
	arbol_ids = AVL()
	original = Clave(1, 4.0, 110)
	duplicada = Clave(3, 7.5, 110)

	assert arbol_ids.insertar(original)
	peso_original = arbol_ids.peso()
	assert not arbol_ids.insertar(duplicada)
	assert arbol_ids.peso() == peso_original
	assert arbol_ids.claves_in_order() == [original]

	assert arbol_ids.eliminar(original)
	assert arbol_ids.peso() == 0
	assert arbol_ids.insertar(duplicada)
	assert arbol_ids.peso() == 1

	arbol_dos_hijos = AVL()
	claves_dos_hijos = [
		Clave(1, magnitud, identificador)
		for magnitud, identificador in [
			(20, 220),
			(10, 210),
			(30, 230),
			(25, 225),
			(40, 240),
		]
	]
	for clave in claves_dos_hijos:
		assert arbol_dos_hijos.insertar(clave)

	nodo_objetivo = arbol_dos_hijos.buscar(claves_dos_hijos[0])
	assert nodo_objetivo is not None
	assert arbol_dos_hijos.eliminar(claves_dos_hijos[0])
	nodo_sucesor = arbol_dos_hijos.buscar(claves_dos_hijos[3])
	assert nodo_sucesor is nodo_objetivo
	assert not arbol_dos_hijos.insertar(Clave(3, 50, 225))
	assert arbol_dos_hijos.peso() == 4
	print("Las pruebas de identificadores y eliminación pasaron")


claves = [
	Clave(3, 6.1, 10),
	Clave(2, 5.8, 20),
	Clave(1, 4.2, 30),
	Clave(3, 5.2, 40),
	Clave(2, 4.5, 50),
	Clave(1, 3.9, 60),
	Clave(3, 5.2, 70),
	Clave(calcular_prioridad(6.0, 100.0, False), 6.0, 80),
	Clave(1, 2.5, 90),
	Clave(3, 7.0, 100),
]

arbol = AVL()
for clave in claves:
	arbol.insertar(clave)

print("Recorrido inorden:")
arbol.in_order()

orden_esperado = sorted(claves)
assert calcular_prioridad(6.0, 100.0, False) == 3
assert next(clave for clave in claves if clave.identificador == 80).prioridad == 3
assert arbol.claves_in_order() == orden_esperado
assert arbol.altura() >= 0
assert arbol.peso() == 10
print("La prueba del AVL pasó")

probar_rotaciones()
probar_identificadores()
