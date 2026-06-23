"""
exchange/factory.py
Fábrica de clientes de exchange
"""
import os
from .binance_real import BinanceRealClient
from .binance_sim import BinanceSimClient

class ExchangeFactory:
    def __init__(self):
        self.api_key_real = os.getenv("BINANCE_API_KEY_REAL")
        self.secret_key_real = os.getenv("BINANCE_SECRET_KEY_REAL")
        self.api_key_test = os.getenv("BINANCE_API_KEY_TEST")
        self.secret_key_test = os.getenv("BINANCE_SECRET_KEY_TEST")
        self._client_cache = {}
    
    def get_client(self, modo, bot_id):
        """Retorna el cliente según el modo"""
        cache_key = f"{modo}_{bot_id}"
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]
        
        if modo == "real":
            client = BinanceRealClient(self.api_key_real, self.secret_key_real)
        else:
            client = BinanceSimClient()
        
        self._client_cache[cache_key] = client
        return client
