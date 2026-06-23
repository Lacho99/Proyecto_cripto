"""
core/__init__.py
Módulo core: lógica base del bot
"""
from .bot import GridBotSim
from .config import ConfigManager, load_config
from .state import StateManager
from .utils import Utils