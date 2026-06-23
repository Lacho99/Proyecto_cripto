"""
core/config.py
Carga y gestión de configuración
"""
import json
import os

class ConfigManager:
    def __init__(self, version="v9.3", test=True):
        self.version = version
        self.test = test
        self.config = None
        self.path_config = None
    
    def load_config(self):
        """Carga la configuración desde config_bots_{version}.json"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file = f"config_bots_{self.version}.json"
        
        # Buscar en el directorio padre (Proyecto_Cripto/)
        parent_path = os.path.join(os.path.dirname(base_dir), config_file)
        if os.path.exists(parent_path):
            path = parent_path
        else:
            path = os.path.join(base_dir, config_file)
        
        self.path_config = path
        
        try:
            with open(path, "r") as f:
                self.config = json.load(f)
            
            # Sobrescribir JSON_FILE según modo TEST
            if self.test:
                self.config["JSON_FILE"] = f"state_trading_TEST_{self.version}.json"
            else:
                self.config["JSON_FILE"] = f"state_trading_{self.version}.json"
            
            return self.config
        except FileNotFoundError:
            print(f"❌ Configuración no encontrada: {path}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Error decodificando JSON: {e}")
            return None
    
    def save_config(self, config=None):
        """Guarda la configuración"""
        if config is None:
            config = self.config
        if self.path_config and config:
            with open(self.path_config, "w") as f:
                json.dump(config, f, indent=4)
    
    def get_bots(self):
        """Retorna lista de bots de la configuración"""
        if not self.config:
            return []
        bots = []
        for symbol, info in self.config.get("SYMBOLS", {}).items():
            for bot_id, cfg in info.get("bots", {}).items():
                cfg["symbol"] = symbol
                cfg["ws_name"] = info.get("ws_name")
                cfg["bot_id"] = bot_id
                bots.append(cfg)
        return bots


# ===== FUNCIÓN RÁPIDA PARA IMPORTAR =====
def load_config(version="v9.3", test=True):
    """Función rápida para cargar configuración"""
    manager = ConfigManager(version, test)
    return manager.load_config()