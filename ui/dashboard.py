from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QProgressBar,
    QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt
from decimal import Decimal
from datetime import datetime, timedelta
import logging

try:
    import pyqtgraph as pg
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False
    logging.warning("Módulo pyqtgraph não encontrado. Gráficos serão desativados.")


from ui.theme import ThemeManager
from ui.worker import run_in_thread
import database as db

class ModernCard(QFrame):
    """Card moderno com sombra"""
    
    def __init__(self, title="", content_widget=None):
        super().__init__()
        self.setObjectName("card")
        
        # Adiciona sombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(ThemeManager().get_color("GRAY")))
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

class ModernDashboard(QWidget):
    """Dashboard aprimorado com KPIs, gráficos e informações em tempo real."""
    
    def __init__(self, scale_handler, printer_handler):
        super().__init__()
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler

        self.kpi_labels = {}
        self._last_update_time = None  # Debounce para evitar múltiplas atualizações
        self._pending_update = False
        self.setup_ui()
        self.update_dashboard_data() # Carga inicial

        # Conexões assíncronas para o status da balança
        self.scale_handler.weight_updated.connect(self.on_scale_ok)
        self.scale_handler.error_occurred.connect(self.on_scale_error)
        # Define um status inicial
        self.scale_status_label.setText("⚖️ Verificando balança...")
        self.scale_status_label.setStyleSheet(f"color: {ThemeManager().get_color('GRAY')}; font-weight: 500;")

    def on_scale_ok(self, weight):
        # Apenas atualiza o status na primeira leitura ou se o estado era de erro
        if "Conectada" not in self.scale_status_label.text():
            self.scale_status_label.setText("⚖️ Balança Conectada")
            self.scale_status_label.setStyleSheet(f"color: {ThemeManager().get_color('SUCCESS')}; font-weight: 500;")

    def on_scale_error(self, error_message):
        self.scale_status_label.setText(f"⚖️ Balança Desconectada")
        self.scale_status_label.setStyleSheet(f"color: {ThemeManager().get_color('ERROR')}; font-weight: 500;")
        logging.warning(f"Dashboard: Erro recebido do ScaleHandler: {error_message}")

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
        title.setObjectName("dashboardTitle")
        subtitle = QLabel("Visão geral do seu negócio em tempo real")
        subtitle.setObjectName("dashboardSubtitle")
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
        
        tm = ThemeManager()
        self.create_kpi_card("revenue", "💰", "Faturamento na Sessão", "R$ 0,00", tm.get_color("PRIMARY"), kpis_layout)
        self.create_kpi_card("sales_count", "🛒", "Vendas na Sessão", "0", tm.get_color("SECONDARY"), kpis_layout)
        self.create_kpi_card("avg_ticket", "📊", "Ticket Médio da Sessão", "R$ 0,00", tm.get_color("SUCCESS"), kpis_layout)
        grid_layout.addLayout(kpis_layout, 0, 0, 1, 2)

        # --- Linha 1: Gráficos ---
        self.sales_by_hour_chart = self.create_sales_by_hour_chart()
        grid_layout.addWidget(ModernCard("Vendas por Hora (Hoje)", self.sales_by_hour_chart), 1, 0)

        # Container para o gráfico de categorias (agora uma lista visual)
        self.category_list_container = QWidget()
        self.category_list_layout = QVBoxLayout(self.category_list_container)
        self.category_list_layout.setContentsMargins(0, 0, 0, 0)
        self.category_list_layout.setSpacing(10)
        
        grid_layout.addWidget(ModernCard("Vendas por Categoria (Últimos 7 dias)", self.category_list_container), 1, 1)

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
        icon_label.setObjectName("metricIcon")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setStyleSheet(f"color: {color};")
        self.kpi_labels[key] = value_label
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")

        card_layout.addWidget(icon_label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(label_widget)
        card.setObjectName("metricCard")
        card.setStyleSheet(f"border-left: 4px solid {color};")
        layout.addWidget(card)

    def create_sales_by_hour_chart(self):
        tm = ThemeManager()
        
        if not PG_AVAILABLE:
            label = QLabel("Gráfico Indisponível\n(pyqtgraph não instalado)")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(f"color: {tm.get_color('GRAY')}; font-style: italic;")
            # Define um atributo dummy para evitar erro no update
            self.bar_graph_item = None 
            return label

        plot_widget = pg.PlotWidget()
        plot_widget.setBackground(None) # Fundo transparente
        plot_widget.showGrid(x=False, y=True, alpha=0.2) # Grade mais sutil e apenas horizontal
        
        # Estilo dos eixos
        styles = {"color": tm.get_color("GRAY"), "font-size": "12px"}
        plot_widget.getAxis('left').setLabel('Faturamento', **styles)
        plot_widget.getAxis('bottom').setLabel('Hora', **styles)
        
        font = QFont()
        font.setPixelSize(12)
        plot_widget.getAxis('left').setTickFont(font)
        plot_widget.getAxis('bottom').setTickFont(font)
        plot_widget.getAxis('left').setTextPen(tm.get_color("GRAY"))
        plot_widget.getAxis('bottom').setTextPen(tm.get_color("GRAY"))
        
        # Itens do gráfico e Configuração
        self.bar_graph_item = pg.BarGraphItem(x=[], height=[], width=0.6, brush=tm.get_color("PRIMARY"))
        plot_widget.addItem(self.bar_graph_item)
        
        # Define range fixo para X (0h as 23h) e margins automáticas um pouco maiores
        plot_widget.setXRange(-0.5, 23.5, padding=0)
        plot_widget.setMouseEnabled(x=False, y=False) # Desabilita zoom/pan pelo usuário para manter fixo
        plot_widget.getPlotItem().setMenuEnabled(False)
        
        # Ajuste de layout interno para evitar corte de labels
        # Margem esquerda e inferior maiores para caber os labels
        plot_widget.getPlotItem().layout.setContentsMargins(10, 10, 10, 10)

        return plot_widget



    def create_latest_sales_table(self):
        table = QTableWidget()
        table.setObjectName("dashboardTable")
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
        self.scale_status_label.setObjectName("dashboardStatusLabel")
        layout.addWidget(self.scale_status_label)

        # Status da Impressora
        self.printer_status_label = QLabel("🖨️ Verificando...")
        self.printer_status_label.setObjectName("dashboardStatusLabel")
        layout.addWidget(self.printer_status_label)
        
        layout.addStretch()
        return widget

    def update_dashboard_data(self, cash_session=None):
        """Inicia a atualização dos dados em background com debounce de 2s."""
        from ui.worker import thread_manager
        
        # Debounce: evita múltiplas atualizações em menos de 2 segundos
        now = datetime.now()
        if self._last_update_time and (now - self._last_update_time).total_seconds() < 2:
            logging.debug("Dashboard: Atualização ignorada (debounce de 2s)")
            return
        
        self._last_update_time = now
        
        # Função wrapper para ser executada
        def fetch_data():
            return self._fetch_dashboard_data(cash_session)

        # Inicia worker
        op_id = run_in_thread("update_dashboard", fetch_data)
        
        # Recupera o worker para conectar o sinal
        if op_id in thread_manager.active_threads:
            worker = thread_manager.active_threads[op_id]
            worker.signals.finished.connect(self._on_dashboard_data_ready)

    def _fetch_dashboard_data(self, cash_session=None):
        """Busca os dados do banco (Executado em thread separada)."""
        data = {}
        try:
            # 1. KPIs
            if cash_session:
                num_sales, total_revenue = db.get_sales_summary_by_session(cash_session['id'])
                avg_ticket = total_revenue / num_sales if num_sales > 0 else Decimal('0.00')
                data['kpis'] = {
                    'revenue': f"R$ {total_revenue:.2f}",
                    'sales_count': str(num_sales),
                    'avg_ticket': f"R$ {avg_ticket:.2f}"
                }
            else:
                data['kpis'] = {
                    'revenue': "R$ 0.00",
                    'sales_count': "0",
                    'avg_ticket': "R$ 0.00"
                }

            # 2. Sales by Hour
            today_str = datetime.now().strftime('%Y-%m-%d')
            sales_by_hour = db.get_sales_by_hour(today_str)
            data['sales_by_hour'] = sales_by_hour

            # 3. Sales by Category
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            sales_by_category = db.get_sales_by_product_group(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            data['sales_by_category'] = sales_by_category

            # 4. Latest Sales
            latest_sales = db.get_latest_sales(limit=5)
            data['latest_sales'] = latest_sales

            return data

        except Exception as e:
            logging.error(f"Erro ao buscar dados do dashboard: {e}", exc_info=True)
            return None

    def _on_dashboard_data_ready(self, data):
        """Atualiza a UI com os dados recebidos (Executado na Main Thread)."""
        if not data:
            return

        try:
            # 1. KPIs
            kpis = data.get('kpis', {})
            self.kpi_labels["revenue"].setText(kpis.get('revenue', 'R$ 0.00'))
            self.kpi_labels["sales_count"].setText(kpis.get('sales_count', '0'))
            self.kpi_labels["avg_ticket"].setText(kpis.get('avg_ticket', 'R$ 0.00'))

            # 2. Sales by Hour
            sales_data = data.get('sales_by_hour', [])
            if self.bar_graph_item:  # Só atualiza se o gráfico existir
                if sales_data:
                    hours = [item['hour'] for item in sales_data]
                    totals = [float(item['total']) for item in sales_data]
                    self.bar_graph_item.setOpts(x=hours, height=totals)
                else:
                    self.bar_graph_item.setOpts(x=[], height=[])

            # 3. Sales by Category (Lista de Progresso Refatorada)
            sales_cat = data.get('sales_by_category', [])
            tm = ThemeManager()
            
            # Limpa layout existente
            while self.category_list_layout.count():
                child = self.category_list_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            if sales_cat:
                total_revenue = sum(item['total'] for item in sales_cat)
                base_colors = [
                    tm.get_color("PRIMARY"), tm.get_color("SECONDARY"), 
                    tm.get_color("SUCCESS"), tm.get_color("INFO"), 
                    tm.get_color("WARNING"), tm.get_color("ERROR")
                ]
                
                for i, item in enumerate(sales_cat):
                    percentage = (item['total'] / total_revenue * 100) if total_revenue > 0 else 0
                    color = base_colors[i % len(base_colors)]
                    
                    item_widget = QWidget()
                    item_layout = QVBoxLayout(item_widget)
                    item_layout.setContentsMargins(0, 0, 0, 0)
                    item_layout.setSpacing(5)
                    
                    # Cabeçalho (Nome e Valor)
                    header_layout = QHBoxLayout()
                    name_label = QLabel(item['group_name'])
                    name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
                    
                    value_label = QLabel(f"R$ {item['total']:.2f} ({percentage:.1f}%)")
                    value_label.setStyleSheet(f"color: {color}; font-weight: bold;")
                    
                    header_layout.addWidget(name_label)
                    header_layout.addStretch()
                    header_layout.addWidget(value_label)
                    item_layout.addLayout(header_layout)
                    
                    # Barra de Progresso
                    pbar = QProgressBar()
                    pbar.setRange(0, 100)
                    pbar.setValue(int(percentage))
                    pbar.setTextVisible(False)
                    pbar.setFixedHeight(8)
                    pbar.setStyleSheet(f"""
                        QProgressBar {{
                            border: none;
                            background-color: {tm.get_color('GRAY_LIGHTER')};
                            border-radius: 4px;
                        }}
                        QProgressBar::chunk {{
                            background-color: {color};
                            border-radius: 4px;
                        }}
                    """)
                    item_layout.addWidget(pbar)
                    
                    self.category_list_layout.addWidget(item_widget)
                
                self.category_list_layout.addStretch() # Empurra tudo pra cima
            else:
                empty_label = QLabel("Nenhuma venda registrada ainda.")
                empty_label.setStyleSheet(f"color: {tm.get_color('GRAY')}; font-style: italic;")
                empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.category_list_layout.addWidget(empty_label)

            # 4. Latest Sales
            latest = data.get('latest_sales', [])
            self.latest_sales_table.setRowCount(0)
            if latest:
                self.latest_sales_table.setRowCount(len(latest))
                for i, sale in enumerate(latest):
                    time_cell = QTableWidgetItem(sale['sale_date'].strftime('%H:%M:%S'))
                    user_cell = QTableWidgetItem(sale['username'])
                    amount_cell = QTableWidgetItem(f"R$ {sale['total_amount']:.2f}")
                    amount_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    self.latest_sales_table.setItem(i, 0, time_cell)
                    self.latest_sales_table.setItem(i, 1, user_cell)
                    self.latest_sales_table.setItem(i, 2, amount_cell)

            self.update_peripherals_status()

        except Exception as e:
            logging.error(f"Erro ao atualizar UI do dashboard: {e}", exc_info=True)

    def update_peripherals_status(self):
        # Status da Impressora (a balança é atualizada por sinais)
        status, message = self.printer_handler.check_status()
        tm = ThemeManager()
        if status:
            self.printer_status_label.setText(f"🖨️ {message}")
            self.printer_status_label.setStyleSheet(f"color: {tm.get_color('SUCCESS')}; font-weight: 500;")
        else:
            self.printer_status_label.setText(f"🖨️ {message}")
            self.printer_status_label.setStyleSheet(f"color: {tm.get_color('ERROR')}; font-weight: 500;")
