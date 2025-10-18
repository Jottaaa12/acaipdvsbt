from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QMessageBox, QDialog, QLineEdit, QLabel, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from datetime import datetime, date
from database import get_credit_sales, add_credit_payment, get_all_payment_methods, get_credit_sale_details, get_monthly_credit_summary, get_overdue_evolution
from decimal import Decimal
from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
import logging
import pyqtgraph as pg

class CreditManagementPage(QWidget):
    def __init__(self, user, cash_session, parent=None):
        super().__init__(parent)
        self.user = user
        self.cash_session = cash_session
        self.setup_ui()
        self.load_credit_sales()
        self.update_dashboard()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Dashboard
        dashboard_group = QGroupBox("Dashboard de Crédito")
        dashboard_layout = QHBoxLayout(dashboard_group)
        self.monthly_summary_chart = pg.PlotWidget()
        self.overdue_evolution_chart = pg.PlotWidget()
        dashboard_layout.addWidget(self.monthly_summary_chart)
        dashboard_layout.addWidget(self.overdue_evolution_chart)
        layout.addWidget(dashboard_group)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Recarregar (F5)")
        self.refresh_button.clicked.connect(self.load_credit_sales)
        self.refresh_button.setShortcut("F5")

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Todos", "Pendentes", "Parcialmente Pagos", "Pagos", "Cancelados"])
        self.status_filter.currentIndexChanged.connect(self.load_credit_sales)

        self.register_payment_button = QPushButton("Registrar Pagamento")
        self.register_payment_button.clicked.connect(self.on_register_payment)

        toolbar_layout.addWidget(self.refresh_button)
        toolbar_layout.addWidget(QLabel("Filtrar por status:"))
        toolbar_layout.addWidget(self.status_filter)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.register_payment_button)
        layout.addLayout(toolbar_layout)

        # Credit Sales Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Cliente", "Valor Total", "Valor Pago", "Saldo Devedor", "Data", "Vencimento", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def update_dashboard(self):
        self.update_monthly_summary_chart()
        self.update_overdue_evolution_chart()

    def update_monthly_summary_chart(self):
        summary = get_monthly_credit_summary()
        total_due = float(summary['total_due'])
        total_paid = float(summary['total_paid_month'])

        self.monthly_summary_chart.clear()
        bg = pg.BarGraphItem(x=[1, 2], height=[total_due, total_paid], width=0.6, brushes=['r', 'g'])
        self.monthly_summary_chart.addItem(bg)
        self.monthly_summary_chart.setTitle("Resumo do Mês")
        ax = self.monthly_summary_chart.getAxis('bottom')
        ax.setTicks([[(1, 'A Receber'), (2, 'Recebido')]])

    def update_overdue_evolution_chart(self):
        evolution = get_overdue_evolution()
        self.overdue_evolution_chart.clear()
        if evolution:
            dates = [datetime.strptime(item['date'], '%Y-%m-%d').timestamp() for item in evolution]
            amounts = [float(item['amount']) for item in evolution]
            self.overdue_evolution_chart.plot(dates, amounts, pen='r', symbol='o')
        self.overdue_evolution_chart.setTitle("Evolução de Vencidos")
        try:
            axis = self.overdue_evolution_chart.getAxis('bottom')
            tick_values_list = axis.tickValues(10, 10)
            
            # tickValues can return a list of lists (major/minor). We'll use the first list.
            if tick_values_list and isinstance(tick_values_list[0], list):
                tick_values = tick_values_list[0]
            else:
                tick_values = tick_values_list

            if tick_values:
                datetime_objects = [datetime.fromtimestamp(t) for t in tick_values]
                ticks = [[(d.timestamp(), d.strftime('%d/%m')) for d in datetime_objects]]
                axis.setTicks(ticks)
        except Exception as e:
            logging.warning(f"Could not set date ticks for chart: {e}")

    def load_credit_sales(self):
        self.update_dashboard() # Atualiza o dashboard sempre que a tabela é carregada
        status_map = {
            "Todos": "all",
            "Pendentes": "pending",
            "Parcialmente Pagos": "partially_paid",
            "Pagos": "paid",
            "Cancelados": "cancelled"
        }
        status = status_map.get(self.status_filter.currentText())

        sales = get_credit_sales(status_filter=status)
        self.table.setRowCount(len(sales))

        today = date.today()
        overdue_color = QColor("#d9534f") # Reddish color

        for row, sale in enumerate(sales):
            # Create items
            item_customer = QTableWidgetItem(sale['customer_name'])
            item_amount = QTableWidgetItem(f"R$ {sale['amount']:.2f}")
            item_paid = QTableWidgetItem(f"R$ {sale['total_paid']:.2f}")
            item_balance = QTableWidgetItem(f"R$ {sale['balance_due']:.2f}")
            item_created = QTableWidgetItem(sale['created_date'])
            item_due = QTableWidgetItem(sale.get('due_date', 'N/A'))
            item_status = QTableWidgetItem(sale['status'])

            # Store the sale ID in the first item of the row
            item_customer.setData(Qt.ItemDataRole.UserRole, sale['id'])

            # Check for overdue
            is_overdue = False
            if sale.get('due_date') and sale['status'] not in ['paid', 'cancelled']:
                try:
                    due_date = datetime.strptime(sale['due_date'], '%Y-%m-%d').date()
                    if due_date < today:
                        is_overdue = True
                except (ValueError, TypeError):
                    pass # Ignore if date is invalid

            # Apply highlighting
            if is_overdue:
                for col in range(self.table.columnCount()):
                    # Must create a new item for each cell to set its background
                    if col == 0: item_customer.setBackground(overdue_color)
                    elif col == 1: item_amount.setBackground(overdue_color)
                    elif col == 2: item_paid.setBackground(overdue_color)
                    elif col == 3: item_balance.setBackground(overdue_color)
                    elif col == 4: item_created.setBackground(overdue_color)
                    elif col == 5: item_due.setBackground(overdue_color)
                    elif col == 6: item_status.setBackground(overdue_color)
            
            # Set items in table
            self.table.setItem(row, 0, item_customer)
            self.table.setItem(row, 1, item_amount)
            self.table.setItem(row, 2, item_paid)
            self.table.setItem(row, 3, item_balance)
            self.table.setItem(row, 4, item_created)
            self.table.setItem(row, 5, item_due)
            self.table.setItem(row, 6, item_status)

    def on_register_payment(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione um fiado para registrar o pagamento.")
            return

        row = selected_items[0].row()
        credit_sale_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        balance_due_str = self.table.item(row, 3).text().replace("R$ ", "")
        balance_due = Decimal(balance_due_str)

        dialog = RegisterPaymentDialog(balance_due, self.user['id'], self)
        if dialog.exec():
            amount, payment_method = dialog.get_payment_data()
            if amount > 0:
                cash_session_id = self.cash_session['id'] if self.cash_session else None
                success, result = add_credit_payment(credit_sale_id, amount, self.user['id'], payment_method, cash_session_id)
                if success:
                    QMessageBox.information(self, "Sucesso", "Pagamento registrado com sucesso!")
                    self.load_credit_sales()

                    # Checar se o fiado foi quitado para enviar notificação
                    try:
                        details = get_credit_sale_details(credit_sale_id)
                        if details and details['status'] == 'paid':
                            notifier = get_whatsapp_sales_notifier()
                            notifier.notify_credit_paid(credit_sale_id)
                    except Exception as e:
                        logging.error(f"Falha ao enviar notificação de quitação de fiado: {e}")
                else:
                    QMessageBox.critical(self, "Erro", f"Falha ao registrar pagamento: {result}")

class RegisterPaymentDialog(QDialog):
    def __init__(self, balance_due, user_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar Pagamento")
        self.balance_due = balance_due
        self.user_id = user_id

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Saldo Devedor: R$ {self.balance_due:.2f}"))

        layout.addWidget(QLabel("Valor Pago:"))
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText(str(self.balance_due))
        layout.addWidget(self.amount_input)

        layout.addWidget(QLabel("Forma de Pagamento:"))
        self.payment_method_combo = QComboBox()
        self.load_payment_methods()
        layout.addWidget(self.payment_method_combo)

        buttons = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        layout.addLayout(buttons)

    def load_payment_methods(self):
        methods = get_all_payment_methods()
        for method in methods:
            self.payment_method_combo.addItem(method['name'])

    def get_payment_data(self):
        amount_str = self.amount_input.text() or self.amount_input.placeholderText()
        try:
            amount = Decimal(amount_str.replace(",", "."))
            if amount <= 0 or amount > self.balance_due:
                raise ValueError
        except:
            QMessageBox.warning(self, "Valor Inválido", f"Por favor, insira um valor válido entre R$ 0,01 e R$ {self.balance_due:.2f}")
            return Decimal("0"), None
        
        payment_method = self.payment_method_combo.currentText()
        return amount, payment_method
