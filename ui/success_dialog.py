from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

class SuccessDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setObjectName("successDialog")
        self.setMinimumWidth(400)
        
        # Remove o botão de ajuda da barra de título
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setup_ui(title, message)

    def setup_ui(self, title_text, message_text):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Ícone de Sucesso (Check grande)
        # Usando um caractere unicode como ícone por enquanto para simplificar, 
        # mas estilizado via CSS para parecer um ícone gráfico
        self.icon_label = QLabel("✔") 
        self.icon_label.setObjectName("successIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Título
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("successTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Mensagem
        self.message_label = QLabel(message_text)
        self.message_label.setObjectName("successMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # Botão OK
        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("successOkButton")
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setMinimumHeight(45)
        layout.addWidget(self.ok_button)

        # Foco no botão OK para fechar rápido com Enter
        self.ok_button.setFocus()
