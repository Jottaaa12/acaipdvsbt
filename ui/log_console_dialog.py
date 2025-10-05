from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtCore import Qt

class LogConsoleDialog(QDialog):
    """
    Uma janela de diálogo que exibe logs em tempo real.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Console de Logs do Sistema")
        self.setMinimumSize(700, 400)
        self.setModal(False) # Permite interagir com a janela principal

        # Layout principal
        layout = QVBoxLayout(self)

        # Widget de texto para exibir os logs
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))

        # Estilo "terminal escuro" (opcional, mas melhora a legibilidade)
        palette = self.log_output.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(29, 31, 33))
        palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        self.log_output.setPalette(palette)
        
        # Botão para limpar o console
        self.clear_button = QPushButton("Limpar Console")
        self.clear_button.clicked.connect(self.log_output.clear)
        
        # Adicionar widgets ao layout
        layout.addWidget(self.log_output)
        layout.addWidget(self.clear_button)

    def append_log(self, message):
        """
        Slot público para adicionar mensagens de log ao console.
        Este método será conectado ao sinal do QtLogHandler.
        """
        self.log_output.appendPlainText(message)
        # Auto-scroll para a última mensagem
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def closeEvent(self, event):
        """
        Sobrescreve o evento de fechamento para apenas ocultar a janela
        em vez de destruí-la, preservando o histórico de logs.
        """
        self.hide()
        event.ignore()