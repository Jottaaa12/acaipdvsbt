# integrations/commands/base_command.py
from abc import ABC, abstractmethod
from typing import List, Any
import database as db
import logging
from decimal import Decimal
from datetime import datetime, timedelta

# Importe o 'manager' type-hinting de forma segura
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager

class BaseCommand(ABC):
    """
    Interface base para um comando que NÃO precisa de acesso ao WhatsAppManager.
    Recebe os argumentos do usuário, o ID do usuário e o ID do chat.
    """
    def __init__(self, args: List[str], user_id: str, chat_id: str):
        self.args = args
        self.user_id = user_id  # Quem enviou o comando
        self.chat_id = chat_id  # De onde o comando foi enviado (grupo ou privado)
        self.db = db
        self.logging = logging

    @abstractmethod
    def execute(self) -> str:
        """Executa o comando e retorna uma string de resposta."""
        pass

class ManagerCommand(BaseCommand):
    """
    Interface base para um comando que PRECISA de acesso ao WhatsAppManager.
    Usado para comandos que precisam verificar status, logar ou interagir com o worker.
    """
    def __init__(self, args: List[str], user_id: str, chat_id: str, manager: 'WhatsAppManager'):
        super().__init__(args, user_id, chat_id)
        self.manager = manager
