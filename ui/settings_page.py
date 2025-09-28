from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QPushButton, QGridLayout, QScrollArea, 
    QDialog, QFrame, QLineEdit, QComboBox, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter

import json
from utils import get_data_path
from ui.theme import ModernTheme, IconTheme
from ui.group_management_widget import GroupManagementWidget
from ui.payment_method_management_widget import PaymentMethodManagementWidget
from ui.user_management_page import UserManagementPage
from ui.audit_log_dialog import AuditLogDialog
from ui.backup_dialog import BackupDialog
from ui.shortcut_management_widget import ShortcutManagementWidget


class SettingsButton(QToolButton):
    """Botão estilizado para o painel de controle."""
    def __init__(self, icon_char, text, parent=None):
        super().__init__(parent)
        
        # Converte o caractere do ícone em um QIcon
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        font = QFont()
        font.setPixelSize(32)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, icon_char)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
        self.setText(text)
        self.setIconSize(QSize(48, 48))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setMinimumSize(180, 120)
        self.setStyleSheet(f"""
            QToolButton {{
                background-color: {ModernTheme.WHITE};
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 12px;
                padding: 15px;
                font-size: 14px;
                font-weight: 500;
                color: {ModernTheme.DARK};
            }}
            QToolButton:hover {{
                background-color: #f5f5f5;
                border: 1px solid {ModernTheme.PRIMARY};
            }}
            QToolButton:pressed {{
                background-color: #e0e0e0;
            }}
        """)

