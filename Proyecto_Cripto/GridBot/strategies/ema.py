"""
strategies/ema.py
Estrategia basada en cruce de EMAs
"""
import time
from datetime import datetime
from .base import BaseStrategy

class EMAStrategy(BaseStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.CALLBACK = 0.002  # 0.2% de rebote para trailing
    
    def procesar(self, precio, timestamp):
        """Procesa el precio para EMA"""
        alertas = []
        
        # Verificar entrada por cruce de EMAs
        alertas.extend(self.verificar_entrada(precio))
        
        # Gestionar cierres
        alertas.extend(self.gestionar_cierres(precio))
        
        return alertas
    
    def verificar_entrada(self, precio):
        """Verifica si hay cruce de EMAs para entrar"""
        if self.bot.pausado:
            return []
        
        alertas = []
        
        # Necesitamos suficientes datos
        if len(self.bot.historial_velas) < self.bot.ema_slow_p:
            return alertas
        
        # Verificar rango de seguridad
        if not self._verificar_rango_seguridad(precio):
            return alertas
        
        # Verificar distancia a otras posiciones
        if not self._verificar_distancia_seguridad(precio):
            return alertas
        
        # Calcular porcentaje ajustado para objetivo
        if self.bot.tp_activacion_aire is not None:
            porcentaje_ajustado = self.bot.tp_activacion_aire / 100
        else:
            porcentaje_ajustado = (self.bot.objetivo / 100) / self.bot.apalancamiento
        
        # SEÑAL SHORT: EMA20 cruza hacia ABAJO la EMA50
        if self.bot.direccion == "short" and self.bot.ultima_ema_fast < self.bot.ultima_ema_slow:
            objetivo = round(precio * (1 - porcentaje_ajustado), self.bot.decimales)
            alertas.append(self._ejecutar_entrada(precio, objetivo, "SHORT"))
        
        # SEÑAL LONG: EMA20 cruza hacia ARRIBA la EMA50
        elif self.bot.direccion == "long" and self.bot.ultima_ema_fast > self.bot.ultima_ema_slow:
            objetivo = round(precio * (1 + porcentaje_ajustado), self.bot.decimales)
            alertas.append(self._ejecutar_entrada(precio, objetivo, "LONG"))
        
        return alertas
    
    def gestionar_cierres(self, precio):
        """Gestiona cierres con trailing para EMA"""
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
            self.bot.registrar_trade_csv(p_ent, precio, ganancia, "ema", self.bot.direccion, hora_entrada, trade_id_s)
            del self.bot.posiciones[p_ent]
            alertas.append(f"💰 <b>TAKE PROFIT (EMA)</b>\n🤖 {self.bot.bot_id}\n📈 Profit: ${ganancia:.2f}")
            
            if self.bot.master:
                self.bot.master.guardar_estado()
        
        return alertas
    
    def _ejecutar_entrada(self, precio, objetivo, tipo):
        """Ejecuta la entrada EMA"""
        self.bot.trade_counter += 1
        trade_id = f"{self.bot.bot_id}_{self.bot.trade_counter}_{int(time.time())}"
        hora_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.bot.posiciones[precio] = [precio, objetivo, False, hora_entrada, trade_id]
        self.bot.ultimo_precio_entrada = precio
        self.bot.comisiones_pagadas += (self.bot.monedas_por_grid * precio) * 0.0004
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        return f"🚀 <b>ENTRADA EMA {tipo}</b>\n🤖 {self.bot.bot_id}\n📈 Precio: {precio}\n🎯 Target: {objetivo:.6f}"
    
    def _verificar_rango_seguridad(self, precio):
        """Verifica que el precio esté dentro del rango"""
        if not self.bot.niveles:
            return True
        p_min = min(self.bot.niveles)
        p_max = max(self.bot.niveles)
        return p_min <= precio <= p_max
    
    def _verificar_distancia_seguridad(self, precio):
        """Verifica distancia a otras posiciones"""
        if not self.bot.posiciones:
            return True
        for p_ent in self.bot.posiciones.keys():
            distancia_real = abs(precio - p_ent) / p_ent
            if distancia_real < self.bot.filtro_distancia:
                return False
        return True
