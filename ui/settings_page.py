from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QPushButton, QGridLayout, QScrollArea,
    QDialog, QFrame, QLineEdit, QComboBox, QMessageBox, QTabWidget, QListWidget, QHBoxLayout,
    QCheckBox, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter
from datetime import datetime
import logging

import json
from utils import get_data_path
from ui.theme import ModernTheme, IconTheme
from ui.group_management_widget import GroupManagementWidget
from ui.payment_method_management_widget import PaymentMethodManagementWidget
from ui.data_management_dialog import DataManagementDialog
from ui.user_management_page import UserManagementPage
from ui.audit_log_dialog import AuditLogDialog
from ui.backup_dialog import BackupDialog
from ui.shortcut_management_widget import ShortcutManagementWidget


class QRCodeDialog(QDialog):
    """Um diálogo modal simples para exibir o QR Code do WhatsApp de forma clara."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Escaneie o QR Code - Conexão WhatsApp")
        self.setModal(True)
        self.setMinimumSize(400, 450)
        self.setStyleSheet(f"background-color: {ModernTheme.WHITE};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        info_label = QLabel("Abra o WhatsApp no seu celular e escaneie o código abaixo:")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(info_label)

        self.qr_label = QLabel("Gerando QR Code...")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(350, 350)
        self.qr_label.setStyleSheet(f"""
            QLabel {{
                background-color: {ModernTheme.GRAY_LIGHTER};
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Aguardando leitura...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; color: #6c757d;")
        layout.addWidget(self.status_label)

    def set_qr_pixmap(self, pixmap):
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.qr_label.setPixmap(scaled_pixmap)
            self.qr_label.setText("")
        else:
            self.qr_label.setText("Falha ao carregar QR Code.")
            self.status_label.setText("Por favor, tente novamente.")

    def update_status(self, text):
        self.status_label.setText(text)


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
    operation_mode_changed = pyqtSignal()
    open_log_console_requested = pyqtSignal()

    def __init__(self, scale_handler, printer_handler, current_user, sales_page=None):
        super().__init__()
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler
        self.current_user = current_user
        self.sales_page = sales_page

        # Inicializar atributos dos widgets de notificação
        self.sales_notifications_checkbox = None
        self.min_sale_value_input = None
        self.cash_opening_checkbox = None
        self.cash_closing_checkbox = None
        self.recipients_list = None
        self.new_recipient_input = None
        self.add_recipient_button = None
        self.remove_recipient_button = None
        self.notification_delay_input = None
        self.stock_alerts_checkbox = None
        self.qr_code_dialog = None # Janela para exibir o QR Code

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
                ("whatsapp", "Configuração WhatsApp", IconTheme.SALES, self.open_whatsapp_settings),
                ("backup", "Backup do Sistema", IconTheme.SAVE, self.open_backup_dialog),
                ("data_management", "Gerenciamento de Dados", IconTheme.DATABASE, self.open_data_management),
                ("log_console", "Console de Logs", IconTheme.REPORTS, self.open_log_console_requested.emit)
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
        """Abre o diálogo de gerenciamento de atalhos e garante a atualização da tela de vendas."""
        widget = ShortcutManagementWidget()
        
        # Abre o diálogo. A execução do código fica "pausada" aqui até o diálogo ser fechado.
        self._create_modal_dialog("Gerenciar Atalhos Rápidos", widget)

        # --- INÍCIO DA CORREÇÃO ---
        # Esta linha SÓ SERÁ executada DEPOIS que a janela de gerenciamento for fechada.
        # Verificamos se a referência à página de vendas existe e, em caso afirmativo,
        # chamamos seu método para recarregar e recriar os botões de atalho.
        if self.sales_page:
            self.sales_page.reload_shortcuts()
        # --- FIM DA CORREÇÃO ---

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

    def open_data_management(self):
        dialog = DataManagementDialog(self.current_user, self)
        dialog.data_deleted.connect(self._handle_data_deleted)  # Conecta o sinal
        dialog.exec()

    def _handle_data_deleted(self):
        # Opcional: Recarregar dados ou atualizar a UI após a exclusão
        QMessageBox.information(self, "Sucesso", "Dados históricos foram excluídos. Recomenda-se reiniciar a aplicação.")
        # Poderíamos forçar um logout ou reiniciar a aplicação aqui, se necessário.

    def _populate_settings_list(self):
        self.settings_list.clear()
        self.stacked_widget.clear()
        self.stacked_widget.addWidget(self.general_settings_page) # Adiciona a página de configurações gerais primeiro
        self.settings_list.addItem(self._create_list_item("Geral", IconTheme.SETTINGS, self.open_general_settings))

        # Opções para gerentes
        if self.user['role'] == 'gerente':
            self.user_management_page = UserManagementPage(self.user)
            self.stacked_widget.addWidget(self.user_management_page)
            self.settings_list.addItem(self._create_list_item("Usuários", IconTheme.USERS, self.open_user_management))

            self.payment_method_management_widget = PaymentMethodManagementWidget()
            self.stacked_widget.addWidget(self.payment_method_management_widget)
            self.settings_list.addItem(self._create_list_item("Formas de Pagamento", IconTheme.SALES, self.open_payment_method_management))

            # Nova opção para gerenciamento de dados
            self.settings_list.addItem(self._create_list_item("Gerenciamento de Dados", IconTheme.DATABASE, self.open_data_management))

    def open_user_management(self):
        widget = UserManagementPage()
        self._create_modal_dialog("Gerenciar Usuários", widget)

    def open_whatsapp_settings(self):
        widget = self.create_whatsapp_config_widget()

        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()

        # Conecta os sinais ANTES de mostrar o diálogo
        manager.qr_code_ready.connect(self._show_qr_code_dialog)
        manager.status_updated.connect(self._handle_whatsapp_connection_status)
        manager.error_occurred.connect(self._handle_whatsapp_connection_status)
        manager.log_updated.connect(self.on_whatsapp_log_updated)

        self._create_modal_dialog("Configurações do WhatsApp", widget)

        # Desconecta os sinais DEPOIS que o diálogo for fechado para evitar erros
        try:
            manager.qr_code_ready.disconnect(self._show_qr_code_dialog)
            manager.status_updated.disconnect(self._handle_whatsapp_connection_status)
            manager.error_occurred.disconnect(self._handle_whatsapp_connection_status)
            manager.log_updated.disconnect(self.on_whatsapp_log_updated)
        except TypeError:
            # Ignora o erro que pode ocorrer se os sinais nunca foram conectados
            pass

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

        # Tipo de impressora
        layout.addWidget(QLabel("Tipo de Impressora:"), 0, 0)
        self.printer_type_combo = QComboBox()
        self.printer_type_combo.addItems([
            "Desabilitada",
            "Térmica (USB)",
            "Térmica (Bluetooth)",
            "Térmica (Serial)",
            "Térmica (Rede)",
            "Impressora do Sistema (A4)"
        ])
        self.printer_type_combo.currentTextChanged.connect(self.on_printer_type_changed)
        layout.addWidget(self.printer_type_combo, 0, 1)

        # Campos USB
        self.usb_group = QWidget()
        usb_layout = QVBoxLayout(self.usb_group)
        usb_layout.setContentsMargins(0, 10, 0, 0)

        self.printer_vendor_id_input = QLineEdit(placeholderText="Ex: 0x04b8")
        self.printer_product_id_input = QLineEdit(placeholderText="Ex: 0x0e28")

        usb_layout.addWidget(QLabel("Vendor ID (Hex):"))
        usb_layout.addWidget(self.printer_vendor_id_input)
        usb_layout.addWidget(QLabel("Product ID (Hex):"))
        usb_layout.addWidget(self.printer_product_id_input)

        # Campos Bluetooth
        self.bluetooth_group = QWidget()
        bluetooth_layout = QVBoxLayout(self.bluetooth_group)
        bluetooth_layout.setContentsMargins(0, 10, 0, 0)

        self.bluetooth_port_input = QLineEdit(placeholderText="Ex: COM3")
        self.bluetooth_search_button = QPushButton("Procurar Portas")
        self.bluetooth_search_button.clicked.connect(self.search_com_ports)

        bluetooth_layout.addWidget(QLabel("Porta Bluetooth:"))
        bluetooth_layout.addWidget(self.bluetooth_port_input)
        bluetooth_layout.addWidget(self.bluetooth_search_button)

        # Campos Serial
        self.serial_group = QWidget()
        serial_layout = QVBoxLayout(self.serial_group)
        serial_layout.setContentsMargins(0, 10, 0, 0)

        self.serial_port_input = QLineEdit(placeholderText="Ex: COM1")
        self.serial_baudrate_input = QLineEdit(placeholderText="9600")
        self.serial_search_button = QPushButton("Procurar Portas")
        self.serial_search_button.clicked.connect(self.search_com_ports)

        serial_layout.addWidget(QLabel("Porta Serial:"))
        serial_layout.addWidget(self.serial_port_input)
        serial_layout.addWidget(QLabel("Baudrate:"))
        serial_layout.addWidget(self.serial_baudrate_input)
        serial_layout.addWidget(self.serial_search_button)

        # Campos Rede
        self.network_group = QWidget()
        network_layout = QVBoxLayout(self.network_group)
        network_layout.setContentsMargins(0, 10, 0, 0)

        self.network_ip_input = QLineEdit(placeholderText="Ex: 192.168.1.100")
        self.network_port_input = QLineEdit(placeholderText="9100")

        network_layout.addWidget(QLabel("Endereço IP:"))
        network_layout.addWidget(self.network_ip_input)
        network_layout.addWidget(QLabel("Porta:"))
        network_layout.addWidget(self.network_port_input)

        # Adiciona todos os grupos ao layout principal
        layout.addWidget(self.usb_group, 1, 0, 1, 2)
        layout.addWidget(self.bluetooth_group, 2, 0, 1, 2)
        layout.addWidget(self.serial_group, 3, 0, 1, 2)
        layout.addWidget(self.network_group, 4, 0, 1, 2)

        # Botão de teste
        self.test_printer_button = QPushButton("Testar Impressora")
        self.test_printer_button.clicked.connect(self.test_printer_connection)
        layout.addWidget(self.test_printer_button, 5, 0, 1, 2)

        # Inicialmente esconde todos os grupos
        self.on_printer_type_changed("Desabilitada")

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

        # Impressora - carrega as configurações usando o novo método
        self.load_printer_config_to_ui()

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

        # Impressora - usa o novo método de salvar
        self.save_printer_config()

        self.save_config(config)
        QMessageBox.information(self, "Sucesso", "Configurações de hardware salvas com sucesso!")
        self.operation_mode_changed.emit()


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

    def load_whatsapp_config_to_ui(self):
        whatsapp_config = self.load_config().get('whatsapp', {})
        self.whatsapp_phone_input.setText(whatsapp_config.get('notification_number', ''))

    def save_whatsapp_config(self):
        config = self.load_config()
        if 'whatsapp' not in config:
            config['whatsapp'] = {}
        config['whatsapp']['notification_number'] = self.whatsapp_phone_input.text()
        self.save_config(config)
        QMessageBox.information(self, "Sucesso", "Configurações do WhatsApp salvas!")

    def test_scale_connection(self):
        # Desabilitar botão durante o teste
        sender = self.sender()
        if sender:
            original_text = sender.text()
            sender.setEnabled(False)
            sender.setText("🔄 Testando...")

        try:
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

        finally:
            # Reabilitar botão
            if sender:
                sender.setEnabled(True)
                sender.setText(original_text)

    def on_printer_type_changed(self, printer_type):
        """Mostra/esconde os campos de configuração baseado no tipo de impressora selecionado."""
        # Esconde todos os grupos primeiro
        self.usb_group.hide()
        self.bluetooth_group.hide()
        self.serial_group.hide()
        self.network_group.hide()

        # Mostra apenas o grupo relevante
        if printer_type == "Térmica (USB)":
            self.usb_group.show()
        elif printer_type == "Térmica (Bluetooth)":
            self.bluetooth_group.show()
        elif printer_type == "Térmica (Serial)":
            self.serial_group.show()
        elif printer_type == "Térmica (Rede)":
            self.network_group.show()
        elif printer_type == "Impressora do Sistema (A4)":
            # Para impressora do sistema, não precisamos de configurações adicionais
            pass

    def search_com_ports(self):
        """Abre um diálogo para procurar e selecionar portas COM disponíveis."""
        try:
            from hardware.printer_handler import PrinterHandler
            available_ports = PrinterHandler.get_available_com_ports()

            if not available_ports:
                QMessageBox.information(self, "Procurar Portas",
                                      "Nenhuma porta COM foi encontrada no sistema.")
                return

            # Cria o diálogo de seleção de porta
            dialog = QDialog(self)
            dialog.setWindowTitle("Selecionar Porta COM")
            dialog.setModal(True)
            dialog.resize(400, 300)

            layout = QVBoxLayout(dialog)

            # Lista de portas
            port_list = QListWidget()
            for port in available_ports:
                port_list.addItem(port)

            layout.addWidget(QLabel("Portas COM disponíveis:"))
            layout.addWidget(port_list)

            # Botões
            button_layout = QHBoxLayout()

            select_button = QPushButton("Selecionar")
            select_button.clicked.connect(dialog.accept)
            cancel_button = QPushButton("Cancelar")
            cancel_button.clicked.connect(dialog.reject)

            button_layout.addWidget(select_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            # Se o usuário selecionou uma porta, preenche o campo apropriado
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_port = port_list.currentItem()
                if selected_port:
                    port_name = selected_port.text()

                    # Determina qual campo preencher baseado no botão que foi clicado
                    sender = self.sender()
                    if sender == self.bluetooth_search_button:
                        self.bluetooth_port_input.setText(port_name)
                    elif sender == self.serial_search_button:
                        self.serial_port_input.setText(port_name)

        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao procurar portas COM: {e}")

    def test_printer_connection(self):
        """Testa a conexão com a impressora usando as configurações atuais."""
        # Desabilitar botão durante o teste
        sender = self.sender()
        if sender:
            original_text = sender.text()
            sender.setEnabled(False)
            sender.setText("🔄 Testando...")

        try:
            # Salva as configurações atuais primeiro
            self.save_printer_config()

            # Recarrega a configuração
            config = self.load_config()
            printer_config = config.get('printer', {})

            # Importa o PrinterHandler localmente
            from hardware.printer_handler import PrinterHandler

            # Cria um handler temporário para teste
            temp_handler = PrinterHandler(printer_config)

            # Testa a conexão
            success, message = temp_handler.test_print()

            if success:
                QMessageBox.information(self, "Teste de Impressora",
                                      f"Teste realizado com sucesso!\n\n{message}")
            else:
                QMessageBox.warning(self, "Teste de Impressora",
                                  f"Falha no teste:\n\n{message}")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao testar impressora: {e}")

    def load_printer_config_to_ui(self):
        """Carrega as configurações da impressora para a interface."""
        config = self.load_config()
        printer_config = config.get('printer', {})

        # Tipo de impressora
        type_mapping = {
            'disabled': 'Desabilitada',
            'thermal_usb': 'Térmica (USB)',
            'thermal_bluetooth': 'Térmica (Bluetooth)',
            'thermal_serial': 'Térmica (Serial)',
            'thermal_network': 'Térmica (Rede)',
            'system_printer': 'Impressora do Sistema (A4)'
        }

        printer_type = type_mapping.get(printer_config.get('type', 'disabled'), 'Desabilitada')
        self.printer_type_combo.setCurrentText(printer_type)

        # Campos USB
        self.printer_vendor_id_input.setText(printer_config.get('usb_vendor_id', ''))
        self.printer_product_id_input.setText(printer_config.get('usb_product_id', ''))

        # Campos Bluetooth
        self.bluetooth_port_input.setText(printer_config.get('bluetooth_port', ''))

        # Campos Serial
        self.serial_port_input.setText(printer_config.get('serial_port', ''))
        self.serial_baudrate_input.setText(str(printer_config.get('serial_baudrate', 9600)))

        # Campos Rede
        self.network_ip_input.setText(printer_config.get('network_ip', ''))
        self.network_port_input.setText(str(printer_config.get('network_port', 9100)))

    def save_printer_config(self):
        """Salva as configurações da impressora da interface."""
        config = self.load_config()

        # Mapeia o texto do combo para o valor interno
        type_mapping = {
            'Desabilitada': 'disabled',
            'Térmica (USB)': 'thermal_usb',
            'Térmica (Bluetooth)': 'thermal_bluetooth',
            'Térmica (Serial)': 'thermal_serial',
            'Térmica (Rede)': 'thermal_network',
            'Impressora do Sistema (A4)': 'system_printer'
        }

        printer_type = type_mapping.get(self.printer_type_combo.currentText(), 'disabled')

        printer_config = {
            'type': printer_type,
            'usb_vendor_id': self.printer_vendor_id_input.text().strip(),
            'usb_product_id': self.printer_product_id_input.text().strip(),
            'bluetooth_port': self.bluetooth_port_input.text().strip(),
            'serial_port': self.serial_port_input.text().strip(),
            'serial_baudrate': int(self.serial_baudrate_input.text()) if self.serial_baudrate_input.text() else 9600,
            'network_ip': self.network_ip_input.text().strip(),
            'network_port': int(self.network_port_input.text()) if self.network_port_input.text() else 9100,
        }

        config['printer'] = printer_config
        self.save_config(config)

    def create_whatsapp_config_widget(self):
        """Cria o widget de configuração do WhatsApp com um design moderno e funcional."""
        whatsapp_widget = QWidget()
        main_layout = QVBoxLayout(whatsapp_widget)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Abas
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Aba 1: Conexão (totalmente redesenhada)
        connection_tab = self._create_whatsapp_connection_tab()
        tab_widget.addTab(connection_tab, "Conexão")

        # Aba 2: Notificações (reutilizada)
        notifications_tab = self.create_notifications_tab()
        tab_widget.addTab(notifications_tab, "Notificações")

        # Aba 3: Instruções (reutilizada)
        instructions_tab = QWidget()
        instructions_layout = QVBoxLayout(instructions_tab)
        instructions = QLabel(
            "<b>Como conectar o WhatsApp:</b><br><br>"
            "1. Clique em <b>Conectar</b> para gerar o QR Code.<br>"
            "2. Abra o WhatsApp no seu celular.<br>"
            "3. Toque no ícone de menu (⋮) → 'Aparelhos conectados' → 'Conectar um aparelho'.<br>"
            "4. Escaneie o QR Code mostrado nesta tela.<br>"
            "5. Aguarde a confirmação de conexão estabelecida.<br><br>"
            "<b>Dica:</b> Após conectar, a sessão será salva. Você não precisará ler o QR Code novamente, a menos que clique em <b>Desconectar</b>."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 13px; line-height: 1.5;")
        instructions_layout.addWidget(instructions)
        instructions_layout.addStretch()
        tab_widget.addTab(instructions_tab, "Instruções")

        # Carregar dados e verificar status inicial
        self.load_whatsapp_config_to_ui()
        
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()
        self._update_whatsapp_ui_state('connected' if manager.is_ready else 'disconnected')

        return whatsapp_widget

    def _create_whatsapp_connection_tab(self):
        """Cria a aba de conexão com design renovado e QR Code em janela separada."""
        connection_tab = QWidget()
        layout = QVBoxLayout(connection_tab)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. Seção de Status
        status_group = QGroupBox("Status da Conexão")
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(10)
        
        self.whatsapp_status_indicator = QLabel()
        self.whatsapp_status_indicator.setFixedSize(20, 20)
        
        self.whatsapp_status_text = QLabel("Verificando...")
        self.whatsapp_status_text.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        status_layout.addWidget(self.whatsapp_status_indicator)
        status_layout.addWidget(self.whatsapp_status_text)
        status_layout.addStretch()
        layout.addWidget(status_group)

        # 2. Seção de Ações e Testes
        actions_group = QGroupBox("Ações e Testes")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(15)

        # Linha 1: Botões de Ação
        buttons_layout = QHBoxLayout()
        self.whatsapp_connect_button = QPushButton("Conectar")
        self.whatsapp_connect_button.setMinimumHeight(40)
        self.whatsapp_connect_button.clicked.connect(self._toggle_whatsapp_connection)
        
        self.send_test_button = QPushButton("Enviar Mensagem de Teste")
        self.send_test_button.setMinimumHeight(40)
        self.send_test_button.clicked.connect(self.send_test_whatsapp_message)
        
        buttons_layout.addWidget(self.whatsapp_connect_button)
        buttons_layout.addWidget(self.send_test_button)
        buttons_layout.addStretch()
        actions_layout.addLayout(buttons_layout)

        # Linha 2: Campo para número de teste
        test_number_widget = QWidget()
        test_number_layout = QHBoxLayout(test_number_widget)
        test_number_layout.setContentsMargins(0,0,0,0)
        test_number_label = QLabel("Nº para Notificações (Gerente):")
        self.whatsapp_phone_input = QLineEdit(placeholderText="Ex: 5511912345678")
        self.save_whatsapp_button = QPushButton("Salvar")
        self.save_whatsapp_button.clicked.connect(self.save_whatsapp_config)
        test_number_layout.addWidget(test_number_label)
        test_number_layout.addWidget(self.whatsapp_phone_input, 1)
        test_number_layout.addWidget(self.save_whatsapp_button)
        actions_layout.addWidget(test_number_widget)
        
        layout.addWidget(actions_group)

        # 3. Seção de QR Code (Informativa)
        qr_info_group = QGroupBox("QR Code")
        qr_info_layout = QVBoxLayout(qr_info_group)
        qr_info_label = QLabel("Ao clicar em 'Conectar', o QR Code será exibido em uma nova janela para facilitar a leitura.")
        qr_info_label.setWordWrap(True)
        qr_info_label.setStyleSheet("font-size: 13px; color: #6c757d;")
        qr_info_layout.addWidget(qr_info_label)
        layout.addWidget(qr_info_group)
        
        layout.addStretch()
        
        return connection_tab

    def _toggle_whatsapp_connection(self):
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()
        
        if manager.is_ready:
            reply = QMessageBox.question(self, "Desconectar WhatsApp",
                                         "Tem certeza que deseja desconectar a sessão atual? Será necessário escanear um novo QR Code para reconectar.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self._update_whatsapp_ui_state('pending', "Desconectando...")
                manager.disconnect()
                self._update_whatsapp_ui_state('disconnected')
                QMessageBox.information(self, "WhatsApp", "Desconectado com sucesso.")
        else:
            self._update_whatsapp_ui_state('pending', "Iniciando conexão...")
            manager.connect()

    def _update_whatsapp_ui_state(self, status, message=""):
        style_indicator_red = "background-color: #dc3545; border-radius: 10px;"
        style_indicator_green = "background-color: #28a745; border-radius: 10px;"
        style_indicator_yellow = "background-color: #ffc107; border-radius: 10px;"

        if status == 'disconnected':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_red)
            self.whatsapp_status_text.setText(message or "Desconectado")
            self.whatsapp_connect_button.setText("📱 Conectar")
            self.whatsapp_connect_button.setEnabled(True)
            self.send_test_button.setEnabled(False)
            # O QR Code agora é gerenciado por um diálogo separado.
        
        elif status == 'connected':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_green)
            self.whatsapp_status_text.setText(message or "Conectado")
            self.whatsapp_connect_button.setText("🔌 Desconectar")
            self.whatsapp_connect_button.setEnabled(True)
            self.send_test_button.setEnabled(True)
            # O QR Code agora é gerenciado por um diálogo separado.

        elif status == 'pending':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_yellow)
            self.whatsapp_status_text.setText(message or "Processando...")
            self.whatsapp_connect_button.setEnabled(False)
            self.send_test_button.setEnabled(False)

        elif status == 'qr':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_yellow)
            self.whatsapp_status_text.setText("Aguardando leitura do QR Code")
            self.whatsapp_connect_button.setText("Cancelar Conexão")
            self.whatsapp_connect_button.setEnabled(True) # Permite cancelar
            self.send_test_button.setEnabled(False)
            if self.qr_code_dialog:
                self.qr_code_dialog.update_status("Aguardando leitura...")

    def _show_qr_code_dialog(self, image_path):
        """Cria e exibe o diálogo com o QR Code."""
        try:
            if not self.qr_code_dialog:
                self.qr_code_dialog = QRCodeDialog(self)

            pixmap = QPixmap(image_path)
            self.qr_code_dialog.set_qr_pixmap(pixmap)
            self.qr_code_dialog.show()
            self._update_whatsapp_ui_state('qr')

        except Exception as e:
            logging.error(f"Erro ao criar diálogo do QR Code: {e}", exc_info=True)
            QMessageBox.critical(self, "Erro", "Não foi possível exibir o QR Code.")
            self._update_whatsapp_ui_state('disconnected', "Erro ao gerar QR Code")

    def _handle_whatsapp_connection_status(self, status_message):
        """Atualiza a UI principal e gerencia o diálogo do QR Code."""
        self.on_whatsapp_status_updated(status_message) # Chama o método original para atualizar a UI

        is_connected = "Conectado" in status_message
        is_failed = "Erro" in status_message or "falhou" in status_message.lower() or "Desconectado" in status_message

        if self.qr_code_dialog and (is_connected or is_failed):
            self.qr_code_dialog.close()
            self.qr_code_dialog = None

    def on_whatsapp_log_updated(self, message):
        """Exibe logs informativos do WhatsApp."""
        QMessageBox.information(self, "Informação do WhatsApp", message)

    def on_whatsapp_status_updated(self, status_message):
        """Slot para receber atualizações de status e atualizar a UI de forma centralizada."""
        logging.info(f"WhatsApp status update received: {status_message}")
        if "Conectado" in status_message:
            self._update_whatsapp_ui_state('connected', status_message)
        elif "Desconectado" in status_message:
            self._update_whatsapp_ui_state('disconnected', status_message)
        elif "Erro" in status_message or "falhou" in status_message.lower():
            self._update_whatsapp_ui_state('disconnected', status_message)
            if not "Desconectado" in status_message: # Evita duplo popup
                QMessageBox.warning(self, "Erro no WhatsApp", status_message)
        else:
            self._update_whatsapp_ui_state('pending', status_message)

    def send_test_whatsapp_message(self):
        """Envia uma mensagem de teste para o número configurado."""
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()

        if not manager.is_ready:
            QMessageBox.warning(self, "WhatsApp Não Conectado", "Por favor, conecte o WhatsApp antes de enviar uma mensagem de teste.")
            return

        notification_number = self.whatsapp_phone_input.text().strip()
        if not notification_number:
            QMessageBox.warning(self, "Número Não Configurado", "Por favor, insira e salve um número de telefone para enviar a mensagem de teste.")
            return

        test_message = "✅ Mensagem de teste do sistema PDV Moderno. A integração com o WhatsApp está funcionando!"
        
        result = manager.send_message(notification_number, test_message)
        if result.get('success'):
            QMessageBox.information(self, "Sucesso", f"Mensagem de teste enviada para {notification_number}.")
        else:
            QMessageBox.critical(self, "Falha", f"Não foi possível enviar a mensagem de teste.\n\nErro: {result.get('error')}")

    def _create_toggle_switch(self, text):
        """Cria um conjunto de widgets para um toggle switch moderno com label de status."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toggle = QCheckBox()
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 44px;
                height: 24px;
                border-radius: 12px;
                border: 1px solid {ModernTheme.GRAY_LIGHT};
                background-color: {ModernTheme.GRAY};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ModernTheme.PRIMARY};
                border: 1px solid {ModernTheme.PRIMARY};
            }}
            QCheckBox::indicator:handle {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                background-color: white;
                margin: 2px;
            }}
            QCheckBox::indicator:unchecked:handle {{
                subcontrol-position: left;
            }}
            QCheckBox::indicator:checked:handle {{
                subcontrol-position: right;
            }}
        """)

        label = QLabel(text)
        label.setStyleSheet("font-size: 14px; font-weight: 500; color: #34495e;")

        status_label = QLabel("Desativado")
        status_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {ModernTheme.ERROR};")

        def update_status_label(state):
            if state == Qt.CheckState.Checked.value:
                status_label.setText("Ativado")
                status_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {ModernTheme.SUCCESS};")
            else:
                status_label.setText("Desativado")
                status_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {ModernTheme.ERROR};")
        
        toggle.stateChanged.connect(update_status_label)
        update_status_label(toggle.checkState().value) # Seta o estado inicial

        layout.addWidget(toggle)
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(status_label)
        
        return widget, toggle

    def create_notifications_tab(self):
        """Cria a aba de configurações de notificações com um design simplificado e funcional."""
        notifications_tab = QWidget()
        main_layout = QVBoxLayout(notifications_tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)

        # --- Seção de Funcionalidades ---
        features_group = QGroupBox("Funcionalidades de Notificação")
        features_layout = QVBoxLayout(features_group)
        features_layout.setSpacing(15)
        
        sales_widget, self.sales_notifications_checkbox = self._create_toggle_switch("Notificar Vendas Realizadas")
        cash_widget, self.cash_notifications_checkbox = self._create_toggle_switch("Notificar Abertura e Fechamento de Caixa")
        stock_widget, self.stock_alerts_checkbox = self._create_toggle_switch("Enviar Alertas de Estoque Baixo")
        
        features_layout.addWidget(sales_widget)
        features_layout.addWidget(cash_widget)
        features_layout.addWidget(stock_widget)
        layout.addWidget(features_group)

        # --- Seção de Configurações Adicionais ---
        settings_group = QGroupBox("Configurações Adicionais")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setSpacing(10)

        settings_layout.addWidget(QLabel("Notificar apenas vendas acima de (R$):"), 0, 0)
        self.min_sale_value_input = QLineEdit("0,00")
        self.min_sale_value_input.setMaximumWidth(120)
        settings_layout.addWidget(self.min_sale_value_input, 0, 1)

        settings_layout.addWidget(QLabel("Delay entre notificações (segundos):"), 1, 0)
        self.notification_delay_input = QLineEdit("0")
        self.notification_delay_input.setMaximumWidth(120)
        settings_layout.addWidget(self.notification_delay_input, 1, 1)
        layout.addWidget(settings_group)

        # --- Seção de Destinatários ---
        recipients_group = QGroupBox("Gerenciar Destinatários")
        recipients_layout = QVBoxLayout(recipients_group)
        
        self.recipients_list = QListWidget()
        self.recipients_list.setMaximumHeight(120)
        recipients_layout.addWidget(self.recipients_list)

        add_recipient_layout = QHBoxLayout()
        self.new_recipient_input = QLineEdit()
        self.new_recipient_input.setPlaceholderText("Novo número (Ex: 5511912345678)")
        add_recipient_layout.addWidget(self.new_recipient_input)
        
        self.add_recipient_button = QPushButton("Adicionar")
        self.add_recipient_button.clicked.connect(self.add_recipient)
        add_recipient_layout.addWidget(self.add_recipient_button)
        
        self.remove_recipient_button = QPushButton("Remover Selecionado")
        self.remove_recipient_button.clicked.connect(self.remove_recipient)
        add_recipient_layout.addWidget(self.remove_recipient_button)
        
        recipients_layout.addLayout(add_recipient_layout)
        layout.addWidget(recipients_group)

        # --- Barra de Ações ---
        action_bar = QHBoxLayout()
        
        preview_button = QPushButton("👁️ Ver Exemplo")
        preview_button.clicked.connect(self.preview_sale_notification)
        preview_button.setMinimumHeight(40)
        action_bar.addWidget(preview_button)

        test_button = QPushButton("📤 Enviar Teste")
        test_button.clicked.connect(self.test_notifications)
        test_button.setMinimumHeight(40)
        action_bar.addWidget(test_button)

        action_bar.addStretch()
        
        self.save_notifications_button = QPushButton("💾 Salvar Configurações")
        self.save_notifications_button.clicked.connect(self.save_notifications_config)
        self.save_notifications_button.setMinimumHeight(40)
        action_bar.addWidget(self.save_notifications_button)
        
        layout.addLayout(action_bar)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        self.load_notifications_config_to_ui()
        return notifications_tab

    def add_recipient(self):
        """Adiciona um novo destinatário."""
        phone = self.new_recipient_input.text().strip()
        if not phone:
            QMessageBox.warning(self, "Campo Vazio", "Digite um número de telefone válido.")
            return

        # Verificar se já existe
        for i in range(self.recipients_list.count()):
            if self.recipients_list.item(i).text() == phone:
                QMessageBox.warning(self, "Número Já Existe", "Este número já está na lista.")
                return

        self.recipients_list.addItem(phone)
        self.new_recipient_input.clear()

    def remove_recipient(self):
        """Remove o destinatário selecionado."""
        current_item = self.recipients_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Nenhum Selecionado", "Selecione um número para remover.")
            return

        reply = QMessageBox.question(self, "Confirmar Remoção",
                                   f"Remover o número {current_item.text()} da lista?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.recipients_list.takeItem(self.recipients_list.row(current_item))

    def load_notifications_config_to_ui(self):
        """Carrega as configurações de notificações para a nova interface."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            settings = notifier.get_settings()

            # Carregar configurações dos checkboxes
            self.sales_notifications_checkbox.setChecked(settings.get('enable_sale_notifications', True))
            self.cash_notifications_checkbox.setChecked(settings.get('enable_cash_notifications', True))
            self.stock_alerts_checkbox.setChecked(settings.get('enable_low_stock_alerts', False))

            # Valor mínimo
            min_value = settings.get('minimum_sale_value', 0.0)
            self.min_sale_value_input.setText(f"{min_value:.2f}".replace('.', ','))

            # Delay
            delay = settings.get('notification_delay', 0)
            self.notification_delay_input.setText(str(delay))
            
            # Destinatários
            self.recipients_list.clear()
            recipients = settings.get('notification_recipients', [])
            if recipients:
                for r in recipients:
                    self.recipients_list.addItem(r)

        except Exception as e:
            logging.error(f"Erro ao carregar configurações de notificações: {e}", exc_info=True)

    def save_notifications_config(self):
        """Salva as configurações de notificações da nova interface."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()

            # Salvar configurações dos checkboxes
            notifier.enable_sale_notifications(self.sales_notifications_checkbox.isChecked())
            notifier.enable_cash_notifications(self.cash_notifications_checkbox.isChecked())
            notifier.enable_low_stock_alerts(self.stock_alerts_checkbox.isChecked())

            # Salvar valor mínimo
            try:
                min_value_text = self.min_sale_value_input.text().replace(',', '.')
                min_value = float(min_value_text) if min_value_text else 0.0
                notifier.set_minimum_sale_value(min_value)
            except ValueError:
                QMessageBox.warning(self, "Valor Inválido", "O valor mínimo deve ser um número válido.")
                return

            # Coletar destinatários da lista
            recipients_from_ui = []
            for i in range(self.recipients_list.count()):
                recipients_from_ui.append(self.recipients_list.item(i).text())

            # Atualizar destinatários
            current_recipients = notifier.get_settings().get('notification_recipients', [])
            # Adicionar novos
            for recipient in recipients_from_ui:
                if recipient not in current_recipients:
                    notifier.add_recipient(recipient)
            # Remover os que não estão mais na UI
            for recipient in current_recipients:
                if recipient not in recipients_from_ui:
                    notifier.remove_recipient(recipient)

            # Salvar delay
            try:
                delay = int(self.notification_delay_input.text()) if self.notification_delay_input.text() else 0
                settings = notifier.get_settings()
                settings['notification_delay'] = delay
                
                # Lógica de salvar no arquivo (mantida da versão anterior)
                import json
                from utils import get_data_path
                config_path = get_data_path('whatsapp_sales_notifications.json')
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=4, ensure_ascii=False)

            except ValueError:
                QMessageBox.warning(self, "Valor Inválido", "O delay deve ser um número inteiro.")
                return

            QMessageBox.information(self, "Sucesso", "Configurações de notificações salvas com sucesso!")
            notifier._load_notification_settings()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar configurações: {e}")
            logging.error(f"Erro detalhado: {e}", exc_info=True)

    def preview_sale_notification(self):
        """Mostra um exemplo da mensagem de venda que seria enviada."""
        try:
            # Criar dados de exemplo
            sample_sale_data = {
                'id': 12345,
                'customer_name': 'João Silva',
                'total_amount': 45.90
            }

            sample_payment_details = [
                {'amount': 25.90, 'method': 'Dinheiro'},
                {'amount': 20.00, 'method': 'PIX'}
            ]

            # Gerar mensagem de exemplo
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()

            example_message = notifier._build_sale_message(sample_sale_data, sample_payment_details)

            if example_message:
                # Mostrar em uma caixa de diálogo
                dialog = QDialog(self)
                dialog.setWindowTitle("Exemplo de Notificação de Venda")
                dialog.setModal(True)
                dialog.resize(500, 400)

                layout = QVBoxLayout(dialog)

                title = QLabel("✨ Como ficará a mensagem de venda:")
                title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
                layout.addWidget(title)

                message_display = QTextEdit()
                message_display.setPlainText(example_message)
                message_display.setReadOnly(True)
                message_display.setStyleSheet("""
                    QTextEdit {
                        font-family: 'Courier New', monospace;
                        font-size: 11px;
                        background-color: #f8f9fa;
                        border: 1px solid #dee2e6;
                        border-radius: 5px;
                        padding: 10px;
                    }
                """)
                layout.addWidget(message_display)

                info_label = QLabel("Esta é uma prévia de como aparecerá no WhatsApp quando uma venda for realizada com as configurações atuais.")
                info_label.setWordWrap(True)
                info_label.setStyleSheet("font-size: 10px; color: #6c757d; margin-top: 10px;")
                layout.addWidget(info_label)

                close_button = QPushButton("Fechar")
                close_button.clicked.connect(dialog.accept)
                layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignCenter)

                dialog.exec()
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível gerar a mensagem de exemplo.")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar exemplo da mensagem:\n{str(e)}")

    def test_notifications(self):
        """Testa o envio de notificações para verificar se estão funcionando."""
        try:
            # Verificar se o WhatsApp está conectado
            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()

            if not manager.is_ready:
                QMessageBox.warning(self, "WhatsApp Desconectado",
                                  "O WhatsApp não está conectado. Por favor, conecte primeiro na aba 'Conexão'.")
                return

            # Verificar se há destinatários configurados
            recipients = []
            for i in range(self.recipients_list.count()):
                recipients.append(self.recipients_list.item(i).text())

            if not recipients:
                # Tentar usar o número padrão
                notification_number = self.whatsapp_phone_input.text().strip()
                if notification_number:
                    recipients.append(notification_number)
                else:
                    QMessageBox.warning(self, "Nenhum Destinatário",
                                      "Não há destinatários configurados. Adicione ao menos um número na lista ou configure um número padrão.")
                    return

            # Criar mensagem de teste
            test_message = f"""🧪 *TESTE DO SISTEMA PDV MODERNO*

✅ Configurações de notificações funcionando normalmente!

📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}
👤 Usuário: {self.current_user.get('username', 'Sistema')}

Este é apenas um teste. Se você recebeu esta mensagem, as notificações estão configuradas corretamente! 🎉"""

            # Enviar para os destinatários
            success_count = 0
            for phone in recipients:
                try:
                    result = manager.send_message(phone, test_message)
                    if result.get('success'):
                        success_count += 1
                    else:
                        logging.warning(f"Falha ao enviar teste para {phone}: {result.get('error')}")
                except Exception as e:
                    logging.error(f"Erro ao enviar teste para {phone}: {e}", exc_info=True)

            if success_count > 0:
                QMessageBox.information(self, "Teste Enviado",
                                      f"✅ Teste enviado com sucesso para {success_count} de {len(recipients)} destinatários!\n\n"
                                      "Verifique seus celulares para confirmar que a mensagem foi recebida.")
            else:
                QMessageBox.warning(self, "Falha no Teste",
                                  "❌ Não foi possível enviar a mensagem de teste para nenhum destinatário.\n\n"
                                  "Verifique a conexão do WhatsApp e os números configurados.")

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao testar notificações:\n{str(e)}")
