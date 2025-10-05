from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout,
    QDialog, QLineEdit, QComboBox, QMessageBox, QTabWidget, QListWidget, QHBoxLayout
)
from PyQt6.QtCore import Qt
from config_manager import ConfigManager

class HardwareWidget(QWidget):
    def __init__(self, scale_handler, printer_handler, parent=None):
        super().__init__(parent)
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_hardware_config_to_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
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

    def load_hardware_config_to_ui(self):
        config = self.config_manager.load_config()

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
        self.load_printer_config_to_ui()

    def save_all_hardware_config(self):
        config = self.config_manager.load_config()

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
        self.save_printer_config()

        self.config_manager.save_config(config)
        QMessageBox.information(self, "Sucesso", "Configurações de hardware salvas com sucesso!")
        # self.operation_mode_changed.emit() # This signal needs to be handled by the main window

    def test_scale_connection(self):
        sender = self.sender()
        if sender:
            original_text = sender.text()
            sender.setEnabled(False)
            sender.setText("🔄 Testando...")

        try:
            self.save_all_hardware_config()
            config = self.config_manager.load_config()
            hardware_mode = config.get('hardware_mode', 'test')
            scale_config = config.get('scale', {})
            self.scale_handler.reconfigure(mode=hardware_mode, **scale_config)
            QMessageBox.information(self, "Configuração Aplicada",
                                    "As novas configurações da balança foram aplicadas.\n\n"
                                    "O sistema tentará se reconectar em segundo plano. "
                                    "Verifique o status no Dashboard.")
        finally:
            if sender:
                sender.setEnabled(True)
                sender.setText(original_text)

    def on_printer_type_changed(self, printer_type):
        self.usb_group.hide()
        self.bluetooth_group.hide()
        self.serial_group.hide()
        self.network_group.hide()

        if printer_type == "Térmica (USB)":
            self.usb_group.show()
        elif printer_type == "Térmica (Bluetooth)":
            self.bluetooth_group.show()
        elif printer_type == "Térmica (Serial)":
            self.serial_group.show()
        elif printer_type == "Térmica (Rede)":
            self.network_group.show()

    def search_com_ports(self):
        try:
            from hardware.printer_handler import PrinterHandler
            available_ports = PrinterHandler.get_available_com_ports()

            if not available_ports:
                QMessageBox.information(self, "Procurar Portas", "Nenhuma porta COM foi encontrada no sistema.")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Selecionar Porta COM")
            dialog.setModal(True)
            dialog.resize(400, 300)
            layout = QVBoxLayout(dialog)
            port_list = QListWidget()
            for port in available_ports:
                port_list.addItem(port)
            layout.addWidget(QLabel("Portas COM disponíveis:"))
            layout.addWidget(port_list)
            button_layout = QHBoxLayout()
            select_button = QPushButton("Selecionar")
            select_button.clicked.connect(dialog.accept)
            cancel_button = QPushButton("Cancelar")
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(select_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_port = port_list.currentItem()
                if selected_port:
                    port_name = selected_port.text()
                    sender = self.sender()
                    if sender == self.bluetooth_search_button:
                        self.bluetooth_port_input.setText(port_name)
                    elif sender == self.serial_search_button:
                        self.serial_port_input.setText(port_name)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao procurar portas COM: {e}")

    def test_printer_connection(self):
        sender = self.sender()
        if sender:
            original_text = sender.text()
            sender.setEnabled(False)
            sender.setText("🔄 Testando...")

        try:
            self.save_printer_config()
            config = self.config_manager.load_config()
            printer_config = config.get('printer', {})
            from hardware.printer_handler import PrinterHandler
            temp_handler = PrinterHandler(printer_config)
            success, message = temp_handler.test_print()
            if success:
                QMessageBox.information(self, "Teste de Impressora", f"Teste realizado com sucesso!\n\n{message}")
            else:
                QMessageBox.warning(self, "Teste de Impressora", f"Falha no teste:\n\n{message}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao testar impressora: {e}")
        finally:
            if sender:
                sender.setEnabled(True)
                sender.setText(original_text)

    def load_printer_config_to_ui(self):
        printer_config = self.config_manager.get_section('printer')
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
        self.printer_vendor_id_input.setText(printer_config.get('usb_vendor_id', ''))
        self.printer_product_id_input.setText(printer_config.get('usb_product_id', ''))
        self.bluetooth_port_input.setText(printer_config.get('bluetooth_port', ''))
        self.serial_port_input.setText(printer_config.get('serial_port', ''))
        self.serial_baudrate_input.setText(str(printer_config.get('serial_baudrate', 9600)))
        self.network_ip_input.setText(printer_config.get('network_ip', ''))
        self.network_port_input.setText(str(printer_config.get('network_port', 9100)))

    def save_printer_config(self):
        config = self.config_manager.load_config()
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
        self.config_manager.save_config(config)
