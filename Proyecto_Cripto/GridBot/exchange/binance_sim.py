"""
exchange/binance_sim.py
Cliente de simulación para pruebas
"""
import time
from .base import BaseExchangeClient

class BinanceSimClient(BaseExchangeClient):
    def __init__(self):
        self.balance = {"USDT": 10000.0}
        self.positions = {}
        self.orders = {}
        self.order_counter = 0
    
    async def get_positions(self, symbol=None):
        """Retorna posiciones simuladas"""
        return []
    
    async def get_orders(self, symbol=None, status='open'):
        """Retorna órdenes simuladas"""
        return []
    
    async def create_market_order(self, symbol, side, amount, leverage):
        """Simula orden de mercado"""
        self.order_counter += 1
        order_id = f"SIM_{self.order_counter}_{int(time.time())}"
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "leverage": leverage,
            "status": "closed",
            "simulated": True
        }
    
    async def create_limit_order(self, symbol, side, amount, price, leverage):
        """Simula orden límite"""
        self.order_counter += 1
        order_id = f"SIM_LIMIT_{self.order_counter}_{int(time.time())}"
        return {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "leverage": leverage,
            "status": "open",
            "simulated": True
        }
    
    async def cancel_order(self, symbol, order_id):
        """Simula cancelación de orden"""
        return True
    
    async def get_balance(self, currency='USDT'):
        """Retorna balance simulado"""
        return self.balance.get(currency, 0)
    
    async def set_leverage(self, symbol, leverage):
        """Simula establecimiento de apalancamiento"""
        return True
        