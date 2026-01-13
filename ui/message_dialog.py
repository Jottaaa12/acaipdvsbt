from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt

class MessageDialog(QDialog):
    def __init__(self, title, message, icon_type="info", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setObjectName("messageDialog")
        self.setMinimumWidth(350)
        
        # Remove help button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setup_ui(title, message, icon_type)

    def setup_ui(self, title_text, message_text, icon_type):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Icons (Unicode simple placeholders which can be styled or replaced with images)
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✔"
        }
        icon_char = icons.get(icon_type, "ℹ️")

        # Icon Label
        self.icon_label = QLabel(icon_char)
        self.icon_label.setObjectName(f"messageIcon_{icon_type}") # Allows styling specific icons
        self.icon_label.setStyleSheet("font-size: 48px;") # Inline default, can be overridden by CSS
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Title
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("messageTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # Message
        self.message_label = QLabel(message_text)
        self.message_label.setObjectName("messageBody")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 14px; color: #555;")
        layout.addWidget(self.message_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("modern_button_outline")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.setVisible(False) # Default hidden
        button_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("modern_button_primary") # Reusing existing style
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setMinimumHeight(40)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)

        self.ok_button.setFocus()

    @staticmethod
    def show_info(parent, title, message):
        dialog = MessageDialog(title, message, "info", parent)
        dialog.exec()

    @staticmethod
    def show_warning(parent, title, message):
        dialog = MessageDialog(title, message, "warning", parent)
        dialog.exec()

    @staticmethod
    def show_error(parent, title, message):
        dialog = MessageDialog(title, message, "error", parent)
        dialog.exec()

    @staticmethod
    def show_success(parent, title, message):
        dialog = MessageDialog(title, message, "success", parent)
        dialog.exec()
        
    @staticmethod
    def show_confirmation(parent, title, message):
        dialog = MessageDialog(title, message, "question", parent)
        dialog.cancel_button.setVisible(True)
        dialog.cancel_button.setText("Não")
        dialog.ok_button.setText("Sim")
        return dialog.exec() == QDialog.DialogCode.Accepted
