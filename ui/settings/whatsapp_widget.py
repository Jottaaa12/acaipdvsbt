import json
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QDialog, QLineEdit,
    QMessageBox, QTabWidget, QListWidget, QHBoxLayout, QCheckBox, QGroupBox, QTextEdit, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from config_manager import ConfigManager
from ui.theme import ModernTheme
from data.settings_repository import SettingsRepository

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

class WhatsAppWidget(QWidget):
    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.config_manager = ConfigManager()
        self.settings_repo = SettingsRepository()
        self.qr_code_dialog = None

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        # Define um tamanho padrão para a janela
        self.resize(600, 700)

        # Layout principal que conterá a área de rolagem
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # Área de rolagem
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll_area)

        # Container para todo o conteúdo
        container = QWidget()
        scroll_area.setWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(15)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        connection_tab = self._create_whatsapp_connection_tab()
        tab_widget.addTab(connection_tab, "Conexão e Gerentes")

        notifications_tab = self.create_notifications_tab()
        tab_widget.addTab(notifications_tab, "Notificações")

        instructions_tab = QWidget()
        instructions_layout = QVBoxLayout(instructions_tab)
        instructions = QLabel(
            "<b>Como conectar o WhatsApp:</b><br><br>"
            "1. Clique em <b>Conectar</b> para gerar o QR Code.<br>"
            "2. Abra o WhatsApp no seu celular.<br>"
            "3. Toque no ícone de menu (⋮) → 'Aparelhos conectados' → 'Conectar um aparelho'.<br>"
            "4. Escaneie o QR Code mostrado nesta tela.<br>"
            "5. Aguarde a confirmação de conexão estabelecida.<br><br>"
            "<b>Gerentes Autorizados:</b><br>"
            "Os números adicionados na lista de gerentes terão permissão para executar comandos no sistema, como <i>/caixa status</i>, <i>/vendas</i>, etc."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 13px; line-height: 1.5;")
        instructions_layout.addWidget(instructions)
        instructions_layout.addStretch()
        tab_widget.addTab(instructions_tab, "Instruções")

        self.load_whatsapp_config_to_ui()
        
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()
        self._update_whatsapp_ui_state('connected' if manager.is_ready else 'disconnected')

    def connect_signals(self):
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()
        manager.qr_code_ready.connect(self._show_qr_code_dialog)
        manager.status_updated.connect(self._handle_whatsapp_connection_status)
        manager.error_occurred.connect(self._handle_whatsapp_connection_status)
        manager.log_updated.connect(self.on_whatsapp_log_updated)

    def disconnect_signals(self):
        try:
            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()
            manager.qr_code_ready.disconnect(self._show_qr_code_dialog)
            manager.status_updated.disconnect(self._handle_whatsapp_connection_status)
            manager.error_occurred.disconnect(self._handle_whatsapp_connection_status)
            manager.log_updated.disconnect(self.on_whatsapp_log_updated)
        except (TypeError, RuntimeError):
            pass # Ignore errors if signals are not connected

    def closeEvent(self, event):
        self.disconnect_signals()
        super().closeEvent(event)

    def _create_whatsapp_connection_tab(self):
        connection_tab = QWidget()
        layout = QVBoxLayout(connection_tab)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(15, 15, 15, 15)

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

        actions_group = QGroupBox("Ações de Conexão")
        actions_layout = QHBoxLayout(actions_group)
        self.whatsapp_connect_button = QPushButton("Conectar")
        self.whatsapp_connect_button.setMinimumHeight(40)
        self.whatsapp_connect_button.clicked.connect(self._toggle_whatsapp_connection)
        actions_layout.addWidget(self.whatsapp_connect_button)
        actions_layout.addStretch()
        layout.addWidget(actions_group)

        # NEW MANAGER GROUP
        managers_group = QGroupBox("Gerentes Autorizados para Comandos")
        managers_layout = QVBoxLayout(managers_group)
        managers_layout.setSpacing(10)

        managers_info = QLabel("Os números nesta lista podem executar comandos como /caixa, /vendas, etc.")
        managers_info.setWordWrap(True)
        managers_layout.addWidget(managers_info)

        self.managers_list_widget = QListWidget()
        managers_layout.addWidget(self.managers_list_widget)

        add_manager_layout = QHBoxLayout()
        self.new_manager_input = QLineEdit(placeholderText="Novo número com DDI (Ex: 5511912345678)")
        self.add_manager_button = QPushButton("Adicionar")
        self.remove_manager_button = QPushButton("Remover Selecionado")
        add_manager_layout.addWidget(self.new_manager_input, 1)
        add_manager_layout.addWidget(self.add_manager_button)
        add_manager_layout.addWidget(self.remove_manager_button)
        managers_layout.addLayout(add_manager_layout)

        self.save_managers_button = QPushButton("Salvar Lista de Gerentes")
        self.save_managers_button.setMinimumHeight(40)
        managers_layout.addWidget(self.save_managers_button)
        
        layout.addWidget(managers_group)

        # Test message group
        test_group = QGroupBox("Teste de Conexão")
        test_layout = QVBoxLayout(test_group)
        self.send_test_button = QPushButton("Enviar Mensagem de Teste")
        self.send_test_button.setMinimumHeight(40)
        self.test_number_input = QLineEdit(placeholderText="Nº para receber a mensagem de teste")
        test_layout.addWidget(QLabel("Enviar um teste para confirmar que a conexão está funcionando:"))
        test_layout.addWidget(self.test_number_input)
        test_layout.addWidget(self.send_test_button)
        layout.addWidget(test_group)

        qr_info_group = QGroupBox("QR Code")
        qr_info_layout = QVBoxLayout(qr_info_group)
        qr_info_label = QLabel("Ao clicar em 'Conectar', o QR Code será exibido em uma nova janela para facilitar a leitura.")
        qr_info_label.setWordWrap(True)
        qr_info_label.setStyleSheet("font-size: 13px; color: #6c757d;")
        qr_info_layout.addWidget(qr_info_label)
        layout.addWidget(qr_info_group)
        
        layout.addStretch()

        # Connect new buttons
        self.add_manager_button.clicked.connect(self._add_manager)
        self.remove_manager_button.clicked.connect(self._remove_manager)
        self.save_managers_button.clicked.connect(self._save_managers)
        self.send_test_button.clicked.connect(self.send_test_whatsapp_message)
        
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
        
        elif status == 'connected':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_green)
            self.whatsapp_status_text.setText(message or "Conectado")
            self.whatsapp_connect_button.setText("🔌 Desconectar")
            self.whatsapp_connect_button.setEnabled(True)
            self.send_test_button.setEnabled(True)

        elif status == 'pending':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_yellow)
            self.whatsapp_status_text.setText(message or "Processando...")
            self.whatsapp_connect_button.setEnabled(False)
            self.send_test_button.setEnabled(False)

        elif status == 'qr':
            self.whatsapp_status_indicator.setStyleSheet(style_indicator_yellow)
            self.whatsapp_status_text.setText("Aguardando leitura do QR Code")
            self.whatsapp_connect_button.setText("Cancelar Conexão")
            self.whatsapp_connect_button.setEnabled(True)
            self.send_test_button.setEnabled(False)
            if self.qr_code_dialog:
                self.qr_code_dialog.update_status("Aguardando leitura...")

    def _show_qr_code_dialog(self, image_path):
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
        self.on_whatsapp_status_updated(status_message)
        is_connected = "Conectado" in status_message
        is_failed = "Erro" in status_message or "falhou" in status_message.lower() or "Desconectado" in status_message
        if self.qr_code_dialog and (is_connected or is_failed):
            self.qr_code_dialog.close()
            self.qr_code_dialog = None

    def on_whatsapp_log_updated(self, message):
        QMessageBox.information(self, "Informação do WhatsApp", message)

    def on_whatsapp_status_updated(self, status_message):
        logging.info(f"WhatsApp status update received: {status_message}")
        if "Conectado" in status_message:
            self._update_whatsapp_ui_state('connected', status_message)
        elif "Desconectado" in status_message:
            self._update_whatsapp_ui_state('disconnected', status_message)
        elif "Erro" in status_message or "falhou" in status_message.lower():
            self._update_whatsapp_ui_state('disconnected', status_message)
            if not "Desconectado" in status_message:
                QMessageBox.warning(self, "Erro no WhatsApp", status_message)
        else:
            self._update_whatsapp_ui_state('pending', status_message)

    def send_test_whatsapp_message(self):
        from integrations.whatsapp_manager import WhatsAppManager
        manager = WhatsAppManager.get_instance()
        if not manager.is_ready:
            QMessageBox.warning(self, "WhatsApp Não Conectado", "Por favor, conecte o WhatsApp antes de enviar uma mensagem de teste.")
            return
        
        test_number = self.test_number_input.text().strip()
        if not test_number:
            QMessageBox.warning(self, "Número Não Configurado", "Por favor, insira um número de telefone para enviar a mensagem de teste.")
            return
            
        test_message = "✅ Mensagem de teste do sistema PDV Moderno. A integração com o WhatsApp está funcionando!"
        result = manager.send_message(test_number, test_message)
        
        if result.get('success'):
            QMessageBox.information(self, "Sucesso", f"Mensagem de teste enviada para {test_number}.")
        else:
            QMessageBox.critical(self, "Falha", f"Não foi possível enviar a mensagem de teste.\n\nErro: {result.get('error')}")

    def load_whatsapp_config_to_ui(self):
        # Load authorized managers
        self.managers_list_widget.clear()
        numbers_str = self.settings_repo.get_setting('whatsapp_manager_numbers', '')
        if numbers_str:
            numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]
            self.managers_list_widget.addItems(numbers)
        
        # Load the test number from the old config for convenience, if it exists
        whatsapp_config = self.config_manager.get_section('whatsapp')
        self.test_number_input.setText(whatsapp_config.get('notification_number', ''))

    def _add_manager(self):
        number = self.new_manager_input.text().strip()
        if not number:
            QMessageBox.warning(self, "Campo Vazio", "Digite um número de telefone.")
            return
        
        # Simple validation to avoid duplicates
        items = [self.managers_list_widget.item(i).text() for i in range(self.managers_list_widget.count())]
        if number in items:
            QMessageBox.warning(self, "Número Duplicado", "Este número já está na lista.")
            return
            
        self.managers_list_widget.addItem(number)
        self.new_manager_input.clear()

    def _remove_manager(self):
        current_item = self.managers_list_widget.currentItem()
        if current_item:
            self.managers_list_widget.takeItem(self.managers_list_widget.row(current_item))
        else:
            QMessageBox.warning(self, "Nenhum Selecionado", "Selecione um número da lista para remover.")

    def _save_managers(self):
        try:
            numbers = [self.managers_list_widget.item(i).text() for i in range(self.managers_list_widget.count())]
            numbers_str = ",".join(numbers)
            self.settings_repo.save_setting('whatsapp_manager_numbers', numbers_str)

            # Update manager in real-time
            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()
            manager.update_authorized_users()

            QMessageBox.information(self, "Sucesso", "Lista de gerentes autorizados foi salva com sucesso!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar a lista de gerentes.\n\nErro: {e}")
            logging.error(f"Erro ao salvar gerentes do WhatsApp: {e}", exc_info=True)

    def _create_toggle_switch(self, text):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        toggle = QCheckBox()
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(f"""
            QCheckBox::indicator {{ width: 44px; height: 24px; border-radius: 12px; border: 1px solid {ModernTheme.GRAY_LIGHT}; background-color: {ModernTheme.GRAY}; }}
            QCheckBox::indicator:checked {{ background-color: {ModernTheme.PRIMARY}; border: 1px solid {ModernTheme.PRIMARY}; }}
            QCheckBox::indicator:handle {{ width: 20px; height: 20px; border-radius: 10px; background-color: white; margin: 2px; }}
            QCheckBox::indicator:unchecked:handle {{ subcontrol-position: left; }}
            QCheckBox::indicator:checked:handle {{ subcontrol-position: right; }}
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
        update_status_label(toggle.checkState().value)
        layout.addWidget(toggle)
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(status_label)
        return widget, toggle

    def create_notifications_tab(self):
        notifications_tab = QWidget()
        main_layout = QVBoxLayout(notifications_tab)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)

        # --- Master Switch ---
        master_group = QGroupBox("Controle Geral de Notificações")
        master_layout = QVBoxLayout(master_group)
        master_widget, self.global_notifications_checkbox = self._create_toggle_switch("Ativar Todas as Notificações (Global)")
        master_layout.addWidget(master_widget)
        layout.addWidget(master_group)

        # --- Features Group ---
        self.features_group = QGroupBox("Funcionalidades de Notificação")
        features_layout = QVBoxLayout(self.features_group)
        features_layout.setSpacing(15)
        sales_widget, self.sales_notifications_checkbox = self._create_toggle_switch("Notificar Vendas Realizadas")
        cash_widget, self.cash_notifications_checkbox = self._create_toggle_switch("Notificar Abertura e Fechamento de Caixa")
        stock_widget, self.stock_alerts_checkbox = self._create_toggle_switch("Enviar Alertas de Estoque Baixo")
        features_layout.addWidget(sales_widget)
        features_layout.addWidget(cash_widget)
        features_layout.addWidget(stock_widget)
        layout.addWidget(self.features_group)

        self.global_notifications_checkbox.stateChanged.connect(
            lambda state: self.features_group.setEnabled(state == Qt.CheckState.Checked.value)
        )

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

        recipients_group = QGroupBox("Gerenciar Destinatários")
        recipients_layout = QVBoxLayout(recipients_group)
        self.recipients_list = QListWidget()
        self.recipients_list.setMaximumHeight(120)
        recipients_layout.addWidget(self.recipients_list)
        add_recipient_layout = QHBoxLayout()
        self.new_recipient_input = QLineEdit(placeholderText="Novo número (Ex: 5511912345678)")
        add_recipient_layout.addWidget(self.new_recipient_input)
        self.add_recipient_button = QPushButton("Adicionar")
        self.add_recipient_button.clicked.connect(self.add_recipient)
        add_recipient_layout.addWidget(self.add_recipient_button)
        self.remove_recipient_button = QPushButton("Remover Selecionado")
        self.remove_recipient_button.clicked.connect(self.remove_recipient)
        add_recipient_layout.addWidget(self.remove_recipient_button)
        recipients_layout.addLayout(add_recipient_layout)
        layout.addWidget(recipients_group)

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

        main_layout.addWidget(container)
        self.load_notifications_config_to_ui()
        return notifications_tab

    def add_recipient(self):
        phone = self.new_recipient_input.text().strip()
        if not phone:
            QMessageBox.warning(self, "Campo Vazio", "Digite um número de telefone válido.")
            return
        for i in range(self.recipients_list.count()):
            if self.recipients_list.item(i).text() == phone:
                QMessageBox.warning(self, "Número Já Existe", "Este número já está na lista.")
                return
        self.recipients_list.addItem(phone)
        self.new_recipient_input.clear()

    def remove_recipient(self):
        current_item = self.recipients_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Nenhum Selecionado", "Selecione um número para remover.")
            return
        reply = QMessageBox.question(self, "Confirmar Remoção", f"Remover o número {current_item.text()} da lista?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.recipients_list.takeItem(self.recipients_list.row(current_item))

    def load_notifications_config_to_ui(self):
        try:
            # Carregar configuração global
            is_globally_enabled = self.settings_repo.are_notifications_globally_enabled()
            self.global_notifications_checkbox.setChecked(is_globally_enabled)
            self.features_group.setEnabled(is_globally_enabled)

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            settings = notifier.get_settings()
            self.sales_notifications_checkbox.setChecked(settings.get('enable_sale_notifications', True))
            self.cash_notifications_checkbox.setChecked(settings.get('enable_cash_notifications', True))
            self.stock_alerts_checkbox.setChecked(settings.get('enable_low_stock_alerts', False))
            min_value = settings.get('minimum_sale_value', 0.0)
            self.min_sale_value_input.setText(f"{min_value:.2f}".replace('.', ','))
            delay = settings.get('notification_delay', 0)
            self.notification_delay_input.setText(str(delay))
            self.recipients_list.clear()
            recipients = settings.get('notification_recipients', [])
            if recipients:
                for r in recipients:
                    self.recipients_list.addItem(r)
        except Exception as e:
            logging.error(f"Erro ao carregar configurações de notificações: {e}", exc_info=True)

    def save_notifications_config(self):
        try:
            # Salvar configuração global
            is_globally_enabled = self.global_notifications_checkbox.isChecked()
            self.settings_repo.set_global_notification_status(is_globally_enabled)

            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            notifier.enable_sale_notifications(self.sales_notifications_checkbox.isChecked())
            notifier.enable_cash_notifications(self.cash_notifications_checkbox.isChecked())
            notifier.enable_low_stock_alerts(self.stock_alerts_checkbox.isChecked())
            try:
                min_value_text = self.min_sale_value_input.text().replace(',', '.')
                min_value = float(min_value_text) if min_value_text else 0.0
                notifier.set_minimum_sale_value(min_value)
            except ValueError:
                QMessageBox.warning(self, "Valor Inválido", "O valor mínimo deve ser um número válido.")
                return
            recipients_from_ui = [self.recipients_list.item(i).text() for i in range(self.recipients_list.count())]
            current_recipients = notifier.get_settings().get('notification_recipients', [])
            for recipient in recipients_from_ui:
                if recipient not in current_recipients:
                    notifier.add_recipient(recipient)
            for recipient in current_recipients:
                if recipient not in recipients_from_ui:
                    notifier.remove_recipient(recipient)
            try:
                delay = int(self.notification_delay_input.text()) if self.notification_delay_input.text() else 0
                settings = notifier.get_settings()
                settings['notification_delay'] = delay
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
        try:
            sample_sale_data = {'id': 12345, 'customer_name': 'João Silva', 'total_amount': 45.90}
            sample_payment_details = [{'amount': 25.90, 'method': 'Dinheiro'}, {'amount': 20.00, 'method': 'PIX'}]
            from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
            notifier = get_whatsapp_sales_notifier()
            example_message = notifier._build_sale_message(sample_sale_data, sample_payment_details)
            if example_message:
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
                message_display.setStyleSheet("QTextEdit { font-family: 'Courier New', monospace; font-size: 11px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; }")
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
        try:
            from integrations.whatsapp_manager import WhatsAppManager
            manager = WhatsAppManager.get_instance()
            if not manager.is_ready:
                QMessageBox.warning(self, "WhatsApp Desconectado", "O WhatsApp não está conectado. Por favor, conecte primeiro na aba 'Conexão'.")
                return
            recipients = [self.recipients_list.item(i).text() for i in range(self.recipients_list.count())]
            if not recipients:
                notification_number = self.test_number_input.text().strip() # Changed from whatsapp_phone_input
                if notification_number:
                    recipients.append(notification_number)
                else:
                    QMessageBox.warning(self, "Nenhum Destinatário", "Não há destinatários configurados. Adicione ao menos um número na lista ou configure um número padrão para teste.")
                    return
            test_message = f"""🧪 *TESTE DO SISTEMA PDV MODERNO*\n\n✅ Configurações de notificações funcionando normalmente!\n\n📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n👤 Usuário: {self.current_user.get('username', 'Sistema')}\n\nEste é apenas um teste. Se você recebeu esta mensagem, as notificações estão configuradas corretamente! 🎉"""
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
                QMessageBox.information(self, "Teste Enviado", f"✅ Teste enviado com sucesso para {success_count} de {len(recipients)} destinatários!\n\nVerifique seus celulares para confirmar que a mensagem foi recebida.")
            else:
                QMessageBox.warning(self, "Falha no Teste", "❌ Não foi possível enviar a mensagem de teste para nenhum destinatário.\n\nVerifique a conexão do WhatsApp e os números configurados.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao testar notificações:\n{str(e)}")
