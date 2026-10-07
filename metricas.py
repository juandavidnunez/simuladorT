from dataclasses import asdict, dataclass


@dataclass
class Metricas:
	correcciones_aceptadas: int = 0
	reportes_descartados: int = 0
	conflictos: int = 0
	archivos_masivos: int = 0
	eventos_archivados: int = 0
	casos_LL: int = 0
	casos_RR: int = 0
	casos_LR: int = 0
	casos_RL: int = 0
	giros_izquierda: int = 0
	giros_derecha: int = 0

	def incrementar(self, contador: str, cantidad: int = 1) -> None:
		if contador not in self.__dataclass_fields__:
			raise KeyError(f"Contador desconocido: {contador}")
		if isinstance(cantidad, bool) or not isinstance(cantidad, int):
			raise TypeError("cantidad debe ser un entero")
		setattr(self, contador, getattr(self, contador) + cantidad)

	def a_dict(self) -> dict[str, int]:
		return asdict(self)

	@classmethod
	def desde_dict(cls, datos: dict):
		return cls(**datos)