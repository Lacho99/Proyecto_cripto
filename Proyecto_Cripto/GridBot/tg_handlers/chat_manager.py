"""
tg_handlers/chat_manager.py
Gestión de múltiples chats de Telegram
"""
import os
from typing import List, Dict, Optional
from telegram import Bot  # ← Esto es la librería real, no el módulo local

class ChatManager:
    def __init__(self, config):
        # TODO: Mover lógica de chat_manager
        pass
    
    def set_bot(self, bot: Bot):
        pass
    
    def get_chat(self, chat_name: str):
        pass
    
    def get_chat_by_id(self, chat_id: int):
        pass
    
    async def send_message(self, chat_name: str, text: str, **kwargs):
        pass
    
    async def send_alert(self, text: str, **kwargs):
        pass
    
    def tiene_permiso(self, chat_id: int, permiso: str) -> bool:
        pass

