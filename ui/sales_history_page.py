from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QCalendarWidget, QPushButton, QFrame
)
from PyQt6.QtCore import QDate, Qt, QThreadPool
import database as db
from datetime import datetime, timedelta
from .worker import Worker
import logging

class SalesHistoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool()
        # Estado da paginação
        self.current_page = 0
        self.page_limit = 100
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

        # --- Painel de Totais e Paginação ---
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(summary_frame)
        self.total_sales_label = QLabel("Total de Vendas: R$ 0,00")
        self.num_sales_label = QLabel("Nº de Vendas: 0")

        # Controles de paginação
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("Anterior")
        self.page_label = QLabel("Página 1 de 1")
        self.next_button = QPushButton("Próximo")

        self.prev_button.clicked.connect(self.prev_page)
        self.next_button.clicked.connect(self.next_page)

        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)

        summary_layout.addWidget(self.total_sales_label)
        summary_layout.addWidget(self.num_sales_label)
        summary_layout.addStretch()
        summary_layout.addLayout(pagination_layout)

        # --- Tabela de Vendas e Itens ---
        tables_layout = QHBoxLayout()
        
        self.sales_table = QTableWidget()
        self.sales_table.setColumnCount(6)
        self.sales_table.setHorizontalHeaderLabels(["ID Sessão", "Data", "Cliente", "Total (R$)", "Pagamento", "Operador"])
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
        # Reseta para a primeira página quando aplicar novo filtro
        self.current_page = 0
        start_date = self.start_date_edit.selectedDate().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.selectedDate().toString("yyyy-MM-dd")
        self.load_sales_history(start_date, end_date)

    def load_today_sales(self):
        # Reseta para a primeira página quando carregar dados de hoje
        self.current_page = 0
        today = datetime.now().strftime("%Y-%m-%d")
        self.start_date_edit.setSelectedDate(QDate.currentDate())
        self.end_date_edit.setSelectedDate(QDate.currentDate())
        self.load_sales_history(today, today)

    def refresh_if_needed(self):
        # Verifica se o calendário inicial e final estão com a data de hoje
        is_today_filter = (self.start_date_edit.selectedDate() == QDate.currentDate() and
                           self.end_date_edit.selectedDate() == QDate.currentDate())

        # Se o filtro for 'Hoje', recarrega os dados de hoje.
        # (Se o usuário estiver vendo 'Ontem', não queremos recarregar)
        if is_today_filter:
            self.load_today_sales()

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
        worker = Worker(db.get_sales_with_payment_methods_by_period, start_date, end_date, self.page_limit, self.current_page * self.page_limit)
        worker.signals.finished.connect(self.populate_sales_table)
        worker.signals.error.connect(lambda err: logging.error(f"Erro ao carregar histórico de vendas: {err}"))
        self.threadpool.start(worker)

    def populate_sales_table(self, result):
        self.sales_table.setRowCount(0)

        # Verifica se o resultado é um dicionário (novo formato) ou lista (compatibilidade)
        if isinstance(result, dict):
            sales = result.get('sales', [])
            total_count = result.get('total_count', 0)
        else:
            # Compatibilidade com código antigo
            sales = result
            total_count = len(sales) if sales else 0

        if not sales:
            self.show_message_in_table(self.sales_table, "Nenhuma venda encontrada para o período")
            self.total_sales_label.setText("<b>Total de Vendas:</b> R$ 0.00")
            self.num_sales_label.setText("<b>Nº de Vendas:</b> 0")
            self.update_pagination_controls(0)
            return

        total_value = 0
        for row, sale in enumerate(sales):
            self.sales_table.insertRow(row)

            # Usa o ID da sessão para exibição, mas armazena o ID global para lookups
            display_id = str(sale.get('session_sale_id') if sale.get('session_sale_id') is not None else sale['id'])
            id_item = QTableWidgetItem(display_id)
            id_item.setData(Qt.ItemDataRole.UserRole, sale['id'])

            self.sales_table.setItem(row, 0, id_item)
            self.sales_table.setItem(row, 1, QTableWidgetItem(sale['sale_date']))
            self.sales_table.setItem(row, 2, QTableWidgetItem(sale.get('customer_name') or '--'))
            self.sales_table.setItem(row, 3, QTableWidgetItem(f"{sale['total_amount']:.2f}"))
            payment_text = sale.get('payment_methods_str', 'N/A')
            self.sales_table.setItem(row, 4, QTableWidgetItem(payment_text))
            self.sales_table.setItem(row, 5, QTableWidgetItem(sale['username'] or 'N/A'))
            total_value += sale['total_amount']

        self.total_sales_label.setText(f"<b>Total de Vendas:</b> R$ {total_value:.2f}")
        self.num_sales_label.setText(f"<b>Nº de Vendas:</b> {total_count}")
        self.update_pagination_controls(total_count)

    def display_sale_items(self):
        selected_rows = self.sales_table.selectionModel().selectedRows()
        self.sale_details_table.setRowCount(0)
        if not selected_rows:
            return

        selected_row = selected_rows[0].row()
        item = self.sales_table.item(selected_row, 0)

        # Pega o ID global da venda, que foi armazenado no item da tabela
        sale_id = item.data(Qt.ItemDataRole.UserRole) if item else None

        if not sale_id:
            return

        try:
            self.show_message_in_table(self.sale_details_table, "Carregando itens...")
            worker = Worker(db.get_items_for_sale, sale_id)
            worker.signals.finished.connect(self.populate_items_table)
            worker.signals.error.connect(lambda err: logging.error(f"Erro ao buscar itens da venda: {err}"))
            self.threadpool.start(worker)
        except ValueError:
            return

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

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            start_date = self.start_date_edit.selectedDate().toString("yyyy-MM-dd")
            end_date = self.end_date_edit.selectedDate().toString("yyyy-MM-dd")
            self.load_sales_history(start_date, end_date)

    def next_page(self):
        self.current_page += 1
        start_date = self.start_date_edit.selectedDate().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.selectedDate().toString("yyyy-MM-dd")
        self.load_sales_history(start_date, end_date)

    def update_pagination_controls(self, total_count):
        total_pages = (total_count + self.page_limit - 1) // self.page_limit
        if total_pages == 0:
            total_pages = 1

        self.page_label.setText(f"Página {self.current_page + 1} de {total_pages}")
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < total_pages - 1)
