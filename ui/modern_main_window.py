from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QStackedWidget, QGraphicsDropShadowEffect,
    QStatusBar, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea
)
from PyQt6.QtGui import QFont, QColor, QBrush, QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect
from datetime import datetime, timedelta
import pyqtgraph as pg
from decimal import Decimal

from ui.theme import ModernTheme, IconTheme
from ui.product_management_window import ProductManagementWindow
from ui.sales_page import SalesPage
from ui.settings_page import SettingsPage
from ui.cash_page import CashPage
from ui.reports_page import ReportsPage
from ui.user_management_page import UserManagementPage
from ui.sales_history_page import SalesHistoryPage
from ui.audit_log_dialog import AuditLogDialog
from ui.backup_dialog import BackupDialog
from hardware.scale_handler import ScaleHandler
from hardware.printer_handler import PrinterHandler
import database as db

class ModernSidebar(QFrame):
    """Sidebar moderna retrátil"""
    
    page_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.expanded = True
        self.setObjectName("sidebar")
        self.setFixedWidth(250)
        
        self.setup_ui()
        self.apply_theme()
        
    def setup_ui(self):
        """Configura a interface da sidebar"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header da sidebar
        header = QFrame()
        header.setFixedHeight(80)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 20)
        
        # Logo e título
        self.logo_label = QLabel("🍇")
        self.logo_label.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(self.logo_label)
        
        self.title_label = QLabel("PDV Açaí")
        self.title_label.setStyleSheet(f"""
            color: {ModernTheme.WHITE};
            font-size: 18px;
            font-weight: 700;
            margin-left: 10px;
        """)
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Botão toggle
        self.toggle_button = QPushButton("☰")
        self.toggle_button.setObjectName("sidebar_button")
        self.toggle_button.setFixedSize(40, 40)
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        header_layout.addWidget(self.toggle_button)
        
        layout.addWidget(header)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: rgba(255, 255, 255, 0.2); height: 1px;")
        layout.addWidget(separator)
        
        # Menu items
        self.menu_container = QFrame()
        menu_layout = QVBoxLayout(self.menu_container)
        menu_layout.setContentsMargins(0, 20, 0, 20)
        menu_layout.setSpacing(5)
        
        # Botões do menu
        self.menu_buttons = {}
        menu_items = [
            ("dashboard", f"{IconTheme.DASHBOARD} Dashboard", "dashboard"),
            ("sales", f"{IconTheme.SALES} Vendas", "sales"),
            ("sales_history", f"{IconTheme.HISTORY} Histórico", "sales_history"),
            ("products", f"{IconTheme.PRODUCTS} Produtos", "products"),
            ("reports", f"{IconTheme.REPORTS} Relatórios", "reports"),
            ("cash", f"{IconTheme.CASH} Caixa", "cash"),
            ("settings", f"{IconTheme.SETTINGS} Configurações", "settings"),
            ("users", f"{IconTheme.USERS} Usuários", "users"),
        ]
        
        for key, text, page in menu_items:
            button = QPushButton(text)
            button.setObjectName("sidebar_button")
            button.clicked.connect(lambda checked, p=page: self.page_changed.emit(p))
            self.menu_buttons[key] = button
            menu_layout.addWidget(button)
        
        menu_layout.addStretch()
        
        # Botão logout
        self.logout_button = QPushButton(f"{IconTheme.LOGOUT} Sair")
        self.logout_button.setObjectName("sidebar_button")
        menu_layout.addWidget(self.logout_button)
        
        layout.addWidget(self.menu_container)
        
        # Define dashboard como ativo por padrão
        self.set_active_button("dashboard")
    
    def apply_theme(self):
        """Aplica o tema da sidebar"""
        self.setStyleSheet(f"""
            QFrame#sidebar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {ModernTheme.PRIMARY},
                    stop:1 {ModernTheme.PRIMARY_DARK});
                border: none;
            }}
            
            QPushButton#sidebar_button {{
                background-color: transparent;
                color: {ModernTheme.WHITE};
                border: none;
                padding: 15px 20px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
                border-radius: 8px;
                margin: 2px 8px;
            }}
            
            QPushButton#sidebar_button:hover {{
                background-color: rgba(255, 255, 255, 0.15);
            }}
            
            QPushButton#sidebar_button:pressed {{
                background-color: rgba(255, 255, 255, 0.25);
            }}
        """)
    
    def set_active_button(self, key):
        """Define o botão ativo"""
        for btn_key, button in self.menu_buttons.items():
            if btn_key == key:
                button.setStyleSheet(f"""
                    QPushButton#sidebar_button {{
                        background-color: {ModernTheme.WHITE};
                        color: {ModernTheme.PRIMARY};
                        border: none;
                        padding: 15px 20px;
                        text-align: left;
                        font-size: 14px;
                        font-weight: 600;
                        border-radius: 8px;
                        margin: 2px 8px;
                    }}
                """)
            else:
                button.setStyleSheet("""
                    QPushButton#sidebar_button {
                        background-color: transparent;
                        color: white;
                    }
                    QPushButton#sidebar_button:hover {
                        background-color: rgba(255, 255, 255, 0.15);
                    }
                    QPushButton#sidebar_button:pressed {
                        background-color: rgba(255, 255, 255, 0.25);
                    }
                """)
    
    def toggle_sidebar(self):
        """Alterna entre expandido e retraído"""
        if self.expanded:
            self.collapse()
        else:
            self.expand()
    
    def collapse(self):
        """Recolhe a sidebar"""
        self.expanded = False
        self.setFixedWidth(70)
        
        # Esconde textos
        self.title_label.hide()
        for button in self.menu_buttons.values():
            # Mantém apenas o ícone
            text = button.text()
            icon = text.split()[0] if text else ""
            button.setText(icon)
        
        logout_text = self.logout_button.text()
        logout_icon = logout_text.split()[0] if logout_text else ""
        self.logout_button.setText(logout_icon)
    
    def expand(self):
        """Expande a sidebar"""
        self.expanded = True
        self.setFixedWidth(250)
        
        # Mostra textos
        self.title_label.show()
        
        # Restaura textos dos botões
        menu_items = [
            ("dashboard", f"{IconTheme.DASHBOARD} Dashboard"),
            ("sales", f"{IconTheme.SALES} Vendas"),
            ("sales_history", f"{IconTheme.HISTORY} Histórico"),
            ("products", f"{IconTheme.PRODUCTS} Produtos"),
            ("reports", f"{IconTheme.REPORTS} Relatórios"),
            ("cash", f"{IconTheme.CASH} Caixa"),
            ("settings", f"{IconTheme.SETTINGS} Configurações"),
            ("users", f"{IconTheme.USERS} Usuários"),
        ]
        
        for key, text in menu_items:
            if key in self.menu_buttons:
                self.menu_buttons[key].setText(text)
        
        self.logout_button.setText(f"{IconTheme.LOGOUT} Sair")


class ModernCard(QFrame):
    """Card moderno com sombra"""
    
    def __init__(self, title="", content_widget=None):
        super().__init__()
        self.setObjectName("card")
        
        # Adiciona sombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(ModernTheme.GRAY))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("card_title")
            layout.addWidget(title_label)
        
        if content_widget:
            layout.addWidget(content_widget)
        
        self.apply_theme()
    
    def apply_theme(self):
        """Aplica tema do card"""
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {ModernTheme.WHITE};
                border: none;
                border-radius: 12px;
            }}
            
            QLabel#card_title {{
                color: {ModernTheme.DARK};
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 10px;
            }}
        """)


