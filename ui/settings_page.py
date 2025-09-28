from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QPushButton, QGridLayout, QScrollArea,
    QDialog, QFrame, QLineEdit, QComboBox, QMessageBox, QTabWidget, QListWidget, QHBoxLayout,
    QCheckBox
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
        self._create_modal_dialog("Configurações do WhatsApp", widget)

        # Tentar conectar automaticamente se já houver sessão salva
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager()
        if manager.client is None:
            print(f"[{datetime.now()}] WhatsApp: Tentando conectar automaticamente...")
            manager.connect()

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
        """Cria o widget de configuração do WhatsApp para QR Code e verificação de conexão."""
        whatsapp_widget = QWidget()
        layout = QVBoxLayout(whatsapp_widget)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Título
        title = QLabel("Configuração do WhatsApp")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Status da conexão
        self.whatsapp_status_label = QLabel("⏳ Aguardando configuração...")
        self.whatsapp_status_label.setStyleSheet("""
            QLabel {{
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
        layout.addWidget(self.whatsapp_status_label)

        # Botões de ação
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)

        self.check_connection_button = QPushButton("🔍 Verificar Conexão")
        self.check_connection_button.setMinimumHeight(40)
        self.check_connection_button.clicked.connect(self.check_whatsapp_connection)
        self.check_connection_button.setStyleSheet("""
            QPushButton {{
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #138496;
            }}
            QPushButton:disabled {{
                background-color: #6c757d;
                color: #adb5bd;
            }}
        """)

        self.qr_code_button = QPushButton("📱 Conectar WhatsApp")
        self.qr_code_button.setMinimumHeight(40)
        self.qr_code_button.clicked.connect(self.generate_qr_code)
        self.qr_code_button.setStyleSheet("""
            QPushButton {{
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
            QPushButton:disabled {{
                background-color: #6c757d;
                color: #adb5bd;
            }}
        """)

        buttons_layout.addWidget(self.check_connection_button)
        buttons_layout.addWidget(self.qr_code_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # Área para exibir QR Code com melhor design
        qr_frame = QFrame()
        qr_frame.setFrameShape(QFrame.Shape.Box)
        qr_frame.setStyleSheet("""
            QFrame {{
                border: 2px dashed #dee2e6;
                border-radius: 8px;
                background-color: #f8f9fa;
            }}
        """)

        qr_layout = QVBoxLayout(qr_frame)

        self.qr_code_label = QLabel("Clique em 'Conectar WhatsApp' para gerar o QR Code")
        self.qr_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_code_label.setStyleSheet("""
            QLabel {{
                padding: 30px;
                color: #6c757d;
                font-size: 14px;
                font-weight: 500;
            }}
        """)
        self.qr_code_label.setMinimumHeight(250)
        qr_layout.addWidget(self.qr_code_label)

        layout.addWidget(qr_frame)

        # Instruções claras
        instructions = QLabel(
            "📱 Como conectar o WhatsApp:\n\n"
            "1. Clique em 'Conectar WhatsApp' para gerar o QR Code\n"
            "2. Abra o WhatsApp no seu celular\n"
            "3. Toque no ícone de menu (⋮) → 'WhatsApp Web'\n"
            "4. Escaneie o QR Code mostrado acima\n"
            "5. Aguarde a confirmação de conexão estabelecida\n\n"
            "⚠️ Mantenha o computador ligado durante o processo de conexão"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            QLabel {{
                color: #495057;
                font-size: 13px;
                line-height: 1.5;
                background-color: #e9ecef;
                padding: 15px;
                border-radius: 6px;
                border: 1px solid #dee2e6;
            }}
        """)
        layout.addWidget(instructions)

        # Status adicional
        status_info = QLabel(
            "💡 Dica: Após conectar, a sessão será salva automaticamente para próximos logins."
        )
        status_info.setWordWrap(True)
        status_info.setStyleSheet("""
            QLabel {{
                color: #6c757d;
                font-size: 12px;
                font-style: italic;
                margin-top: 5px;
            }}
        """)
        layout.addWidget(status_info)

        # Verificar status inicial
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
            manager = WhatsAppManager()

            # Conectar os sinais corretos
            manager.qr_code_ready.connect(self.on_qr_code_path_received)
            manager.status_updated.connect(self.on_whatsapp_status_updated)

            # Iniciar conexão
            manager.connect()

            self.whatsapp_status_label.setText("🔄 Iniciando conexão com WhatsApp...")
            self.whatsapp_status_label.setStyleSheet("""
                QLabel {{
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

    def check_whatsapp_connection(self):
        """Verifica o status de conexão do WhatsApp."""
        try:
            self.check_connection_button.setText("Verificando...")
            self.check_connection_button.setEnabled(False)

            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager()

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
