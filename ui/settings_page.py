from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QPushButton, QGridLayout, QScrollArea,
    QDialog, QFrame, QLineEdit, QComboBox, QMessageBox, QTabWidget, QListWidget, QHBoxLayout,
    QCheckBox, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter
from datetime import datetime

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
    operation_mode_changed = pyqtSignal()

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

    def open_user_management(self):
        widget = UserManagementPage()
        self._create_modal_dialog("Gerenciar Usuários", widget)

    def open_whatsapp_settings(self):
        widget = self.create_whatsapp_config_widget()

        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()

        # Conecta os sinais ANTES de mostrar o diálogo
        manager.qr_code_ready.connect(self.on_qr_code_path_received)
        manager.status_updated.connect(self.on_whatsapp_status_updated)
        manager.error_occurred.connect(self.on_whatsapp_status_updated)
        manager.log_updated.connect(self.on_whatsapp_log_updated)

        self._create_modal_dialog("Configurações do WhatsApp", widget)

        # Desconecta os sinais DEPOIS que o diálogo for fechado para evitar erros
        try:
            manager.qr_code_ready.disconnect(self.on_qr_code_path_received)
            manager.status_updated.disconnect(self.on_whatsapp_status_updated)
            manager.error_occurred.disconnect(self.on_whatsapp_status_updated)
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
        """Cria o widget de configuração do WhatsApp com abas para melhor organização."""
        whatsapp_widget = QWidget()
        main_layout = QVBoxLayout(whatsapp_widget)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título
        title = QLabel("Configuração do WhatsApp")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        main_layout.addWidget(title)

        # Campo para número de notificações
        notification_layout = QHBoxLayout()
        notification_layout.setSpacing(10)
        
        notification_label = QLabel("Nº para Notificações (Gerente):")
        self.whatsapp_phone_input = QLineEdit(placeholderText="Ex: 5511912345678")
        self.save_whatsapp_button = QPushButton("Salvar")
        self.save_whatsapp_button.clicked.connect(self.save_whatsapp_config)

        notification_layout.addWidget(notification_label)
        notification_layout.addWidget(self.whatsapp_phone_input, 1)
        notification_layout.addWidget(self.save_whatsapp_button)
        main_layout.addLayout(notification_layout)

        # Status da conexão
        self.whatsapp_status_label = QLabel("⏳ Aguardando configuração...")
        self.whatsapp_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whatsapp_status_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }
        """)
        main_layout.addWidget(self.whatsapp_status_label)

        # Abas
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Aba 1: Conexão
        connection_tab = QWidget()
        connection_layout = QVBoxLayout(connection_tab)
        connection_layout.setSpacing(15)

        # Botões de ação
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        self.check_connection_button = QPushButton("🔍 Verificar")
        self.check_connection_button.setMinimumHeight(40)
        self.check_connection_button.clicked.connect(self.check_whatsapp_connection)

        self.qr_code_button = QPushButton("📱 Conectar")
        self.qr_code_button.setMinimumHeight(40)
        self.qr_code_button.clicked.connect(self.generate_qr_code)

        self.disconnect_button = QPushButton("🔌 Desconectar")
        self.disconnect_button.setMinimumHeight(40)
        self.disconnect_button.clicked.connect(self.disconnect_whatsapp)

        self.send_test_button = QPushButton("✉️ Enviar Teste")
        self.send_test_button.setMinimumHeight(40)

        self.send_test_button.clicked.connect(self.send_test_whatsapp_message)

        buttons_layout.addWidget(self.check_connection_button)
        buttons_layout.addWidget(self.qr_code_button)
        buttons_layout.addWidget(self.disconnect_button)
        buttons_layout.addWidget(self.send_test_button)
        buttons_layout.addStretch()
        connection_layout.addLayout(buttons_layout)

        # Área para exibir QR Code
        qr_frame = QFrame()
        qr_frame.setFrameShape(QFrame.Shape.Box)
        qr_frame.setStyleSheet("border: 2px dashed #dee2e6; border-radius: 8px; background-color: #f8f9fa;")
        qr_layout = QVBoxLayout(qr_frame)
        self.qr_code_label = QLabel("Clique em 'Conectar' para gerar o QR Code")
        self.qr_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_code_label.setMinimumHeight(250)
        qr_layout.addWidget(self.qr_code_label)
        connection_layout.addWidget(qr_frame)

        tab_widget.addTab(connection_tab, "Conexão")

        # Aba 2: Notificações
        notifications_tab = self.create_notifications_tab()
        tab_widget.addTab(notifications_tab, "Notificações")

        # Aba 3: Instruções
        instructions_tab = QWidget()
        instructions_layout = QVBoxLayout(instructions_tab)
        instructions = QLabel(
            "<b>Como conectar o WhatsApp:</b><br><br>"
            "1. Clique em <b>Conectar</b> para gerar o QR Code.<br>"
            "2. Abra o WhatsApp no seu celular.<br>"
            "3. Toque no ícone de menu (⋮) → 'Aparelhos conectados' → 'Conectar um aparelho'.<br>"
            "4. Escaneie o QR Code mostrado na aba 'Conexão'.<br>"
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
        self.update_whatsapp_status()

        return whatsapp_widget

    def generate_qr_code(self):
        """Gera QR code para conexão do WhatsApp."""
        from PyQt6.QtGui import QPixmap
        from integrations.whatsapp_manager import WhatsAppManager

        try:
            self.qr_code_button.setText("Conectando...")
            self.qr_code_button.setEnabled(False)
            self.check_connection_button.setEnabled(False)

            print(f"[{datetime.now()}] Settings: Iniciando conexão do WhatsApp...")
            manager = WhatsAppManager.get_instance()

            # Iniciar conexão
            manager.connect()

            self.whatsapp_status_label.setText("🔄 Iniciando conexão com WhatsApp...")
            self.whatsapp_status_label.setStyleSheet("""                QLabel {{
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    text-align: center;
                    background-color: #fff3cd;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                }}
            """)

        except Exception as e:
            print(f"[{datetime.now()}] Settings: Erro ao iniciar conexão - {str(e)}")
            import traceback
            print(f"[{datetime.now()}] Settings: Traceback - {traceback.format_exc()}")

            self.whatsapp_status_label.setText("❌ Erro ao Iniciar Conexão")
            self.whatsapp_status_label.setStyleSheet("""                QLabel {{
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    text-align: center;
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }}
            """)
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar conexão com WhatsApp:\n{str(e)}")
        finally:
            self.qr_code_button.setText("📱 Conectar WhatsApp")
            self.qr_code_button.setEnabled(True)
            self.check_connection_button.setEnabled(True)

    def on_qr_code_path_received(self, image_path):
        """Slot para receber o caminho do arquivo do QR code e exibi-lo."""
        try:
            # Carregar o QR code do arquivo
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise Exception("Falha ao carregar imagem do QR Code")

            # Redimensionar para caber na área
            scaled_pixmap = pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.qr_code_label.setPixmap(scaled_pixmap)
            self.qr_code_label.setText("")  # Remove o texto

            self.whatsapp_status_label.setText("📱 QR Code Gerado - Escaneie com o WhatsApp")
            self.whatsapp_status_label.setStyleSheet("""
                QLabel {{
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    text-align: center;
                    background-color: #d1ecf1;
                    color: #0c5460;
                    border: 1px solid #bee5eb;
                }}
            """)

        except Exception as e:
            print(f"Erro ao exibir QR Code: {str(e)}")
            self.qr_code_label.setText("❌ Erro ao carregar QR Code")
            self.whatsapp_status_label.setText("❌ Erro ao gerar QR Code")
            self.whatsapp_status_label.setStyleSheet("""
                QLabel {{
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    text-align: center;
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }}
            """)



    def on_whatsapp_log_updated(self, message):
        """Exibe logs informativos do WhatsApp."""
        QMessageBox.information(self, "Informação do WhatsApp", message)

    def on_whatsapp_status_updated(self, status):
        """Slot para receber atualizações de status do WhatsApp."""
        try:
            self.whatsapp_status_label.setText(status)

            # Atualizar cores baseado no status
            if "Conectado" in status:
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {
                        padding: 10px;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                        background-color: #d4edda;
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }
                """)
            elif "Aguardando" in status or "QR Code" in status:
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {
                        padding: 10px;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                        background-color: #d1ecf1;
                        color: #0c5460;
                        border: 1px solid #bee5eb;
                    }
                """)
            elif "Erro" in status:
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {
                        padding: 10px;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                        background-color: #f8d7da;
                        color: #721c24;
                        border: 1px solid #f5c6cb;
                    }
                """)
            else:
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {
                        padding: 10px;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                        background-color: #fff3cd;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                    }
                """)

        except Exception as e:
            print(f"Erro ao atualizar status: {str(e)}")

    def disconnect_whatsapp(self):
        """Desconecta do WhatsApp."""
        try:
            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()
            manager.disconnect()
            self.on_whatsapp_status_updated("Desconectado")
            self.qr_code_label.setText("Clique em 'Conectar WhatsApp' para gerar o QR Code")
            self.qr_code_label.setPixmap(QPixmap()) # Clear pixmap
            QMessageBox.information(self, "WhatsApp", "Desconectado com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao desconectar do WhatsApp:\n{str(e)}")

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
        
        manager.send_message(notification_number, test_message)

    def check_whatsapp_connection(self):
        """Verifica o status de conexão do WhatsApp."""
        try:
            self.check_connection_button.setText("Verificando...")
            self.check_connection_button.setEnabled(False)

            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()

            # Atualizar status baseado na conexão atual
            if manager.is_ready:
                self.whatsapp_status_label.setText("✅ WhatsApp Conectado com Sucesso")
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {{
                        padding: 15px;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 13px;
                        text-align: center;
                        background-color: #d4edda;
                        color: #155724;
                        border: 1px solid #c3e6cb;
                    }}
                """)
                QMessageBox.information(self, "WhatsApp Conectado",
                                      "✅ WhatsApp está conectado e pronto para uso!")
            else:
                self.whatsapp_status_label.setText("❌ WhatsApp Desconectado")
                self.whatsapp_status_label.setStyleSheet("""
                    QLabel {{
                        padding: 15px;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 13px;
                        text-align: center;
                        background-color: #f8d7da;
                        color: #721c24;
                        border: 1px solid #f5c6cb;
                    }}
                """)
                QMessageBox.warning(self, "WhatsApp Desconectado",
                                  "❌ WhatsApp não está conectado.\n\n"
                                  "Clique em 'Conectar WhatsApp' para gerar um novo QR Code e estabelecer a conexão.")

        except Exception as e:
            self.whatsapp_status_label.setText("❌ Erro ao Verificar Conexão")
            self.whatsapp_status_label.setStyleSheet("""
                QLabel {{
                    padding: 15px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 13px;
                    text-align: center;
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }}
            """)
            QMessageBox.critical(self, "Erro", f"Erro ao verificar conexão com WhatsApp:\n{str(e)}")
        finally:
            self.check_connection_button.setText("🔍 Verificar Conexão")
            self.check_connection_button.setEnabled(True)

    def create_notifications_tab(self):
        """Cria a aba de configurações de notificações com design profissional."""
        notifications_tab = QWidget()
        main_layout = QVBoxLayout(notifications_tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Scroll area para conteúdo extenso
        scroll_area = QScrollArea(notifications_tab)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # === CABEÇALHO PRINCIPAL ===
        header_widget = self._create_header_widget()
        layout.addWidget(header_widget)

        # === DASHBOARD DE STATUS ===
        status_dashboard = self._create_status_dashboard()
        layout.addWidget(status_dashboard)

        # === SEÇÃO PRINCIPAL - NOTIFICAÇÕES ===
        main_section = QGroupBox()
        main_section.setStyleSheet(self._get_section_style())
        main_layout_inner = QVBoxLayout(main_section)
        main_layout_inner.setContentsMargins(20, 20, 20, 20)
        main_layout_inner.setSpacing(25)

        section_title = QLabel("🎯 Funcionalidades Disponíveis")
        section_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        main_layout_inner.addWidget(section_title)

        # Notificação de Vendas
        sales_feature = self._create_advanced_feature(
            icon="🛒",
            title="Notificar Vendas Realizadas",
            description="Sempre que uma venda for finalizada no PDV, receba uma notificação detalhada por WhatsApp com:\n• Data e hora da venda\n• Cliente atendido\n• Valor total\n• Formas de pagamento utilizadas",
            feature_key="sale_notifications",
            default_enabled=True,
            color_theme="#4CAF50"
        )
        main_layout_inner.addWidget(sales_feature)

        # Campo de filtro de valor (para vendas)
        self.sales_filter_widget = self._create_filter_widget()
        main_layout_inner.addWidget(self.sales_filter_widget)

        # Notificação de Caixa
        cash_feature = self._create_advanced_feature(
            icon="💰",
            title="Controle de Caixa",
            description="Seja informado sobre todas as operações de caixa:\n• Notificação quando abrir o caixa\n• Relatório completo quando fechar (com totais por forma de pagamento)\n• Alertas de diferenças no fechamento",
            feature_key="cash_notifications",
            default_enabled=True,
            color_theme="#FF9800"
        )
        main_layout_inner.addWidget(cash_feature)

        # Alertas de Estoque
        stock_feature = self._create_advanced_feature(
            icon="📦",
            title="Alertas de Estoque Baixo",
            description="Monitoramento inteligente do estoque:\n• Alertas automáticos quando produtos atingem o estoque mínimo\n• Identificação clara do produto afetado\n• Sugestão para reposição",
            feature_key="stock_alerts",
            default_enabled=False,
            color_theme="#2196F3"
        )
        main_layout_inner.addWidget(stock_feature)

        layout.addWidget(main_section)

        # === SEÇÃO DESTINATÁRIOS ===
        recipients_section = self._create_recipients_section()
        layout.addWidget(recipients_section)

        # === SEÇÃO AVANÇADA ===
        advanced_section = self._create_advanced_section()
        layout.addWidget(advanced_section)

        # === RODAPÉ DE AÇÕES ===
        action_bar = self._create_action_bar()
        layout.addWidget(action_bar)

        # Configurar scroll area
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

        # Carregar configurações
        self.load_notifications_config_to_ui()
        self.update_all_ui_states()

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
        """Carrega as configurações de notificações para a interface."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            settings = notifier.get_settings()

            # Carregar configurações dos checkboxes se existirem
            if hasattr(self, 'sales_notifications_checkbox') and self.sales_notifications_checkbox:
                enabled = settings.get('enable_sale_notifications', True)
                self.sales_notifications_checkbox.setChecked(enabled)
                self.sales_notifications_checkbox.setText("ON" if enabled else "OFF")

            if hasattr(self, 'cash_opening_checkbox') and self.cash_opening_checkbox:
                enabled = settings.get('enable_cash_notifications', True)
                self.cash_opening_checkbox.setChecked(enabled)
                self.cash_opening_checkbox.setText("ON" if enabled else "OFF")

            if hasattr(self, 'stock_alerts_checkbox') and self.stock_alerts_checkbox:
                enabled = settings.get('enable_low_stock_alerts', False)
                self.stock_alerts_checkbox.setChecked(enabled)
                self.stock_alerts_checkbox.setText("ON" if enabled else "OFF")

            # Valor mínimo
            if hasattr(self, 'min_sale_value_input') and self.min_sale_value_input:
                min_value = settings.get('minimum_sale_value', 0.0)
                self.min_sale_value_input.setText(f"{min_value:.2f}".replace('.', ','))

            # Delay
            if hasattr(self, 'notification_delay_input') and self.notification_delay_input:
                delay = settings.get('notification_delay', 0)
                self.notification_delay_input.setText(str(delay))

        except Exception as e:
            print(f"Erro ao carregar configurações de notificações: {e}")

    def save_notifications_config(self):
        """Salva as configurações de notificações."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()

            # Salvar configurações baseado nos widgets que existem
            if hasattr(self, 'sales_notifications_checkbox') and self.sales_notifications_checkbox:
                notifier.enable_sale_notifications(self.sales_notifications_checkbox.isChecked())

            if hasattr(self, 'cash_opening_checkbox') and self.cash_opening_checkbox:
                notifier.enable_cash_notifications(self.cash_opening_checkbox.isChecked())

            if hasattr(self, 'stock_alerts_checkbox') and self.stock_alerts_checkbox:
                notifier.enable_low_stock_alerts(self.stock_alerts_checkbox.isChecked())

            # Salvar valor mínimo
            if hasattr(self, 'min_sale_value_input') and self.min_sale_value_input:
                try:
                    min_value_text = self.min_sale_value_input.text().replace(',', '.')
                    min_value = float(min_value_text) if min_value_text else 0.0
                    notifier.set_minimum_sale_value(min_value)
                except ValueError:
                    QMessageBox.warning(self, "Valor Inválido", "O valor mínimo deve ser um número válido.")
                    return

            # Coletar destinatários da lista
            recipients = []
            if hasattr(self, 'recipients_list') and self.recipients_list:
                for i in range(self.recipients_list.count()):
                    recipients.append(self.recipients_list.item(i).text())

            # Atualizar destinatários
            if recipients:
                current_recipients = notifier.get_settings().get('notification_recipients', [])
                for recipient in recipients:
                    if recipient not in current_recipients:
                        notifier.add_recipient(recipient)

                # Remover destinatários que não estão mais na lista
                for recipient in current_recipients:
                    if recipient not in recipients:
                        notifier.remove_recipient(recipient)

            # Salvar delay (atualizar settings diretamente)
            if hasattr(self, 'notification_delay_input') and self.notification_delay_input:
                try:
                    delay = int(self.notification_delay_input.text()) if self.notification_delay_input.text() else 0
                    settings = notifier.get_settings()
                    settings['notification_delay'] = delay
                    # Salvar no arquivo
                    import json
                    from utils import get_data_path
                    config_path = get_data_path('whatsapp_sales_notifications.json')
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(settings, f, indent=4, ensure_ascii=False)
                except ValueError:
                    QMessageBox.warning(self, "Valor Inválido", "O delay deve ser um número inteiro.")
                    return

            QMessageBox.information(self, "Sucesso", "Configurações de notificações salvas com sucesso!")

            # Recarregar configurações para refletir mudanças
            notifier._load_notification_settings()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar configurações: {e}")
            print(f"Erro detalhado: {e}")

    def update_whatsapp_status(self):
        """Atualiza o status inicial do WhatsApp."""
        self.whatsapp_status_label.setText("⏳ Aguardando configuração...")
        self.whatsapp_status_label.setStyleSheet("""
            QLabel {{
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                text-align: center;
                background-color: #fff3cd;
                color: #856404;
                border: 1px solid #ffeaa7;
            }}
        """)

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
                        print(f"Falha ao enviar teste para {phone}: {result.get('error')}")
                except Exception as e:
                    print(f"Erro ao enviar teste para {phone}: {e}")

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

    def on_sale_notifications_toggled(self, state):
        """Chamado quando o checkbox de notificações de vendas é alterado."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_sale_notifications(bool(state))
        except Exception as e:
            print(f"Erro ao alterar notificações de vendas: {e}")

    def on_cash_notifications_toggled(self, state):
        """Chamado quando os checkboxes de notificações de caixa são alterados."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_cash_notifications(bool(state))
        except Exception as e:
            print(f"Erro ao alterar notificações de caixa: {e}")

    def on_stock_alerts_toggled(self, state):
        """Chamado quando o checkbox de alertas de estoque é alterado."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_low_stock_alerts(bool(state))
        except Exception as e:
            print(f"Erro ao alterar alertas de estoque: {e}")

    def _create_feature_card(self, title, description, feature_key, default_enabled=True):
        """Cria um cartão estilizado para um recurso de notificação."""
        # Container do cartão
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Cabeçalho do cartão
        header_layout = QHBoxLayout()

        # Título e descrição
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6c757d;
                line-height: 1.2;
            }
        """)
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        header_layout.addLayout(text_layout, 1)

        # Toggle switch
        toggle_button = QPushButton()
        toggle_button.setFixedSize(50, 25)
        toggle_button.setCheckable(True)
        toggle_button.setChecked(default_enabled)
        toggle_button.setStyleSheet("""
            QPushButton {
                border-radius: 12px;
                border: 1px solid #dee2e6;
                background-color: #dc3545;
                position: relative;
            }
            QPushButton:checked {
                background-color: #28a745;
                border-color: #28a745;
            }
            QPushButton:!checked {
                background-color: #6c757d;
                border-color: #6c757d;
            }
        """)

        # Conectar sinais baseado na funcionalidade
        if feature_key == "sale_notifications":
            toggle_button.clicked.connect(self.on_sale_notifications_ui_toggled)
            self.sales_notifications_checkbox = toggle_button  # Referência para compatibilidade
        elif feature_key == "cash_notifications":
            toggle_button.clicked.connect(self.on_cash_notifications_ui_toggled)
            self.cash_opening_checkbox = toggle_button  # Referência para compatibilidade
        elif feature_key == "stock_alerts":
            toggle_button.clicked.connect(self.on_stock_alerts_ui_toggled)
            self.stock_alerts_checkbox = toggle_button  # Referência para compatibilidade

        header_layout.addWidget(toggle_button)
        layout.addLayout(header_layout)

        return card

    def on_sale_notifications_ui_toggled(self):
        """Chamado quando o toggle de vendas na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()

            # Mostrar/esconder o campo de valor mínimo
            self.min_value_widget.setVisible(enabled)

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_sale_notifications(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar notificações de vendas: {e}")

    def on_cash_notifications_ui_toggled(self):
        """Chamado quando o toggle de caixa na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_cash_notifications(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar notificações de caixa: {e}")

    def on_stock_alerts_ui_toggled(self):
        """Chamado quando o toggle de alertas de estoque na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_low_stock_alerts(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar alertas de estoque: {e}")

    def on_master_toggle_changed(self):
        """Chamado quando o controle mestre é alterado."""
        try:
            enabled = self.master_notification_toggle.isChecked()

            # Atualizar visual do botão mestre
            if enabled:
                self.master_notification_toggle.setStyleSheet("""
                    QPushButton {
                        border-radius: 15px;
                        border: 2px solid #dee2e6;
                        background-color: #28a745;
                        color: white;
                    }
                """)
                self.master_notification_toggle.setText("ATIVADO")
                self.master_status_label.setText("ATIVADO")
                self.master_status_label.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        color: #28a745;
                        margin-left: 10px;
                        font-size: 12px;
                    }
                """)
            else:
                self.master_notification_toggle.setStyleSheet("""
                    QPushButton {
                        border-radius: 15px;
                        border: 2px solid #dee2e6;
                        background-color: #6c757d;
                        color: white;
                    }
                """)
                self.master_notification_toggle.setText("DESLIGADO")
                self.master_status_label.setText("DESLIGADO")
                self.master_status_label.setStyleSheet("""
                    QLabel {
                        font-weight: bold;
                        color: #dc3545;
                        margin-left: 10px;
                        font-size: 12px;
                    }
                """)

            # Aplicar configuração globalmente (esta é apenas uma demonstração visual)
            # Em uma implementação real, isso poderia desabilitar todas as notificações
            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar controle mestre: {e}")

    def on_min_value_changed(self):
        """Chamado quando o valor mínimo é alterado."""
        try:
            text = self.min_sale_value_input.text().replace(',', '.')
            if text.strip():
                try:
                    value = float(text)
                    from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                    notifier = get_whatsapp_sales_notifier()
                    notifier.set_minimum_sale_value(value)
                except ValueError:
                    pass  # Ignora valores inválidos temporariamente
        except Exception as e:
            print(f"Erro ao alterar valor mínimo: {e}")

    def update_notifications_status(self):
        """Atualiza o status das notificações na barra de status."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            settings = notifier.get_settings()

            active_count = 0
            total_features = 3

            if settings.get('enable_sale_notifications', False):
                active_count += 1
            if settings.get('enable_cash_notifications', False):
                active_count += 1
            if settings.get('enable_low_stock_alerts', False):
                active_count += 1

            recipients = len(settings.get('notification_recipients', []))

            if active_count == 0:
                status_text = "Sistema de notificações: DESLIGADO"
                status_color = "#dc3545"
                icon = "🔴"
            elif active_count == total_features:
                status_text = f"Todas as notificações estão ativas ({recipients} destinatários)"
                status_color = "#28a745"
                icon = "🟢"
            else:
                status_text = f"{active_count} de {total_features} notificações ativas ({recipients} destinatários)"
                status_color = "#ffc107"
                icon = "🟡"

            # Atualizar o label de status
            status_label = self.notifications_status_widget.findChild(QLabel, "notifications_status_label")
            if status_label:
                status_label.setText(status_text)
                status_label.setStyleSheet(f"""
                    QLabel {{
                        font-size: 14px;
                        font-weight: 500;
                        color: {status_color};
                    }}
                """)

            # Atualizar ícone
            icon_labels = self.notifications_status_widget.findChildren(QLabel)
            for label in icon_labels:
                if label.text() in ["⚙️", "🔴", "🟢", "🟡"]:
                    label.setText(icon)
                    break

        except Exception as e:
            print(f"Erro ao atualizar status das notificações: {e}")

    def _create_header_widget(self):
        """Cria o widget do cabeçalho da seção de notificações."""
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        title = QLabel("📱 Sistema de Notificações WhatsApp")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 5px;
            }
        """)
        layout.addWidget(title)

        description = QLabel("Configure notificações automáticas para acompanhar todas as operações do seu PDV em tempo real")
        description.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #6c757d;
                margin-bottom: 15px;
            }
        """)
        description.setWordWrap(True)
        layout.addWidget(description)

        return header

    def _create_status_dashboard(self):
        """Cria o dashboard de status das notificações."""
        self.notifications_status_widget = QWidget()
        self.notifications_status_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
            }
        """)

        layout = QHBoxLayout(self.notifications_status_widget)
        layout.setSpacing(15)

        # Ícone de status
        icon_label = QLabel("⚙️")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setFixedSize(40, 40)
        layout.addWidget(icon_label)

        # Texto de status
        status_label = QLabel("Carregando configurações...")
        status_label.setObjectName("notifications_status_label")
        status_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: white;
            }
        """)
        layout.addWidget(status_label)
        layout.addStretch()

        return self.notifications_status_widget

    def _create_advanced_feature(self, icon, title, description, feature_key, default_enabled=False, color_theme="#4CAF50"):
        """Cria um cartão avançado para uma funcionalidade."""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 2px solid %s;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 15px;
                border-left: 6px solid %s;
            }
            QWidget:hover {
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
        """ % (color_theme, color_theme))

        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        # Cabeçalho
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(12)

        feature_icon = QLabel(icon)
        feature_icon.setStyleSheet(f"font-size: 28px;")
        header_layout.addWidget(feature_icon)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: {color_theme};
            }}
        """)
        header_layout.addWidget(title_label)

        # Toggle
        toggle = QPushButton()
        toggle.setFixedSize(60, 30)
        toggle.setCheckable(True)
        toggle.setChecked(default_enabled)
        toggle.setStyleSheet(f"""
            QPushButton {{
                border-radius: 15px;
                border: 2px solid #dee2e6;
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:checked {{
                background-color: {color_theme};
                border-color: {color_theme};
            }}
            QPushButton:!checked {{
                background-color: #6c757d;
                border-color: #6c757d;
            }}
        """)

        # Conectar sinais
        if feature_key == "sale_notifications":
            toggle.clicked.connect(self.on_sale_notifications_ui_toggled)
            self.sales_notifications_checkbox = toggle
        elif feature_key == "cash_notifications":
            toggle.clicked.connect(self.on_cash_notifications_ui_toggled)
            self.cash_opening_checkbox = toggle
        elif feature_key == "stock_alerts":
            toggle.clicked.connect(self.on_stock_alerts_ui_toggled)
            self.stock_alerts_checkbox = toggle

        toggle.setText("ON" if default_enabled else "OFF")
        toggle.clicked.connect(lambda: toggle.setText("ON" if toggle.isChecked() else "OFF"))

        header_layout.addStretch()
        header_layout.addWidget(toggle)

        layout.addWidget(header)

        # Descrição
        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #495057;
                line-height: 1.4;
                padding-left: 8px;
            }
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        return card

    def _create_filter_widget(self):
        """Cria widget de filtro para valor mínimo de vendas."""
        self.min_value_widget = QWidget()
        layout = QHBoxLayout(self.min_value_widget)
        layout.setContentsMargins(40, 5, 20, 15)
        layout.setSpacing(10)

        filter_icon = QLabel("💵")
        filter_icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(filter_icon)

        label = QLabel("Filtrar vendas por valor mínimo:")
        label.setStyleSheet("font-size: 13px; color: #6c757d; font-weight: bold;")
        layout.addWidget(label)

        self.min_sale_value_input = QLineEdit("0,00")
        self.min_sale_value_input.setMaximumWidth(100)
        self.min_sale_value_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e9ecef;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        self.min_sale_value_input.setToolTip("Vendas com valor menor que este não serão notificadas")
        self.min_sale_value_input.textChanged.connect(self.on_min_value_changed)
        layout.addWidget(self.min_sale_value_input)

        info_label = QLabel("Apenas vendas acima deste valor serão notificadas")
        info_label.setStyleSheet("font-size: 11px; color: #868e96; font-style: italic;")
        layout.addWidget(info_label)
        layout.addStretch()

        return self.min_value_widget

    def _create_recipients_section(self):
        """Cria a seção de gerenciamento de destinatários."""
        section = QGroupBox("👥 Gerenciamento de Destinatários")
        section.setStyleSheet(self._get_section_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Descrição
        desc = QLabel("Configure os números de telefone que receberão todas as notificações do sistema")
        desc.setStyleSheet("font-size: 13px; color: #6c757d; margin-bottom: 10px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Lista de destinatários
        self.recipients_list = QListWidget()
        self.recipients_list.setMaximumHeight(140)
        self.recipients_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #e9ecef;
                border-radius: 10px;
                background-color: white;
                font-size: 13px;
                padding: 8px;
                selection-background-color: #007bff;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f8f9fa;
                background-color: transparent;
                border-radius: 6px;
                margin-bottom: 5px;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                border: 2px solid #007bff;
                color: #007bff;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
                border: 1px solid #007bff;
            }
        """)
        layout.addWidget(self.recipients_list)

        # Controles de adicionar/remover
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(15)

        # Adicionar
        add_widget = QWidget()
        add_layout = QHBoxLayout(add_widget)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(8)

        add_label = QLabel("Adicionar número:")
        add_label.setStyleSheet("font-size: 12px; color: #495057;")
        add_layout.addWidget(add_label)

        self.new_recipient_input = QLineEdit()
        self.new_recipient_input.setPlaceholderText("Ex: 5511999999999")
        self.new_recipient_input.setMaximumWidth(150)
        self.new_recipient_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        add_layout.addWidget(self.new_recipient_input)

        add_button = QPushButton("➕ Adicionar")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        add_button.clicked.connect(self.add_recipient)
        add_layout.addWidget(add_button)

        controls_layout.addWidget(add_widget)
        controls_layout.addStretch()

        # Remover
        remove_button = QPushButton("🗑️ Remover Selecionado")
        remove_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        remove_button.clicked.connect(self.remove_recipient)
        controls_layout.addWidget(remove_button)

        layout.addWidget(controls_widget)

        return section

    def _create_advanced_section(self):
        """Cria a seção de configurações avançadas."""
        section = QGroupBox("⚙️ Configurações Avançadas")
        section.setStyleSheet(self._get_section_style())
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Controle de delay
        delay_widget = QWidget()
        delay_layout = QHBoxLayout(delay_widget)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        delay_layout.setSpacing(12)

        delay_icon = QLabel("⏱️")
        delay_icon.setStyleSheet("font-size: 24px;")
        delay_layout.addWidget(delay_icon)

        delay_label = QLabel("Delay mínimo entre notificações:")
        delay_label.setStyleSheet("font-size: 14px; color: #495057; font-weight: bold;")
        delay_layout.addWidget(delay_label)

        self.notification_delay_input = QLineEdit("0")
        self.notification_delay_input.setMaximumWidth(80)
        self.notification_delay_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
                background-color: white;
                font-weight: bold;
                text-align: center;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
        """)
        self.notification_delay_input.setToolTip("Segundos de espera entre notificações consecutivas (0 = sem delay)")
        delay_layout.addWidget(self.notification_delay_input)

        delay_unit = QLabel("segundos")
        delay_unit.setStyleSheet("font-size: 12px; color: #6c757d;")
        delay_layout.addWidget(delay_unit)

        delay_hint = QLabel("(0 = enviar imediatamente)")
        delay_hint.setStyleSheet("font-size: 11px; color: #868e96; font-style: italic;")
        delay_layout.addWidget(delay_hint)

        delay_layout.addStretch()

        layout.addWidget(delay_widget)

        return section

    def _create_action_bar(self):
        """Cria a barra de ações no rodapé."""
        action_bar = QWidget()
        action_bar.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 2px solid #e9ecef;
                padding: 20px;
                margin-top: 20px;
            }
        """)
        layout = QHBoxLayout(action_bar)
        layout.setSpacing(20)

        # Botão de prévia
        preview_button = QPushButton("👁️ Ver Exemplo de Mensagem")
        preview_button.setMinimumHeight(45)
        preview_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 25px;
                font-weight: bold;
                font-size: 13px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #138496;
                border: 2px solid #17a2b8;
            }
        """)
        preview_button.clicked.connect(self.preview_sale_notification)
        layout.addWidget(preview_button)

        layout.addStretch()

        # Botão de teste
        test_button = QPushButton("📤 Enviar Teste")
        test_button.setMinimumHeight(45)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                border-radius: 10px;
                padding: 12px 25px;
                font-weight: bold;
                font-size: 13px;
                min-width: 160px;
            }
            QPushButton:hover {
                background-color: #e0a800;
                border: 2px solid #ffc107;
            }
        """)
        test_button.clicked.connect(self.test_notifications)
        layout.addWidget(test_button)

        # Botão salvar
        save_button = QPushButton("💾 Salvar Configurações")
        save_button.setMinimumHeight(45)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 25px;
                font-weight: bold;
                font-size: 13px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #0056b3;
                border: 2px solid #007bff;
            }
        """)
        save_button.clicked.connect(self.save_notifications_config)
        layout.addWidget(save_button)

        return action_bar

    def _get_section_style(self):
        """Retorna estilos comuns para seções."""
        return """
            QGroupBox {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #e9ecef;
                border-radius: 12px;
                margin-top: 15px;
                padding-top: 20px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 10px;
                color: #2c3e50;
                font-weight: bold;
                font-size: 16px;
            }
        """

    def update_all_ui_states(self):
        """Atualiza todos os estados da interface com base nas configurações atuais."""
        try:
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            settings = notifier.get_settings()

            # Atualizar estados dos toggles
            if hasattr(self, 'sales_notifications_checkbox'):
                enabled = settings.get('enable_sale_notifications', True)
                self.sales_notifications_checkbox.setChecked(enabled)
                self.sales_notifications_checkbox.setText("ON" if enabled else "OFF")
                self.min_value_widget.setVisible(enabled)

            if hasattr(self, 'cash_opening_checkbox'):
                enabled = settings.get('enable_cash_notifications', True)
                self.cash_opening_checkbox.setChecked(enabled)
                self.cash_opening_checkbox.setText("ON" if enabled else "OFF")

            if hasattr(self, 'stock_alerts_checkbox'):
                enabled = settings.get('enable_low_stock_alerts', False)
                self.stock_alerts_checkbox.setChecked(enabled)
                self.stock_alerts_checkbox.setText("ON" if enabled else "OFF")

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao atualizar estados da UI: {e}")

    def on_sale_notifications_ui_toggled(self):
        """Chamado quando o toggle de vendas na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()
            sender.setText("ON" if enabled else "OFF")

            # Mostrar/esconder o campo de valor mínimo
            if hasattr(self, 'min_value_widget'):
                self.min_value_widget.setVisible(enabled)

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_sale_notifications(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar notificações de vendas: {e}")

    def on_cash_notifications_ui_toggled(self):
        """Chamado quando o toggle de caixa na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()
            sender.setText("ON" if enabled else "OFF")

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_cash_notifications(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar notificações de caixa: {e}")

    def on_stock_alerts_ui_toggled(self):
        """Chamado quando o toggle de alertas de estoque na UI é alterado."""
        try:
            sender = self.sender()
            enabled = sender.isChecked()
            sender.setText("ON" if enabled else "OFF")

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_low_stock_alerts(enabled)

            self.update_notifications_status()

        except Exception as e:
            print(f"Erro ao alterar alertas de estoque: {e}")
