from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class CustomInputDialog(QDialog):
    def __init__(self, title, label_text, default_value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setObjectName("customInputDialog")
        self.setMinimumWidth(400)
        
        # Remove o botão de ajuda da barra de título
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setup_ui(title, label_text, default_value)

    def setup_ui(self, title_text, label_text, default_value):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Título
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("inputDialogTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Label do Campo
        self.field_label = QLabel(label_text)
        self.field_label.setObjectName("inputDialogLabel")
        layout.addWidget(self.field_label)

        # Input
        self.input_field = QLineEdit(default_value)
        self.input_field.setObjectName("inputDialogInput")
        self.input_field.selectAll() # Seleciona todo o texto para facilitar a digitação
        layout.addWidget(self.input_field)

        # Botões
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("inputDialogCancelButton")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setMinimumHeight(40)
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("inputDialogOkButton")
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True) # Enter aciona o OK
        self.ok_button.setMinimumHeight(40)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

    def get_text(self):
        return self.input_field.text()

    @staticmethod
    def get_value(parent, title, label, default_value=""):
        dialog = CustomInputDialog(title, label, default_value, parent)
        result = dialog.exec()
        return dialog.get_text(), result == QDialog.DialogCode.Accepted
