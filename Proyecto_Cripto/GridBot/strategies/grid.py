"""
strategies/grid.py
Estrategia Grid clásica
"""
import time
from datetime import datetime
from .base import BaseStrategy

class GridStrategy(BaseStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        # Copiar variables necesarias
        self.niveles = bot.niveles
        self.direccion = bot.direccion
        self.decimales = bot.decimales
        self.last_price_checked = bot.last_price_checked
        self.estado_rango = bot.estado_rango
        self.posiciones = bot.posiciones
        self.trade_counter = bot.trade_counter
    
    def procesar(self, precio, timestamp):
        """Procesa el precio para Grid"""
        alertas = []
        
        # Verificar aperturas grid
        alertas.extend(self.verificar_entrada(precio))
        
        # Gestionar cierres
        alertas.extend(self.gestionar_cierres(precio))
        
        return alertas
    
    def verificar_entrada(self, precio):
        """Verifica si el precio cruzó un nivel para abrir SHORT/LONG"""
        if self.bot.pausado:
            return []
        
        alertas = []
        p_old = self.bot.last_price_checked
        p_new = precio
        
        if self.bot.estado_rango == "DENTRO":
            for i, nivel in enumerate(self.bot.niveles):
                nivel_ocupado = nivel in self.bot.posiciones
                
                # Detectar cruce físico
                cruzo_short = (p_old < nivel <= p_new)
                cruzo_long = (p_old > nivel >= p_new)
                
                if (self.bot.direccion == "short" and cruzo_short and not nivel_ocupado) or \
                   (self.bot.direccion == "long" and cruzo_long and not nivel_ocupado):
                    
                    objetivo = self._obtener_proximo_objetivo(nivel)
                    hora_in = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    self.bot.trade_counter += 1
                    trade_id = f"{self.bot.bot_id}_{self.bot.trade_counter}_{int(time.time())}"
                    self.bot.posiciones[nivel] = [precio, objetivo, False, hora_in, trade_id]
                    self.bot.comisiones_pagadas += (self.bot.monedas_por_grid * nivel) * 0.0004
                    
                    if self.bot.master:
                        self.bot.master.guardar_estado()
                    
                    alertas.append(f"⚡ <b>ENTRADA GRID (CRUCE)</b>\n🤖 {self.bot.bot_id}\n📍 Nivel: {nivel}")
        
        # Sincronizar índice de nivel
        idx_detectado = -1
        for i, nivel in enumerate(self.bot.niveles):
            if p_new >= nivel:
                idx_detectado = i
        
        if idx_detectado != self.bot.last_index_crossed:
            self.bot.last_index_crossed = idx_detectado
        
        self.bot.last_price_checked = precio
        return alertas
    
    def gestionar_cierres(self, precio):
        """Gestiona cierres de grid (sin trailing)"""
        alertas = []
        niveles_a_cerrar = []
        
        monedas = float(self.bot.monedas_por_grid) if self.bot.monedas_por_grid else 0.0
        
        for p_ent, datos in self.bot.posiciones.items():
            # ===== CONVERTIR p_ent A FLOAT =====
            p_ent = float(p_ent)
            mejor_p, objetivo, trailing_activo = datos[:3]
            
            if (self.bot.direccion == "short" and precio <= objetivo) or \
               (self.bot.direccion == "long" and precio >= objetivo):
                niveles_a_cerrar.append(p_ent)
        
        for p_ent in niveles_a_cerrar:
            p_ent = float(p_ent)
            datos = self.bot.posiciones[p_ent]
            hora_entrada = datos[3] if len(datos) > 3 else "N/A"
            trade_id_s = datos[4] if len(datos) > 4 else "N/A"
            
            if self.bot.direccion == "short":
                ganancia = (p_ent - precio) * monedas
            else:
                ganancia = (precio - p_ent) * monedas
            
            self.bot.pnl_acumulado += ganancia
            self.bot.comisiones_pagadas += (monedas * precio) * 0.0004
            self.bot.trades_cerrados += 1
            self.bot.registrar_trade_csv(p_ent, precio, ganancia, "grid", self.bot.direccion, hora_entrada, trade_id_s)
            del self.bot.posiciones[p_ent]
            alertas.append(f"💰 <b>TAKE PROFIT</b>\n🤖 {self.bot.bot_id}\n📈 Profit: ${ganancia:.2f}")
            
            if self.bot.master:
                self.bot.master.guardar_estado()
        
        return alertas
    
    def _obtener_proximo_objetivo(self, p_ent):
        """Calcula el siguiente objetivo para grid"""
        if self.bot.direccion == "short":
            inferiores = [n for n in self.bot.niveles if n < p_ent]
            if inferiores:
                return max(inferiores)
            else:
                # FUERA DE RANGO (Hacia abajo)
                if hasattr(self.bot, 'tipo_grid') and self.bot.tipo_grid == "geometrico":
                    razon = self.bot.niveles[1] / self.bot.niveles[0]
                    return round(p_ent / razon, self.bot.decimales)
                else:
                    distancia_grid = abs(self.bot.niveles[1] - self.bot.niveles[0])
                    return round(p_ent - distancia_grid, self.bot.decimales)
        else:
            superiores = [n for n in self.bot.niveles if n > p_ent]
            if superiores:
                return min(superiores)
            else:
                if hasattr(self.bot, 'tipo_grid') and self.bot.tipo_grid == "geometrico":
                    razon = self.bot.niveles[1] / self.bot.niveles[0]
                    return round(p_ent * razon, self.bot.decimales)
                else:
                    distancia_grid = abs(self.bot.niveles[1] - self.bot.niveles[0])
                    return round(p_ent + distancia_grid, self.bot.decimales)
