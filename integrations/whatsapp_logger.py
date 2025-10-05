"""
Sistema de logging estruturado para integração WhatsApp.
Fornece logs centralizados com níveis apropriados e auditoria de mensagens.
"""
import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from utils import get_data_path

class WhatsAppLogger:
    """
    Logger estruturado para WhatsApp com múltiplos níveis e formatação JSON.
    """

    # Níveis de log específicos para WhatsApp
    LEVEL_CONNECTION = 25  # Entre INFO e WARNING
    LEVEL_MESSAGE = 24     # Entre DEBUG e INFO
    LEVEL_AUDIT = 26       # Entre WARNING e ERROR

    # Categorias de mensagens para melhor organização
    MESSAGE_CATEGORIES = {
        'sale_notification': 'VENDA',
        'cash_opening': 'ABERTURA_CAIXA',
        'cash_closing': 'FECHAMENTO_CAIXA',
        'system_alert': 'ALERTA_SISTEMA',
        'manual_message': 'MANUAL',
        'low_stock_alert': 'ESTOQUE_BAIXO',
        'maintenance': 'MANUTENCAO'
    }

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or get_data_path("whatsapp.log")
        self._setup_logger()
        self._message_log_file = get_data_path("whatsapp_messages.log")
        self._command_log_file = get_data_path("whatsapp_commands.log")
        self._lock = threading.Lock()

    def log_command(self, sender: str, command: str, success: bool, response_preview: str = ""):
        """Log de auditoria para comandos recebidos."""
        command_data = {
            'timestamp': datetime.now().isoformat(),
            'sender': sender,
            'command': command,
            'success': success,
            'response_preview': response_preview[:150]
        }
        self._save_command_audit(command_data)

    def _save_command_audit(self, command_data: Dict[str, Any]):
        """Salva auditoria de comandos em arquivo separado."""
        with self._lock:
            try:
                with open(self._command_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(command_data, ensure_ascii=False) + '\n')
            except Exception as e:
                self.logger.error(f"Falha ao salvar auditoria de comando: {e}", extra={'error_type': 'command_audit_save_failed'})

    def _setup_logger(self):
        """Configura o logger principal com formato JSON estruturado."""
        self.logger = logging.getLogger('whatsapp_integration')
        self.logger.setLevel(logging.DEBUG)

        # Limpar handlers existentes
        self.logger.handlers.clear()

        # Formatter JSON estruturado
        formatter = WhatsAppJSONFormatter()

        # Handler para arquivo
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Handler para console (só warnings e acima)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Adicionar níveis customizados
        logging.addLevelName(self.LEVEL_CONNECTION, "CONNECTION")
        logging.addLevelName(self.LEVEL_MESSAGE, "MESSAGE")
        logging.addLevelName(self.LEVEL_AUDIT, "AUDIT")

    def log_connection(self, message: str, **kwargs):
        """Log de eventos de conexão."""
        self.logger.log(self.LEVEL_CONNECTION, message, extra=kwargs)

    def log_message(self, message: str, **kwargs):
        """Log de operações com mensagens."""
        self.logger.log(self.LEVEL_MESSAGE, message, extra=kwargs)

    def log_audit(self, operation: str, phone: str, message: str, success: bool, **kwargs):
        """Log de auditoria para mensagens enviadas."""
        audit_data = {
            'operation': operation,
            'phone': phone,
            'message_preview': message[:100] + "..." if len(message) > 100 else message,
            'success': success,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }

        # Log estruturado
        self.logger.log(self.LEVEL_AUDIT, f"Audit: {operation}", extra=audit_data)

        # Salvar em arquivo separado para auditoria
        self._save_message_audit(audit_data)

    def log_error(self, error: str, error_type: str = "unknown", **kwargs):
        """Log de erros com categorização."""
        # Incorporate error_type into the message to avoid extra parameter conflicts
        enhanced_message = f"[{error_type}] {error}"

        # Only log traceback if provided
        if 'traceback' in kwargs:
            enhanced_message += f" | Traceback: {kwargs['traceback']}"

        # Simple logging without extra to avoid LogRecord conflicts
        self.logger.error(enhanced_message)

    def log_health_check(self, status: str, **kwargs):
        """Log de verificação de saúde."""
        extra_data = {
            'health_check': True,
            **kwargs
        }
        # Ensure 'message' is not in extra_data
        extra_data.pop('message', None)

        self.logger.info(f"Health check: {status}", extra=extra_data)

    def _save_message_audit(self, audit_data: Dict[str, Any]):
        """Salva auditoria de mensagens em arquivo separado."""
        with self._lock:
            try:
                with open(self._message_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(audit_data, ensure_ascii=False) + '\n')
            except Exception as e:
                self.logger.error(f"Falha ao salvar auditoria: {e}", extra={'error_type': 'audit_save_failed'})

class WhatsAppJSONFormatter(logging.Formatter):
    """Formatter que gera logs em formato JSON estruturado."""

    def format(self, record):
        # Criar dicionário base do log
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': getattr(record, 'module', 'unknown'),
            'function': getattr(record, 'funcName', 'unknown'),
            'line': getattr(record, 'lineno', 0),
        }

        # Adicionar campos extras se existirem
        if hasattr(record, 'error_type'):
            log_data['error_type'] = record.error_type
        if hasattr(record, 'health_check'):
            log_data['health_check'] = record.health_check
        if hasattr(record, 'traceback'):
            log_data['traceback'] = record.traceback

        # Adicionar phone se existir (para anonimização)
        if hasattr(record, 'phone') and record.phone:
            log_data['phone_hash'] = hash(record.phone) % 1000000  # Hash simples para anonimização

        # Mesclar extras restantes (exceto os que já existem)
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                              'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                              'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'error_type', 'health_check', 'traceback', 'phone',
                              'message', 'traceback_info']:
                    if isinstance(value, (str, int, float, bool, type(None))):
                        log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)

# Instância global do logger
_logger_instance = None
_logger_lock = threading.Lock()

def get_whatsapp_logger() -> WhatsAppLogger:
    """Retorna instância singleton do logger WhatsApp."""
    global _logger_instance
    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = WhatsAppLogger()
    return _logger_instance
