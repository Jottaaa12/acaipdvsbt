import logging
import traceback
from PyQt6.QtWidgets import QMessageBox, QApplication, QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPixmap, QIcon
from typing import Optional, Callable, Any, Dict
import sys
import os
from datetime import datetime

class ErrorHandler(QObject):
    """
    Sistema centralizado de tratamento de erros para o PDV.
    Fornece tratamento específico para diferentes tipos de erro,
    logging estruturado e feedback visual adequado ao usuário.
    """

    # Sinais para diferentes tipos de erro
    critical_error_occurred = pyqtSignal(str, str)  # título, mensagem
    error_occurred = pyqtSignal(str, str)  # título, mensagem
    warning_occurred = pyqtSignal(str, str)  # título, mensagem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recovery_actions: Dict[str, Callable] = {}
        self.error_count = 0
        self.last_error_time = None

        # Configurar logging específico para erros
        self.error_logger = logging.getLogger('error_handler')
        self.error_logger.setLevel(logging.ERROR)

        # Criar handler para arquivo se não existir
        if not any(isinstance(h, logging.FileHandler) for h in self.error_logger.handlers):
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            file_handler = logging.FileHandler(
                os.path.join(log_dir, f"errors_{datetime.now().strftime('%Y%m%d')}.log")
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s\n%(exc_text)s'
            ))
            self.error_logger.addHandler(file_handler)

    def show_error(self, title: str, message: str, details: str = "",
                  recovery_action: Optional[Callable] = None,
                  parent: Optional[QWidget] = None) -> bool:
        """
        Exibe erro para usuário com opção de ação de recuperação.

        Args:
            title: Título da mensagem de erro
            message: Mensagem principal do erro
            details: Detalhes técnicos do erro
            recovery_action: Função a ser executada para recuperação
            parent: Widget pai para o diálogo

        Returns:
            bool: True se o usuário escolheu tentar novamente
        """

        # Registrar erro no log
        full_message = f"{message}\nDetalhes: {details}" if details else message
        self.error_logger.error(full_message, extra={'exc_text': traceback.format_exc()})

        # Contadores de erro para evitar spam
        current_time = datetime.now()
        if (self.last_error_time and
            (current_time - self.last_error_time).seconds < 5 and
            self.error_count > 3):
            logging.warning("Muitos erros em sequência, suprimindo diálogo para evitar spam")
            return False

        self.error_count += 1
        self.last_error_time = current_time

        # Emitir sinal
        self.error_occurred.emit(title, message)

        # Preparar mensagem detalhada
        full_message = message
        if details:
            full_message += f"\n\nDetalhes técnicos:\n{details}"

        # Criar diálogo de erro
        msg_box = QMessageBox(parent or self.parent())
        msg_box.setIcon(QMessageBox.Icon.Error)
        msg_box.setWindowTitle(title)
        msg_box.setText(full_message)

        # Adicionar botão de recuperação se disponível
        if recovery_action:
            retry_btn = msg_box.addButton("Tentar Novamente", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)

            if msg_box.exec() == 0:  # Usuário clicou em "Tentar Novamente"
                try:
                    recovery_action()
                    return True
                except Exception as e:
                    self.show_error("Erro na Recuperação",
                                  f"Falha ao executar ação de recuperação: {str(e)}",
                                  traceback.format_exc())
                    return False
        else:
            msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            msg_box.exec()

        return False

    def handle_database_error(self, error: Exception, operation: str,
                            recovery_action: Optional[Callable] = None) -> bool:
        """
        Tratamento específico de erros de banco de dados.

        Args:
            error: Exceção do banco de dados
            operation: Operação que estava sendo executada
            recovery_action: Ação de recuperação específica

        Returns:
            bool: True se conseguiu recuperar
        """

        error_msg = f"Erro no banco de dados durante {operation}"
        details = f"Tipo: {type(error).__name__}\nErro: {str(error)}"

        # Tratamento específico por tipo de erro SQLite
        if "UNIQUE constraint failed" in str(error):
            error_msg = f"Erro de duplicação durante {operation}"
            details = "Já existe um registro com estes dados únicos."
        elif "FOREIGN KEY constraint failed" in str(error):
            error_msg = f"Erro de referência durante {operation}"
            details = "Não é possível excluir este registro pois está sendo usado por outros dados."
        elif "NOT NULL constraint failed" in str(error):
            error_msg = f"Erro de dados obrigatórios durante {operation}"
            details = "Alguns campos obrigatórios não foram preenchidos."
        elif "no such table" in str(error).lower():
            error_msg = "Estrutura do banco de dados desatualizada"
            details = "O banco de dados precisa ser atualizado. Execute a migração."

        return self.show_error(
            "Erro de Banco de Dados",
            error_msg,
            details,
            recovery_action
        )

    def handle_hardware_error(self, error: Exception, device: str,
                            recovery_action: Optional[Callable] = None) -> bool:
        """
        Tratamento específico de erros de hardware.

        Args:
            error: Exceção do hardware
            device: Nome do dispositivo (balança, impressora, etc.)
            recovery_action: Ação de recuperação específica

        Returns:
            bool: True se conseguiu recuperar
        """

        error_msg = f"Erro no dispositivo {device}"
        details = f"Tipo: {type(error).__name__}\nErro: {str(error)}"

        # Tratamento específico por dispositivo
        if device.lower() == "balança":
            error_msg = "Erro na balança conectada"
            details = "Verifique se a balança está ligada e conectada corretamente."
        elif device.lower() == "impressora":
            error_msg = "Erro na impressora térmica"
            details = "Verifique se a impressora está ligada e com papel."

        return self.show_error(
            f"Erro de Hardware - {device.title()}",
            error_msg,
            details,
            recovery_action
        )

    def handle_network_error(self, error: Exception, operation: str,
                           recovery_action: Optional[Callable] = None) -> bool:
        """
        Tratamento específico de erros de rede/internet.

        Args:
            error: Exceção de rede
            operation: Operação que estava sendo executada
            recovery_action: Ação de recuperação específica

        Returns:
            bool: True se conseguiu recuperar
        """

        error_msg = f"Erro de conexão durante {operation}"
        details = f"Tipo: {type(error).__name__}\nErro: {str(error)}"

        # Tratamento específico por tipo de erro de rede
        if "ConnectionError" in str(type(error)) or "Timeout" in str(error):
            error_msg = "Sem conexão com a internet"
            details = "Verifique sua conexão com a internet e tente novamente."
        elif "HTTP" in str(error):
            error_msg = "Erro no servidor remoto"
            details = "O servidor pode estar temporariamente indisponível."

        return self.show_error(
            "Erro de Conexão",
            error_msg,
            details,
            recovery_action
        )

    def handle_validation_error(self, field_name: str, error_message: str,
                              parent: Optional[QWidget] = None) -> None:
        """
        Tratamento específico de erros de validação de entrada.

        Args:
            field_name: Nome do campo com erro
            error_message: Mensagem de erro da validação
            parent: Widget pai para o diálogo
        """

        self.error_logger.warning(f"Erro de validação em {field_name}: {error_message}")

        msg_box = QMessageBox(parent or self.parent())
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Erro de Validação")
        msg_box.setText(f"Campo '{field_name}' inválido:")
        msg_box.setInformativeText(error_message)
        msg_box.addButton("Corrigir", QMessageBox.ButtonRole.AcceptRole)
        msg_box.exec()

    def show_warning(self, title: str, message: str, parent: Optional[QWidget] = None) -> None:
        """
        Exibe aviso para o usuário.

        Args:
            title: Título do aviso
            message: Mensagem do aviso
            parent: Widget pai para o diálogo
        """

        self.error_logger.warning(f"Aviso: {title} - {message}")
        self.warning_occurred.emit(title, message)

        msg_box = QMessageBox(parent or self.parent())
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg_box.exec()

    def show_critical_error(self, title: str, message: str,
                          details: str = "", parent: Optional[QWidget] = None) -> None:
        """
        Exibe erro crítico que pode exigir o fechamento da aplicação.

        Args:
            title: Título do erro crítico
            message: Mensagem do erro
            details: Detalhes técnicos
            parent: Widget pai para o diálogo
        """

        full_message = f"{message}\n\nDetalhes técnicos:\n{details}" if details else message

        self.error_logger.critical(full_message, extra={
            'exc_text': traceback.format_exc(),
            'error_count': self.error_count
        })

        self.critical_error_occurred.emit(title, message)

        msg_box = QMessageBox(parent or self.parent())
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(full_message)
        msg_box.addButton("Fechar Aplicação", QMessageBox.ButtonRole.AcceptRole)
        msg_box.exec()

        # Registrar erro crítico no log do sistema
        logging.critical(f"Erro crítico detectado: {title} - {message}")

    def register_recovery_action(self, action_name: str, action: Callable) -> None:
        """
        Registra uma ação de recuperação para uso posterior.

        Args:
            action_name: Nome identificador da ação
            action: Função a ser executada
        """
        self.recovery_actions[action_name] = action
        logging.info(f"Ação de recuperação registrada: {action_name}")

    def execute_recovery_action(self, action_name: str) -> bool:
        """
        Executa uma ação de recuperação registrada.

        Args:
            action_name: Nome da ação registrada

        Returns:
            bool: True se a ação foi executada com sucesso
        """
        if action_name in self.recovery_actions:
            try:
                self.recovery_actions[action_name]()
                logging.info(f"Ação de recuperação executada: {action_name}")
                return True
            except Exception as e:
                self.show_error(
                    "Erro na Recuperação",
                    f"Falha ao executar ação '{action_name}'",
                    str(e)
                )
                return False
        else:
            self.show_error(
                "Ação Não Encontrada",
                f"Ação de recuperação '{action_name}' não foi registrada"
            )
            return False

    def reset_error_count(self) -> None:
        """Reseta contador de erros (útil após período sem erros)."""
        self.error_count = 0
        self.last_error_time = None

    def get_error_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de erros.

        Returns:
            Dict com estatísticas de erro
        """
        return {
            'error_count': self.error_count,
            'last_error_time': self.last_error_time,
            'recovery_actions_count': len(self.recovery_actions)
        }

# Instância global do ErrorHandler
error_handler = ErrorHandler()

def setup_global_error_handler() -> None:
    """
    Configura tratamento global de exceções não tratadas.
    Deve ser chamado no início da aplicação.
    """

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Tratador global de exceções não tratadas."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Não trata KeyboardInterrupt (Ctrl+C)
            return

        error_details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        error_handler.show_critical_error(
            "Erro Fatal Não Tratado",
            "Ocorreu um erro inesperado na aplicação.",
            error_details
        )

        # Continua com o tratamento padrão do Python
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    # Substitui o tratador de exceção padrão
    sys.excepthook = global_exception_handler
    logging.info("Tratamento global de erros configurado")
