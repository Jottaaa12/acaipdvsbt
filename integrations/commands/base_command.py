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
    Recebe apenas os argumentos do usuário.
    """
    def __init__(self, args: List[str]):
        self.args = args
        self.db = db  # Disponibiliza o módulo de banco de dados para todos os comandos
        self.logging = logging

    @abstractmethod
    def execute(self) -> str:
        """Executa o comando e retorna uma string de resposta."""
        pass

class ManagerCommand(BaseCommand):
    """
    Interface base para um comando que PRECISA de acesso ao WhatsAppManager.
    Usado para comandos que precisam verificar status, logar ou interagir com o worker (ex: /status, /logs, /sistema).
    """
    def __init__(self, args: List[str], manager: 'WhatsAppManager'):
        super().__init__(args)
        self.manager = manager
