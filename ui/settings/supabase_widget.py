from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import Qt
from config_manager import ConfigManager

class SupabaseWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_config_to_ui()

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        group_box = QGroupBox("Configurações de Sincronização (Supabase)")
        group_layout = QGridLayout()

        self.supabase_url_input = QLineEdit()
        self.supabase_key_input = QLineEdit()
        self.supabase_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        group_layout.addWidget(QLabel("URL do Supabase:"), 0, 0)
        group_layout.addWidget(self.supabase_url_input, 0, 1)
        group_layout.addWidget(QLabel("Chave de Acesso (public-anon):"), 1, 0)
        group_layout.addWidget(self.supabase_key_input, 1, 1)

        group_box.setLayout(group_layout)
        layout.addWidget(group_box, 0, 0, 1, 2)

        save_button = QPushButton("Salvar Configurações de Sincronização")
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button, 1, 0, 1, 2)

    def load_config_to_ui(self):
        supabase_config = self.config_manager.get_section('supabase')
        self.supabase_url_input.setText(supabase_config.get('url', ''))
        self.supabase_key_input.setText(supabase_config.get('key', ''))

    def save_config(self):
        supabase_data = {
            "url": self.supabase_url_input.text(),
            "key": self.supabase_key_input.text(),
        }
        self.config_manager.update_section('supabase', supabase_data)
        QMessageBox.information(self, "Sucesso", "Configurações do Supabase salvas com sucesso!")
