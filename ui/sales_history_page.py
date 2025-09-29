from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QCalendarWidget, QPushButton, QFrame
)
from PyQt6.QtCore import QDate, Qt, QThreadPool
import database as db
from datetime import datetime, timedelta
from .worker import Worker

class SalesHistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool()
        self.setup_ui()
        self.load_today_sales()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Painel de Filtros ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("<b>Filtros:</b>"))
        
        self.start_date_edit = QCalendarWidget()
        self.start_date_edit.setMaximumDate(QDate.currentDate())
        self.start_date_edit.setSelectedDate(QDate.currentDate())
        self.start_date_edit.setGridVisible(True)
        self.start_date_edit.setMaximumHeight(250)
        
        self.end_date_edit = QCalendarWidget()
        self.end_date_edit.setMaximumDate(QDate.currentDate())
        self.end_date_edit.setSelectedDate(QDate.currentDate())
        self.end_date_edit.setGridVisible(True)
        self.end_date_edit.setMaximumHeight(250)

        shortcuts_layout = QVBoxLayout()
        shortcuts_layout.addWidget(QLabel("<b>Atalhos:</b>"))
        today_button = QPushButton("Hoje")
        yesterday_button = QPushButton("Ontem")
        this_month_button = QPushButton("Este Mês")
        
        today_button.clicked.connect(self.load_today_sales)
        yesterday_button.clicked.connect(self.load_yesterday_sales)
        this_month_button.clicked.connect(self.load_this_month_sales)

        shortcuts_layout.addWidget(today_button)
        shortcuts_layout.addWidget(yesterday_button)
        shortcuts_layout.addWidget(this_month_button)
        shortcuts_layout.addStretch()

        filter_button = QPushButton("Filtrar Período")
        filter_button.clicked.connect(self.apply_date_filter)

        filter_layout.addLayout(shortcuts_layout)
        filter_layout.addWidget(QLabel("Data Inicial:"))
        filter_layout.addWidget(self.start_date_edit)
        filter_layout.addWidget(QLabel("Data Final:"))
        filter_layout.addWidget(self.end_date_edit)
        filter_layout.addWidget(filter_button)
        filter_layout.addStretch()

        # --- Painel de Totais ---
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(summary_frame)
        self.total_sales_label = QLabel("Total de Vendas: R$ 0,00")
        self.num_sales_label = QLabel("Nº de Vendas: 0")
        summary_layout.addWidget(self.total_sales_label)
        summary_layout.addWidget(self.num_sales_label)

        # --- Tabela de Vendas e Itens ---
        tables_layout = QHBoxLayout()
        
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(5)
        self.sales_table.setHorizontalHeaderLabels(["ID", "Data", "Total (R$)", "Pagamento", "Operador"])
        self.sales_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sales_table.itemSelectionChanged.connect(self.display_sale_items)
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.sale_details_table = QTableWidget()
        self.sale_details_table.setColumnCount(4)
        self.sale_details_table.setHorizontalHeaderLabels(["Produto", "Qtd/Peso", "Vl. Unit.", "Vl. Total"])
        self.sale_details_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        tables_layout.addWidget(self.sales_table, 3)
        tables_layout.addWidget(self.sale_details_table, 2)
        
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(summary_frame)
        main_layout.addLayout(tables_layout)

    def apply_date_filter(self):
        start_date = self.start_date_edit.selectedDate().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.selectedDate().toString("yyyy-MM-dd")
        self.load_sales_history(start_date, end_date)

    def load_today_sales(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.start_date_edit.setSelectedDate(QDate.currentDate())
        self.end_date_edit.setSelectedDate(QDate.currentDate())
        self.load_sales_history(today, today)

    def load_yesterday_sales(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        qdate_yesterday = QDate.fromString(yesterday, "yyyy-MM-dd")
        self.start_date_edit.setSelectedDate(qdate_yesterday)
        self.end_date_edit.setSelectedDate(qdate_yesterday)
        self.load_sales_history(yesterday, yesterday)
    
    def load_this_month_sales(self):
        today = datetime.now()
        start_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        end_of_month = today.strftime("%Y-%m-%d")
        self.start_date_edit.setSelectedDate(QDate.fromString(start_of_month, "yyyy-MM-dd"))
        self.end_date_edit.setSelectedDate(QDate.fromString(end_of_month, "yyyy-MM-dd"))
        self.load_sales_history(start_of_month, end_of_month)

    def load_sales_history(self, start_date, end_date):
        self.sales_table.setRowCount(0)
        self.sale_details_table.setRowCount(0)
        self.show_message_in_table(self.sales_table, "Carregando histórico...")
        worker = Worker(db.get_sales_with_payment_methods_by_period, start_date, end_date)
        worker.signals.result.connect(self.populate_sales_table)
        worker.signals.error.connect(lambda err: print(f"Erro ao carregar histórico de vendas: {err}"))
        self.threadpool.start(worker)

    def populate_sales_table(self, sales):
        self.sales_table.setRowCount(0)
        if not sales:
            self.show_message_in_table(self.sales_table, "Nenhuma venda encontrada para o período")
            self.total_sales_label.setText("<b>Total de Vendas:</b> R$ 0.00")
            self.num_sales_label.setText("<b>Nº de Vendas:</b> 0")
            return

        total_value = 0
        for row, sale in enumerate(sales):
            self.sales_table.insertRow(row)
            self.sales_table.setItem(row, 0, QTableWidgetItem(str(sale['id'])))
            self.sales_table.setItem(row, 1, QTableWidgetItem(sale['sale_date']))
            self.sales_table.setItem(row, 2, QTableWidgetItem(f"{sale['total_amount']:.2f}"))
            # Usar método de pagamento diretamente da consulta otimizada
            payment_text = sale.get('payment_methods_str', 'N/A')
            self.sales_table.setItem(row, 3, QTableWidgetItem(payment_text))
            self.sales_table.setItem(row, 4, QTableWidgetItem(sale['username'] or 'N/A'))
            total_value += sale['total_amount']
        
        self.total_sales_label.setText(f"<b>Total de Vendas:</b> R$ {total_value:.2f}")
        self.num_sales_label.setText(f"<b>Nº de Vendas:</b> {len(sales)}")

    def display_sale_items(self):
        selected_rows = self.sales_table.selectionModel().selectedRows()
        self.sale_details_table.setRowCount(0)
        if not selected_rows:
            return
            
        selected_row = selected_rows[0].row()
        sale_id = int(self.sales_table.item(selected_row, 0).text())
        
        self.show_message_in_table(self.sale_details_table, "Carregando itens...")
        worker = Worker(db.get_items_for_sale, sale_id)
        worker.signals.result.connect(self.populate_items_table)
        worker.signals.error.connect(lambda err: print(f"Erro ao buscar itens da venda: {err}"))
        self.threadpool.start(worker)

    def populate_items_table(self, items):
        self.sale_details_table.setRowCount(0)
        if not items:
            self.show_message_in_table(self.sale_details_table, "Nenhum item para esta venda")
            return

        for row, item in enumerate(items):
            self.sale_details_table.insertRow(row)
            self.sale_details_table.setItem(row, 0, QTableWidgetItem(item['description']))
            
            qty_str = f"{item['quantity']:.3f}" if item['sale_type'] == 'weight' else str(int(item['quantity']))
            self.sale_details_table.setItem(row, 1, QTableWidgetItem(qty_str))
            
            self.sale_details_table.setItem(row, 2, QTableWidgetItem(f"R$ {item['unit_price']:.2f}"))
            self.sale_details_table.setItem(row, 3, QTableWidgetItem(f"R$ {item['total_price']:.2f}"))

    def show_message_in_table(self, table, message):
        table.setRowCount(1)
        item = QTableWidgetItem(message)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(0, 0, item)
        table.setSpan(0, 0, 1, table.columnCount())
