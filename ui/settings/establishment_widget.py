from PyQt6.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox
)
from PyQt6.QtCore import Qt
from config_manager import ConfigManager

class EstablishmentWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_store_config_to_ui()

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.store_name_input = QLineEdit()
        self.store_address_input = QLineEdit()
        self.store_phone_input = QLineEdit()
        self.store_cnpj_input = QLineEdit()

        layout.addWidget(QLabel("Nome Fantasia:"), 1, 0)
        layout.addWidget(self.store_name_input, 1, 1)
        layout.addWidget(QLabel("Endereço:"), 2, 0)
        layout.addWidget(self.store_address_input, 2, 1)
        layout.addWidget(QLabel("Telefone/Whatsapp:"), 3, 0)
        layout.addWidget(self.store_phone_input, 3, 1)
        layout.addWidget(QLabel("CNPJ/CPF:"), 4, 0)
        layout.addWidget(self.store_cnpj_input, 4, 1)

        save_button = QPushButton("Salvar Informações")
        save_button.clicked.connect(self.save_store_config)
        layout.addWidget(save_button, 5, 0, 1, 2)

    def load_store_config_to_ui(self):
        store_config = self.config_manager.get_section('store')
        self.store_name_input.setText(store_config.get('name', ''))
        self.store_address_input.setText(store_config.get('address', ''))
        self.store_phone_input.setText(store_config.get('phone', ''))
        self.store_cnpj_input.setText(store_config.get('cnpj', ''))

    def save_store_config(self):
        store_data = {
            "name": self.store_name_input.text(),
            "address": self.store_address_input.text(),
            "phone": self.store_phone_input.text(),
            "cnpj": self.store_cnpj_input.text(),
        }
        self.config_manager.update_section('store', store_data)
        QMessageBox.information(self, "Sucesso", "Informações do estabelecimento salvas!")
