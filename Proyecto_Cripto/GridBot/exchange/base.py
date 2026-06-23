"""
exchange/base.py
Clase base para clientes de exchange
"""
from abc import ABC, abstractmethod

class BaseExchangeClient(ABC):
    @abstractmethod
    async def get_positions(self, symbol=None):
        """Obtiene posiciones abiertas"""
        pass
    
    @abstractmethod
    async def get_orders(self, symbol=None, status='open'):
        """Obtiene órdenes pendientes"""
        pass
    
    @abstractmethod
    async def create_market_order(self, symbol, side, amount, leverage):
        """Crea orden de mercado"""
        pass
    
    @abstractmethod
    async def create_limit_order(self, symbol, side, amount, price, leverage):
        """Crea orden límite"""
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol, order_id):
        """Cancela orden"""
        pass
    
    @abstractmethod
    async def get_balance(self, currency='USDT'):
        """Obtiene balance"""
        pass
    
    @abstractmethod
    async def set_leverage(self, symbol, leverage):
        """Establece apalancamiento"""
        pass
