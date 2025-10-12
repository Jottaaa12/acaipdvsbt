from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, 
    QListWidgetItem, QMessageBox, QDateEdit, QTextEdit, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QDate
from database import search_customers, add_customer, create_credit_sale, get_customer_balance
from decimal import Decimal
from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
import logging

class CreditDialog(QDialog):
    def __init__(self, total_amount, user_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Venda a Crédito (Fiado)")
        self.setMinimumSize(500, 600)

        self.total_amount = total_amount
        self.user_id = user_id
        self.selected_customer = None

        self.setup_ui()
        self.apply_styles()
        self.on_customer_search_changed("") # Load initial customers

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Total Amount Display
        total_label = QLabel(f"Valor Total: R$ {self.total_amount:.2f}")
        total_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(total_label)

        # --- Customer Selection Area ---
        customer_group = QFrame()
        customer_group.setObjectName("customerGroup")
        customer_layout = QVBoxLayout(customer_group)
        
        # Search Input
        search_layout = QHBoxLayout()
        self.customer_search_input = QLineEdit(placeholderText="Buscar cliente por nome, CPF ou telefone...")
        self.customer_search_input.textChanged.connect(self.on_customer_search_changed)
        search_layout.addWidget(self.customer_search_input)

        self.new_customer_button = QPushButton("Novo Cliente")
        self.new_customer_button.clicked.connect(self.on_new_customer)
        search_layout.addWidget(self.new_customer_button)
        customer_layout.addLayout(search_layout)

        # Customer List
        self.customer_list_widget = QListWidget()
        self.customer_list_widget.itemSelectionChanged.connect(self.on_customer_selection_changed)
        customer_layout.addWidget(self.customer_list_widget)
        main_layout.addWidget(customer_group)

        # Selected Customer Info
        self.selected_customer_label = QLabel("Nenhum cliente selecionado")
        self.selected_customer_label.setObjectName("selectedCustomerLabel")
        self.selected_customer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.selected_customer_label)

        # Due Date
        main_layout.addWidget(QLabel("Data de Vencimento:"))
        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setDate(QDate.currentDate().addDays(30))
        self.due_date_input.setDisplayFormat("dd/MM/yyyy")
        main_layout.addWidget(self.due_date_input)

        # Observations
        main_layout.addWidget(QLabel("Observações:"))
        self.observations_input = QTextEdit()
        main_layout.addWidget(self.observations_input)

        # Action Buttons
        action_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Confirmar Fiado")
        self.confirm_button.setObjectName("confirmButton")
        self.confirm_button.clicked.connect(self.on_confirm)
        self.confirm_button.setEnabled(False)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)

        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.confirm_button)
        main_layout.addLayout(action_layout)

    def apply_styles(self):
        self.setStyleSheet('''
            QDialog {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QLabel { font-size: 14px; }
            QFrame#customerGroup { 
                border: 1px solid #4a627a; 
                border-radius: 5px; 
                padding: 5px;
            }
            QLineEdit, QTextEdit, QDateEdit, QListWidget {
                background-color: #34495e;
                border: 1px solid #4a627a;
                border-radius: 5px;
                padding: 8px;
                color: #ecf0f1;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected {
                background-color: #16a085;
                color: white;
            }
            QPushButton {
                background-color: #34495e;
                color: #ecf0f1;
                border: 2px solid #4a627a;
                padding: 10px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4a627a; }
            QPushButton#confirmButton { background-color: #27ae60; border: none; }
            QPushButton#confirmButton:hover { background-color: #2ecc71; }
            QPushButton#confirmButton:disabled { background-color: #7f8c8d; }
            QLabel#selectedCustomerLabel {
                font-weight: bold;
                color: #ecf0f1;
                padding: 8px;
                background-color: #34495e;
                border-radius: 4px;
                min-height: 30px;
            }
        ''')

    def on_customer_search_changed(self, text):
        self.customer_list_widget.clear()
        customers = search_customers(text)
        for customer in customers:
            item_text = f"{customer['name']} (CPF: {customer.get('cpf', 'N/A')})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, customer) # Attach customer data to the item
            self.customer_list_widget.addItem(item)

    def on_customer_selection_changed(self):
        selected_items = self.customer_list_widget.selectedItems()
        if not selected_items:
            self.selected_customer = None
            self.confirm_button.setEnabled(False)
            self.selected_customer_label.setText("Nenhum cliente selecionado")
            return

        self.selected_customer = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        if self.selected_customer:
            try:
                balance = get_customer_balance(self.selected_customer['id'])
                balance_str = f"{balance:.2f}".replace('.', ',')
                label_text = f"<b>Cliente:</b> {self.selected_customer['name']}<br><b>Saldo Devedor:</b> R$ {balance_str}"
                self.selected_customer_label.setText(label_text)
            except Exception:
                self.selected_customer_label.setText(f"<b>Cliente:</b> {self.selected_customer['name']}")
            
            self.confirm_button.setEnabled(True)
        else:
            self.selected_customer = None
            self.confirm_button.setEnabled(False)
            self.selected_customer_label.setText("Erro ao selecionar cliente")

    def on_new_customer(self):
        name, ok = self.getText(self, 'Novo Cliente', 'Nome do Cliente:')
        if ok and name:
            phone, ok = self.getText(self, 'Novo Cliente', 'Telefone:')
            if ok:
                success, result = add_customer(name=name, phone=phone)
                if success:
                    QMessageBox.information(self, "Sucesso", "Cliente cadastrado com sucesso!")
                    self.customer_search_input.setText(name)
                    self.on_customer_search_changed(name)
                else:
                    QMessageBox.warning(self, "Erro", f"Não foi possível cadastrar o cliente: {result}")

    def on_confirm(self):
        if not self.selected_customer:
            QMessageBox.warning(self, "Atenção", "Selecione um cliente da lista antes de confirmar.")
            return

        customer_id = self.selected_customer['id']
        
        if self.selected_customer.get('is_blocked', False):
            QMessageBox.critical(self, "Cliente Bloqueado", 
                                 f"O cliente {self.selected_customer['name']} está bloqueado e não pode fazer novas compras a prazo.")
            return

        credit_limit = self.selected_customer.get('credit_limit', 0)
        if credit_limit > 0:
            current_balance = get_customer_balance(customer_id)
            new_total_due = self.total_amount + current_balance
            if new_total_due > credit_limit:
                QMessageBox.critical(self, "Limite de Crédito Excedido",
                                     f"Esta venda ultrapassará o limite de crédito do cliente.\n\n"
                                     f"Limite: R$ {credit_limit:.2f}\n"
                                     f"Saldo Atual: R$ {current_balance:.2f}\n"
                                     f"Novo Saldo: R$ {new_total_due:.2f}")
                return

        due_date = self.due_date_input.date().toString("yyyy-MM-dd")
        observations = self.observations_input.toPlainText()

        success, result = create_credit_sale(
            customer_id=customer_id,
            amount=self.total_amount,
            user_id=self.user_id,
            observations=observations,
            due_date=due_date
        )

        if success:
            self.credit_sale_id = result
            try:
                notifier = get_whatsapp_sales_notifier()
                notifier.notify_credit_created(self.credit_sale_id)
            except Exception as e:
                logging.error(f"Falha ao enviar notificação de criação de fiado: {e}")

            QMessageBox.information(self, "Sucesso", "Venda a crédito registrada com sucesso!")
            self.accept()
        else:
            QMessageBox.critical(self, "Erro", f"Falha ao registrar a venda a crédito: {result}")

    def get_selected_customer(self):
        '''Returns the dictionary of the selected customer.'''
        return self.selected_customer

    def getText(self, parent, title, label):
        '''Helper for simple input dialogs.'''
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(label))
        input_field = QLineEdit(dialog)
        layout.addWidget(input_field)
        buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        buttons.addWidget(ok_button)
        layout.addLayout(buttons)
        
        if dialog.exec():
            return input_field.text(), True
        return "", False