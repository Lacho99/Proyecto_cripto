"""
Grid_Master.py
PUNTO DE ENTRADA - Versión modular
"""
import asyncio
import os
import sys
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# MODO DE EJECUCIÓN
# ==========================================
TEST = True  # Cambiar a False para Producción (Casa)
VERSION = 'v9.3'

# Importar módulos desde GridBot
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GridBot'))

# Verificar que los módulos existen
try:
    from core.bot import GridBotSim
    from core.config import ConfigManager, load_config
    from core.state import StateManager
    from strategies.manual import ManualStrategy
    from tg_handlers.handlers import TelegramHandlers
    print("✅ Módulos cargados correctamente")
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print("   Asegúrate de que GridBot/ existe y tiene los módulos necesarios")
    sys.exit(1)

class MasterController:
    def __init__(self):
        load_dotenv()
        self.last_prices = {}
        print(f"🧪 MODO {'DESARROLLO (PRUEBAS)' if TEST else 'PRODUCCIÓN (CASA)'}")
        print(f"📂 Directorio: {os.getcwd()}")
        
        # ===== CARGAR CONFIGURACIÓN =====
        self.config_manager = ConfigManager(VERSION, TEST)
        self.config = self.config_manager.load_config()
        
        if not self.config:
            print("❌ Error: No se pudo cargar la configuración")
            sys.exit(1)
        
        # ===== INICIALIZAR STATE MANAGER =====
        self.state_manager = StateManager(VERSION, TEST)
        self.state = self.state_manager.load_state(self.config)
        
        # ===== INICIALIZAR BOTS =====
        self.bots = []
        self._initialize_bots()
        
        # ===== INICIALIZAR TELEGRAM =====
        self.token = os.getenv("BOT_TEST_TOKEN") if TEST else os.getenv("BOT_TOKEN")
        self.chat_id = os.getenv("CHAT_TEST_ID") if TEST else os.getenv("CHAT_ID")
        
        from telegram import Bot
        self.t_bot = Bot(token=self.token)
        self.app = None
        
        # ===== INICIALIZAR HANDLERS =====
        self.handlers = TelegramHandlers(self)
        
        # ===== VARIABLES DE ESTADO =====
        self.start_time = time.time()
        
        self.last_funding_time = 0
        self.flag_telegram = True
        self.websocket = None
        self.heartbeat_task = None
        self.last_alive_file = f"last_alive_{VERSION}.txt"
        self.reporte_caida = self._verificar_downtime()

    
        # ===== VERIFICAR QUE NO HAYA OTRA INSTANCIA =====
        self.pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.pid")
        self._check_single_instance()
    
        print(f"✅ MasterController inicializado")

    def _check_single_instance(self):
        """Verifica que no haya otra instancia del bot corriendo"""
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                # Verificar si el proceso aún existe
                try:
                    os.kill(old_pid, 0)
                    print(f"⚠️ Ya hay una instancia corriendo (PID: {old_pid})")
                    print("   Si estás seguro de que no hay otra instancia, elimina bot.pid")
                    sys.exit(1)
                except OSError:
                    # El proceso ya no existe, podemos continuar
                    os.remove(self.pid_file)
            except:
                pass
        
        # Escribir PID actual
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    
    def _initialize_bots(self):
        """Inicializa todos los bots desde la configuración"""
        import math
        import ccxt
        
        print("🔄 Inicializando bots...")
        
        # Cargar exchange para obtener precisiones
        api_key = os.getenv("BINANCE_API_KEY_TEST") if TEST else os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_SECRET_KEY_TEST") if TEST else os.getenv("BINANCE_SECRET_KEY")
        
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'timeout': 50000,
                'enableRateLimit': True
            }
        })
        
        # Obtener precios actuales
        for symbol_ccxt, info in self.config.get("SYMBOLS", {}).items():
            try:
                ticker = exchange.fetch_ticker(symbol_ccxt)
                p_actual = ticker['last']
                self.last_prices[info["ws_name"]] = p_actual
            except Exception as e:
                print(f"⚠️ Error obteniendo precio para {symbol_ccxt}: {e}")
                p_actual = 0
            
            for b_id, cfg in info.get("bots", {}).items():
                try:
                    # ===== OBTENER PRECISIÓN =====
                    try:
                        market = exchange.market(symbol_ccxt)
                        precision_val = market['precision']['price']
                        if precision_val < 1:
                            precision = int(-math.log10(precision_val))
                        else:
                            precision = int(precision_val)
                        print(f"🎯 Precisión para {b_id}: {precision} decimales")
                    except:
                        precision = 6
                    
                    # ===== DETECTAR BOT MANUAL =====
                    if cfg.get("estrategia") == "manual":
                        print(f"📝 Creando bot manual: {b_id}")
                        niveles = []
                        bot = GridBotSim(
                            self, b_id, info["ws_name"], niveles,
                            capital_total=0.0,
                            etiqueta="Manual",
                            liq_price=0.0,
                            monedas_per_grid=0.0,
                            objetivo=0.0,
                            apalancamiento=1,
                            direccion=cfg.get("direccion", "ambas"),
                            stop_loss=0.0,
                            estrategia="manual",
                            timeframe="1m",
                            ema_fast=20,
                            ema_slow=50,
                            filtro_distancia=0.01,
                            tp_activacion_aire=None,
                            decimales=precision,
                            enable_ema200_cross=False,
                            ema_slow2=200,
                            max_posiciones_scalp=3,
                            callback_scalp=0.001,
                            activacion_trailing_en=100,
                            tiempo_maximo_segundos=120,
                            trailing_por_defecto=False,
                            callback=0.002,
                            limite_entrada_por_defecto=True,
                            limite_salida_por_defecto=True,
                            max_posiciones=cfg.get("max_posiciones", 10),
                            allow_modify=True,
                            notificar_cada_tick=True,
                            comision=0.0004,
                            modo=cfg.get("modo", "simulacion"),
                            exchange_client=None
                        )
                    else:
                        # ===== BOT NORMAL (Grid, EMA, etc.) =====
                        print(f"📊 Creando bot {cfg.get('estrategia', 'grid')}: {b_id}")
                        n = cfg.get("n_grids", 50)
                        p_min = cfg.get("p_min", 0)
                        p_max = cfg.get("p_max", 0)
                        
                        if n <= 0 or p_min <= 0 or p_max <= 0:
                            print(f"⚠️ Configuración inválida para {b_id}, saltando...")
                            continue
                        
                        if cfg.get("tipo") == "geometrico":
                            r = (p_max / p_min) ** (1 / n)
                            niveles = [round(p_min * (r ** i), precision) for i in range(n + 1)]
                        else:
                            diff = (p_max - p_min) / n
                            niveles = [round(p_min + (diff * i), precision) for i in range(n + 1)]
                        
                        bot = GridBotSim(
                            self, b_id, info["ws_name"], niveles,
                            capital_total=float(cfg.get("capital", 0)),
                            etiqueta=cfg.get("etiqueta", ""),
                            liq_price=float(cfg.get("liquis", 0.0)),
                            monedas_per_grid=float(cfg.get("cantidad", 0.0)),
                            objetivo=float(cfg.get("objetivo", 5)),
                            apalancamiento=int(cfg.get("apalancamiento", 1)),
                            direccion=cfg.get("direccion", "short"),
                            stop_loss=float(cfg.get("stop_loss", 5)),
                            estrategia=cfg.get("estrategia", "grid"),
                            timeframe=cfg.get("timeframe", "1m"),
                            ema_fast=int(cfg.get("ema_fast", 20)),
                            ema_slow=int(cfg.get("ema_slow", 50)),
                            filtro_distancia=float(cfg.get("filtro_distancia", 0.01)),
                            tp_activacion_aire=cfg.get("tp_activacion_aire"),
                            decimales=precision,
                            enable_ema200_cross=cfg.get("enable_ema200_cross", False),
                            ema_slow2=int(cfg.get("ema_slow2", 200)),
                            max_posiciones_scalp=int(cfg.get("max_posiciones_scalp", 3)),
                            callback_scalp=float(cfg.get("callback_scalp", 0.001)),
                            activacion_trailing_en=float(cfg.get("activacion_trailing_en", 100)),
                            tiempo_maximo_segundos=int(cfg.get("tiempo_maximo_segundos", 120))
                        )
                    
                    # Sincronizar estado guardado
                    if self.state:
                        for s in self.state.get("bots", []):
                            if s.get("bot_id") == b_id:
                                bot.trade_counter = s.get("trade_counter", 0)
                                bot.pausado = s.get("pausado", False)
                                bot.pnl_acumulado = s.get("pnl_acumulado", 0.0)
                                bot.comisiones_pagadas = s.get("comisiones_pagadas", 0.0)
                                bot.funding_acumulado = s.get("funding_acumulado", 0.0)
                                bot.trades_cerrados = s.get("trades_cerrados", 0)
                                if s.get("posiciones"):
                                    bot.posiciones = s["posiciones"]
                    
                    self.bots.append(bot)
                    print(f"   ✅ {b_id} cargado")
                    
                except Exception as e:
                    print(f"⚠️ Error creando bot {b_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
    
        print(f"✅ {len(self.bots)} bots inicializados")

    def registrar_latido(self):
        """Registra el latido para el watchdog"""
        ahora = int(time.time())
        # Guardar en Logs/ (donde el watchdog lo espera)
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        archivo = os.path.join(logs_dir, f"last_alive_{VERSION}.txt")
        archivo_tmp = f"{archivo}.tmp"
        
        try:
            # Escribir en archivo temporal (evita archivos corruptos)
            with open(archivo_tmp, "w") as f:
                f.write(str(ahora))
                f.flush()
                os.fsync(f.fileno())
            
            # Renombrar atómicamente
            os.replace(archivo_tmp, archivo)
        except Exception as e:
            print(f"⚠️ Error escribiendo latido: {e}")
    
    def _verificar_downtime(self):
        """Verifica si hubo una caída"""
        if os.path.exists(self.last_alive_file):
            with open(self.last_alive_file, "r") as f:
                try:
                    last_ts = float(f.read())
                    diff = time.time() - last_ts
                    if diff > 120:
                        minutos = int(diff // 60)
                        return f"⚠️ <b>RECONEXIÓN TRAS CAÍDA</b>\n⏱️ Estuve fuera: <code>{minutos} min</code>"
                except:
                    pass
        return None

    async def heartbeat_loop(self):
        """Loop independiente que escribe el latido cada 10 segundos"""
        while True:
            try:
                self.registrar_latido()
            except Exception as e:
                print(f"⚠️ Error en heartbeat: {e}")
            await asyncio.sleep(10)
    
    def guardar_estado(self):
        """Guarda el estado de todos los bots"""
        data = {
            "last_funding_time": self.last_funding_time,
            "start_time": self.start_time,
            "bots": []
        }
        
        for b in self.bots:
            bot_data = {
                "bot_id": b.bot_id,
                "pnl_acumulado": b.pnl_acumulado,
                "comisiones_pagadas": b.comisiones_pagadas,
                "funding_acumulado": b.funding_acumulado,
                "trades_cerrados": b.trades_cerrados,
                "posiciones": b.posiciones,
                "is_liquidated": b.is_liquidated,
                "sl_alcanzado": b.sl_alcanzado,
                "trade_counter": b.trade_counter,
                "pausado": b.pausado,
                "ordenes_pendientes": getattr(b, 'ordenes_pendientes', {}),
                "modo": getattr(b, 'modo', 'simulacion')
            }
            data["bots"].append(bot_data)
        
        self.state_manager.save_state(data)
    
    async def run_websocket(self):
        """Ejecuta el WebSocket de Binance"""
        import websockets
        import json
        
        streams = "/".join([i["ws_name"] + "@markPrice" for i in self.config["SYMBOLS"].values()])
        uri = f"wss://fstream.binance.com/market/stream?streams={streams}"
        
        print(f"🔗 Conectando WebSocket: {uri}")
        
        while True:
            try:
                async with websockets.connect(uri, ping_interval=30, ping_timeout=60, close_timeout=20) as ws:
                    self.websocket = ws
                    print(f"📡 {VERSION} ONLINE - Monitoreando: {list(self.config['SYMBOLS'].keys())}")
                    
                    while True:
                        msg = await ws.recv()
                        try:
                            data = json.loads(msg)['data']
                            s_ws = data['s'].lower()
                            precio = float(data['p'])
                            self.last_prices[s_ws] = precio
                            timestamp_actual = time.time()
                            
                            for bot in self.bots:
                                if bot.symbol_ws == s_ws:
                                    alertas = bot.procesar_precio_v9(precio, timestamp_actual)
                                    if alertas:
                                        self.guardar_estado()
                                    if self.flag_telegram:
                                        for m in alertas:
                                            await self.t_bot.send_message(
                                                chat_id=self.chat_id,
                                                text=f"{m}\n⏰ {datetime.now().strftime('%H:%M')}",
                                                parse_mode='HTML'
                                            )
                        except Exception as e:
                            # ===== AQUÍ DETECTAMOS QUÉ BOT FALLA =====
                            print(f"⚠️ Error procesando BOT {bot.bot_id}: {e}")
                            print(f"   Estrategia: {bot.estrategia}")
                            print(f"   Precio: {precio}")
                            print(f"   Posiciones: {len(bot.posiciones)}")
                            import traceback
                            traceback.print_exc()
                            # Continuar con el siguiente bot
                            continue
                            
            except Exception as e:
                print(f"❌ Error de conexión: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
    
    async def start(self):
        """Inicia el sistema completo"""
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
        
        print("🚀 Iniciando aplicación...")
        
        self.app = ApplicationBuilder().token(self.token).build()
        
        # Registrar comandos
        # ===== REGISTRAR TODOS LOS COMANDOS =====
        # Generales
        self.app.add_handler(CommandHandler("status", self.handlers.status))
        self.app.add_handler(CommandHandler("inspect", self.handlers.inspect))
        self.app.add_handler(CommandHandler("history", self.handlers.history))
        self.app.add_handler(CommandHandler("price", self.handlers.price))
        self.app.add_handler(CommandHandler("help", self.handlers.help))
        self.app.add_handler(CommandHandler("grid_levels", self.handlers.grid_levels))
        
        # Manual Trading
        self.app.add_handler(CommandHandler("entry", self.handlers.entry))
        self.app.add_handler(CommandHandler("exit", self.handlers.exit))
        self.app.add_handler(CommandHandler("exit_all", self.handlers.exit_all))
        self.app.add_handler(CommandHandler("modify", self.handlers.modify))
        self.app.add_handler(CommandHandler("trailing", self.handlers.trailing))
        self.app.add_handler(CommandHandler("cancel", self.handlers.cancel))
        self.app.add_handler(CommandHandler("list_orders", self.handlers.list_orders))
        
        # DCA
        self.app.add_handler(CommandHandler("status_dca", self.handlers.status_dca))
        self.app.add_handler(CommandHandler("send_all", self.handlers.send_all))
        
        # Gestión
        self.app.add_handler(CommandHandler("pause", self.handlers.pause))
        self.app.add_handler(CommandHandler("resume", self.handlers.resume))
        self.app.add_handler(CommandHandler("close", self.handlers.close))
        self.app.add_handler(CommandHandler("close_all", self.handlers.close_all))
        
        # Configuración
        self.app.add_handler(CommandHandler("set_tp", self.handlers.set_tp))
        self.app.add_handler(CommandHandler("set_sl", self.handlers.set_sl))
        
        # Trailing Stats
        self.app.add_handler(CommandHandler("trailing_stats", self.handlers.trailing_stats))
        self.app.add_handler(CommandHandler("set_trailing_stats", self.handlers.set_trailing_stats))
        self.app.add_handler(CommandHandler("reset_trailing_stats", self.handlers.reset_trailing_stats))
        
        # Sistema
        self.app.add_handler(CommandHandler("flag_telegram", self.handlers.flag_telegram))
        self.app.add_handler(CommandHandler("ip", self.handlers.ip))

        # Sistema (comandos esenciales desde el campo)
        self.app.add_handler(CommandHandler("restart", self.handlers.restart))
        self.app.add_handler(CommandHandler("reset_factory", self.handlers.reset_factory))
        self.app.add_handler(CommandHandler("shell", self.handlers.shell))
        self.app.add_handler(CommandHandler("send_file", self.handlers.send_file))
        self.app.add_handler(CommandHandler("send_all_logs", self.handlers.send_all_logs))
        self.app.add_handler(CommandHandler("emas", self.handlers.emas))

        # Handler para recibir documentos
        from telegram.ext import MessageHandler, filters
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handlers.handle_document))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        
        # ===== INICIAR HEARTBEAT LOOP =====
        # Solo crear el heartbeat loop una vez
        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            print("💓 Heartbeat loop iniciado")

        # Enviar saludo
        nombres_bots = [b.bot_id for b in self.bots]
        saludo = (
            f"🚀 <b>SISTEMA {VERSION} INICIADO</b>\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🏠 Entorno: <code>{'TEST' if TEST else 'PRODUCCIÓN'}</code>\n"
            f"🤖 Bots activos: <code>{len(nombres_bots)}</code>\n"
            f"📋 Lista: {', '.join(nombres_bots)}"
        )
        try:
            await self.t_bot.send_message(chat_id=self.chat_id, text=saludo, parse_mode='HTML')
        except Exception as e:
            print(f"⚠️ Error enviando saludo: {e}")
        
        # Iniciar WebSocket
        await self.run_websocket()
    
    async def shutdown(self):
        """Cierra gracefulmente todas las conexiones con timeout"""
        print("🛑 Cerrando conexiones...")
        
        # 1. Cerrar WebSocket de Binance
        if self.websocket is not None:
            try:
                await asyncio.wait_for(self.websocket.close(), timeout=5)
                print("✅ WebSocket cerrado")
            except asyncio.TimeoutError:
                print("⚠️ Timeout cerrando WebSocket")
            except Exception as e:
                print(f"⚠️ Error al cerrar WebSocket: {e}")
        else:
            print("ℹ️ No hay WebSocket activo para cerrar")
        
        # 2. Detener Telegram gracefulmente con timeout extendido
        if self.app is not None:
            try:
                # Detener el updater primero
                await asyncio.wait_for(self.app.updater.stop(), timeout=10)
                print("✅ Updater detenido")
            except asyncio.TimeoutError:
                print("⚠️ Timeout deteniendo updater")
            except Exception as e:
                print(f"⚠️ Error en updater: {e}")
            
            try:
                # Detener la aplicación
                await asyncio.wait_for(self.app.stop(), timeout=10)
                print("✅ App detenida")
            except asyncio.TimeoutError:
                print("⚠️ Timeout deteniendo app")
            except Exception as e:
                print(f"⚠️ Error en app.stop: {e}")
      
            # Eliminar archivo PID
            try:
                if os.path.exists(self.pid_file):
                    os.remove(self.pid_file)
            except:
                pass
                
            try:
                # Shutdown completo
                await asyncio.wait_for(self.app.shutdown(), timeout=10)
                print("✅ Telegram detenido correctamente")
            except asyncio.TimeoutError:
                print("⚠️ Timeout en shutdown de Telegram")
            except Exception as e:
                print(f"⚠️ Error en shutdown: {e}")
        else:
            print("ℹ️ No hay aplicación de Telegram para detener")
        
        # 3. Esperar un momento para que Telegram libere el token
        await asyncio.sleep(2)
        
        # 4. Asegurar que no queden procesos colgados de Telegram
        import subprocess
        try:
            subprocess.run(["pkill", "-f", "python.*Grid_Master"], check=False)
            print("✅ Procesos Python limpiados")
        except:
            pass
        
        print("✅ Shutdown completado")

if __name__ == "__main__":
    while True:
        controller = None
        try:
            controller = MasterController()
            asyncio.run(controller.start())
        except KeyboardInterrupt:
            print("\n👋 Cerrando por solicitud del usuario...")
            if controller:
                try:
                    asyncio.run(controller.shutdown())
                except:
                    pass
            break
        except Exception as e:
            print(f"🔥 Error: {e}. Reiniciando en 5s...")
            if controller:
                try:
                    asyncio.run(controller.shutdown())
                except:
                    pass
            time.sleep(5)
