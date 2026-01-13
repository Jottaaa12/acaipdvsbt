from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QStatusBar,
    QMessageBox, QApplication, QScrollArea
)
from PyQt6.QtGui import QFont, QColor, QBrush, QPainter, QScreen
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation, QRect
from datetime import datetime, timedelta
import json

from utils import get_data_path
from config_manager import ConfigManager

from ui.theme import ModernTheme, IconTheme, ThemeManager
from ui.sidebar import ModernSidebar
from ui.dashboard import ModernDashboard
from ui.product_management_window import ProductManagementWindow
from ui.sales_page import SalesPage
from ui.settings_page import SettingsPage
from ui.cash_page import CashPage
from ui.reports_page import ReportsPage
from ui.user_management_page import UserManagementPage
from ui.sales_history_page import SalesHistoryPage
from ui.credit_management_page import CreditManagementPage
from ui.customer_management_page import CustomerManagementPage
from ui.stock_management_page import StockManagementPage
from ui.audit_log_dialog import AuditLogDialog
from ui.backup_dialog import BackupDialog
from ui.log_console_dialog import LogConsoleDialog
from hardware.scale_handler import ScaleHandler
from hardware.printer_handler import PrinterHandler
from data.sync_manager import SyncManager
from ui.worker import run_in_thread
import database as db
import logging



