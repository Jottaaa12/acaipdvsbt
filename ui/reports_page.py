
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout, QDateEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
import database as db
from datetime import datetime, timedelta

class ReportsPage(QWidget):
    """Página para visualização de relatórios."""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title_label = QLabel("Central de Relatórios")
        title_label.setObjectName("title")
        main_layout.addWidget(title_label)

        # Abas para cada tipo de relatório
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Cria as abas
        sales_tab = self.create_sales_report_tab()
        stock_tab = self.create_stock_report_tab()
        cash_history_tab = self.create_cash_history_tab()

        tab_widget.addTab(sales_tab, "Vendas")
        tab_widget.addTab(stock_tab, "Estoque")
        tab_widget.addTab(cash_history_tab, "Histórico de Caixa")

        # Conecta o sinal de mudança de aba
        tab_widget.currentChanged.connect(self.on_tab_changed)

        # Gera o relatório de vendas inicial
        self.generate_sales_report()

    def on_tab_changed(self, index):
        """Chamado quando o usuário muda de aba."""
        # 0: Vendas, 1: Estoque, 2: Histórico de Caixa
        if index == 2: # Aba de Histórico de Caixa
            self.generate_cash_history_report()

    def create_sales_report_tab(self):
        """Cria a aba de relatório de vendas."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Filtros
        filter_group = QGroupBox("Filtrar Período")
        filter_layout = QHBoxLayout(filter_group)

        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setDate(QDate.currentDate())
        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.setDate(QDate.currentDate())

        today_button = QPushButton("Hoje")
        week_button = QPushButton("Esta Semana")
        month_button = QPushButton("Este Mês")
        generate_button = QPushButton("Gerar Relatório")
        generate_button.setObjectName("modern_button_primary")

        filter_layout.addWidget(QLabel("De:"))
        filter_layout.addWidget(self.start_date_edit)
        filter_layout.addWidget(QLabel("Até:"))
        filter_layout.addWidget(self.end_date_edit)
        filter_layout.addStretch()
        filter_layout.addWidget(today_button)
        filter_layout.addWidget(week_button)
        filter_layout.addWidget(month_button)
        filter_layout.addWidget(generate_button)
        layout.addWidget(filter_group)

        # Conexões dos botões de filtro
        today_button.clicked.connect(self.set_date_today)
        week_button.clicked.connect(self.set_date_this_week)
        month_button.clicked.connect(self.set_date_this_month)
        generate_button.clicked.connect(self.generate_sales_report)

        # Área de Resumo
        summary_group = QGroupBox("Resumo do Período")
        summary_layout = QGridLayout(summary_group)
        self.total_revenue_label = QLabel("R$ 0,00")
        self.total_sales_label = QLabel("0")
        self.avg_ticket_label = QLabel("R$ 0,00")
        summary_layout.addWidget(QLabel("Faturamento Total:"), 0, 0)
        summary_layout.addWidget(self.total_revenue_label, 0, 1)
        summary_layout.addWidget(QLabel("Total de Vendas:"), 1, 0)
        summary_layout.addWidget(self.total_sales_label, 1, 1)
        summary_layout.addWidget(QLabel("Ticket Médio:"), 2, 0)
        summary_layout.addWidget(self.avg_ticket_label, 2, 1)
        layout.addWidget(summary_group)

        # Tabelas de detalhes
        details_layout = QHBoxLayout()
        
        # Tabela de formas de pagamento
        payment_group = QGroupBox("Vendas por Forma de Pagamento")
        payment_layout = QVBoxLayout(payment_group)
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(3)
        self.payment_table.setHorizontalHeaderLabels(["Forma de Pagamento", "Nº de Vendas", "Valor Total"])
        self.payment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        payment_layout.addWidget(self.payment_table)
        details_layout.addWidget(payment_group)

        # Tabela de produtos mais vendidos
        products_group = QGroupBox("Produtos Mais Vendidos")
        products_layout = QVBoxLayout(products_group)
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(3)
        self.products_table.setHorizontalHeaderLabels(["Produto", "Quantidade Vendida", "Faturamento"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        products_layout.addWidget(self.products_table)
        details_layout.addWidget(products_group)

        layout.addLayout(details_layout)

        return widget

    def create_stock_report_tab(self):
        """Cria a aba de relatório de estoque."""
        widget = QWidget()
        # Placeholder - a ser implementado
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Relatório de Estoque - Em breve"))
        return widget

    def create_cash_history_tab(self):
        """Cria a aba de histórico de caixa."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Ações
        actions_layout = QHBoxLayout()
        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.generate_cash_history_report)
        actions_layout.addWidget(refresh_button)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # Tabela de histórico
        self.cash_history_table = QTableWidget()
        self.cash_history_table.setColumnCount(8)
        self.cash_history_table.setHorizontalHeaderLabels([
            "ID", "Abertura", "Fechamento", "Valor Inicial", 
            "Valor Esperado", "Valor Contado", "Diferença", "Usuário"
        ])
        self.cash_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cash_history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.cash_history_table)

        return widget

    # --- Funções de Lógica para Relatório de Vendas ---

    def generate_cash_history_report(self):
        """Gera e exibe o relatório de histórico de caixa."""
        history_data = db.get_cash_session_history()

        self.cash_history_table.setRowCount(0)
        for row, item in enumerate(history_data):
            self.cash_history_table.insertRow(row)

            # Formata a diferença com cor
            difference = item['difference']
            diff_item = QTableWidgetItem(f"R$ {difference:.2f}")
            if difference > 0:
                diff_item.setForeground(Qt.GlobalColor.darkGreen)
            elif difference < 0:
                diff_item.setForeground(Qt.GlobalColor.red)

            self.cash_history_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            self.cash_history_table.setItem(row, 1, QTableWidgetItem(item['open_time']))
            self.cash_history_table.setItem(row, 2, QTableWidgetItem(item['close_time']))
            self.cash_history_table.setItem(row, 3, QTableWidgetItem(f"R$ {item['initial_amount']:.2f}"))
            self.cash_history_table.setItem(row, 4, QTableWidgetItem(f"R$ {item['expected_amount']:.2f}"))
            self.cash_history_table.setItem(row, 5, QTableWidgetItem(f"R$ {item['final_amount']:.2f}"))
            self.cash_history_table.setItem(row, 6, diff_item)
            self.cash_history_table.setItem(row, 7, QTableWidgetItem(item['user_opened']))

    def set_date_today(self):
        today = QDate.currentDate()
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)

    def set_date_this_week(self):
        today = QDate.currentDate()
        start_of_week = today.addDays(-today.dayOfWeek() + 1)
        self.start_date_edit.setDate(start_of_week)
        self.end_date_edit.setDate(today)

    def set_date_this_month(self):
        today = QDate.currentDate()
        start_of_month = QDate(today.year(), today.month(), 1)
        self.start_date_edit.setDate(start_of_month)
        self.end_date_edit.setDate(today)

    def generate_sales_report(self):
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        report_data = db.get_sales_report(start_date, end_date)

        # Atualiza resumo
        self.total_revenue_label.setText(f"R$ {report_data['total_revenue']:.2f}")
        self.total_sales_label.setText(str(report_data['total_sales_count']))
        self.avg_ticket_label.setText(f"R$ {report_data['average_ticket']:.2f}")

        # Atualiza tabela de formas de pagamento
        self.payment_table.setRowCount(0)
        for row, item in enumerate(report_data['payment_methods']):
            self.payment_table.insertRow(row)
            self.payment_table.setItem(row, 0, QTableWidgetItem(item['payment_method']))
            self.payment_table.setItem(row, 1, QTableWidgetItem(str(item['count'])))
            self.payment_table.setItem(row, 2, QTableWidgetItem(f"R$ {item['total']:.2f}"))

        # Atualiza tabela de produtos
        self.products_table.setRowCount(0)
        for row, item in enumerate(report_data['top_products']):
            self.products_table.insertRow(row)
            self.products_table.setItem(row, 0, QTableWidgetItem(item['description']))
            self.products_table.setItem(row, 1, QTableWidgetItem(str(item['quantity_sold'])))
            self.products_table.setItem(row, 2, QTableWidgetItem(f"R$ {item['revenue']:.2f}"))
