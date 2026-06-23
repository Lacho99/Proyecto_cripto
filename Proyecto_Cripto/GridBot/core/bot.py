"""
core/bot.py
Clase GridBotSim - Lógica principal del bot
"""
import time
import math
import csv
import os
from collections import deque
from datetime import datetime

class GridBotSim:
    def __init__(self, master, bot_id, symbol_ws, niveles, capital_total=0, 
                 etiqueta="", liq_price=0.0, monedas_per_grid=0.0, objetivo=5,
                 apalancamiento=1, direccion="short", stop_loss=5, estrategia="grid",
                 timeframe="1m", ema_fast=20, ema_slow=50, filtro_distancia=0.01,
                 tp_activacion_aire=0.0, decimales=6, enable_ema200_cross=False,
                 ema_slow2=200, max_posiciones_scalp=3, callback_scalp=0.001,
                 activacion_trailing_en=100, tiempo_maximo_segundos=300,
                 trailing_por_defecto=False, callback=0.002, limite_entrada_por_defecto=True,
                 limite_salida_por_defecto=True, max_posiciones=10, allow_modify=True,
                 notificar_cada_tick=True, comision=0.0004, modo="simulacion",
                 exchange_client=None):
        
        self.master = master
        self.bot_id = bot_id
        self.symbol_ws = symbol_ws
        self.etiqueta = etiqueta
        self.niveles = niveles if niveles else []
        
        self.liq_price = float(liq_price)
        self.monedas_por_grid = float(monedas_per_grid)
        self.capital_total = float(capital_total)
        self.precio_suelo = min(niveles) if niveles else 0
        self.precio_techo = max(niveles) if niveles else 0
        self.objetivo = float(objetivo)
        self.apalancamiento = int(apalancamiento)
        self.direccion = direccion.lower()
        self.stop_loss = float(stop_loss)
        self.fecha_inicio = time.time()
        
        # Estados persistentes
        self.is_liquidated = False
        self.sl_alcanzado = False
        self.umbral_alcanzado = False
        self.estado_rango = "DENTRO"
        self.posiciones = {}
        self.pnl_acumulado = 0.0
        self.comisiones_pagadas = 0.0
        self.funding_acumulado = 0.0
        self.trades_abiertos_count = 0
        self.trades_cerrados = 0
        self.last_index_crossed = -1
        self.tiempo_en_rango = 0.0
        self.last_timestamp = time.time()
        self.last_price = 0.0
        self.last_price_checked = 0.0
        self.tiempo_total_activo = 0.0
        self.tiempo_dentro_rango = 0.0
        self.last_time_check = time.time()
        
        # Parámetros de estrategia
        self.estrategia = estrategia
        self.timeframe = timeframe
        self.filtro_distancia = float(filtro_distancia)
        self.ema_fast_p = int(ema_fast)
        self.ema_slow_p = int(ema_slow)
        self.tp_activacion_aire = float(tp_activacion_aire) if tp_activacion_aire is not None else None
        
        
        # Historial y EMAs
        self.historial_velas = deque(maxlen=600)
        self.ultima_ema_fast = 0.0
        self.ultima_ema_slow = 0.0
        self.ultimo_precio_entrada = 0.0
        self.trade_counter = 0
        self.pausado = False
        self.porcentaje_en_rango = 100
        self.decimales = int(decimales)
        self.enable_ema200_cross = enable_ema200_cross
        self.ema_slow2_p = int(ema_slow2)
        self.ultima_ema_slow2 = 0.0
        self.pico_max = 0
        self.pico_min = 999999
        self.trailing_plus = 0
        self.trailing_minus = 0
        self.peor_pnl_flotante = 0.0
        self.mejor_realizable = 0.0
        self.ultimo_realizable = 0.0
        self.peor_pnl_flotante_global = 999999.0
        self.mejor_realizable_global = -999999.0
        
        # Parámetros de scalping
        self.max_posiciones_scalp = int(max_posiciones_scalp)
        self.callback_scalp = float(callback_scalp)
        self.activacion_trailing_en = float(activacion_trailing_en)
        self.tiempo_maximo_segundos = int(tiempo_maximo_segundos)
        self.tiempo_entrada_posiciones = {}
        self.ultima_vela_cerrada = 0
        
        # Parámetros para bot manual
        self.trailing_por_defecto = trailing_por_defecto
        self.callback = float(callback)
        self.limite_entrada_por_defecto = limite_entrada_por_defecto
        self.limite_salida_por_defecto = limite_salida_por_defecto
        self.max_posiciones = int(max_posiciones)
        self.allow_modify = allow_modify
        self.notificar_cada_tick = notificar_cada_tick
        self.comision = float(comision)
        
        # Estado adicional para manual
        self.ordenes_pendientes = {}
        self.posiciones_historial = {}
        
        # Para el modo real
        self.modo = modo
        self.exchange_client = exchange_client
    
    # ========================================================
    # MÉTODOS DE EMAs
    # ========================================================
    
    def calcular_ema(self, precio_actual):
        """Calcula las EMAs usando la fórmula recursiva"""
        if len(self.historial_velas) < self.ema_slow2_p:
            self.historial_velas.append(precio_actual)
            
            if len(self.historial_velas) >= self.ema_fast_p:
                self.ultima_ema_fast = sum(list(self.historial_velas)[-self.ema_fast_p:]) / self.ema_fast_p
            else:
                self.ultima_ema_fast = precio_actual
                
            if len(self.historial_velas) >= self.ema_slow_p:
                self.ultima_ema_slow = sum(list(self.historial_velas)[-self.ema_slow_p:]) / self.ema_slow_p
            else:
                self.ultima_ema_slow = precio_actual
                
            if len(self.historial_velas) >= self.ema_slow2_p:
                self.ultima_ema_slow2 = sum(list(self.historial_velas)[-self.ema_slow2_p:]) / self.ema_slow2_p
            else:
                self.ultima_ema_slow2 = precio_actual
        else:
            k_fast = 2 / (self.ema_fast_p + 1)
            k_slow = 2 / (self.ema_slow_p + 1)
            k_slow2 = 2 / (self.ema_slow2_p + 1)
            
            self.ultima_ema_fast = (precio_actual - self.ultima_ema_fast) * k_fast + self.ultima_ema_fast
            self.ultima_ema_slow = (precio_actual - self.ultima_ema_slow) * k_slow + self.ultima_ema_slow
            self.ultima_ema_slow2 = (precio_actual - self.ultima_ema_slow2) * k_slow2 + self.ultima_ema_slow2
    
    def gestionar_velas(self, precio, timestamp):
        """Convierte el flujo de precios en velas del timeframe elegido"""
        try:
            minutos = int(''.join(filter(str.isdigit, self.timeframe)))
        except:
            minutos = 1
        
        if 'h' in self.timeframe:
            segundos_tf = minutos * 3600
        elif 'd' in self.timeframe:
            segundos_tf = minutos * 86400
        else:
            segundos_tf = minutos * 60
        
        intervalo_actual = int(timestamp // segundos_tf)
        
        if intervalo_actual > self.ultima_vela_cerrada:
            if self.ultima_vela_cerrada != 0:
                self.historial_velas.append(precio)
                self.calcular_ema(precio)
            self.ultima_vela_cerrada = intervalo_actual
            return True
        return False
    
    # ========================================================
    # PROCESAMIENTO DE PRECIO (Principal)
    # ========================================================
    
    def procesar_precio_v9(self, precio, timestamp):
        """Procesa el precio recibido del WebSocket"""
        self.last_price = precio
        
        if precio > self.pico_max:
            self.pico_max = precio
        if precio < self.pico_min:
            self.pico_min = precio
        if self.is_liquidated or self.sl_alcanzado:
            return []
        
        # ===== CONVERTIR TODAS LAS POSICIONES A FLOAT ANTES DE USARLAS =====
        posiciones_convertidas = {}
        for p_ent, datos in self.posiciones.items():
            p_ent_float = float(p_ent) if p_ent is not None else 0.0
            datos_convertidos = []
            for d in datos:
                if isinstance(d, (int, float)):
                    datos_convertidos.append(float(d))
                elif isinstance(d, str) and d.replace('.', '').isdigit():
                    datos_convertidos.append(float(d))
                else:
                    datos_convertidos.append(d)
            posiciones_convertidas[p_ent_float] = datos_convertidos
        self.posiciones = posiciones_convertidas
        
        # ===== ACTUALIZAR MÉTRICAS DE RIESGO =====
        pnl_flotante_actual = 0.0
        monedas = float(self.monedas_por_grid) if self.monedas_por_grid else 0.0
        
        for p_ent, datos in self.posiciones.items():
            p_ent_num = float(p_ent) if p_ent is not None else 0.0
            if self.direccion == "short":
                pnl_flotante_actual += (p_ent_num - precio) * monedas
            else:
                pnl_flotante_actual += (precio - p_ent_num) * monedas
        
        neto_cerrado = self.pnl_acumulado - self.comisiones_pagadas + self.funding_acumulado
        realizable_actual = neto_cerrado + pnl_flotante_actual
        
        if pnl_flotante_actual < self.peor_pnl_flotante:
            self.peor_pnl_flotante = pnl_flotante_actual
        if realizable_actual > self.mejor_realizable:
            self.mejor_realizable = realizable_actual
        
        self.ultimo_realizable = realizable_actual
        
        if pnl_flotante_actual < self.peor_pnl_flotante_global:
            self.peor_pnl_flotante_global = pnl_flotante_actual
        if realizable_actual > self.mejor_realizable_global:
            self.mejor_realizable_global = realizable_actual
        
        ahora = time.time()
        delta = ahora - self.last_time_check
        if delta < 60:
            self.tiempo_total_activo += delta
            if self.precio_suelo <= precio <= self.precio_techo:
                self.tiempo_dentro_rango += delta
            if self.tiempo_total_activo > 0:
                self.porcentaje_en_rango = (self.tiempo_dentro_rango / self.tiempo_total_activo) * 100
        
        self.last_time_check = ahora
        alertas = []
        
        # ===== BOT MANUAL =====
        if self.estrategia == "manual":
            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(self)
            alertas = strategy.procesar(precio, timestamp)
            return alertas
        
        # ===== ACTUALIZAR VELAS Y EMAs =====
        vela_nueva = self.gestionar_velas(precio, timestamp)
        
        # ===== GESTIÓN DE RANGO =====
        nuevo_estado = "DENTRO"
        if precio < self.precio_suelo:
            nuevo_estado = "POR_DEBAJO"
        elif precio > self.precio_techo:
            nuevo_estado = "POR_ENCIMA"
        
        if nuevo_estado != self.estado_rango:
            self.estado_rango = nuevo_estado
        
        # ===== VERIFICAR EMA200 =====
        ema200_ok = True
        if self.enable_ema200_cross and len(self.historial_velas) >= self.ema_slow2_p:
            if self.direccion == "short":
                ema200_ok = self.ultima_ema_slow2 > precio
            else:
                ema200_ok = self.ultima_ema_slow2 < precio
        
        # ===== PROCESAR ESTRATEGIA =====
        if self.estrategia == "ema" and not self.pausado:
            from strategies.ema import EMAStrategy
            strategy = EMAStrategy(self)
            if vela_nueva and len(self.historial_velas) >= self.ema_slow_p:
                alertas.extend(strategy.procesar(precio, timestamp))
        
        elif self.estrategia in ["grid", "gridT"] and not self.pausado:
            if ema200_ok:
                if self.estrategia == "grid":
                    from strategies.grid import GridStrategy
                    strategy = GridStrategy(self)
                else:
                    from strategies.gridT import GridTStrategy
                    strategy = GridTStrategy(self)
                alertas.extend(strategy.procesar(precio, timestamp))
        
        elif self.estrategia == "ema_scalp" and not self.pausado:
            from strategies.scalp import ScalpStrategy
            strategy = ScalpStrategy(self)
            alertas.extend(strategy.procesar(precio, timestamp))
        
        self.last_timestamp = timestamp
        return alertas
    
    # ========================================================
    # REGISTRO DE TRADES EN CSV
    # ========================================================
    
    def registrar_trade_csv(self, p_ent, p_salida, pnl, tipo, direccion, hora_entrada=None, trade_id=None):
        """Registra un trade en el archivo CSV"""
        archivo = f"trades_{self.bot_id}.csv"
        
        try:
            es_nuevo = not os.path.exists(archivo)
            with open(archivo, mode='a', newline='') as f:
                writer = csv.writer(f)
                if es_nuevo:
                    writer.writerow(['Bot_ID', 'Tipo', 'direccion', 'symbol', 'Precio_Entrada', 'Precio_Salida', 'PnL', 'Hora_Entrada', 'Hora_Cierre', 'Trade_Id'])
                
                if hora_entrada is None or trade_id is None:
                    datos_pos = self.posiciones.get(p_ent)
                    if datos_pos:
                        if len(datos_pos) >= 12:
                            if hora_entrada is None:
                                hora_entrada = datos_pos[10] if len(datos_pos) > 10 else "N/A"
                            if trade_id is None:
                                trade_id = datos_pos[11] if len(datos_pos) > 11 else "N/A"
                        elif len(datos_pos) >= 5:
                            if hora_entrada is None:
                                hora_entrada = datos_pos[3] if len(datos_pos) > 3 else "N/A"
                            if trade_id is None:
                                trade_id = datos_pos[4] if len(datos_pos) > 4 else "N/A"
                
                if hora_entrada is None:
                    hora_entrada = "N/A"
                if trade_id is None:
                    trade_id = "N/A"
                
                hora_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                writer.writerow([
                    self.bot_id,
                    tipo,
                    direccion,
                    self.symbol_ws,
                    p_ent,
                    p_salida,
                    f"{pnl:.4f}",
                    hora_entrada,
                    hora_out,
                    trade_id
                ])
        
        except Exception as e:
            print(f"❌ Error escribiendo en {archivo}: {e}")
            