class ModernMainWindow(QMainWindow):
    """Janela principal moderna"""
    
    logout_requested = pyqtSignal()
    show_notification_signal = pyqtSignal(str, str)
    
    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.current_cash_session = None

        # Gerenciador de Configuração
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        hardware_mode = self.config.get('hardware_mode', 'test')
        
        # Gerenciador de Temas
        self.theme_manager = ThemeManager()

        self.setWindowTitle(f"PDV Açaí - {current_user['username']}")
        self.adjust_window_geometry()

        # Handlers
        self.scale_handler = ScaleHandler(
            mode=hardware_mode,
            **self.config.get('scale', {})
        )
        self.printer_handler = PrinterHandler(
            self.config.get('printer', {})
        )
        self.sync_manager = SyncManager()

        # Integração com WhatsApp para notificações
        try:
            from integrations.whatsapp_manager import WhatsAppManager
            self.whatsapp_manager = WhatsAppManager.get_instance()
            self.whatsapp_manager.set_main_window(self)
            logging.info("Integração com WhatsApp Manager estabelecida na janela principal.")
        except Exception as e:
            logging.error(f"Falha ao integrar com WhatsApp Manager: {e}", exc_info=True)

        # Inicia o handler da balança globalmente
        self.scale_handler.start()

        self.log_console_dialog = LogConsoleDialog(self)

        self.setup_ui()
        self.apply_theme() # Aplica o tema inicial
        self.check_cash_session()
        
        # Timer para atualizações
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(30000)  # 30 segundos

        # Armazena a data da última atualização do dashboard
        self.last_dashboard_date = datetime.now().date()

        # Timer para checagem de data (reiniciar dashboard)
        self.daily_refresh_timer = QTimer()
        self.daily_refresh_timer.timeout.connect(self.check_date_and_refresh)
        self.daily_refresh_timer.start(60000)  # Checa a cada 1 minuto

        # Timer para checagem de status de crédito
        self.credit_check_timer = QTimer()
        self.credit_check_timer.timeout.connect(self.check_credit_status)
        self.credit_check_timer.start(3600000) # Checa a cada hora
        self.check_credit_status() # Checagem inicial

        self.show_notification_signal.connect(self.display_notification)

    def adjust_window_geometry(self):
        """Ajusta a geometria da janela dinamicamente baseada na resolução da tela disponível."""
        try:
            # Obtém a tela primária
            screen = self.screen()
            if not screen:
                # Fallback para tela primária da aplicação
                app = QApplication.instance()
                if app:
                    screen = app.primaryScreen()

            if screen:
                # Obtém a geometria disponível (excluindo barra de tarefas)
                available_geometry = screen.availableGeometry()

                # Calcula tamanho ideal da janela (75% da largura e 70% da altura disponíveis)
                # Usamos porcentagens menores para garantir que caiba considerando margens da janela
                ideal_width = int(available_geometry.width() * 0.75)
                ideal_height = int(available_geometry.height() * 0.7)

                # Define limites mínimos e máximos mais conservadores
                min_width = 1024 # Reduzido para caber em 1366x768 com margem
                min_height = 600 # Reduzido para caber com barra de tarefas
                max_width = available_geometry.width() - 50  # Margem segura
                max_height = available_geometry.height() - 50  # Margem segura

                # Aplica limites
                width = max(min_width, min(ideal_width, max_width))
                height = max(min_height, min(ideal_height, max_height))

                # Centraliza a janela na tela
                x = (available_geometry.width() - width) // 2 + available_geometry.x()
                y = (available_geometry.height() - height) // 2 + available_geometry.y()

                # Define a geometria
                self.setGeometry(x, y, width, height)

                logging.info(f"Janela ajustada dinamicamente: {width}x{height} em ({x},{y}) - Tela disponível: {available_geometry.width()}x{available_geometry.height()}")
            else:
                # Fallback para geometria padrão se não conseguir obter informações da tela
                logging.warning("Não foi possível obter informações da tela. Usando geometria padrão.")
                self.setGeometry(100, 100, 1024, 600)

        except Exception as e:
            logging.error(f"Erro ao ajustar geometria da janela: {e}. Usando geometria padrão.")
            # Fallback seguro com tamanho menor
            self.setGeometry(100, 100, 1024, 600)

    def show_update_notification(self, version, description):
        """Exibe uma notificação de que uma nova atualização está disponível."""
        logging.info(f"Notificando usuário sobre a atualização para a versão {version}")
        
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle("Atualização Disponível")
        msg_box.setText(f"Uma nova versão do sistema está disponível: <b>{version}</b>")
        msg_box.setInformativeText(f"{description}\n\nDeseja abrir a página de atualizações para saber mais?")
        
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def check_credit_status(self):
        """Verifica o status dos fiados (Alerta visual desativado)."""
        # A lógica de alerta visual foi removida conforme solicitação do usuário.
        pass
    
    def setup_ui(self):
        """Configura a interface principal"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal que pode conter o banner
        self.root_layout = QVBoxLayout(central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # Adicionar banner de modo de teste se necessário
        if self.config.get('hardware_mode', 'test') == 'test':
            self.test_mode_banner = QLabel("AMBIENTE DE TESTES - O hardware real (balança, impressora) não será utilizado.")
            self.test_mode_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.test_mode_banner.setStyleSheet("""
                background-color: #FFC107; /* Amarelo Âmbar */
                color: black;
                font-weight: bold;
                padding: 8px;
                font-size: 14px;
            """)
            self.root_layout.addWidget(self.test_mode_banner)

        # Container para a sidebar e conteúdo
        main_content_widget = QWidget()
        main_layout = QHBoxLayout(main_content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.root_layout.addWidget(main_content_widget)
        
        # Sidebar
        self.sidebar = ModernSidebar()
        self.sidebar.page_changed.connect(self.change_page)
        self.sidebar.logout_button.clicked.connect(self.logout)
        self.sidebar.theme_button.clicked.connect(self.toggle_theme) # Conecta o botão de tema
        main_layout.addWidget(self.sidebar)
        
        # Área de conteúdo com Scroll para evitar travamento de redimensionamento
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # O QStackedWidget agora fica dentro do ScrollArea
        self.content_area = QStackedWidget()
        self.scroll_area.setWidget(self.content_area)
        
        main_layout.addWidget(self.scroll_area)
        
        # Páginas
        self.pages = {}
        self.create_pages()
        
        # Define página inicial
        self.change_page("dashboard")

        # Status bar
        self.setup_status_bar()
        
    
    def reload_hardware_handlers(self):
        """Recarrega os handlers de hardware quando o modo de operação muda."""
        logging.info("ModernMainWindow: Recebido sinal para recarregar os handlers de hardware.")
        self.config = self.config_manager.get_config()
        hardware_mode = self.config.get('hardware_mode', 'test')

        # Reconfigura os handlers existentes
        self.scale_handler.reconfigure(
            mode=hardware_mode,
            **self.config.get('scale', {})
        )
        self.printer_handler.reconfigure(
            self.config.get('printer', {})
        )

        # Atualiza o banner de modo de teste
        if hardware_mode == 'test':
            if not hasattr(self, 'test_mode_banner'):
                self.test_mode_banner = QLabel("AMBIENTE DE TESTES - O hardware real (balança, impressora) não será utilizado.")
                self.test_mode_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.test_mode_banner.setStyleSheet("""
                    background-color: #FFC107; /* Amarelo Âmbar */
                    color: black;
                    font-weight: bold;
                    padding: 8px;
                    font-size: 14px;
                """)
                self.root_layout.insertWidget(0, self.test_mode_banner)
            self.test_mode_banner.show()
        else:
            if hasattr(self, 'test_mode_banner'):
                self.test_mode_banner.hide()

        logging.info(f"Handlers de hardware reconfigurados para o modo: {hardware_mode}")

    def create_pages(self):
        """Cria as páginas do sistema"""
        # Dashboard
        self.pages["dashboard"] = ModernDashboard(self.scale_handler, self.printer_handler)
        self.content_area.addWidget(self.pages["dashboard"])
        
        # Products
        self.pages["products"] = ProductManagementWindow()
        self.pages["products"].data_changed.connect(self.on_products_changed)
        self.content_area.addWidget(self.pages["products"])

        # Sales
        self.pages["sales"] = SalesPage(self, self.scale_handler, self.printer_handler)
        self.content_area.addWidget(self.pages["sales"])

        # Sales History
        self.pages["sales_history"] = SalesHistoryPage()
        self.content_area.addWidget(self.pages["sales_history"])

        # Settings
        self.pages["settings"] = SettingsPage(
            scale_handler=self.scale_handler,
            printer_handler=self.printer_handler,
            sync_manager=self.sync_manager,
            current_user=self.current_user,
            sales_page=self.pages["sales"]
        )
        self.content_area.addWidget(self.pages["settings"])
        self.pages["settings"].operation_mode_changed.connect(self.reload_hardware_handlers)
        self.pages["settings"].open_log_console_requested.connect(self.show_log_console)

        # Cash
        self.pages["cash"] = CashPage(self.current_user)
        self.content_area.addWidget(self.pages["cash"])

        # Conecta o sinal de mudança de sessão da página de caixa
        self.pages["cash"].cash_session_changed.connect(self.check_cash_session)

        # Reports Page
        self.pages["reports"] = ReportsPage()
        self.content_area.addWidget(self.pages["reports"])

        # Users page
        self.pages["users"] = UserManagementPage()
        self.content_area.addWidget(self.pages["users"])

        # Stock page
        self.pages["stock"] = StockManagementPage()
        self.content_area.addWidget(self.pages["stock"])

        # Credit management page
        self.pages["credit"] = CreditManagementPage(self.current_user, self.current_cash_session)
        self.content_area.addWidget(self.pages["credit"])

        # Customer management page
        self.pages["customers"] = CustomerManagementPage(self.current_user)
        self.content_area.addWidget(self.pages["customers"])

    def on_products_changed(self):
        """Slot para recarregar dados quando os produtos são alterados."""
        if "sales" in self.pages:
            self.pages["sales"].reload_data()

    def show_log_console(self):
        """Exibe e traz para a frente a janela do console de logs."""
        self.log_console_dialog.show()
        self.log_console_dialog.raise_()
        self.log_console_dialog.activateWindow()
    
    def change_page(self, page_name):
        """Muda para a página especificada"""
        if page_name in self.pages:
            # Chama a atualização ANTES de exibir se for a página de histórico
            if page_name == "sales_history":
                self.pages["sales_history"].refresh_if_needed()

            self.content_area.setCurrentWidget(self.pages[page_name])

            if page_name == "dashboard":
                self.pages["dashboard"].update_dashboard_data(self.current_cash_session)

            # Atualiza botão ativo na sidebar
            page_map = {
                "dashboard": "dashboard",
                "sales": "sales",
                "sales_history": "sales_history",
                "credit": "credit",
                "products": "products",
                "customers": "customers",
                "stock": "stock",
                "reports": "reports",
                "cash": "cash",
                "settings": "settings"
            }

            if page_name in page_map:
                button_key = page_map[page_name]
                if button_key in self.sidebar.menu_buttons:
                    self.sidebar.set_active_button(self.sidebar.menu_buttons[button_key])
    
    def setup_status_bar(self):
        """Configura a barra de status"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Informações do usuário
        user_info = f"👤 {self.current_user['username']} ({self.current_user['role'].title()})"
        status_bar.addPermanentWidget(QLabel(user_info))
        
        # Status do caixa
        self.cash_status_label = QLabel()
        status_bar.addPermanentWidget(self.cash_status_label)
        
        self.update_status_bar()
    
    def update_status_bar(self):
        """Atualiza informações da barra de status"""
        tm = ThemeManager()
        if self.current_cash_session:
            cash_text = f"💰 Caixa: ABERTO (ID: {self.current_cash_session['id']})"
            self.cash_status_label.setStyleSheet(f"""
                background-color: {tm.get_color('SUCCESS')};
                color: {tm.get_color('WHITE')};
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
            """)
        else:
            cash_text = "💰 Caixa: FECHADO"
            self.cash_status_label.setStyleSheet(f"""
                background-color: {tm.get_color('ERROR')};
                color: {tm.get_color('WHITE')};
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
            """)
        
        self.cash_status_label.setText(cash_text)
    
    def check_cash_session(self):
        """Verifica sessão de caixa atual"""
        self.current_cash_session = db.get_current_cash_session()
        self.update_status_bar()
        if "dashboard" in self.pages:
            self.pages["dashboard"].update_dashboard_data(self.current_cash_session)
    
    def update_data(self):
        """Atualiza dados do dashboard"""
        if "dashboard" in self.pages:
            self.pages["dashboard"].update_dashboard_data(self.current_cash_session)

    def check_date_and_refresh(self):
        """Verifica se o dia mudou e atualiza o dashboard se necessário."""
        today = datetime.now().date()
        if today != self.last_dashboard_date:
            logging.info(f"Novo dia detectado ({today}). Atualizando o dashboard.")
            self.last_dashboard_date = today
            # Chama a atualização da página do dashboard
            self.change_page("dashboard")
    
    def apply_theme(self):
        """Aplica o tema atual"""
        self.theme_manager.apply_theme(QApplication.instance(), self.theme_manager.current_theme)

    def toggle_theme(self):
        """Alterna entre os temas claro e escuro"""
        new_theme = "dark" if self.theme_manager.current_theme == "light" else "light"
        self.theme_manager.apply_theme(QApplication.instance(), new_theme)
        
        # Atualiza componentes que precisam de atualização manual (ex: gráficos)
        if "dashboard" in self.pages:
            self.pages["dashboard"].update_dashboard_data(self.current_cash_session)
        
        self.update_status_bar()
        logging.info(f"Tema alterado para: {new_theme}")
    
    def logout(self):
        """Realiza logout"""
        self.logout_requested.emit()

    def closeEvent(self, event):
        """Garante que os handlers de hardware sejam parados corretamente ao fechar."""
        logging.info("Fechando a janela principal. Parando handlers.")
        self.scale_handler.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)

    @pyqtSlot(str, str)
    def display_notification(self, title, message):
        """Exibe uma caixa de diálogo de notificação estilizada."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        
        # HTML para formatar o texto com quebra de linha
        formatted_message = message.replace('\n', '<br>')
        msg_box.setText(f"<p style='font-size: 16px; color: #333;'>{formatted_message}</p>")
        
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        tm = ThemeManager()
        # Estilo customizado para um visual mais agradável
        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {tm.get_color('WHITE')};
                border: 1px solid {tm.get_color('GRAY_LIGHT')};
                border-radius: 15px;
                padding: 20px;
            }}
            QMessageBox QLabel {{
                color: {tm.get_color('DARK')};
            }}
            QMessageBox QPushButton {{
                background-color: {tm.get_color('PRIMARY')};
                color: {tm.get_color('WHITE')};
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                font-weight: bold;
                min-width: 90px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {tm.get_color('PRIMARY_DARK')};
            }}
        """)
        
        # Traz a janela principal para frente antes de mostrar o diálogo
        self.raise_()
        self.activateWindow()
        msg_box.exec()
