"""
core/state.py
Persistencia de estado
"""
import json
import os

class StateManager:
    def __init__(self, version="v9.3", test=True):
        self.version = version
        self.test = test
        self.state = None
        self.path_state = None
    
    def load_state(self, config=None):
        """Carga el estado desde state_trading_{version}.json"""
        if config and "JSON_FILE" in config:
            state_file = config["JSON_FILE"]
        else:
            suffix = "TEST" if self.test else ""
            state_file = f"state_trading{suffix}_{self.version}.json"
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        parent_path = os.path.join(base_dir, "..", state_file)
        
        if os.path.exists(parent_path):
            path = parent_path
        else:
            path = os.path.join(base_dir, state_file)
        
        self.path_state = path
        
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.state = json.load(f)
                return self.state
            except:
                return None
        return None
    
    def save_state(self, state):
        """Guarda el estado"""
        if self.path_state:
            with open(self.path_state, "w") as f:
                json.dump(state, f, indent=4)
    
    def get_bot_state(self, bot_id):
        """Retorna el estado de un bot específico"""
        if not self.state:
            return None
        for bot in self.state.get("bots", []):
            if bot.get("bot_id") == bot_id:
                return bot
        return None
    
    def update_bot_state(self, bot_id, data):
        """Actualiza el estado de un bot específico"""
        if not self.state:
            self.state = {"bots": []}
        
        for i, bot in enumerate(self.state.get("bots", [])):
            if bot.get("bot_id") == bot_id:
                self.state["bots"][i].update(data)
                self.save_state(self.state)
                return True
        
        # Si no existe, agregar
        self.state["bots"].append(data)
        self.save_state(self.state)
        return True
        