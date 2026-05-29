"""
exceptions.py — Jerarquía de excepciones personalizadas del sistema.
"""


class MineriaIAException(Exception):
    """Excepción base del sistema."""


class ModeloNoEncontrado(MineriaIAException):
    """Se lanzó cuando un archivo de modelo (.keras / .pkl) no existe."""
    def __init__(self, ruta: str):
        super().__init__(f"Modelo no encontrado en: {ruta}")
        self.ruta = ruta


class ZonaNoSoportada(MineriaIAException):
    """La zona solicitada no tiene modelos entrenados."""
    def __init__(self, zona: str):
        super().__init__(f"Zona no soportada: {zona}")
        self.zona = zona


class AgenteNoDisponible(MineriaIAException):
    """Un agente especializado no responde."""
    def __init__(self, agente: str, url: str):
        super().__init__(f"Agente {agente} no disponible en {url}")
        self.agente = agente
        self.url = url


class DatosInsuficientes(MineriaIAException):
    """Historial insuficiente para realizar predicción."""
    def __init__(self, requeridos: int, disponibles: int):
        super().__init__(
            f"Se necesitan {requeridos} lecturas, solo hay {disponibles}"
        )


class RAGNoInicializado(MineriaIAException):
    """El sistema RAG no fue inicializado antes de consultar."""