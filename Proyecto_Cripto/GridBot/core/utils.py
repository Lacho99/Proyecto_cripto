"""
core/utils.py
Funciones auxiliares
"""
import math
import time
from datetime import datetime

class Utils:
    @staticmethod
    def calcular_porcentaje(actual, anterior):
        """Calcula porcentaje entre dos valores"""
        if anterior == 0:
            return 0
        return ((actual - anterior) / anterior) * 100
    
    @staticmethod
    def redondear_precio(valor, decimales):
        """Redondea un precio a los decimales especificados"""
        if valor is None:
            return None
        return round(valor, decimales)
    
    @staticmethod
    def timestamp_a_fecha(timestamp):
        """Convierte timestamp a fecha legible"""
        if not timestamp:
            return "N/A"
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def ahora_str():
        """Retorna la fecha/hora actual como string"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        