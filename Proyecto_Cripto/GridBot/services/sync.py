"""
services/sync.py
Servicio de sincronización con Binance
"""
from .conflict_resolver import ConflictResolver

class SyncService:
    def __init__(self, master):
        self.master = master
        self.resolver = ConflictResolver(master)
    
    async def sincronizar_bot(self, bot):
        # TODO: Implementar
        pass
    
    async def sincronizar_todos(self):
        # TODO: Implementar
        pass
    
    async def comparar_estados(self, bot, posiciones_binance, ordenes_binance):
        # TODO: Implementar
        pass
