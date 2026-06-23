"""
tg_handlers/handlers.py
TODOS los comandos de Telegram - Versión Completa
"""
import asyncio
import time
import math
import os
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

class TelegramHandlers:
    def __init__(self, master):
        self.master = master

    # ============================================================
    # 1. COMANDOS GENERALES
    # ============================================================

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import math
            encabezado = f"🌐 <b>MONITOR ESTRATÉGICO {self.master.config_manager.version}</b>\n"
            uptime_seg = time.time() - self.master.start_time
            dias = max(uptime_seg / 86400, 0.01)
            encabezado += f"⏱️ Uptime: <code>{dias:.2f} días</code>\n"
            inicio_f = datetime.fromtimestamp(self.master.start_time).strftime('%d/%m %H:%M')
            encabezado += f"📅 Inicio: <code>{inicio_f}</code>\n"
            encabezado += "----------------------------------\n"
            await update.message.reply_html(encabezado)

            total_realizable_global = 0

            for bot in self.master.bots:
                p_act = self.master.last_prices.get(bot.symbol_ws, 0)
                ahora = time.time()
                edad_bot_seg = max(ahora - bot.fecha_inicio, 60)
                dias_bot = edad_bot_seg / 86400
                trades_per_day = bot.trades_cerrados / math.ceil(dias_bot) if dias_bot > 0 else 0

                reporte = f"💰 <b>{bot.symbol_ws.upper()}</b> | <code>{p_act:.{bot.decimales}f}</code>\n"

                if bot.estrategia == "manual":
                    neto_cerrado = bot.pnl_acumulado - bot.comisiones_pagadas + bot.funding_acumulado
                    float_pnl = 0.0
                    liq_info = ""
                    liq_contador = 0

                    for p_ent, datos in bot.posiciones.items():
                        p_ent_num = float(p_ent)
                        if len(datos) >= 5:
                            direccion_pos = datos[4] if len(datos) > 4 else "long"
                            cantidad = float(datos[2]) if len(datos) > 2 else 0
                            if direccion_pos == "short":
                                float_pnl += (p_ent_num - p_act) * cantidad
                            else:
                                float_pnl += (p_act - p_ent_num) * cantidad
                            if len(datos) >= 17:
                                liq_price = datos[16]
                                if liq_price and liq_price > 0:
                                    liq_contador += 1
                                    if direccion_pos == "long":
                                        dist_liq = ((p_ent_num - liq_price) / p_ent_num) * 100
                                        flecha = "📉"
                                    else:
                                        dist_liq = ((liq_price - p_ent_num) / p_ent_num) * 100
                                        flecha = "📈"
                                    if liq_contador <= 1:
                                        liq_info += f"  ├ {flecha} Liq: ${liq_price:.2f} (a {dist_liq:.1f}%)\n"

                    realizable = neto_cerrado + float_pnl
                    total_realizable_global += realizable
                    pos_abiertas = len(bot.posiciones)
                    ordenes_pendientes = len(bot.ordenes_pendientes)
                    estado = "🟢" if pos_abiertas > 0 else "⚪"

                    reporte += (
                        f"  {estado} <b>🤖 {bot.bot_id}</b> (MANUAL)\n"
                        f"  ├ 📅 Inicio: <code>{datetime.fromtimestamp(bot.fecha_inicio).strftime('%d/%m %H:%M')}</code>\n"
                        f"  ├ 🛠️ Modo: MANUAL\n"
                        f"  ├ 🎮 Estado: {'⏸️ PAUSADO' if bot.pausado else '▶️ ACTIVO'}\n"
                        f"  ├ 📦 Posiciones: <code>{pos_abiertas}</code>\n"
                        f"  ├ 📝 Órdenes Pendientes: <code>{ordenes_pendientes}</code>\n"
                        f"  ├ 💰 Neto: <code>${neto_cerrado:+.2f}</code> | 📉 Float: <code>{float_pnl:+.2f}</code>\n"
                        f"  ├ 💵 <b>REALIZABLE: ${realizable:.2f}</b>\n"
                    )
                    if liq_info:
                        reporte += liq_info
                    reporte += (
                        f"  ├ 🔄 Trades: <code>{bot.trades_cerrados}</code> | ⚡ {trades_per_day:.2f}/d\n"
                        f"  └ ⚓ Máx Posiciones: <code>{bot.max_posiciones}</code>\n"
                    )
                    await update.message.reply_html(reporte)
                    continue

                # BOT GRID
                neto_cerrado = bot.pnl_acumulado - bot.comisiones_pagadas + bot.funding_acumulado
                float_pnl = 0.0
                monedas_por_grid = float(bot.monedas_por_grid) if bot.monedas_por_grid else 0
                for p_ent, datos in bot.posiciones.items():
                    p_ent_num = float(p_ent)
                    if bot.direccion == "short":
                        float_pnl += (p_ent_num - p_act) * monedas_por_grid
                    else:
                        float_pnl += (p_act - p_ent_num) * monedas_por_grid

                realizable = neto_cerrado + float_pnl
                total_realizable_global += realizable

                capital_real = bot.capital_total / bot.apalancamiento if bot.apalancamiento > 0 else 0
                rentabilidad = ((realizable - capital_real) / capital_real * 100) if capital_real != 0 else 0.0
                objetivo_monto = (bot.capital_total / bot.apalancamiento) * (bot.objetivo / 100) if bot.apalancamiento > 0 else 0
                sl_monto = (bot.capital_total / bot.apalancamiento) * (bot.stop_loss / 100) if bot.apalancamiento > 0 else 0

                estado = "✅" if bot.estado_rango == "DENTRO" else ("⚠️📉" if bot.estado_rango == "POR_DEBAJO" else "⚠️📈")
                if bot.is_liquidated: estado = "💀"
                if bot.sl_alcanzado: estado = "🛑"

                dist_liq = abs(bot.liq_price - p_act) / p_act * 100 if p_act > 0 else 0
                pct_rango_total = ((bot.precio_techo / bot.precio_suelo) - 1) * 100 if bot.precio_suelo > 0 else 0
                pct_desde_suelo = ((p_act / bot.precio_suelo) - 1) * 100 if bot.precio_suelo > 0 else 0
                pct_rango_libre = pct_rango_total - pct_desde_suelo if bot.precio_suelo > 0 else 0
                progreso_total = ((p_act - bot.precio_suelo) / (bot.precio_techo - bot.precio_suelo)) * 100 if bot.precio_techo > bot.precio_suelo else 0

                if bot.direccion == "long":
                    distancia_liq = ((p_act - bot.liq_price) / p_act) * 100 if p_act > 0 else 0
                    distancia_visual = f"📉 A {distancia_liq:.2f}% de Liq (Abajo)"
                else:
                    distancia_liq = ((bot.liq_price - p_act) / p_act) * 100 if p_act > 0 else 0
                    distancia_visual = f"📈 A {distancia_liq:.2f}% de Liq (Arriba)"

                estado_pausa = "⏸️ PAUSADO" if bot.pausado else "▶️ ACTIVO"

                if bot.precio_suelo > 0:
                    if bot.direccion == "short":
                        pico_porcentaje = ((bot.pico_max / bot.precio_suelo) - 1) * 100
                    else:
                        pico_porcentaje = ((bot.pico_min / bot.precio_suelo) - 1) * 100
                    pico_precision = bot.decimales
                else:
                    pico_porcentaje = 0
                    pico_precision = 0

                reporte += (
                    f"  {estado} <b>{bot.bot_id}</b> ({'🟢' if bot.direccion == 'long' else '🔴'} {bot.direccion.upper()})\n"
                    f"  ├ 🤖 <code>{bot.etiqueta}</code> | Rango: {round(bot.porcentaje_en_rango, 1)}%\n"
                    f"  ├ 📅 Inicio: <code>{datetime.fromtimestamp(bot.fecha_inicio).strftime('%d/%m %H:%M')}</code>\n"
                    f"  ├ 🛠️ Modo: {bot.estrategia.upper()} ({bot.timeframe})\n"
                    f"  ├ 📏 Filtro: {bot.filtro_distancia * 100}%\n"
                    f"  ├ 🎮 Estado: <code>{estado_pausa}</code>\n"
                    f"  ├ 🔒 EMA200: <code>{'🟠 ACTIVO' if bot.enable_ema200_cross else '⚪ INACTIVO'}</code>\n"
                )
                if bot.enable_ema200_cross and len(bot.historial_velas) >= bot.ema_slow2_p:
                    ema200_ok = (bot.ultima_ema_slow2 > p_act) if bot.direccion == "short" else (bot.ultima_ema_slow2 < p_act)
                    estado_ema = "🟢 OK" if ema200_ok else "🔴 BLOQUEADO"
                    reporte += f"  ├ 📊 EMA200 Estado: <code>{estado_ema}</code> | Valor: <code>{bot.ultima_ema_slow2:.6f}</code>\n"

                reporte += (
                    f"  ├ 💰 Neto: <code>${neto_cerrado:+.2f}</code> | 📉 Float: <code>{float_pnl:+.2f}</code>\n"
                    f"  ├ 💵 <b>REALIZABLE: ${realizable:.2f}</b> | Rent: {rentabilidad:+.2f}%\n"
                    f"  ├ 🎯 Obj: <code>{bot.objetivo}% ({objetivo_monto:.2f})</code> | 🛑 SL: <code>-{bot.stop_loss}% (-{sl_monto:.2f})</code>\n"
                    f"  ├ 📏 Rango <code>{bot.precio_suelo}</code> | <code>{bot.precio_techo}</code>\n"
                    f"  ├ 📊 Total Rango: <code>{pct_rango_total:.2f}%</code>\n"
                )
                if bot.direccion == "short":
                    reporte += f"  ├ 📈 Pico: {bot.pico_max:.{bot.decimales}f} | {pico_porcentaje:.{pico_precision}f}%\n"
                else:
                    reporte += f"  ├ 📈 Pico: {bot.pico_min:.{bot.decimales}f} | {pico_porcentaje:.{pico_precision}f}%\n"
                reporte += (
                    f"  ├ ✅ Ya a subido:   <code>{pct_desde_suelo:.2f}%</code>\n"
                    f"  ├ 🟢 Rango Libre: <code>{pct_rango_libre:.2f}%</code>\n"
                    f"  ├ 🏁 Avance: <code>{progreso_total:.2f}%</code>\n"
                    f"  ├ <b>{distancia_visual}</b>\n"
                    f"  ├ ⚓ Abiertos: <code>{len(bot.posiciones)}</code>\n"
                    f"  ├ ⛽ Funding: <code>${bot.funding_acumulado:+.4f}</code>\n"
                    f"  ├ 🔄 Trades: <code>{bot.trades_cerrados}</code> | ⚡ {trades_per_day:.2f}/d)\n"
                    f"  ├ 🎯 Trailing Stats: +{bot.trailing_plus} / -{bot.trailing_minus}\n"
                    f"  ├ 🔴 Peor pnl: {bot.peor_pnl_flotante_global:.2f}\n"
                    f"  ├ 🟢 Mejor realizable: {bot.mejor_realizable_global:.2f}\n"
                    f"  └ 💀 Liq: <code>{bot.liq_price}</code> (a {dist_liq:.1f}%)\n"
                )
                await update.message.reply_html(reporte)

            reporte_final = "----------------------------------\n"
            reporte_final += f"📈 <b>BALANCE TOTAL: ${total_realizable_global:.2f}</b>"
            await update.message.reply_html(reporte_final)

        except Exception as e:
            import traceback
            await update.message.reply_text(f"❌ Error en /status: {str(e)[:300]}\n{traceback.format_exc()[:500]}")

    async def inspect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Indica el ID del bot: /inspect NOMBRE_BOT")
                return
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado.")
                return
            p_act = self.master.last_prices.get(bot.symbol_ws, 0)
            res = (
                f"🔍 <b>INSPECCIÓN: {bot.bot_id}</b>\n"
                f"📈 Precio Actual: <code>{p_act:.{bot.decimales}f}</code>\n"
                f"🛠️ Estrategia: {bot.estrategia.upper()}\n"
                f"{'----------------------------------'}\n"
            )
            res += "⚓ <b>Detalle de Posiciones:</b>\n"
            total_pnl_f = 0
            if not bot.posiciones:
                res += "   <i>Sin posiciones abiertas.</i>\n"
            else:
                for p_ent, datos in bot.posiciones.items():
                    p_ent_num = float(p_ent)
                    if bot.estrategia == "manual" and len(datos) >= 17:
                        cantidad = float(datos[2])
                        direccion = datos[4]
                        tp = datos[6]
                        sl = datos[7]
                        trailing_activo = datos[8]
                        callback = datos[9]
                        fecha_open = datos[10]
                        t_id = datos[11]
                        liq_price = datos[16]
                        if direccion == "short":
                            ganancia = (p_ent_num - p_act) * cantidad
                        else:
                            ganancia = (p_act - p_ent_num) * cantidad
                        total_pnl_f += ganancia
                        if direccion == "long":
                            dist_liq = ((p_ent_num - liq_price) / p_ent_num) * 100 if p_ent_num > 0 else 0
                            flecha = "📉"
                        else:
                            dist_liq = ((liq_price - p_ent_num) / p_ent_num) * 100 if p_ent_num > 0 else 0
                            flecha = "📈"
                        res += (
                            f"   • Ent: <code>{p_ent_num:.{bot.decimales}f}</code> | 📅 {fecha_open}\n"
                            f"     🆔 <b>ID:</b> <code>{t_id}</code>\n"
                            f"     📐 Dirección: <b>{direccion.upper()}</b>\n"
                            f"     📦 Cantidad: {cantidad:.4f} | 🔧 {datos[3]}x\n"
                            f"     💀 Liq: <code>{liq_price:.{bot.decimales}f}</code> {flecha} a {dist_liq:.1f}%\n"
                            f"     🎯 TP: {tp if tp else 'N/A'}\n"
                            f"     🛑 SL: {sl if sl else 'N/A'}\n"
                            f"     🛰️ Trailing: {'✅ ACTIVADO' if trailing_activo else '❌ DESACTIVADO'} (callback {callback*100}%)\n"
                            f"     ❌ Cerrar: <code>/exit {bot.bot_id} {t_id} M 0</code>\n"
                            f"\n"
                        )
                        continue
                    # Grid
                    objetivo = datos[1]
                    trailing_activo = datos[2]
                    fecha_open = datos[3] if len(datos) >= 4 else "N/A"
                    t_id = datos[4] if len(datos) >= 5 else "N/A"
                    monedas = float(bot.monedas_por_grid) if bot.monedas_por_grid else 0
                    if bot.direccion == "short":
                        ganancia = (p_ent_num - p_act) * monedas
                    else:
                        ganancia = (p_act - p_ent_num) * monedas
                    total_pnl_f += ganancia
                    dist_tp = (objetivo - p_act) / p_act * 100 if p_act > 0 else 0
                    estado_t = "🛰️ ARMADO" if trailing_activo else f"⏳ a {dist_tp:.2f}%"
                    res += f"   • Ent: <code>{p_ent_num:.6f}</code> | 📅 {fecha_open}\n"
                    res += f"     🆔 <b>ID:</b> <code>{t_id}</code>\n"
                    res += f"     TP: {estado_t} | Obj: {objetivo:.6f}\n"
            res += f"\n⚓ Posiciones: {len(bot.posiciones)}\n"
            res += f"💰 PnL Flotante: <b>${total_pnl_f:.4f}</b>"
            await update.message.reply_html(res)
        except Exception as e:
            import traceback
            await update.message.reply_text(f"❌ Error en /inspect: {str(e)[:300]}\n{traceback.format_exc()[:500]}")

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/history BOT_ID - Últimos trades"""
        try:
            if not context.args:
                await update.message.reply_text("❌ Indica el bot: /history BOT_ID")
                return
            
            bot_id = context.args[0]
            
            # ===== BUSCAR EN EL DIRECTORIO PADRE =====
            # El archivo CSV se guarda en Proyecto_Cripto/, no en GridBot/
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            archivo = os.path.join(base_dir, f"trades_{bot_id}.csv")
            
            # Verificar también en el directorio actual por si acaso
            if not os.path.exists(archivo):
                archivo = os.path.join(os.getcwd(), f"trades_{bot_id}.csv")
            
            if not os.path.exists(archivo):
                await update.message.reply_text(f"❓ No hay historial para {bot_id}\nArchivo buscado: {archivo}")
                return
            
            with open(archivo, 'r') as f:
                lineas = f.readlines()
                
                if len(lineas) < 2:
                    await update.message.reply_text(f"📭 Historial vacío para {bot_id}")
                    return
                
                ultimos_10 = lineas[1:][-10:]
                ultimos_10.reverse()
            
            if not ultimos_10:
                await update.message.reply_text(f"📭 No hay trades registrados para {bot_id}")
                return
            
            reporte = f"📜 <b>Últimos {len(ultimos_10)} Trades: {bot_id}</b>\n"
            reporte += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for linea in ultimos_10:
                if not linea.strip():
                    continue
                    
                d = linea.strip().split(',')
                
                if len(d) < 8:
                    continue
                
                tipo = d[1] if len(d) > 1 else "N/A"
                direccion = d[2] if len(d) > 2 else "N/A"
                p_ent = d[4] if len(d) > 4 else "N/A"
                p_sal = d[5] if len(d) > 5 else "N/A"
                pnl = d[6] if len(d) > 6 else "0.0000"
                hora_in = d[7] if len(d) > 7 else "N/A"
                hora_out = d[8] if len(d) > 8 else "N/A"
                trade_id = d[9] if len(d) > 9 else "N/A"
                
                reporte += (
                    f"💰 <b>PnL: {pnl} USDT</b> ({direccion})\n"
                    f"🛫 <i>In:</i>  {hora_in} | {p_ent}\n"
                    f"🛬 <i>Out:</i> {hora_out} | {p_sal}\n"
                    f"🆔 ID: <code>{trade_id}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                )
            
            await update.message.reply_html(reporte)
            
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error en /history: {str(e)[:300]}\n\nDetalle:\n{traceback.format_exc()[:500]}"
            )

    async def price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if context.args:
                moneda = context.args[0]
                p_act = self.master.last_prices.get(moneda.lower().replace("/", ""), 0)
                if p_act > 0:
                    await update.message.reply_text(f"💰 {moneda}: ${p_act:.4f}")
                else:
                    await update.message.reply_text(f"❌ No se pudo obtener el precio de {moneda}")
            else:
                mensaje = "💰 <b>PRECIOS ACTUALES</b>\n"
                for bot in self.master.bots:
                    p_act = self.master.last_prices.get(bot.symbol_ws, 0)
                    if p_act > 0:
                        mensaje += f"• {bot.symbol_ws.upper()}: <code>{p_act:.{bot.decimales}f}</code>\n"
                await update.message.reply_html(mensaje)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /price: {str(e)[:200]}")

    # ============================================================
    # 2. COMANDOS MANUALES
    # ============================================================

    async def entry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 7:
                await update.message.reply_text(
                    "⚠️ Uso: /entry BOT_ID LONG|SHORT L|M PRECIO CANTIDAD APALANCAMIENTO LIQ_PRICE [TP] [SL] [TRAILING]\n"
                    "Ej: /entry BNB_Manual LONG M 0 0.5 5 464.32 590 550 true"
                )
                return
            bot_id = context.args[0]
            direccion = context.args[1].upper()
            tipo_orden = context.args[2].upper()
            precio = float(context.args[3]) if context.args[3] != "0" else self.master.last_prices.get(bot_id.split('_')[0].lower() + "usdt", 0)
            cantidad = float(context.args[4])
            apalancamiento = int(context.args[5])
            liq_price = float(context.args[6])
            tp = float(context.args[7]) if len(context.args) > 7 else None
            sl = float(context.args[8]) if len(context.args) > 8 else None
            trailing = context.args[9].lower() == "true" if len(context.args) > 9 else False

            if direccion not in ["LONG", "SHORT"]:
                await update.message.reply_text("❌ Dirección inválida. Usa LONG o SHORT")
                return
            if tipo_orden not in ["L", "M"]:
                await update.message.reply_text("❌ Tipo de orden inválido. Usa L (límite) o M (mercado)")
                return
            if apalancamiento < 1:
                await update.message.reply_text("❌ Apalancamiento mínimo 1x")
                return

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            if tipo_orden == "M":
                precio = self.master.last_prices.get(bot.symbol_ws, 0)
                if precio == 0:
                    await update.message.reply_text("❌ No se pudo obtener el precio actual")
                    return

            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(bot)
            resultado = strategy.ejecutar_entrada_manual(
                precio, cantidad, apalancamiento, direccion.lower(),
                tipo_orden, liq_price, tp, sl, trailing
            )
            await update.message.reply_html(resultado)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /entry: {str(e)[:200]}")

    async def exit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 4:
                await update.message.reply_text(
                    "⚠️ Uso: /exit BOT_ID TRADE_ID L|M PRECIO\n"
                    "Ej: /exit BNB_Manual BNB_Manual_MANUAL_1_1234567890 M 0"
                )
                return
            bot_id = context.args[0]
            trade_id = context.args[1]
            tipo_orden = context.args[2].upper()
            precio = float(context.args[3]) if context.args[3] != "0" else self.master.last_prices.get(bot_id.split('_')[0].lower() + "usdt", 0)

            if tipo_orden not in ["L", "M"]:
                await update.message.reply_text("❌ Tipo de orden inválido. Usa L (límite) o M (mercado)")
                return

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            if tipo_orden == "M":
                precio = self.master.last_prices.get(bot.symbol_ws, 0)
                if precio == 0:
                    await update.message.reply_text("❌ No se pudo obtener el precio actual")
                    return

            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(bot)
            resultado = strategy.cerrar_posicion_manual(trade_id, precio, tipo_orden)
            await update.message.reply_html(resultado)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /exit: {str(e)[:200]}")

    async def exit_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 3:
                await update.message.reply_text("⚠️ Uso: /exit_all BOT_ID L|M PRECIO\nEj: /exit_all BNB_Manual M 0")
                return
            bot_id = context.args[0]
            tipo_orden = context.args[1].upper()
            precio = float(context.args[2]) if context.args[2] != "0" else self.master.last_prices.get(bot_id.split('_')[0].lower() + "usdt", 0)

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            if tipo_orden == "M":
                precio = self.master.last_prices.get(bot.symbol_ws, 0)
                if precio == 0:
                    await update.message.reply_text("❌ No se pudo obtener el precio actual")
                    return
            if not bot.posiciones:
                await update.message.reply_text(f"📭 El bot {bot_id} no tiene posiciones abiertas.")
                return

            trades_cerrados = 0
            pnl_total = 0
            for p_ent, datos in list(bot.posiciones.items()):
                if len(datos) >= 12:
                    trade_id = datos[11]
                    cantidad = float(datos[2])
                    direccion = datos[4]
                    ganancia = (p_ent - precio) * cantidad if direccion == "short" else (precio - p_ent) * cantidad
                    pnl_total += ganancia
                    trades_cerrados += 1
                    bot.pnl_acumulado += ganancia
                    bot.comisiones_pagadas += (cantidad * precio) * bot.comision
                    bot.trades_cerrados += 1
                    bot.registrar_trade_csv(p_ent, precio, ganancia, "MANUAL_EXIT_ALL", direccion)
                    del bot.posiciones[p_ent]

            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_html(
                f"⚠️ <b>CIERRE TOTAL</b>\n🤖 {bot_id}\n📦 Cerradas: {trades_cerrados}\n💰 PnL: ${pnl_total:.4f}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /exit_all: {str(e)[:200]}")

    async def modify(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 4:
                await update.message.reply_text("⚠️ Uso: /modify BOT_ID TRADE_ID TP|SL PRECIO\nEj: /modify BNB_Manual MANUAL_1 TP 590")
                return
            bot_id = context.args[0]
            trade_id = context.args[1]
            tipo_mod = context.args[2].upper()
            nuevo_precio = float(context.args[3])

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(bot)
            resultado = strategy.modificar_posicion_manual(trade_id, tipo_mod, nuevo_precio)
            await update.message.reply_html(resultado)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /modify: {str(e)[:200]}")

    async def trailing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 3:
                await update.message.reply_text("⚠️ Uso: /trailing BOT_ID TRADE_ID ON|OFF [CALLBACK]\nEj: /trailing BNB_Manual MANUAL_1 ON 0.002")
                return
            bot_id = context.args[0]
            trade_id = context.args[1]
            activar = context.args[2].upper() == "ON"
            callback = float(context.args[3]) if len(context.args) > 3 else 0.002

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            encontrado = False
            for p_ent, datos in bot.posiciones.items():
                if len(datos) >= 12 and datos[11] == trade_id:
                    datos[8] = activar
                    datos[9] = callback
                    datos[15] += 1
                    encontrado = True
                    break
            if not encontrado:
                await update.message.reply_text(f"❌ Trade ID {trade_id} no encontrado")
                return

            if bot.master:
                bot.master.guardar_estado()
            estado = "ACTIVADO" if activar else "DESACTIVADO"
            await update.message.reply_html(f"✅ <b>Trailing {estado}</b>\n🤖 {bot_id}\n🆔 {trade_id}\n📊 Callback: {callback*100}%")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /trailing: {str(e)[:200]}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("⚠️ Uso: /cancel BOT_ID TRADE_ID\nEj: /cancel BNB_Manual MANUAL_1")
                return
            bot_id = context.args[0]
            trade_id = context.args[1]

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(bot)
            resultado = strategy.cancelar_orden(trade_id)
            await update.message.reply_html(resultado)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /cancel: {str(e)[:200]}")

    async def list_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /list_orders BOT_ID")
                return
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            from strategies.manual import ManualStrategy
            strategy = ManualStrategy(bot)
            resultado = strategy.listar_ordenes_pendientes()
            await update.message.reply_html(resultado)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /list_orders: {str(e)[:200]}")

    # ============================================================
    # 3. COMANDOS DCA
    # ============================================================

    async def status_dca(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("⚠️ Uso: /status_dca BOT_ID DIRECCION [TP%] [SL%]\nEj: /status_dca BNB_Manual long 5 10")
                return
            bot_id = context.args[0]
            direccion = context.args[1].lower()
            tp_porcentaje = float(context.args[2]) if len(context.args) > 2 else None
            sl_porcentaje = float(context.args[3]) if len(context.args) > 3 else None

            if direccion not in ["long", "short"]:
                await update.message.reply_text("❌ Dirección inválida. Usa 'long' o 'short'")
                return

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            p_act = self.master.last_prices.get(bot.symbol_ws, 0)
            if p_act == 0:
                await update.message.reply_text("❌ No se pudo obtener el precio actual")
                return

            posiciones_filtradas = []
            for p_ent, datos in bot.posiciones.items():
                if len(datos) >= 17 and datos[4] == direccion:
                    posiciones_filtradas.append((float(p_ent), datos))

            if not posiciones_filtradas:
                await update.message.reply_text(f"📭 No hay posiciones {direccion.upper()} abiertas en {bot_id}")
                return

            total_cantidad = 0.0
            total_pnl_flotante = 0.0
            suma_precio_cantidad = 0.0
            for p_ent, datos in posiciones_filtradas:
                cantidad = float(datos[2])
                precio_entrada = p_ent
                total_cantidad += cantidad
                suma_precio_cantidad += precio_entrada * cantidad
                pnl = (p_act - precio_entrada) * cantidad if direccion == "long" else (precio_entrada - p_act) * cantidad
                total_pnl_flotante += pnl

            precio_promedio = suma_precio_cantidad / total_cantidad if total_cantidad > 0 else 0
            valor_nominal = total_cantidad * precio_promedio

            mensaje = (
                f"📊 <b>ESTADO DCA - {bot.bot_id}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔄 Dirección: <b>{direccion.upper()}</b>\n"
                f"📈 Precio Actual: <code>{p_act:.{bot.decimales}f}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>RESUMEN</b>\n"
                f"   • Posiciones: <code>{len(posiciones_filtradas)}</code>\n"
                f"   • Cantidad: <code>{total_cantidad:.4f}</code>\n"
                f"   • Valor Nominal: <code>${valor_nominal:.2f}</code>\n"
                f"   • Precio Promedio: <code>{precio_promedio:.{bot.decimales}f}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>PnL FLOTANTE</b>\n"
                f"   • PnL: <b>${total_pnl_flotante:+.4f}</b>\n"
            )
            if valor_nominal > 0:
                mensaje += f"   • Rendimiento: <b>{(total_pnl_flotante / valor_nominal * 100):+.2f}%</b>\n"

            if tp_porcentaje is not None:
                tp_price = precio_promedio * (1 + tp_porcentaje/100) if direccion == "long" else precio_promedio * (1 - tp_porcentaje/100)
                mensaje += f"\n🎯 <b>TP ({tp_porcentaje}%)</b>\n   • Precio: <code>{tp_price:.{bot.decimales}f}</code> | Dist: <b>{(tp_price - p_act)/p_act*100:+.2f}%</b>\n"
            if sl_porcentaje is not None:
                sl_price = precio_promedio * (1 - sl_porcentaje/100) if direccion == "long" else precio_promedio * (1 + sl_porcentaje/100)
                mensaje += f"\n🛑 <b>SL ({sl_porcentaje}%)</b>\n   • Precio: <code>{sl_price:.{bot.decimales}f}</code> | Dist: <b>{(sl_price - p_act)/p_act*100:+.2f}%</b>\n"

            await update.message.reply_html(mensaje)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /status_dca: {str(e)[:200]}")

    async def send_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 3:
                await update.message.reply_text("⚠️ Uso: /send_all BOT_ID DIRECCION PRECIO_TP [PRECIO_SL]\nEj: /send_all BNB_Manual long 590 560")
                return
            bot_id = context.args[0]
            direccion = context.args[1].lower()
            tp_price = float(context.args[2])
            sl_price = float(context.args[3]) if len(context.args) > 3 else None

            if direccion not in ["long", "short"]:
                await update.message.reply_text("❌ Dirección inválida. Usa 'long' o 'short'")
                return

            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if bot.estrategia != "manual":
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo manual")
                return

            posiciones = []
            for p_ent, datos in bot.posiciones.items():
                if len(datos) >= 17 and datos[4] == direccion:
                    posiciones.append((p_ent, datos))

            if not posiciones:
                await update.message.reply_text(f"📭 No hay posiciones {direccion.upper()} en {bot_id}")
                return

            modificadas = 0
            for p_ent, datos in posiciones:
                datos[6] = tp_price
                if sl_price is not None:
                    datos[7] = sl_price
                datos[15] += 1
                modificadas += 1

            if bot.master:
                bot.master.guardar_estado()

            await update.message.reply_html(
                f"✅ <b>SEND ALL</b>\n🤖 {bot_id}\n🔄 {direccion.upper()}\n📦 {modificadas} posiciones\n🎯 TP: {tp_price}\n" +
                (f"🛑 SL: {sl_price}" if sl_price else "")
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /send_all: {str(e)[:200]}")

    # ============================================================
    # 4. GESTIÓN DE BOTS
    # ============================================================

    async def pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /pause BOT_ID")
                return
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            bot.pausado = True
            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_text(f"⏸️ Bot {bot_id} PAUSADO")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /pause: {str(e)[:200]}")

    async def resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /resume BOT_ID")
                return
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            bot.pausado = False
            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_text(f"▶️ Bot {bot_id} REANUDADO")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /resume: {str(e)[:200]}")

    async def close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("⚠️ Uso: /close BOT_ID TRADE_ID")
                return
            bot_id = context.args[0]
            trade_id = context.args[1]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return

            p_act = self.master.last_prices.get(bot.symbol_ws, 0)
            if not p_act:
                await update.message.reply_text("❌ No se pudo obtener el precio actual")
                return

            target_p_ent = None
            for p_ent, datos in bot.posiciones.items():
                if len(datos) >= 5 and datos[4] == trade_id:
                    target_p_ent = p_ent
                    break

            if not target_p_ent:
                await update.message.reply_text(f"❌ Trade ID {trade_id} no encontrado")
                return

            datos = bot.posiciones[target_p_ent]
            hora_entrada = datos[3] if len(datos) > 3 else "N/A"
            trade_id_s = datos[4] if len(datos) > 4 else "N/A"
            ganancia = (target_p_ent - p_act if bot.direccion == "short" else p_act - target_p_ent) * bot.monedas_por_grid

            bot.pnl_acumulado += ganancia
            bot.comisiones_pagadas += (bot.monedas_por_grid * p_act) * 0.0004
            bot.trades_cerrados += 1
            bot.registrar_trade_csv(target_p_ent, p_act, ganancia, f"MANUAL_{bot.estrategia}", bot.direccion, hora_entrada, trade_id_s)
            del bot.posiciones[target_p_ent]
            if bot.master:
                bot.master.guardar_estado()

            await update.message.reply_html(f"✅ <b>CIERRE MANUAL</b>\n🤖 {bot_id}\n🆔 {trade_id}\n💰 PnL: ${ganancia:.4f}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /close: {str(e)[:200]}")

    async def close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /close_all BOT_ID")
                return
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            if not bot.posiciones:
                await update.message.reply_text(f"📭 El bot {bot_id} no tiene posiciones abiertas.")
                return

            p_act = self.master.last_prices.get(bot.symbol_ws, 0)
            if not p_act:
                await update.message.reply_text("❌ No se pudo obtener el precio actual")
                return

            bot.pausado = True
            total_pnl = 0
            num_trades = len(bot.posiciones)
            for p_ent in list(bot.posiciones.keys()):
                datos = bot.posiciones[p_ent]
                hora_entrada = datos[3] if len(datos) > 3 else "N/A"
                trade_id_s = datos[4] if len(datos) > 4 else "N/A"
                ganancia = (p_ent - p_act if bot.direccion == "short" else p_act - p_ent) * bot.monedas_por_grid
                total_pnl += ganancia
                bot.registrar_trade_csv(p_ent, p_act, ganancia, "FORCE_CLOSE_ALL", bot.direccion, hora_entrada, trade_id_s)
                del bot.posiciones[p_ent]

            bot.pnl_acumulado += total_pnl
            bot.trades_cerrados += num_trades
            if bot.master:
                bot.master.guardar_estado()

            await update.message.reply_html(
                f"⚠️ <b>CIERRE TOTAL</b>\n🤖 {bot_id}\n📦 {num_trades}\n💰 PnL: ${total_pnl:.4f}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /close_all: {str(e)[:200]}")

    # ============================================================
    # 5. CONFIGURACIÓN
    # ============================================================

    async def set_tp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("⚠️ Uso: /set_tp BOT_ID VALOR%")
                return
            bot_id = context.args[0]
            nuevo_tp = float(context.args[1])
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            bot.objetivo = nuevo_tp
            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_text(f"🎯 TP actualizado: {bot_id} → {nuevo_tp}%")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /set_tp: {str(e)[:200]}")

    async def set_sl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 2:
                await update.message.reply_text("⚠️ Uso: /set_sl BOT_ID VALOR%")
                return
            bot_id = context.args[0]
            nuevo_sl = float(context.args[1])
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            bot.stop_loss = nuevo_sl
            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_text(f"🛑 SL actualizado: {bot_id} → {nuevo_sl}%")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /set_sl: {str(e)[:200]}")

    # ============================================================
    # 6. ESTADÍSTICAS TRAILING
    # ============================================================

    async def trailing_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if context.args:
                bot_id = context.args[0]
                bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
                if not bot:
                    await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                    return
                await update.message.reply_html(
                    f"📊 <b>Trailing Stats: {bot.bot_id}</b>\n✅ PLUS: {bot.trailing_plus}\n❌ MINUS: {bot.trailing_minus}\n📈 Total: {bot.trailing_plus + bot.trailing_minus}"
                )
            else:
                mensaje = "📊 <b>TRAILING STATS GLOBALES</b>\n"
                total_plus = 0
                total_minus = 0
                for bot in self.master.bots:
                    if bot.estrategia in ["gridT", "ema"]:
                        total_plus += bot.trailing_plus
                        total_minus += bot.trailing_minus
                        mensaje += f"🤖 {bot.bot_id}: +{bot.trailing_plus}/-{bot.trailing_minus}\n"
                mensaje += f"━━━━━━━━━━━━━━━\n✅ TOTAL PLUS: {total_plus}\n❌ TOTAL MINUS: {total_minus}"
                await update.message.reply_html(mensaje)
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /trailing_stats: {str(e)[:200]}")

    async def set_trailing_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) < 3:
                await update.message.reply_text("⚠️ Uso: /set_trailing_stats BOT_ID PLUS MINUS")
                return
            bot_id = context.args[0]
            nuevo_plus = int(context.args[1])
            nuevo_minus = int(context.args[2])
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                return
            bot.trailing_plus = nuevo_plus
            bot.trailing_minus = nuevo_minus
            if bot.master:
                bot.master.guardar_estado()
            await update.message.reply_text(f"✅ Trailing Stats: +{nuevo_plus}/-{nuevo_minus}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /set_trailing_stats: {str(e)[:200]}")

    async def reset_trailing_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /reset_trailing_stats BOT_ID|all")
                return
            if context.args[0].lower() == "all":
                for bot in self.master.bots:
                    if bot.estrategia in ["gridT", "ema"]:
                        bot.trailing_plus = 0
                        bot.trailing_minus = 0
                if self.master:
                    self.master.guardar_estado()
                await update.message.reply_text("✅ TODOS reseteados")
            else:
                bot_id = context.args[0]
                bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
                if not bot:
                    await update.message.reply_text(f"❌ Bot {bot_id} no encontrado")
                    return
                bot.trailing_plus = 0
                bot.trailing_minus = 0
                if bot.master:
                    bot.master.guardar_estado()
                await update.message.reply_text(f"✅ {bot_id} reseteado")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /reset_trailing_stats: {str(e)[:200]}")

    # ============================================================
    # 7. SISTEMA
    # ============================================================

    async def flag_telegram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text(f"📊 Estado actual: {self.master.flag_telegram}\nUso: /flag_telegram true|false")
                return
            valor = context.args[0].lower()
            if valor in ["true", "1", "yes", "on"]:
                self.master.flag_telegram = True
            elif valor in ["false", "0", "no", "off"]:
                self.master.flag_telegram = False
            else:
                await update.message.reply_text("❌ Usa 'true' o 'false'")
                return
            estado = "ACTIVADO ✅" if self.master.flag_telegram else "DESACTIVADO ❌"
            await update.message.reply_text(f"🔔 Notificaciones: {estado}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /flag_telegram: {str(e)[:200]}")

    async def ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Obtiene las IPs usando sockets y comandos de sistema"""
        try:
            import socket
            import subprocess
            import re
            
            mensaje = f"🌐 <b>ESTADO DE RED ({self.master.config_manager.version})</b>\n\n"
            encontrada = False
            ips_detectadas = set()
    
            # ===== MÉTODO 1: Usando sockets (Rápido y compatible) =====
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                ips_detectadas.add(local_ip)
                s.close()
            except:
                pass
    
            # ===== MÉTODO 2: Comandos de sistema =====
            for cmd in ["/system/bin/ip addr show", "ip addr show", "ifconfig"]:
                try:
                    output = subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT).decode("utf-8")
                    matches = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', output)
                    for ip in matches:
                        if ip != "127.0.0.1":
                            ips_detectadas.add(ip)
                except:
                    continue
    
            # ===== MÉTODO 3: Intentar obtener IP pública =====
            try:
                import requests
                response = requests.get('https://api.ipify.org', timeout=5)
                if response.status_code == 200:
                    ip_publica = response.text.strip()
                    if ip_publica and ip_publica not in ips_detectadas:
                        ips_detectadas.add(ip_publica)
            except:
                pass
    
            # ===== MÉTODO 4: Buscar Tailscale específicamente =====
            try:
                output = subprocess.check_output(["tailscale", "ip"], stderr=subprocess.STDOUT).decode("utf-8")
                for line in output.split('\n'):
                    if line.strip():
                        ip_tailscale = line.strip()
                        if ip_tailscale and ip_tailscale not in ips_detectadas:
                            ips_detectadas.add(ip_tailscale)
            except:
                pass
    
            # ===== MÉTODO 5: Buscar interfaz Tailscale con ip addr =====
            try:
                output = subprocess.check_output(["ip", "addr", "show"], stderr=subprocess.STDOUT).decode("utf-8")
                # Buscar interfaces con "tailscale" o "ts"
                for line in output.split('\n'):
                    if 'tailscale' in line.lower() or 'ts' in line.lower():
                        matches = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', line)
                        for ip in matches:
                            if ip != "127.0.0.1":
                                ips_detectadas.add(ip)
            except:
                pass
    
            # ===== CLASIFICAR Y MOSTRAR =====
            for ip in sorted(ips_detectadas):
                if ip.startswith("100."):
                    tipo = "🛰️ <b>Tailscale:</b>"
                elif ip.startswith("192.168.") or ip.startswith("10."):
                    tipo = "🏠 <b>Red Local:</b>"
                else:
                    tipo = "🌐 <b>IP Pública:</b>"
                
                mensaje += f"{tipo} <code>{ip}</code>\n"
                encontrada = True
    
            if not encontrada:
                mensaje += "⚠️ No se detectaron IPs. ¿Está el WiFi o los Datos activos?"
            else:
                mensaje += "\n<i>Toca la IP para copiarla en Termius.</i>"
    
            await update.message.reply_html(mensaje)
    
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error crítico en /ip: {str(e)[:300]}\n\n{traceback.format_exc()[:500]}"
            )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mensaje = (
            f"📖 <b>GUÍA DE COMANDOS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔹 <b>INFORMACIÓN</b>\n"
            "• /status - Estado general\n"
            "• /inspect BOT_ID - Inspeccionar bot\n"
            "• /history BOT_ID - Historial de trades\n"
            "• /price [MONEDA] - Precio actual\n"
            "• /list_orders BOT_ID - Órdenes pendientes\n\n"
            "🔹 <b>MANUAL TRADING</b>\n"
            "• /entry BOT_ID LONG|SHORT L|M PRECIO CANTIDAD APALANCAMIENTO LIQ_PRICE [TP] [SL] [TRAILING]\n"
            "  Ej: /entry BNB_Manual LONG M 0 0.5 5 464.32 590 550 true\n"
            "• /exit BOT_ID TRADE_ID L|M PRECIO\n"
            "• /exit_all BOT_ID L|M PRECIO\n"
            "• /modify BOT_ID TRADE_ID TP|SL PRECIO\n"
            "• /trailing BOT_ID TRADE_ID ON|OFF [CALLBACK]\n"
            "• /cancel BOT_ID TRADE_ID\n\n"
            "🔹 <b>DCA</b>\n"
            "• /status_dca BOT_ID DIRECCION [TP%] [SL%]\n"
            "• /send_all BOT_ID DIRECCION PRECIO_TP [PRECIO_SL]\n\n"
            "🔹 <b>GESTIÓN</b>\n"
            "• /pause BOT_ID - Pausar bot\n"
            "• /resume BOT_ID - Reanudar bot\n"
            "• /set_tp BOT_ID % - Cambiar TP global\n"
            "• /set_sl BOT_ID % - Cambiar SL global\n"
            "• /trailing_stats [BOT_ID] - Estadísticas\n"
            "• /reset_trailing_stats BOT_ID|all\n\n"
            "🔹 <b>SISTEMA</b>\n"
            "• /flag_telegram true|false - Notificaciones\n"
            "• /ip - Mostrar IP\n"
            "• /restart - Reiniciar\n"
            "• /reset_factory - Resetear TODO\n"
        )
        await update.message.reply_html(mensaje)

    async def restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/restart - Reinicia el bot gracefulmente"""
        try:
            # Verificar que el usuario es admin
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            await update.message.reply_text("🔄 <b>REINICIANDO...</b>\nEl Guardián Bash tomará el control.", parse_mode='HTML')
            
            # Programar reinicio con delay
            import asyncio
            asyncio.create_task(self._shutdown_and_restart())
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /restart: {str(e)[:200]}")
    
    async def _shutdown_and_restart(self):
        """Cierra el bot y permite que el script Bash lo reinicie"""
        try:
            if self.master:
                await self.master.shutdown()
                # Esperar un momento para que todo se cierre
                await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Error en shutdown: {e}")
        
        # Forzar salida
        os._exit(0)

    async def reset_factory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/reset_factory - Limpia TODO y reinicia"""
        try:
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            await update.message.reply_html("🧹 <b>LIMPIEZA TOTAL EN CURSO...</b>\nEl servidor Bash tomará el control. Espera el mensaje de inicio en unos segundos.")
            
            # Crear archivo de bloqueo para reset
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            path_lock = os.path.join(base_dir, "reset.lock")
            with open(path_lock, "w") as f:
                f.write(f"reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            import asyncio
            await asyncio.sleep(1)
            
            # Cerrar el bot y salir
            if self.master:
                await self.master.shutdown()
                await asyncio.sleep(2)
            os._exit(0)
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /reset_factory: {str(e)[:200]}")

    async def shell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/shell COMANDO - Ejecuta comandos shell (SOLO ADMIN)"""
        try:
            # Verificar que el usuario es admin
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            if not context.args:
                await update.message.reply_text("⚠️ Uso: /shell COMANDO\nEj: /shell ls -la")
                return
            
            comando = " ".join(context.args)
            resultado = subprocess.check_output(comando, shell=True, stderr=subprocess.STDOUT, text=True)
            
            # Limitar a 4000 caracteres para Telegram
            if len(resultado) > 4000:
                resultado = resultado[:4000] + "\n... (truncado)"
            
            await update.message.reply_text(f"🖥️ <b>Salida:</b>\n<code>{resultado}</code>", parse_mode='HTML')
            
        except subprocess.CalledProcessError as e:
            await update.message.reply_text(f"❌ <b>Error:</b>\n<code>{e.output[:500]}</code>", parse_mode='HTML')
        except Exception as e:
            await update.message.reply_text(f"❌ Error en /shell: {str(e)[:200]}")

    def _listar_archivos_proyecto(self, base_dir=None):
        """Lista recursivamente TODOS los archivos del proyecto con sus rutas"""
        if base_dir is None:
            base_dir = base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        archivos = []
        
        # Extensiones a incluir
        extensiones = ['.py', '.json', '.csv', '.txt', '.log', '.sh', '.env', '.md', '.yml', '.yaml']
        
        # Excluir directorios
        excluir = ['__pycache__', '.git', 'venv', 'env', 'node_modules', '.pytest_cache', '.mypy_cache']
        
        # ===== RECORRER TODO EL PROYECTO RECURSIVAMENTE =====
        for root, dirs, files in os.walk(base_dir):
            # Saltar directorios excluidos
            dirs[:] = [d for d in dirs if d not in excluir]
            
            # Saltar directorios de datos históricos (si existen)
            if 'Data BackTesting' in root or 'historical_data' in root or 'BackTesting' in root:
                continue
            
            for f in files:
                # Verificar extensión
                if any(f.endswith(ext) for ext in extensiones):
                    ruta_completa = os.path.join(root, f)
                    rel_path = os.path.relpath(ruta_completa, base_dir)
                    
                    # Si la ruta relativa empieza con '..', es que está fuera del proyecto
                    if rel_path.startswith('..'):
                        continue
                    
                    archivos.append({
                        'nombre': f,
                        'ruta': ruta_completa,
                        'relativa': rel_path,
                        'tamaño': os.path.getsize(ruta_completa)
                    })
        
        # Ordenar por ruta relativa
        archivos.sort(key=lambda x: x['relativa'])
        return archivos
    
    async def send_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/send_file [RUTA] - Envía un archivo del bot"""
        try:
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            

            # Si no se especifica argumento, mostrar todos los archivos
            if not context.args:
                archivos = self._listar_archivos_proyecto(base_dir)
                
                if not archivos:
                    await update.message.reply_text("📭 No hay archivos disponibles")
                    return
                
                # ===== CONSTRUIR MENSAJE CON JERARQUÍA =====
                mensaje = "📁 <b>ARCHIVOS DEL PROYECTO</b>\n"
                mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                # Agrupar por directorio
                directorios = {}
                for a in archivos:
                    dir_name = os.path.dirname(a['relativa'])
                    if dir_name not in directorios:
                        directorios[dir_name] = []
                    directorios[dir_name].append(a)
                
                # Mostrar por directorio
                for dir_name in sorted(directorios.keys()):
                    # Mostrar nombre del directorio
                    if dir_name == '.':
                        display_name = "📂 <b>Raíz (Proyecto_Cripto/)</b>"
                    elif dir_name == '':
                        display_name = "📂 <b>Raíz (Proyecto_Cripto/)</b>"
                    else:
                        display_name = f"📂 <b>{dir_name}/</b>"
                    
                    mensaje += f"{display_name}\n"
                    
                    # Mostrar archivos (hasta 15 por directorio para no saturar)
                    archivos_dir = directorios[dir_name]
                    for a in archivos_dir[:15]:
                        mensaje += f"   📄 <code>{a['nombre']}</code>\n"
                    
                    if len(archivos_dir) > 15:
                        mensaje += f"   ... y {len(archivos_dir)-15} más\n"
                    
                    mensaje += "\n"
                
                mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                mensaje += f"<i>Total: {len(archivos)} archivos</i>\n"
                mensaje += "<i>Usa /send_file RUTA para descargar</i>"
                
                # ===== SI EL MENSAJE ES MUY LARGO, ENVIAR POR PARTES =====
                MAX_LEN = 4000
                if len(mensaje) > MAX_LEN:
                    # Enviar primero el encabezado
                    await update.message.reply_html(mensaje[:MAX_LEN])
                    
                    # Enviar el resto en trozos
                    resto = mensaje[MAX_LEN:]
                    while resto:
                        # Buscar un punto de corte limpio
                        corte = resto.find('\n\n', 500)
                        if corte == -1:
                            corte = min(4000, len(resto))
                        await update.message.reply_html(resto[:corte])
                        resto = resto[corte:]
                else:
                    await update.message.reply_html(mensaje)
                
                return
            
            # ===== BUSCAR ARCHIVO POR RUTA O NOMBRE =====
            buscar = context.args[0]
            archivos = self._listar_archivos_proyecto(base_dir)
            
            # Buscar coincidencia exacta (por ruta o nombre)
            encontrados = []
            for a in archivos:
                if a['relativa'] == buscar or a['nombre'] == buscar:
                    encontrados.append(a)
            
            # Si no hay coincidencia exacta, buscar por nombre parcial
            if not encontrados:
                for a in archivos:
                    if buscar in a['relativa'] or buscar in a['nombre']:
                        encontrados.append(a)
            
            if not encontrados:
                await update.message.reply_text(f"❌ Archivo no encontrado: {buscar}\n\nSugerencia: Usa la ruta completa. Ej: /send_file Grid_Master.py")
                return
            
            # Si hay múltiples coincidencias, mostrar lista
            if len(encontrados) > 1:
                mensaje = f"🔍 <b>Múltiples archivos coinciden con '{buscar}'</b>\n"
                mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                for i, a in enumerate(encontrados[:20]):
                    mensaje += f"{i+1}. 📄 <code>{a['relativa']}</code>\n"
                if len(encontrados) > 20:
                    mensaje += f"... y {len(encontrados)-20} más\n"
                mensaje += "\n<i>Usa la ruta completa para descargar</i>"
                await update.message.reply_html(mensaje)
                return
            
            # Enviar el archivo
            archivo = encontrados[0]
            with open(archivo['ruta'], 'rb') as f:
                caption = f"📎 <b>{archivo['nombre']}</b>\n📂 {archivo['relativa']}\n📦 {archivo['tamaño']} bytes"
                await update.message.reply_document(
                    document=f,
                    filename=archivo['nombre'],
                    caption=caption,
                    parse_mode='HTML'
                )
            
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error en /send_file: {str(e)[:300]}\n\n{traceback.format_exc()[:500]}"
            )
    
    async def send_all_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/send_all_logs - Envía ZIP con todos los logs y estados"""
        try:
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            import zipfile
            from io import BytesIO
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Buscar archivos importantes en todo el proyecto
                patrones = [
                    'trades_*.csv',
                    'log_eficiencia_*.csv',
                    'state_trading_*.json',
                    'config_bots_*.json',
                    '*.log',
                    'last_alive_*.txt',
                    'restart_counter.txt',
                    'reset.lock'
                ]
                
                archivos_agregados = set()
                
                for root, dirs, files in os.walk(base_dir):
                    # Saltar directorios grandes
                    if 'venv' in root or '__pycache__' in root or '.git' in root:
                        continue
                        
                    for f in files:
                        # Verificar si coincide con algún patrón
                        for patron in patrones:
                            if patron.replace('*', '') in f:
                                ruta_completa = os.path.join(root, f)
                                if ruta_completa not in archivos_agregados:
                                    # Guardar con ruta relativa para organización
                                    arcname = os.path.relpath(ruta_completa, base_dir)
                                    zip_file.write(ruta_completa, arcname)
                                    archivos_agregados.add(ruta_completa)
                                break
            
            zip_buffer.seek(0)
            
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_zip = f"bot_backup_{fecha}.zip"
            
            await update.message.reply_document(
                document=zip_buffer,
                filename=nombre_zip,
                caption=f"📦 <b>BACKUP COMPLETO</b>\n"
                       f"🗓️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                       f"📁 {len(archivos_agregados)} archivos incluidos",
                parse_mode='HTML'
            )
            
        except Exception as e:
            import traceback
            await update.message.reply_text(f"❌ Error en /send_all_logs: {str(e)[:300]}")
    
    async def emas(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/emas [BOT_ID] - Estado de EMAs para bots scalp"""
        try:
            # Filtrar bots scalp
            bots_scalp = [b for b in self.master.bots if b.estrategia == "ema_scalp"]
            
            if not bots_scalp:
                await update.message.reply_text("❌ No hay bots con estrategia 'ema_scalp' activos.")
                return
            
            # Si se especificó un bot_id, filtrar
            if context.args:
                bot_id_filter = context.args[0]
                bots_scalp = [b for b in bots_scalp if b.bot_id == bot_id_filter]
                if not bots_scalp:
                    await update.message.reply_text(f"❌ Bot {bot_id_filter} no encontrado o no es tipo scalp.")
                    return
            
            # ===== CONSTRUIR MENSAJE EN TEXTO PLANO (NO HTML) =====
            # Esto evita errores de parseo HTML
            mensaje = "📊 ESTADO EMAs - SCALP BOTS\n"
            mensaje += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for bot in bots_scalp:
                p_act = self.master.last_prices.get(bot.symbol_ws, 0)
                dec = bot.decimales
                
                mensaje += f"🤖 {bot.bot_id} | {bot.symbol_ws.upper()}\n"
                mensaje += f"📈 Precio Actual: {p_act:.{dec}f}\n"
                mensaje += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                mensaje += f"📊 VALORES EMAs:\n"
                mensaje += f"   • EMA{bot.ema_fast_p}: {bot.ultima_ema_fast:.{dec}f}\n"
                mensaje += f"   • EMA{bot.ema_slow_p}: {bot.ultima_ema_slow:.{dec}f}\n"
                mensaje += f"   • EMA{bot.ema_slow2_p}: {bot.ultima_ema_slow2:.{dec}f}\n\n"
                
                # CONDICIÓN LONG
                cond_long_1 = bot.ultima_ema_fast > bot.ultima_ema_slow
                cond_long_2 = bot.ultima_ema_slow > bot.ultima_ema_slow2
                
                mensaje += f"🟢 LONG: "
                if cond_long_1 and cond_long_2:
                    mensaje += f"✅ ACTIVA (EMA{bot.ema_fast_p} > EMA{bot.ema_slow_p} > EMA{bot.ema_slow2_p})\n"
                else:
                    mensaje += "❌ INACTIVA\n"
                    if not cond_long_1:
                        mensaje += f"   └─ EMA{bot.ema_fast_p} ({bot.ultima_ema_fast:.{dec}f}) NO es > EMA{bot.ema_slow_p} ({bot.ultima_ema_slow:.{dec}f})\n"
                    if not cond_long_2:
                        mensaje += f"   └─ EMA{bot.ema_slow_p} ({bot.ultima_ema_slow:.{dec}f}) NO es > EMA{bot.ema_slow2_p} ({bot.ultima_ema_slow2:.{dec}f})\n"
                
                # CONDICIÓN SHORT
                cond_short_1 = bot.ultima_ema_fast < bot.ultima_ema_slow
                cond_short_2 = bot.ultima_ema_slow < bot.ultima_ema_slow2
                
                mensaje += f"🔴 SHORT: "
                if cond_short_1 and cond_short_2:
                    mensaje += f"✅ ACTIVA (EMA{bot.ema_fast_p} < EMA{bot.ema_slow_p} < EMA{bot.ema_slow2_p})\n"
                else:
                    mensaje += "❌ INACTIVA\n"
                    if not cond_short_1:
                        mensaje += f"   └─ EMA{bot.ema_fast_p} ({bot.ultima_ema_fast:.{dec}f}) NO es < EMA{bot.ema_slow_p} ({bot.ultima_ema_slow:.{dec}f})\n"
                    if not cond_short_2:
                        mensaje += f"   └─ EMA{bot.ema_slow_p} ({bot.ultima_ema_slow:.{dec}f}) NO es < EMA{bot.ema_slow2_p} ({bot.ultima_ema_slow2:.{dec}f})\n"
                
                mensaje += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Enviar como texto plano (NO HTML)
            MAX_CHARS = 4000
            if len(mensaje) <= MAX_CHARS:
                await update.message.reply_text(mensaje)  # ← reply_text, no reply_html
            else:
                for i in range(0, len(mensaje), MAX_CHARS):
                    chunk = mensaje[i:i + MAX_CHARS]
                    await update.message.reply_text(chunk)  # ← reply_text
                    await asyncio.sleep(0.5)
            
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error en /emas: {str(e)[:300]}\n\n{traceback.format_exc()[:500]}"
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Maneja la recepción de archivos enviados al bot
        Soporta: config_bots.json, state_trading.json, Grid_Master.py, CSVs
        """
        try:
            # Verificar autorización
            if str(update.effective_user.id) != str(self.master.chat_id):
                await update.message.reply_text("⛔ ACCESO DENEGADO")
                return
            
            document = update.message.document
            file_name = document.file_name
            file_size = document.file_size
            
            # Limitar tamaño (10MB)
            if file_size > 10 * 1024 * 1024:
                await update.message.reply_text("❌ Archivo demasiado grande. Máximo 10MB.")
                return
            
            # Descargar archivo
            file = await document.get_file()
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # ===== VERIFICAR TIPO DE ARCHIVO =====
            
            # 1. CONFIGURACIÓN
            if file_name == f'config_bots_{self.master.config_manager.version}.json':
                # Backup del config actual
                config_path = os.path.join(base_dir, file_name)
                if os.path.exists(config_path):
                    backup_name = f"config_bots_{self.master.config_manager.version}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    backup_path = os.path.join(base_dir, backup_name)
                    os.rename(config_path, backup_path)
                    await update.message.reply_text(f"📦 Backup guardado: {backup_name}")
                
                # Guardar nuevo config
                await file.download_to_drive(config_path)
                await update.message.reply_text(
                    f"✅ <b>config_bots_{self.master.config_manager.version}.json actualizado</b>\n"
                    "🔄 Usa /restart para aplicar los cambios.",
                    parse_mode='HTML'
                )
            
            # 2. ESTADO
            elif file_name.startswith('state_trading_') and file_name.endswith('.json'):
                state_path = os.path.join(base_dir, "GridBot", file_name)
                
                # Backup del estado actual
                if os.path.exists(state_path):
                    backup_name = f"state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    backup_path = os.path.join(base_dir, "GridBot", backup_name)
                    os.rename(state_path, backup_path)
                    await update.message.reply_text(f"📦 Backup del estado guardado: {backup_name}")
                
                # Guardar nuevo estado
                await file.download_to_drive(state_path)
                await update.message.reply_text(
                    "✅ <b>Archivo de estado actualizado</b>\n"
                    "🔄 Usa /restart para aplicar los cambios.",
                    parse_mode='HTML'
                )
            
            # 3. SCRIPT PRINCIPAL
            elif file_name == 'Grid_Master.py':
                script_path = os.path.join(base_dir, file_name)
                
                # Backup del script actual
                if os.path.exists(script_path):
                    backup_name = f"Grid_Master_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                    backup_path = os.path.join(base_dir, backup_name)
                    os.rename(script_path, backup_path)
                    await update.message.reply_text(f"📦 Backup del script guardado: {backup_name}")
                
                # Guardar nuevo script
                await file.download_to_drive(script_path)
                await update.message.reply_text(
                    f"✅ <b>Grid_Master.py actualizado</b>\n"
                    "🔄 Usa /restart para aplicar los cambios.",
                    parse_mode='HTML'
                )
            
            # 4. SCRIPT DE BOOT
            elif file_name == f'boot_bot_{self.master.config_manager.version}.sh':
                script_path = os.path.join(base_dir, file_name)
                
                # Backup del script actual
                if os.path.exists(script_path):
                    backup_name = f"boot_bot_{self.master.config_manager.version}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sh"
                    backup_path = os.path.join(base_dir, backup_name)
                    os.rename(script_path, backup_path)
                    await update.message.reply_text(f"📦 Backup del boot guardado: {backup_name}")
                
                # Guardar nuevo script
                await file.download_to_drive(script_path)
                # Dar permisos de ejecución
                os.chmod(script_path, 0o755)
                await update.message.reply_text(
                    f"✅ <b>boot_bot_{self.master.config_manager.version}.sh actualizado</b>\n"
                    "🔄 Usa /restart para aplicar los cambios.",
                    parse_mode='HTML'
                )
            
            # 5. ARCHIVO .ENV
            elif file_name == '.env':
                env_path = os.path.join(base_dir, file_name)
                
                # Backup del .env actual
                if os.path.exists(env_path):
                    backup_name = f".env_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = os.path.join(base_dir, backup_name)
                    os.rename(env_path, backup_path)
                    await update.message.reply_text(f"📦 Backup del .env guardado: {backup_name}")
                
                # Guardar nuevo .env
                await file.download_to_drive(env_path)
                await update.message.reply_text(
                    "✅ <b>.env actualizado</b>\n"
                    "🔄 Usa /restart para aplicar los cambios.",
                    parse_mode='HTML'
                )
            
            # 6. ARCHIVOS CSV (trades, logs, etc.)
            elif file_name.endswith('.csv'):
                # Guardar en la carpeta correspondiente
                if file_name.startswith('trades_'):
                    dest_dir = base_dir  # Proyecto_Cripto/
                else:
                    dest_dir = os.path.join(base_dir, "GridBot")  # GridBot/
                
                dest_path = os.path.join(dest_dir, file_name)
                
                # Si el archivo ya existe, hacer backup
                if os.path.exists(dest_path):
                    backup_name = f"{file_name}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = os.path.join(dest_dir, backup_name)
                    os.rename(dest_path, backup_path)
                    await update.message.reply_text(f"📦 Backup del CSV guardado: {backup_name}")
                
                # Guardar nuevo CSV
                await file.download_to_drive(dest_path)
                await update.message.reply_text(
                    f"✅ <b>CSV recibido</b>\n"
                    f"📄 Guardado como: <code>{file_name}</code>\n"
                    f"📂 Ubicación: <code>{dest_dir}</code>",
                    parse_mode='HTML'
                )
            
            # 7. CUALQUIER OTRO ARCHIVO
            else:
                # Guardar en GridBot por defecto
                dest_dir = os.path.join(base_dir, "GridBot")
                dest_path = os.path.join(dest_dir, file_name)
                
                # Verificar si es un archivo de script
                if file_name.endswith('.py'):
                    dest_dir = base_dir  # Proyecto_Cripto/
                    dest_path = os.path.join(dest_dir, file_name)
                
                # Si el archivo ya existe, hacer backup
                if os.path.exists(dest_path):
                    backup_name = f"{file_name}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = os.path.join(dest_dir, backup_name)
                    os.rename(dest_path, backup_path)
                    await update.message.reply_text(f"📦 Backup guardado: {backup_name}")
                
                # Guardar archivo
                await file.download_to_drive(dest_path)
                await update.message.reply_text(
                    f"✅ <b>Archivo recibido</b>\n"
                    f"📄 Guardado como: <code>{file_name}</code>\n"
                    f"📂 Ubicación: <code>{dest_dir}</code>",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error al recibir archivo: {str(e)[:300]}\n\n{traceback.format_exc()[:500]}"
            )

    async def grid_levels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/grid_levels BOT_ID - Muestra los niveles del grid con estado"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Uso: /grid_levels BOT_ID\n"
                    "Ejemplo: /grid_levels BNB_Grid_0.3"
                )
                return
            
            bot_id = context.args[0]
            bot = next((b for b in self.master.bots if b.bot_id == bot_id), None)
            
            if not bot:
                await update.message.reply_text(f"❌ Bot {bot_id} no encontrado.")
                return
            
            # Verificar que sea un bot grid
            if bot.estrategia not in ["grid", "gridT"]:
                await update.message.reply_text(f"❌ El bot {bot_id} no es de tipo grid (estrategia: {bot.estrategia})")
                return
            
            if not bot.niveles:
                await update.message.reply_text(f"❌ El bot {bot_id} no tiene niveles configurados.")
                return
            
            p_act = self.master.last_prices.get(bot.symbol_ws, 0)
            if p_act == 0:
                await update.message.reply_text("❌ No se pudo obtener el precio actual")
                return
            
            # ===== CONSTRUIR REPORTE =====
            moneda = bot.symbol_ws.upper().replace("USDT", "")
            
            mensaje = (
                f"📊 <b>GRID LEVELS - {bot.bot_id}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 Precio Actual: <code>{p_act:.{bot.decimales}f}</code>\n"
                f"🔄 Dirección: <b>{bot.direccion.upper()}</b>\n"
                f"📦 Niveles: <code>{len(bot.niveles)}</code>\n"
                f"📊 Rango: <code>{bot.niveles[0]:.{bot.decimales}f}</code> → <code>{bot.niveles[-1]:.{bot.decimales}f}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            # ===== MOSTRAR NIVELES =====
            # Encontrar el índice del nivel actual
            idx_actual = -1
            for i, nivel in enumerate(bot.niveles):
                if p_act >= nivel:
                    idx_actual = i
            
            # Determinar cuántos niveles mostrar (máximo 30 para no saturar)
            total_niveles = len(bot.niveles)
            mostrar_desde = max(0, idx_actual - 10)
            mostrar_hasta = min(total_niveles, idx_actual + 20)
            
            # Si hay muchos niveles, mostrar un resumen
            if total_niveles > 30:
                mensaje += f"📌 <i>Mostrando niveles {mostrar_desde+1} a {mostrar_hasta} de {total_niveles}</i>\n\n"
            
            for i in range(mostrar_desde, mostrar_hasta):
                nivel = bot.niveles[i]
                
                # Verificar si hay posición en este nivel
                posicion = bot.posiciones.get(nivel)
                ocupado = posicion is not None
                
                # Calcular distancia desde el precio actual
                if bot.direccion == "long":
                    distancia = ((nivel - p_act) / p_act) * 100
                    if distancia >= 0:
                        flecha = "⬆️"
                        color = "🟢"
                    else:
                        flecha = "⬇️"
                        color = "🔴"
                else:  # short
                    distancia = ((p_act - nivel) / p_act) * 100
                    if distancia >= 0:
                        flecha = "⬇️"
                        color = "🟢"
                    else:
                        flecha = "⬆️"
                        color = "🔴"
                
                # Indicador de nivel actual
                if i == idx_actual:
                    indicador = "📍 <b>← ACTUAL</b>"
                elif i < idx_actual and bot.direccion == "long":
                    indicador = "✅ YA PASADO"
                elif i > idx_actual and bot.direccion == "short":
                    indicador = "✅ YA PASADO"
                else:
                    indicador = ""
                
                # Estado de la posición
                if ocupado:
                    # Obtener datos de la posición
                    datos = bot.posiciones[nivel]
                    objetivo = datos[1] if len(datos) > 1 else "N/A"
                    trailing = "🛰️" if datos[2] else ""
                    estado_pos = f"⚓ OCUPADO {trailing}"
                    if bot.estrategia == "gridT":
                        estado_pos += f" | TP: {objetivo:.{bot.decimales}f}"
                    else:
                        estado_pos += f" | Obj: {objetivo:.{bot.decimales}f}"
                else:
                    estado_pos = "⬜ LIBRE"
                
                # Formato del nivel
                if i == idx_actual:
                    nivel_str = f"<b>{nivel:.{bot.decimales}f}</b>"
                else:
                    nivel_str = f"{nivel:.{bot.decimales}f}"
                
                # Barra de progreso visual
                if ocupado:
                    barra = "█" * 10
                elif i == idx_actual:
                    barra = "▓" * 10
                else:
                    barra = "░" * 10
                
                mensaje += (
                    f"{i+1:3d}. {nivel_str} "
                    f"{flecha} {distancia:+.2f}% "
                    f"{estado_pos}\n"
                )
                
                # Mostrar barra visual cada 5 niveles
                if (i - mostrar_desde) % 5 == 4:
                    mensaje += "\n"
            
            # ===== RESUMEN DE POSICIONES ABIERTAS =====
            posiciones_abiertas = [p for p in bot.posiciones.keys() if p in bot.niveles]
            if posiciones_abiertas:
                mensaje += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                mensaje += f"⚓ <b>POSICIONES ABIERTAS: {len(posiciones_abiertas)}</b>\n"
                
                # Calcular PnL promedio
                pnl_total = 0
                for p_ent in posiciones_abiertas:
                    datos = bot.posiciones[p_ent]
                    if bot.direccion == "short":
                        ganancia = (p_ent - p_act) * bot.monedas_por_grid
                    else:
                        ganancia = (p_act - p_ent) * bot.monedas_por_grid
                    pnl_total += ganancia
                    objetivo = datos[1] if len(datos) > 1 else "N/A"
                    mensaje += f"   • Entrada: <code>{p_ent:.{bot.decimales}f}</code> | Obj: {objetivo:.{bot.decimales}f} | PnL: ${ganancia:+.4f}\n"
                
                mensaje += f"\n💰 <b>PnL Flotante Total: ${pnl_total:+.4f}</b>\n"
            
            # ===== ÍNDICE DE NIVEL ACTUAL =====
            mensaje += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            mensaje += f"📍 Nivel Actual: <b>{idx_actual+1}/{len(bot.niveles)}</b>\n"
            
            if bot.direccion == "long":
                niveles_faltantes = len([n for n in bot.niveles if n > p_act])
                mensaje += f"⬆️ Niveles por subir: <b>{niveles_faltantes}</b>\n"
                if idx_actual >= 0:
                    siguiente = bot.niveles[idx_actual+1] if idx_actual+1 < len(bot.niveles) else "N/A"
                    mensaje += f"🎯 Siguiente nivel: <b>{siguiente}</b>\n"
            else:
                niveles_faltantes = len([n for n in bot.niveles if n < p_act])
                mensaje += f"⬇️ Niveles por bajar: <b>{niveles_faltantes}</b>\n"
                if idx_actual >= 0:
                    siguiente = bot.niveles[idx_actual-1] if idx_actual-1 >= 0 else "N/A"
                    mensaje += f"🎯 Siguiente nivel: <b>{siguiente}</b>\n"
            
            mensaje += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            await update.message.reply_html(mensaje)
            
        except Exception as e:
            import traceback
            await update.message.reply_text(
                f"❌ Error en /grid_levels: {str(e)[:300]}\n\n{traceback.format_exc()[:500]}"
            )