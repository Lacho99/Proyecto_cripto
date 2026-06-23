"""
strategies/scalp.py
Estrategia de Scalping con EMAs
"""
import time
from datetime import datetime
from .base import BaseStrategy

class ScalpStrategy(BaseStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.tiempo_entrada_posiciones = {}
    
    def procesar(self, precio, timestamp):
        """Procesa el precio para Scalp"""
        alertas = []
        
        # Actualizar EMAs en cada tick
        self.bot.historial_velas.append(precio)
        self.bot.calcular_ema(precio)
        
        # Verificar señales de entrada
        if len(self.bot.posiciones) < self.bot.max_posiciones_scalp:
            alertas.extend(self.verificar_entrada(precio))
        
        # Gestionar cierres
        alertas.extend(self.gestionar_cierres(precio, timestamp))
        
        return alertas
    
    def verificar_entrada(self, precio):
        """Detecta cruces de EMAs para scalping"""
        alertas = []
        
        # Necesitamos suficientes datos
        if len(self.bot.historial_velas) < self.bot.ema_slow2_p:
            return alertas
        
        # Verificar rango de seguridad
        if not self._verificar_rango_seguridad(precio):
            return alertas
        
        # Verificar distancia a otras posiciones
        if not self._verificar_distancia_seguridad(precio):
            return alertas
        
        # DETECCIÓN LONG (EMA20 > EMA50 > EMA200)
        if self.bot.direccion in ["long", "ambas"]:
            if (self.bot.ultima_ema_fast > self.bot.ultima_ema_slow and 
                self.bot.ultima_ema_slow > self.bot.ultima_ema_slow2):
                alertas.append(self._ejecutar_entrada_scalp(precio, "long"))
        
        # DETECCIÓN SHORT (EMA20 < EMA50 < EMA200)
        if self.bot.direccion in ["short", "ambas"]:
            if (self.bot.ultima_ema_fast < self.bot.ultima_ema_slow and 
                self.bot.ultima_ema_slow < self.bot.ultima_ema_slow2):
                alertas.append(self._ejecutar_entrada_scalp(precio, "short"))
        
        return alertas
    
    def gestionar_cierres(self, precio, timestamp):
        """Gestiona cierres con trailing y timeout para scalping"""
        alertas = []
        niveles_a_cerrar = []
        ahora = time.time()

        monedas = float(self.bot.monedas_por_grid) if self.bot.monedas_por_grid else 0  
        
        # Limpiar timestamps
        temp_dict = self.tiempo_entrada_posiciones
        self.tiempo_entrada_posiciones = {float(str(k)): v for k, v in temp_dict.items()}
        
        for p_ent, datos in self.bot.posiciones.items():
            p_ent = float(p_ent)
            mejor_p, objetivo, trailing_activo = datos[:3]
            tiempo_posicion = ahora - self.tiempo_entrada_posiciones.get(p_ent, ahora)
            sl_price = datos[5] if len(datos) > 5 else None
            direccion_scalp = datos[6] if len(datos) > 6 else "short"
            
            # ===== STOP LOSS =====
            if sl_price is not None:
                if direccion_scalp == "short":
                    if precio >= sl_price:
                        niveles_a_cerrar.append((p_ent, "SL"))
                        continue
                else:
                    if precio <= sl_price:
                        niveles_a_cerrar.append((p_ent, "SL"))
                        continue
            
            # TIMEOUT: Cerrar si pasa demasiado tiempo (opcional)
            # if tiempo_posicion > self.bot.tiempo_maximo_segundos:
            #     niveles_a_cerrar.append((p_ent, "TIMEOUT"))
            #     continue
            
            # ACTIVAR TRAILING al alcanzar % del objetivo
            if not trailing_activo:
                if direccion_scalp == "short":
                    progreso = (p_ent - precio) / (p_ent - objetivo) * 100 if p_ent != objetivo else 0
                else:
                    progreso = (precio - p_ent) / (objetivo - p_ent) * 100 if objetivo != p_ent else 0
                
                if progreso >= self.bot.activacion_trailing_en:
                    self.bot.posiciones[p_ent][2] = True
                    self.bot.posiciones[p_ent][0] = precio
                    alertas.append(f"🛰️ <b>Trailing Armado</b> | {self.bot.bot_id} ({progreso:.0f}%)")
                continue
            
            # TRAILING ACTIVADO
            if direccion_scalp == "short":
                if precio < mejor_p:
                    self.bot.posiciones[p_ent][0] = precio
                if precio >= round(mejor_p * (1 + self.bot.callback_scalp), self.bot.decimales):
                    niveles_a_cerrar.append((p_ent, "TRAILING"))
            else:
                if precio > mejor_p:
                    self.bot.posiciones[p_ent][0] = precio
                if precio <= round(mejor_p * (1 - self.bot.callback_scalp), self.bot.decimales):
                    niveles_a_cerrar.append((p_ent, "TRAILING"))
        
        # Ejecutar cierres
        for p_ent, motivo in niveles_a_cerrar:
            datos = self.bot.posiciones[p_ent]
            hora_entrada = datos[3] if len(datos) > 3 else "N/A"
            trade_id_s = datos[4] if len(datos) > 4 else "N/A"
            direccion_scalp = datos[6] if len(datos) > 6 else "short"
            
            if motivo == "SL":
                ganancia = (p_ent - precio if direccion_scalp == "short" else precio - p_ent) * monedas
            else:
                ganancia = (p_ent - precio if direccion_scalp == "short" else precio - p_ent) * monedas
            
            self.bot.pnl_acumulado += ganancia
            self.bot.comisiones_pagadas += (self.bot.monedas_por_grid * precio) * 0.0004
            self.bot.trades_cerrados += 1
            self.bot.registrar_trade_csv(p_ent, precio, ganancia, "SCALP", direccion_scalp, hora_entrada, trade_id_s)
            
            del self.bot.posiciones[p_ent]
            if p_ent in self.tiempo_entrada_posiciones:
                del self.tiempo_entrada_posiciones[p_ent]
            
            if self.bot.master:
                self.bot.master.guardar_estado()
            
            emoji = "🛑" if motivo == "SL" else "💰"
            alertas.append(f"{emoji} <b>SCALP CLOSE ({motivo})</b>\n🤖 {self.bot.bot_id}\n📈 Profit: ${ganancia:.4f}")
        
        return alertas
    
    def _ejecutar_entrada_scalp(self, precio, tipo):
        """Ejecuta entrada con parámetros de scalping"""
        if self.bot.pausado:
            return ""
        
        # Calcular TP
        porcentaje_tp = self.bot.objetivo / 100
        
        if tipo == "short":
            objetivo = round(precio * (1 - porcentaje_tp), self.bot.decimales)
        else:
            objetivo = round(precio * (1 + porcentaje_tp), self.bot.decimales)
        
        # Calcular SL
        porcentaje_sl = self.bot.stop_loss / 100
        if tipo == "short":
            sl_price = round(precio * (1 + porcentaje_sl), self.bot.decimales)
        else:
            sl_price = round(precio * (1 - porcentaje_sl), self.bot.decimales)
        
        self.bot.trade_counter += 1
        trade_id = f"{self.bot.bot_id}_SCALP_{self.bot.trade_counter}_{int(time.time())}"
        hora_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Guardar posición
        self.bot.posiciones[precio] = [precio, objetivo, False, hora_entrada, trade_id, sl_price, tipo]
        self.tiempo_entrada_posiciones[precio] = time.time()
        self.bot.comisiones_pagadas += (self.bot.monedas_por_grid * precio) * 0.0004
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        return f"⚡ <b>SCALP ENTRY {tipo}</b>\n🤖 {self.bot.bot_id}\n📈 Precio: {precio}\n🎯 TP: {objetivo:.{self.bot.decimales}f} ({self.bot.objetivo}%)\n🛑 SL: {sl_price:.{self.bot.decimales}f} ({self.bot.stop_loss}%)"
    
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
