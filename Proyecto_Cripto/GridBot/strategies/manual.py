"""
strategies/manual.py
Estrategia Manual (trading manual)
"""
import time
from datetime import datetime
from .base import BaseStrategy

class ManualStrategy(BaseStrategy):
    def __init__(self, bot):
        super().__init__(bot)
        self.ordenes_pendientes = bot.ordenes_pendientes if hasattr(bot, 'ordenes_pendientes') else {}
    
    def procesar(self, precio, timestamp):
        """Procesa el precio para el bot manual"""
        alertas = []
        
        # Verificar órdenes límite pendientes
        alertas.extend(self.verificar_ordenes_pendientes(precio))
        
        # Gestionar cierres automáticos (TP/SL/Trailing)
        alertas.extend(self.gestionar_cierres(precio))
        
        return alertas
    
    def verificar_entrada(self, precio):
        """No hay entradas automáticas en modo manual"""
        return []
    
    def gestionar_cierres(self, precio):
        """Gestiona cierres automáticos de posiciones manuales (TP/SL/Trailing/Liquidación)"""
        alertas = []
        niveles_a_cerrar = []
        
        for p_ent, datos in self.bot.posiciones.items():
            if len(datos) < 13:
                continue
            
            direccion = datos[4]
            tp = datos[6]
            sl = datos[7]
            trailing_activo = datos[8]
            callback = datos[9]
            mejor_precio = datos[1]
            liq_price = datos[16] if len(datos) > 16 else None
            
            # ===== VERIFICAR LIQUIDACIÓN (prioridad máxima) =====
            if liq_price is not None and liq_price > 0:
                if direccion == "long" and precio <= liq_price:
                    niveles_a_cerrar.append((p_ent, "LIQUIDACIÓN"))
                    continue
                elif direccion == "short" and precio >= liq_price:
                    niveles_a_cerrar.append((p_ent, "LIQUIDACIÓN"))
                    continue
            
            # Verificar TP
            if tp is not None:
                if direccion == "long" and precio >= tp:
                    niveles_a_cerrar.append((p_ent, "TP"))
                    continue
                elif direccion == "short" and precio <= tp:
                    niveles_a_cerrar.append((p_ent, "TP"))
                    continue
            
            # Verificar SL
            if sl is not None:
                if direccion == "long" and precio <= sl:
                    niveles_a_cerrar.append((p_ent, "SL"))
                    continue
                elif direccion == "short" and precio >= sl:
                    niveles_a_cerrar.append((p_ent, "SL"))
                    continue
            
            # Verificar Trailing
            if trailing_activo:
                if direccion == "long":
                    if precio > mejor_precio:
                        datos[1] = precio
                    if precio <= round(mejor_precio * (1 - callback), self.bot.decimales):
                        niveles_a_cerrar.append((p_ent, "TRAILING"))
                else:  # short
                    if precio < mejor_precio:
                        datos[1] = precio
                    if precio >= round(mejor_precio * (1 + callback), self.bot.decimales):
                        niveles_a_cerrar.append((p_ent, "TRAILING"))
        
        # Ejecutar cierres
        for p_ent, motivo in niveles_a_cerrar:
            datos = self.bot.posiciones[p_ent]
            cantidad = datos[2]
            direccion = datos[4]
            trade_id = datos[11]
            hora_entrada = datos[10] if len(datos) > 10 else "N/A"
             
            if direccion == "short":
                ganancia = (p_ent - precio) * cantidad
            else:
                ganancia = (precio - p_ent) * cantidad
            
            # Si es liquidación, la ganancia es -100% (pérdida total del margen)
            if motivo == "LIQUIDACIÓN":
                margen_usado = (p_ent * cantidad) / datos[3]
                ganancia = -margen_usado
            
            self.bot.pnl_acumulado += ganancia
            self.bot.comisiones_pagadas += (cantidad * precio) * self.bot.comision
            self.bot.trades_cerrados += 1
            
            self.bot.registrar_trade_csv(p_ent, precio, ganancia, f"MANUAL_{motivo}", direccion, hora_entrada, trade_id)
            del self.bot.posiciones[p_ent]
            
            emoji = "💀" if motivo == "LIQUIDACIÓN" else "💰" if motivo == "TP" else "🛑"
            alertas.append(f"{emoji} <b>CIERRE MANUAL ({motivo})</b>\n🤖 {self.bot.bot_id}\n🆔 ID: {trade_id}\n💰 PnL: ${ganancia:.4f}")
            
            if self.bot.master:
                self.bot.master.guardar_estado()
        
        return alertas
    
    def verificar_ordenes_pendientes(self, precio):
        """Verifica si alguna orden límite pendiente se ha ejecutado"""
        alertas = []
        ordenes_a_ejecutar = []
        
        for trade_id, orden in self.ordenes_pendientes.items():
            precio_limite = orden['precio_limite']
            direccion = orden['direccion']
            
            # Verificar si el precio alcanzó el límite
            if direccion == "long" and precio <= precio_limite:
                ordenes_a_ejecutar.append(trade_id)
            elif direccion == "short" and precio >= precio_limite:
                ordenes_a_ejecutar.append(trade_id)
        
        for trade_id in ordenes_a_ejecutar:
            orden = self.ordenes_pendientes.pop(trade_id)
            alerta = self.ejecutar_entrada_manual_desde_orden(orden, precio)
            alertas.append(alerta)
        
        return alertas
    
    def ejecutar_entrada_manual_desde_orden(self, orden, precio_ejecucion):
        """Ejecuta una orden límite que se ha activado"""
        trade_id = orden['trade_id']
        precio_entrada = precio_ejecucion
        cantidad = orden['cantidad']
        apalancamiento = orden['apalancamiento']
        direccion = orden['direccion']
        tp = orden.get('tp', None)
        sl = orden.get('sl', None)
        trailing = orden.get('trailing', False)
        callback = orden.get('callback', self.bot.callback)
        liq_price = orden.get('liq_price', None)
        
        hora_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.bot.posiciones[precio_entrada] = [
            precio_entrada,
            precio_entrada,
            cantidad,
            apalancamiento,
            direccion,
            "L",
            tp,
            sl,
            trailing,
            callback,
            hora_entrada,
            trade_id,
            "ABIERTO",
            None,
            None,
            0,
            liq_price
        ]
        
        self.bot.comisiones_pagadas += (cantidad * precio_entrada) * self.bot.comision
        self.bot.trade_counter += 1
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        return f"✅ <b>ORDEN LÍMITE EJECUTADA</b>\n🤖 {self.bot.bot_id}\n📈 Precio: {precio_entrada:.{self.bot.decimales}f}\n🆔 ID: {trade_id}"
    
    def ejecutar_entrada_manual(self, precio, cantidad, apalancamiento, direccion, tipo_orden, liq_price, tp=None, sl=None, trailing=False, callback=None):
        """Ejecuta una entrada manual (mercado o límite)"""
        if self.bot.pausado:
            return "⏸️ Bot pausado. No se pueden abrir posiciones."
        
        if len(self.bot.posiciones) >= self.bot.max_posiciones:
            return f"❌ Límite de posiciones alcanzado ({self.bot.max_posiciones})"
        
        # Validar LIQ_PRICE
        if liq_price is None or liq_price <= 0:
            return "❌ Precio de liquidación (LIQ_PRICE) es OBLIGATORIO y debe ser > 0"
        
        # Validar SL vs LIQUIDACIÓN
        if sl is not None:
            if direccion == "long":
                if sl <= liq_price:
                    return f"❌ SL ({sl}) debe ser MAYOR que el precio de liquidación ({liq_price}) para LONG"
                if sl >= precio:
                    return f"❌ SL ({sl}) debe ser MENOR que el precio de entrada ({precio}) para LONG"
            else:  # short
                if sl >= liq_price:
                    return f"❌ SL ({sl}) debe ser MENOR que el precio de liquidación ({liq_price}) para SHORT"
                if sl <= precio:
                    return f"❌ SL ({sl}) debe ser MAYOR que el precio de entrada ({precio}) para SHORT"
        
        # Validar TP
        if tp is not None:
            if direccion == "long" and tp <= precio:
                return "❌ TP debe ser mayor que el precio actual para LONG"
            if direccion == "short" and tp >= precio:
                return "❌ TP debe ser menor que el precio actual para SHORT"
        
        # Si es orden límite, guardar pendiente
        if tipo_orden == "L":
            return self.guardar_orden_pendiente(precio, cantidad, apalancamiento, direccion, 
                                                tp, sl, trailing, callback, liq_price)
        
        # Si es mercado, ejecutar inmediatamente
        return self.ejecutar_entrada_mercado(precio, cantidad, apalancamiento, direccion, 
                                             tp, sl, trailing, callback, liq_price)
    
    def guardar_orden_pendiente(self, precio_limite, cantidad, apalancamiento, direccion, 
                                tp, sl, trailing, callback, liq_price):
        """Guarda una orden límite pendiente con precio de liquidación"""
        self.bot.trade_counter += 1
        trade_id = f"{self.bot.bot_id}_MANUAL_{self.bot.trade_counter}_{int(time.time())}"
        
        self.ordenes_pendientes[trade_id] = {
            'trade_id': trade_id,
            'precio_limite': precio_limite,
            'cantidad': cantidad,
            'apalancamiento': apalancamiento,
            'direccion': direccion,
            'tp': tp,
            'sl': sl,
            'trailing': trailing or self.bot.trailing_por_defecto,
            'callback': callback or self.bot.callback,
            'liq_price': liq_price,
            'hora_creacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'estado': "PENDIENTE"
        }
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        mensaje = (
            f"📝 <b>ORDEN LÍMITE GUARDADA</b>\n"
            f"🤖 {self.bot.bot_id}\n"
            f"📍 Precio: {precio_limite:.{self.bot.decimales}f}\n"
            f"💀 Liq: {liq_price:.{self.bot.decimales}f}\n"
            f"🆔 ID: {trade_id}\n"
        )
        if tp is not None:
            mensaje += f"🎯 TP: {tp:.{self.bot.decimales}f}\n"
        if sl is not None:
            mensaje += f"🛑 SL: {sl:.{self.bot.decimales}f}\n"
        if trailing:
            mensaje += f"🛰️ Trailing: ACTIVADO ({callback or self.bot.callback*100}%)\n"
        mensaje += "⏳ Esperando ejecución..."
        return mensaje
    
    def ejecutar_entrada_mercado(self, precio, cantidad, apalancamiento, direccion, 
                                 tp, sl, trailing, callback, liq_price):
        """Ejecuta una entrada a mercado con precio de liquidación"""
        self.bot.trade_counter += 1
        trade_id = f"{self.bot.bot_id}_MANUAL_{self.bot.trade_counter}_{int(time.time())}"
        hora_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.bot.posiciones[precio] = [
            precio,
            precio,
            cantidad,
            apalancamiento,
            direccion,
            "M",
            tp,
            sl,
            trailing or self.bot.trailing_por_defecto,
            callback or self.bot.callback,
            hora_entrada,
            trade_id,
            "ABIERTO",
            None,
            None,
            0,
            liq_price
        ]
        
        self.bot.comisiones_pagadas += (cantidad * precio) * self.bot.comision
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        mensaje = f"🚀 <b>ENTRADA MANUAL {direccion.upper()}</b>\n🤖 {self.bot.bot_id}\n📈 Precio: {precio:.{self.bot.decimales}f}\n📦 Cantidad: {cantidad}\n🔧 Apalancamiento: {apalancamiento}x\n💀 Liq: {liq_price:.{self.bot.decimales}f}\n🆔 ID: {trade_id}"
        
        if tp:
            mensaje += f"\n🎯 TP: {tp:.{self.bot.decimales}f}"
        if sl:
            mensaje += f"\n🛑 SL: {sl:.{self.bot.decimales}f}"
        if trailing:
            mensaje += f"\n🛰️ Trailing: ACTIVADO ({callback or self.bot.callback*100}%)"
        
        return mensaje
    
    def cerrar_posicion_manual(self, trade_id, precio_salida, tipo_salida):
        """Cierra una posición manualmente"""
        target_p_ent = None
        datos_pos = None
        
        for p_ent, datos in self.bot.posiciones.items():
            if len(datos) >= 12 and datos[11] == trade_id:
                target_p_ent = p_ent
                datos_pos = datos
                break
        
        if not target_p_ent:
            return f"❌ Trade ID {trade_id} no encontrado"
        
        hora_entrada = datos_pos[10] if len(datos_pos) > 10 else "N/A"
        cantidad = datos_pos[2]
        direccion = datos_pos[4]
        
        if direccion == "short":
            ganancia = (target_p_ent - precio_salida) * cantidad
        else:
            ganancia = (precio_salida - target_p_ent) * cantidad
        
        self.bot.pnl_acumulado += ganancia
        self.bot.comisiones_pagadas += (cantidad * precio_salida) * self.bot.comision
        self.bot.trades_cerrados += 1
        
        self.bot.registrar_trade_csv(target_p_ent, precio_salida, ganancia, "MANUAL", direccion, hora_entrada, trade_id)
        del self.bot.posiciones[target_p_ent]
        
        if self.bot.master:
            self.bot.master.guardar_estado()
        
        return f"✅ <b>CIERRE MANUAL</b>\n🤖 {self.bot.bot_id}\n🆔 ID: {trade_id}\n💰 PnL: ${ganancia:.4f}\n📈 Precio salida: {precio_salida:.{self.bot.decimales}f}"
    
    def modificar_posicion_manual(self, trade_id, tipo_modificacion, nuevo_precio):
        """Modifica TP o SL de una posición"""
        for p_ent, datos in self.bot.posiciones.items():
            if len(datos) >= 12 and datos[11] == trade_id:
                if tipo_modificacion.upper() == "TP":
                    datos[6] = nuevo_precio
                    datos[15] += 1
                    if self.bot.master:
                        self.bot.master.guardar_estado()
                    return f"✅ TP modificado a {nuevo_precio:.{self.bot.decimales}f} para {trade_id}"
                elif tipo_modificacion.upper() == "SL":
                    datos[7] = nuevo_precio
                    datos[15] += 1
                    if self.bot.master:
                        self.bot.master.guardar_estado()
                    return f"✅ SL modificado a {nuevo_precio:.{self.bot.decimales}f} para {trade_id}"
                else:
                    return f"❌ Modificación inválida. Usa TP o SL"
        
        return f"❌ Trade ID {trade_id} no encontrado"
    
    def listar_ordenes_pendientes(self):
        """Lista todas las órdenes pendientes"""
        if not self.ordenes_pendientes:
            return "📭 No hay órdenes pendientes"
        
        mensaje = f"📝 <b>ÓRDENES PENDIENTES - {self.bot.bot_id}</b>\n"
        mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        for trade_id, orden in self.ordenes_pendientes.items():
            mensaje += (
                f"🆔 {trade_id}\n"
                f"   📍 {orden['direccion'].upper()} LÍMITE @ {orden['precio_limite']:.{self.bot.decimales}f}\n"
                f"   📦 {orden['cantidad']} | 🔧 {orden['apalancamiento']}x\n"
                f"   ⏳ Creada: {orden['hora_creacion']}\n"
            )
            if orden.get('tp'):
                mensaje += f"   🎯 TP: {orden['tp']:.{self.bot.decimales}f}\n"
            if orden.get('sl'):
                mensaje += f"   🛑 SL: {orden['sl']:.{self.bot.decimales}f}\n"
            if orden.get('liq_price'):
                mensaje += f"   💀 Liq: {orden['liq_price']:.{self.bot.decimales}f}\n"
            mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        return mensaje
    
    def cancelar_orden(self, trade_id):
        """Cancela una orden límite pendiente"""
        if trade_id in self.ordenes_pendientes:
            orden = self.ordenes_pendientes.pop(trade_id)
            if self.bot.master:
                self.bot.master.guardar_estado()
            return f"❌ Orden cancelada: {trade_id}\n📍 Precio: {orden['precio_limite']:.{self.bot.decimales}f}"
        else:
            return f"❌ Orden {trade_id} no encontrada o ya ejecutada"
            
