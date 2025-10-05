from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QPushButton, QGridLayout, QScrollArea,
    QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter

from ui.theme import ModernTheme, IconTheme
from ui.group_management_widget import GroupManagementWidget
from ui.payment_method_management_widget import PaymentMethodManagementWidget
from ui.data_management_dialog import DataManagementDialog
from ui.user_management_page import UserManagementPage
from ui.audit_log_dialog import AuditLogDialog
from ui.backup_dialog import BackupDialog
from ui.shortcut_management_widget import ShortcutManagementWidget
from ui.settings.establishment_widget import EstablishmentWidget
from ui.settings.hardware_widget import HardwareWidget
from ui.settings.whatsapp_widget import WhatsAppWidget


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
        widget = EstablishmentWidget()
        self._create_modal_dialog("Configurações do Estabelecimento", widget)

    def open_hardware_settings(self):
        widget = HardwareWidget(self.scale_handler, self.printer_handler)
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
        widget = WhatsAppWidget(self.current_user)
        self._create_modal_dialog("Configurações do WhatsApp", widget)
