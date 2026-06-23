"""
services/order_manager.py
Gestión de órdenes
"""
class OrderManager:
    def __init__(self, master):
        self.master = master
    
    async def ejecutar_orden_mercado(self, bot, side, amount, leverage):
        # TODO: Implementar
        pass
    
    async def ejecutar_orden_limite(self, bot, side, amount, price, leverage):
        # TODO: Implementar
        pass
    
    async def ejecutar_oco(self, bot, precio_entrada, tp, sl, cantidad, direccion):
        # TODO: Implementar
        pass
    
    async def cancelar_orden(self, bot, order_id):
        # TODO: Implementar
        pass