class ModernDashboard(QWidget):
    """Dashboard aprimorado com KPIs, gráficos e informações em tempo real."""
    
    def __init__(self, scale_handler, printer_handler):
        super().__init__()
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler

        self.kpi_labels = {}
        self.setup_ui()
        self.update_dashboard_data() # Carga inicial

        # Conexões assíncronas para o status da balança
        self.scale_handler.weight_updated.connect(self.on_scale_ok)
        self.scale_handler.error_occurred.connect(self.on_scale_error)
        # Define um status inicial
        self.scale_status_label.setText("⚖️ Verificando balança...")
        self.scale_status_label.setStyleSheet(f"color: {ModernTheme.GRAY}; font-weight: 500;")

    def on_scale_ok(self, weight):
        # Apenas atualiza o status na primeira leitura ou se o estado era de erro
        if "Conectada" not in self.scale_status_label.text():
            self.scale_status_label.setText("⚖️ Balança Conectada")
            self.scale_status_label.setStyleSheet(f"color: {ModernTheme.SUCCESS}; font-weight: 500;")

    def on_scale_error(self, error_message):
        self.scale_status_label.setText(f"⚖️ Balança Desconectada")
        self.scale_status_label.setStyleSheet(f"color: {ModernTheme.ERROR}; font-weight: 500;")
        print(f"Dashboard: Erro recebido do ScaleHandler: {error_message}")

    def setup_ui(self):
        """Configura a UI do dashboard com uma área de rolagem."""
        # O layout principal do dashboard agora contém apenas a área de rolagem
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)  # Permite que o conteúdo se expanda
        scroll_area.setFrameShape(QFrame.Shape.NoFrame) # Remove a borda
        main_layout.addWidget(scroll_area)

        # Container para todo o conteúdo que ficará dentro da área de rolagem
        content_container = QWidget()
        content_container.setObjectName("dashboard_content_container")
        scroll_area.setWidget(content_container)

        # Layout do conteúdo (vertical)
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(30)

        # Header
        header_layout = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("title")
        subtitle = QLabel("Visão geral do seu negócio em tempo real")
        subtitle.setObjectName("subtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        content_layout.addLayout(header_layout)

        # Layout de Grid para os cards
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        content_layout.addLayout(grid_layout)

        # --- Linha 0: KPIs ---
        kpis_layout = QHBoxLayout()
        kpis_layout.setSpacing(20)
        self.create_kpi_card("revenue", "💰", "Faturamento Hoje", "R$ 0,00", ModernTheme.PRIMARY, kpis_layout)
        self.create_kpi_card("sales_count", "🛒", "Vendas Hoje", "0", ModernTheme.SECONDARY, kpis_layout)
        self.create_kpi_card("avg_ticket", "📊", "Ticket Médio", "R$ 0,00", ModernTheme.SUCCESS, kpis_layout)
        grid_layout.addLayout(kpis_layout, 0, 0, 1, 2)

        # --- Linha 1: Gráficos ---
        self.sales_by_hour_chart = self.create_sales_by_hour_chart()
        grid_layout.addWidget(ModernCard("Vendas por Hora (Hoje)", self.sales_by_hour_chart), 1, 0)

        self.sales_by_category_chart = self.create_sales_by_category_chart()
        grid_layout.addWidget(ModernCard("Vendas por Categoria (Últimos 7 dias)", self.sales_by_category_chart), 1, 1)

        # --- Linha 2: Informações Adicionais ---
        self.latest_sales_table = self.create_latest_sales_table()
        grid_layout.addWidget(ModernCard("Últimas 5 Vendas", self.latest_sales_table), 2, 0)

        self.peripherals_status_widget = self.create_peripherals_status_widget()
        grid_layout.addWidget(ModernCard("Status dos Periféricos", self.peripherals_status_widget), 2, 1)

        # Define como as linhas e colunas do grid devem se expandir
        grid_layout.setRowStretch(1, 1)
        grid_layout.setRowStretch(2, 1)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

        content_layout.addStretch() # Adiciona um espaçador no final do conteúdo rolável
        self.apply_styles()

    def create_kpi_card(self, key, icon, label, value, color, layout):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(120)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(color))
        shadow.setOffset(0, 3)
        card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(card)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 700;")
        self.kpi_labels[key] = value_label
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {ModernTheme.GRAY}; font-size: 12px; font-weight: 500;")

        card_layout.addWidget(icon_label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(label_widget)
        card.setStyleSheet(f"""QFrame#card {{ background-color: {ModernTheme.WHITE}; border: none; border-radius: 12px; border-left: 4px solid {color}; padding: 15px; }} """)
        layout.addWidget(card)

    def create_sales_by_hour_chart(self):
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('w')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.getAxis('left').setLabel('Faturamento (R$)')
        plot_widget.getAxis('bottom').setLabel('Hora do Dia')
        self.bar_graph_item = pg.BarGraphItem(x=[], height=[], width=0.6, brush=ModernTheme.PRIMARY)
        plot_widget.addItem(self.bar_graph_item)
        return plot_widget

    def create_sales_by_category_chart(self):
        # Usaremos um QTableWidget para simular um gráfico de pizza/rosca com legendas
        # PyQtGraph não tem um item de pizza nativo fácil de usar.
        chart_widget = QTableWidget()
        chart_widget.setColumnCount(3)
        chart_widget.setHorizontalHeaderLabels(["Cor", "Categoria", "Faturamento (%)"])
        chart_widget.verticalHeader().setVisible(False)
        chart_widget.setShowGrid(False)
        chart_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        chart_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        chart_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        return chart_widget

    def create_latest_sales_table(self):
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Horário", "Usuário", "Valor"])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def create_peripherals_status_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Status da Balança
        self.scale_status_label = QLabel("⚖️ Verificando...")
        self.scale_status_label.setObjectName("status_label")
        layout.addWidget(self.scale_status_label)

        # Status da Impressora
        self.printer_status_label = QLabel("🖨️ Verificando...")
        self.printer_status_label.setObjectName("status_label")
        layout.addWidget(self.printer_status_label)
        
        layout.addStretch()
        return widget

    def update_dashboard_data(self):
        """Busca todos os dados e atualiza os componentes do dashboard."""
        self.update_kpis()
        self.update_sales_by_hour_chart()
        self.update_sales_by_category_chart()
        self.update_latest_sales_table()
        self.update_peripherals_status()

    def update_kpis(self):
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            summary = db.get_daily_summary(today_str)
            self.kpi_labels["revenue"].setText(f"R$ {summary['total_revenue']:.2f}")
            self.kpi_labels["sales_count"].setText(str(summary['total_sales_count']))
            self.kpi_labels["avg_ticket"].setText(f"R$ {summary['average_ticket']:.2f}")
        except Exception as e:
            print(f"Erro ao atualizar KPIs: {e}")

    def update_sales_by_hour_chart(self):
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            sales_data = db.get_sales_by_hour(today_str)
            if not sales_data:
                self.bar_graph_item.setOpts(x=[], height=[])
                return

            hours = [item['hour'] for item in sales_data]
            totals = [float(item['total']) for item in sales_data]
            self.bar_graph_item.setOpts(x=hours, height=totals)
        except Exception as e:
            print(f"Erro ao atualizar gráfico de vendas por hora: {e}")

    def update_sales_by_category_chart(self):
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            sales_data = db.get_sales_by_product_group(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            
            self.sales_by_category_chart.setRowCount(0)
            if not sales_data:
                return

            total_revenue = sum(item['total'] for item in sales_data)
            colors = [ModernTheme.PRIMARY, ModernTheme.SECONDARY, ModernTheme.SUCCESS, ModernTheme.INFO, ModernTheme.WARNING, ModernTheme.ERROR]

            self.sales_by_category_chart.setRowCount(len(sales_data))
            for i, item in enumerate(sales_data):
                percentage = (item['total'] / total_revenue * 100) if total_revenue > 0 else 0
                color = colors[i % len(colors)]

                color_cell = QTableWidgetItem()
                color_cell.setBackground(QColor(color))
                
                name_cell = QTableWidgetItem(item['group_name'])
                value_cell = QTableWidgetItem(f"R$ {item['total']:.2f} ({percentage:.1f}%)")

                self.sales_by_category_chart.setItem(i, 0, color_cell)
                self.sales_by_category_chart.setItem(i, 1, name_cell)
                self.sales_by_category_chart.setItem(i, 2, value_cell)

        except Exception as e:
            print(f"Erro ao atualizar gráfico de vendas por categoria: {e}")

    def update_latest_sales_table(self):
        try:
            latest_sales = db.get_latest_sales(limit=5)
            self.latest_sales_table.setRowCount(0)
            if not latest_sales:
                return

            self.latest_sales_table.setRowCount(len(latest_sales))
            for i, sale in enumerate(latest_sales):
                time_cell = QTableWidgetItem(sale['sale_date'].strftime('%H:%M:%S'))
                user_cell = QTableWidgetItem(sale['username'])
                amount_cell = QTableWidgetItem(f"R$ {sale['total_amount']:.2f}")
                amount_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                self.latest_sales_table.setItem(i, 0, time_cell)
                self.latest_sales_table.setItem(i, 1, user_cell)
                self.latest_sales_table.setItem(i, 2, amount_cell)
        except Exception as e:
            print(f"Erro ao atualizar tabela de últimas vendas: {e}")

    def update_peripherals_status(self):
        # Status da Impressora (a balança é atualizada por sinais)
        status, message = self.printer_handler.check_status()
        if status:
            self.printer_status_label.setText(f"🖨️ {message}")
            self.printer_status_label.setStyleSheet(f"color: {ModernTheme.SUCCESS}; font-weight: 500;")
        else:
            self.printer_status_label.setText(f"🖨️ {message}")
            self.printer_status_label.setStyleSheet(f"color: {ModernTheme.ERROR}; font-weight: 500;")

    def apply_styles(self):
        self.setStyleSheet(f"""
            #dashboard_content_container {{
                background-color: {ModernTheme.GRAY_LIGHTER};
            }}
            ModernDashboard {{
                background-color: transparent; /* Garante que o fundo do widget principal não interfira */
            }}
            QLabel#title {{ color: {ModernTheme.DARK}; font-size: 28px; font-weight: 700; }}
            QLabel#subtitle {{ color: {ModernTheme.GRAY}; font-size: 16px; }}
            QTableWidget {{ border: none; background-color: {ModernTheme.WHITE}; }}
            QHeaderView::section {{ background-color: {ModernTheme.GRAY_LIGHTER}; padding: 4px; border: none; font-weight: bold; }}
            QLabel#status_label {{ font-size: 14px; }}
        """)


import json

class ModernMainWindow(QMainWindow):
    """Janela principal moderna"""
    
    logout_requested = pyqtSignal()
    
    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.current_cash_session = None

        # Carregar configuração
        self.config = self.load_config()
        hardware_mode = self.config.get('hardware_mode', 'test')
        
        self.setWindowTitle(f"PDV Açaí - {current_user['username']}")
        self.setGeometry(100, 100, 1400, 900)

        # Handlers
        self.scale_handler = ScaleHandler(
            mode=hardware_mode,
            **self.config.get('scale', {})
        )
        self.printer_handler = PrinterHandler(
            self.config.get('printer', {})
        )
        
        self.setup_ui()
        self.apply_theme()
        self.check_cash_session()
        
        # Timer para atualizações
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(30000)  # 30 segundos
    
    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Retorna uma config padrão em caso de erro
            return {
                "hardware_mode": "test",
                "scale": {},
                "printer": {}
            }

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
        main_layout.addWidget(self.sidebar)
        
        # Área de conteúdo
        self.content_area = QStackedWidget()
        main_layout.addWidget(self.content_area)
        
        # Páginas
        self.pages = {}
        self.create_pages()
        
        # Define página inicial
        self.change_page("dashboard")

        # Status bar
        self.setup_status_bar()
        

    
    def reload_hardware_handlers(self):
        """Recarrega os handlers de hardware quando o modo de operação muda."""
        print("ModernMainWindow: Recebido sinal para recarregar os handlers de hardware.")
        self.config = self.load_config()
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

        print(f"Handlers de hardware reconfigurados para o modo: {hardware_mode}")

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
            current_user=self.current_user,
            sales_page=self.pages["sales"]  # Injetando a dependência
        )
        self.content_area.addWidget(self.pages["settings"])
        self.pages["settings"].operation_mode_changed.connect(self.reload_hardware_handlers)

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

    def on_products_changed(self):
        """Slot para recarregar dados quando os produtos são alterados."""
        if "sales" in self.pages:
            self.pages["sales"].reload_data()
        # Adicionar aqui outras páginas que dependem dos dados de produtos, como relatórios.
        # if "reports" in self.pages:
        #     self.pages["reports"].reload_data()
    
    def change_page(self, page_name):
        """Muda para a página especificada"""
        if page_name in self.pages:
            self.content_area.setCurrentWidget(self.pages[page_name])
            
            if page_name == "dashboard":
                self.pages["dashboard"].update_dashboard_data()

            # Atualiza botão ativo na sidebar
            page_map = {
                "dashboard": "dashboard",
                "sales": "sales", 
                "sales_history": "sales_history",
                "products": "products",
                "reports": "reports",
                "cash": "cash",
                "settings": "settings",
                "users": "users"
            }
            
            if page_name in page_map:
                self.sidebar.set_active_button(page_map[page_name])
    
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
        if self.current_cash_session:
            cash_text = f"💰 Caixa: ABERTO (ID: {self.current_cash_session['id']})"
            self.cash_status_label.setStyleSheet(f"""
                background-color: {ModernTheme.SUCCESS};
                color: {ModernTheme.WHITE};
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
            """)
        else:
            cash_text = "💰 Caixa: FECHADO"
            self.cash_status_label.setStyleSheet(f"""
                background-color: {ModernTheme.ERROR};
                color: {ModernTheme.WHITE};
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 10px;
            """)
        
        self.cash_status_label.setText(cash_text)
    
    def check_cash_session(self):
        """Verifica sessão de caixa atual"""
        self.current_cash_session = db.get_current_cash_session()
        self.update_status_bar()
    
    def update_data(self):
        """Atualiza dados do dashboard"""
        # self.check_cash_session() # Removido: agora é baseado em evento
        if "dashboard" in self.pages:
            self.pages["dashboard"].update_dashboard_data()
    
    def apply_theme(self):
        """Aplica o tema moderno"""
        self.setStyleSheet(ModernTheme.get_main_stylesheet())
    
    def logout(self):
        """Realiza logout"""
        self.logout_requested.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)
