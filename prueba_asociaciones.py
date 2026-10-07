from datetime import datetime

from AVL import AVL
from asociaciones import (
	FuentesEventos,
	candidatos_de,
	distancia_euclidiana,
	recuperar_afectadas,
	referencia_de,
)
from clave import Clave
from evento import Evento
from escenario import Escenario
from historico import GestorHistorico


escenario = Escenario(
	reloj=datetime(2026, 9, 29, 12, 0),
	W=48,
	R=40,
)
arbol = AVL()
indice_activos = {}
historico = GestorHistorico(indice_activos)
fuentes = FuentesEventos(arbol, indice_activos, historico)

evento_56 = Evento(
	560,
	5.6,
	20.0,
	(0.0, 0.0),
	datetime(2026, 9, 29, 10, 0),
	1,
	"revisado",
)
evento_42 = Evento(
	420,
	4.2,
	30.0,
	(0.0, 20.0),
	datetime(2026, 9, 29, 10, 20),
	1,
	"revisado",
)
for evento, prioridad in ((evento_56, 2), (evento_42, 1)):
	assert arbol.insertar(Clave(prioridad, evento.magnitud, evento.identificador))
	indice_activos[evento.identificador] = evento

referencias = {}
iniciales_actualizadas = recuperar_afectadas(
	evento_42,
	fuentes,
	escenario,
	referencias,
)
assert iniciales_actualizadas == {420: 560}
assert referencias == {420: 560}

evento_archivado = Evento(
	590,
	5.9,
	40.0,
	(0.0, 8.0),
	datetime(2026, 9, 29, 9, 58),
	1,
	"archivado",
)
historico.eventos_archivados[590] = evento_archivado
historico.identificadores_eliminados.add(590)
evento_eliminado = Evento(
	700,
	7.0,
	10.0,
	(0.0, 1.0),
	datetime(2026, 9, 29, 9, 50),
	1,
	"eliminado",
)
historico.identificadores_eliminados.add(700)

evento_tardio = Evento(
	610,
	6.1,
	15.0,
	(0.0, 5.0),
	datetime(2026, 9, 29, 9, 55),
	1,
	"revisado",
)
assert arbol.insertar(Clave(3, evento_tardio.magnitud, evento_tardio.identificador))
indice_activos[evento_tardio.identificador] = evento_tardio

actualizados = recuperar_afectadas(
	evento_tardio,
	fuentes,
	escenario,
	referencias,
)
assert actualizados == {610: None, 560: 610, 420: 610, 590: 610}
assert referencias == {420: 610, 560: 610, 590: 610}

candidatos_42 = candidatos_de(evento_42, fuentes, escenario)
assert [candidato.identificador for candidato in candidatos_42] == [610, 590, 560]
assert referencia_de(evento_42, list(reversed(candidatos_42))).identificador == 610
assert all(candidato.identificador != 700 for candidato in candidatos_42)
assert distancia_euclidiana((0, 0), (3, 4)) == 5

evento_objetivo = Evento(
	800,
	4.0,
	10.0,
	(0.0, 0.0),
	datetime(2026, 9, 29, 10, 20),
	1,
	"revisado",
)
fuera_de_criterio = [
	Evento(801, 4.1, 10.0, (0.0, 1.0), datetime(2026, 9, 29, 10, 20), 1, "revisado"),
	Evento(802, 5.0, 10.0, (0.0, 1.0), datetime(2026, 9, 29, 10, 20), 1, "revisado"),
	Evento(803, 5.0, 10.0, (0.0, 1.0), datetime(2026, 9, 27, 10, 19), 1, "revisado"),
	Evento(804, 5.0, 10.0, (0.0, 41.0), datetime(2026, 9, 29, 10, 0), 1, "revisado"),
	Evento(805, 5.0, 10.0, (0.0, 1.0), datetime(2026, 9, 29, 10, 21), 1, "revisado"),
]
assert candidatos_de(evento_objetivo, fuera_de_criterio, escenario) == []

candidato_lejano_en_tiempo = Evento(
	502,
	5.0,
	10.0,
	(0.0, 2.0),
	datetime(2026, 9, 29, 10, 0),
	1,
	"revisado",
)
candidato_cercano_menor_id = Evento(
	501,
	5.0,
	10.0,
	(0.0, 2.0),
	datetime(2026, 9, 29, 10, 10),
	1,
	"revisado",
)
candidato_cercano_mayor_id = Evento(
	503,
	5.0,
	10.0,
	(0.0, 2.0),
	datetime(2026, 9, 29, 10, 10),
	1,
	"revisado",
)
assert referencia_de(
	evento_objetivo,
	[candidato_lejano_en_tiempo, candidato_cercano_mayor_id, candidato_cercano_menor_id],
) is candidato_cercano_menor_id

print("Antes del reporte tardío: evento 420 -> referencia 560")
print("Después del reporte tardío: evento 560 -> referencia 610")
print("Después del reporte tardío: evento 420 -> referencia 610")
print("Archivados considerados y eliminados excluidos")
print("La prueba de asociaciones pasó")