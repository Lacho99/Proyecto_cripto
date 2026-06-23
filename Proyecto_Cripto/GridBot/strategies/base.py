"""
strategies/base.py
Clase base para todas las estrategias
"""
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, bot):
        self.bot = bot
    
    @abstractmethod
    def procesar(self, precio, timestamp):
        """Procesa el precio según la estrategia"""
        pass
    
    @abstractmethod
    def verificar_entrada(self, precio):
        """Verifica si hay señal de entrada"""
        pass
    
    @abstractmethod
    def gestionar_cierres(self, precio):
        """Gestiona cierres de posiciones"""
        pass