"""
strategies/gridT.py
Estrategia Grid con Trailing
"""
from .base import BaseStrategy
from .grid import GridStrategy
from datetime import datetime

class GridTStrategy(GridStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.CALLBACK = 0.002  # 0.2% de rebote para trailing
    
    def gestionar_cierres(self, precio):
        """Gestiona cierres con trailing"""
        alertas = []
        niveles_a_cerrar = []
        
        monedas = float(self.bot.monedas_por_grid) if self.bot.monedas_por_grid else 0  

        for p_ent, datos in self.bot.posiciones.items():
            mejor_p, objetivo, trailing_activo = datos[:3]
            
            # Primero: alcanzó el objetivo? Activar trailing
            if not trailing_activo:
                if (self.bot.direccion == "short" and precio <= objetivo) or \
                   (self.bot.direccion == "long" and precio >= objetivo):
                    self.bot.posiciones[p_ent][2] = True
                    self.bot.posiciones[p_ent][0] = precio
                    alertas.append(f"🛰️ <b>Trailing Armado</b> | {self.bot.bot_id}")
                continue
            
            # Trailing activado: hacer seguimiento
            if self.bot.direccion == "short":
                if precio < mejor_p:
                    self.bot.posiciones[p_ent][0] = precio
                if precio >= round(self.bot.posiciones[p_ent][0] * (1 + self.CALLBACK), self.bot.decimales):
                    niveles_a_cerrar.append(p_ent)
                    if precio < objetivo:
                        self.bot.trailing_plus += 1
                    else:
                        self.bot.trailing_minus += 1
            else:  # long
                if precio > mejor_p:
                    self.bot.posiciones[p_ent][0] = precio
                if precio <= round(self.bot.posiciones[p_ent][0] * (1 - self.CALLBACK), self.bot.decimales):
                    niveles_a_cerrar.append(p_ent)
                    if precio > objetivo:
                        self.bot.trailing_plus += 1
                    else:
                        self.bot.trailing_minus += 1
        
        # Ejecutar cierres
        for p_ent in niveles_a_cerrar:
            datos = self.bot.posiciones[p_ent]
            hora_entrada = datos[3] if len(datos) > 3 else "N/A"
            trade_id_s = datos[4] if len(datos) > 4 else "N/A"
            
            ganancia = (p_ent - precio if self.bot.direccion == "short" else precio - p_ent) * monedas
            self.bot.pnl_acumulado += ganancia
            self.bot.comisiones_pagadas += (self.bot.monedas_por_grid * precio) * 0.0004
            self.bot.trades_cerrados += 1
            self.bot.registrar_trade_csv(p_ent, precio, ganancia, "gridT", self.bot.direccion, hora_entrada, trade_id_s)
            del self.bot.posiciones[p_ent]
            alertas.append(f"💰 <b>TAKE PROFIT (TRAILING)</b>\n🤖 {self.bot.bot_id}\n📈 Profit: ${ganancia:.2f}")
            
            if self.bot.master:
                self.bot.master.guardar_estado()
        
        return alertas
