"""
core/__init__.py
Módulo core: lógica base del bot
"""
from .config import ConfigManager, load_config
from .state import StateManager
from .utils import Utils

# GridBotSim se importa desde bot.py
# from .bot import GridBotSim