class SettingsPage(QWidget):
    def __init__(self, scale_handler, printer_handler, current_user, sales_page=None):
        super().__init__()
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler
        self.current_user = current_user
        self.sales_page = sales_page
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título
        title = QLabel("Painel de Controle")
        title.setObjectName("title")
        main_layout.addWidget(title)

        # Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("scroll_area")
        
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(20)
        
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        self.populate_grid()

    def populate_grid(self):
        # Itens de configuração
        settings_items = [
            ("establishment", "Estabelecimento", IconTheme.DASHBOARD, self.open_establishment_settings),
            ("hardware", "Hardware", IconTheme.SETTINGS, self.open_hardware_settings),
            ("product_groups", "Grupos de Produtos", IconTheme.PRODUCTS, self.open_group_management),
            ("payment_methods", "Formas de Pagamento", IconTheme.SALES, self.open_payment_method_management),
            ("shortcuts", "Atalhos Rápidos", IconTheme.SALES, self.open_shortcut_management),
        ]

        # Adiciona itens de gerente
        if self.current_user.get('role') == 'gerente':
            settings_items.extend([
                ("users", "Usuários", IconTheme.USERS, self.open_user_management),
                ("audit_log", "Log de Auditoria", IconTheme.REPORTS, self.open_audit_log),
                ("backup", "Backup do Sistema", IconTheme.SAVE, self.open_backup_dialog)
            ])

        row, col = 0, 0
        for key, name, icon, method in settings_items:
            button = SettingsButton(icon, name)
            button.clicked.connect(method)
            self.grid_layout.addWidget(button, row, col)
            
            col += 1
            if col > 3: # 4 botões por linha
                col = 0
                row += 1
    
    def open_shortcut_management(self):
        """Abre o diálogo de gerenciamento de atalhos."""
        widget = ShortcutManagementWidget()
        # Conecta o sinal do widget diretamente ao slot da página de vendas
        if self.sales_page:
            widget.shortcuts_changed.connect(self.sales_page.reload_shortcuts)
        self._create_modal_dialog("Gerenciar Atalhos Rápidos", widget)

    def open_audit_log(self):
        """Abre o diálogo de log de auditoria."""
        dialog = AuditLogDialog(self)
        dialog.exec()

    def open_backup_dialog(self):
        """Abre o diálogo de gerenciamento de backup."""
        dialog = BackupDialog(self)
        dialog.exec()

    def _create_modal_dialog(self, title, widget):
        """Cria e executa um diálogo modal com o widget fornecido."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumSize(800, 600)
        dialog.setStyleSheet(ModernTheme.get_main_stylesheet())
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(widget)
        
        # Adiciona um botão de fechar, se o widget não for um dos que já tem controle próprio
        if not isinstance(widget, (UserManagementPage, GroupManagementWidget, PaymentMethodManagementWidget, ShortcutManagementWidget)):
            close_button = QPushButton("Fechar")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)
        
        dialog.exec()

    def open_establishment_settings(self):
        widget = self.create_store_config_widget()
        self._create_modal_dialog("Configurações do Estabelecimento", widget)

    def open_hardware_settings(self):
        widget = self.create_hardware_config_widget()
        self._create_modal_dialog("Configurações de Hardware", widget)

    def open_group_management(self):
        widget = GroupManagementWidget()
        self._create_modal_dialog("Gerenciar Grupos de Produtos", widget)

    def open_payment_method_management(self):
        widget = PaymentMethodManagementWidget()
        self._create_modal_dialog("Gerenciar Formas de Pagamento", widget)

    def open_user_management(self):
        widget = UserManagementPage()
        self._create_modal_dialog("Gerenciar Usuários", widget)

    # --- Métodos para criar os widgets de configuração (reutilizados) ---

    def create_hardware_config_widget(self):
        hardware_widget = QWidget()
        main_layout = QVBoxLayout(hardware_widget)
        
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Abas
        general_tab = self.create_general_hardware_tab()
        scale_tab = self.create_scale_config_widget()
        printer_tab = self.create_printer_config_widget()

        tab_widget.addTab(general_tab, "Geral")
        tab_widget.addTab(scale_tab, "Balança")
        tab_widget.addTab(printer_tab, "Impressora")

        save_button = QPushButton("Salvar Todas as Configurações de Hardware")
        save_button.clicked.connect(self.save_all_hardware_config)
        main_layout.addWidget(save_button)

        self.load_hardware_config_to_ui()
        return hardware_widget

    def create_general_hardware_tab(self):
        general_tab = QWidget()
        layout = QGridLayout(general_tab)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.hardware_mode_combo = QComboBox()
        self.hardware_mode_combo.addItems(["Modo de Teste (Simulado)", "Modo de Produção (Real)"])

        layout.addWidget(QLabel("Modo de Operação:"), 0, 0)
        layout.addWidget(self.hardware_mode_combo, 0, 1)
        
        return general_tab

    def create_store_config_widget(self):
        store_group = QWidget()
        layout = QGridLayout(store_group)
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
        
        self.load_store_config_to_ui()
        return store_group

    def create_printer_config_widget(self):
        printer_group = QWidget()
        layout = QGridLayout(printer_group)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(QLabel("Deixe os campos em branco para usar o modo de simulação."), 1, 0, 1, 2)

        self.printer_vendor_id_input = QLineEdit(placeholderText="Ex: 0x04b8")
        self.printer_product_id_input = QLineEdit(placeholderText="Ex: 0x0202")

        layout.addWidget(QLabel("Vendor ID (Hex):"), 2, 0)
        layout.addWidget(self.printer_vendor_id_input, 2, 1)
        layout.addWidget(QLabel("Product ID (Hex):"), 3, 0)
        layout.addWidget(self.printer_product_id_input, 3, 1)

        return printer_group

    def create_scale_config_widget(self):
        scale_group = QWidget()
        scale_layout = QGridLayout(scale_group)
        scale_layout.setSpacing(10)
        scale_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scale_port_input = QLineEdit()
        self.scale_baud_input = QLineEdit()
        self.scale_bytesize_combo = QComboBox()
        self.scale_bytesize_combo.addItems(["8", "7"])
        self.scale_parity_combo = QComboBox()
        self.scale_parity_combo.addItems(["N (None)", "E (Even)", "O (Odd)"])
        self.scale_stopbits_combo = QComboBox()
        self.scale_stopbits_combo.addItems(["1", "1.5", "2"])
        
        scale_layout.addWidget(QLabel("Porta COM:"), 1, 0)
        scale_layout.addWidget(self.scale_port_input, 1, 1)
        scale_layout.addWidget(QLabel("Baudrate:"), 2, 0)
        scale_layout.addWidget(self.scale_baud_input, 2, 1)
        scale_layout.addWidget(QLabel("Byte Size:"), 3, 0)
        scale_layout.addWidget(self.scale_bytesize_combo, 3, 1)
        scale_layout.addWidget(QLabel("Parity:"), 4, 0)
        scale_layout.addWidget(self.scale_parity_combo, 4, 1)
        scale_layout.addWidget(QLabel("Stop Bits:"), 5, 0)
        scale_layout.addWidget(self.scale_stopbits_combo, 5, 1)
        
        test_button = QPushButton("Testar Conexão com a Balança")
        scale_layout.addWidget(test_button, 7, 0, 1, 2)
        
        test_button.clicked.connect(self.test_scale_connection)
        
        return scale_group

    # --- Métodos de salvar/carregar (reutilizados e adaptados) ---

    def load_config(self):
        try:
            with open(get_data_path('config.json'), 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_config(self, config):
        with open(get_data_path('config.json'), 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

    def load_hardware_config_to_ui(self):
        config = self.load_config()
        
        # Geral
        hardware_mode = config.get('hardware_mode', 'test')
        self.hardware_mode_combo.setCurrentIndex(1 if hardware_mode == 'production' else 0)

        # Balança
        scale_config = config.get('scale', {})
        self.scale_port_input.setText(scale_config.get('port', 'COM3'))
        self.scale_baud_input.setText(str(scale_config.get('baudrate', 9600)))
        self.scale_bytesize_combo.setCurrentText(str(scale_config.get('bytesize', 8)))
        parity_map = {"N": "N (None)", "E": "E (Even)", "O": "O (Odd)"}
        self.scale_parity_combo.setCurrentText(parity_map.get(scale_config.get('parity', 'N')))
        self.scale_stopbits_combo.setCurrentText(str(scale_config.get('stopbits', 1)))

        # Impressora
        printer_config = config.get('printer', {})
        self.printer_vendor_id_input.setText(printer_config.get('vendor_id', ''))
        self.printer_product_id_input.setText(printer_config.get('product_id', ''))

    def save_all_hardware_config(self):
        config = self.load_config()
        
        # Geral
        config['hardware_mode'] = 'production' if self.hardware_mode_combo.currentIndex() == 1 else 'test'

        # Balança
        parity_map = {"N (None)": "N", "E (Even)": "E", "O (Odd)": "O"}
        try:
            scale_config = {
                "port": self.scale_port_input.text(),
                "baudrate": int(self.scale_baud_input.text()),
                "bytesize": int(self.scale_bytesize_combo.currentText()),
                "parity": parity_map.get(self.scale_parity_combo.currentText(), "N"),
                "stopbits": int(self.scale_stopbits_combo.currentText())
            }
            config['scale'] = scale_config
        except ValueError:
            QMessageBox.warning(self, "Erro de Formato", "As configurações da balança (Baudrate, etc.) contêm valores inválidos.")
            return

        # Impressora
        vendor_id_str = self.printer_vendor_id_input.text().strip()
        product_id_str = self.printer_product_id_input.text().strip()
        try:
            if vendor_id_str: int(vendor_id_str, 16)
            if product_id_str: int(product_id_str, 16)
            config['printer'] = {
                "vendor_id": vendor_id_str,
                "product_id": product_id_str
            }
        except ValueError:
            QMessageBox.warning(self, "Erro de Formato", "Vendor ID e Product ID da impressora devem ser valores hexadecimais válidos (ex: 0x04b8).")
            return

        self.save_config(config)
        QMessageBox.information(self, "Sucesso", "Configurações de hardware salvas com sucesso! Reinicie o aplicativo para que todas as alterações entrem em vigor.")


    def load_store_config_to_ui(self):
        store_config = self.load_config().get('store', {})
        self.store_name_input.setText(store_config.get('name', ''))
        self.store_address_input.setText(store_config.get('address', ''))
        self.store_phone_input.setText(store_config.get('phone', ''))
        self.store_cnpj_input.setText(store_config.get('cnpj', ''))

    def save_store_config(self):
        config = self.load_config()
        config['store'] = {
            "name": self.store_name_input.text(),
            "address": self.store_address_input.text(),
            "phone": self.store_phone_input.text(),
            "cnpj": self.store_cnpj_input.text(),
        }
        self.save_config(config)
        QMessageBox.information(self, "Sucesso", "Informações do estabelecimento salvas!")

    def test_scale_connection(self):
        # Salva as configurações da UI no config.json. A própria função já lida com pop-ups de erro.
        self.save_all_hardware_config()

        # Recarrega a configuração para passar ao handler
        config = self.load_config()
        hardware_mode = config.get('hardware_mode', 'test')
        scale_config = config.get('scale', {})

        # Reconfigura o handler. Ele tentará se reconectar em segundo plano.
        self.scale_handler.reconfigure(mode=hardware_mode, **scale_config)

        # Informa o usuário sobre a ação
        QMessageBox.information(self, "Configuração Aplicada", 
                                "As novas configurações da balança foram aplicadas.\n\n" 
                                "O sistema tentará se reconectar em segundo plano. "
                                "Verifique o status no Dashboard.")