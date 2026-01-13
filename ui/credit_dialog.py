from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton, QListWidget, QDateEdit, QPlainTextEdit, QCalendarWidget, QListWidgetItem
from PyQt6.QtCore import QDate, Qt
from database import search_customers, add_customer, get_customer_balance
from ui.theme import ModernTheme

class CreditDialog(QDialog):
    def __init__(self, total_amount, user_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Venda a Crédito (Fiado)")
        self.setMinimumSize(500, 600)

        self.total_amount = total_amount
        self.user_id = user_id
        self.selected_customer = None
        self.credit_data = None

        self.setup_ui()
        self.apply_styles()
        self.on_customer_search_changed("") # Load initial customers

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Customer Search
        customer_search_layout = QHBoxLayout()
        self.customer_search_input = QLineEdit(placeholderText="Buscar cliente por nome ou CPF")
        self.customer_search_input.textChanged.connect(self.on_customer_search_changed)
        self.add_customer_button = QPushButton("Novo Cliente")
        self.add_customer_button.clicked.connect(self.add_new_customer)
        customer_search_layout.addWidget(self.customer_search_input)
        customer_search_layout.addWidget(self.add_customer_button)
        main_layout.addLayout(customer_search_layout)

        self.customer_list_widget = QListWidget()
        self.customer_list_widget.itemClicked.connect(self.on_customer_selected)
        main_layout.addWidget(self.customer_list_widget)

        # Selected Customer Display
        self.selected_customer_label = QLabel("Cliente Selecionado: Nenhum")
        self.selected_customer_label.setObjectName("selectedCustomerLabel")
        main_layout.addWidget(self.selected_customer_label)

        # Credit Details
        main_layout.addWidget(QLabel(f"Valor da Venda: R$ {self.total_amount:.2f}"))
        
        main_layout.addWidget(QLabel("Observações (opcional):"))
        self.observations_input = QPlainTextEdit()
        self.observations_input.setPlaceholderText("Adicione observações sobre a venda a crédito...")
        self.observations_input.setMaximumHeight(80)
        main_layout.addWidget(self.observations_input)

        main_layout.addWidget(QLabel("Data de Vencimento:"))
        self.due_date_input = QDateEdit(QDate.currentDate())
        self.due_date_input.setCalendarPopup(True)
        self.due_date_input.setMinimumDate(QDate.currentDate()) # Cannot set due date in the past
        main_layout.addWidget(self.due_date_input)

        # Action Buttons
        button_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Confirmar Venda Fiado")
        self.confirm_button.clicked.connect(self.on_confirm)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.confirm_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

    def apply_styles(self):
        self.setStyleSheet(ModernTheme.get_payment_dialog_stylesheet())
        self.customer_search_input.setObjectName("modern_input")
        self.add_customer_button.setObjectName("modern_button_secondary")
        self.confirm_button.setObjectName("modern_button_primary")
        self.cancel_button.setObjectName("modern_button_outline")
        self.observations_input.setObjectName("modern_text_edit")
        self.due_date_input.setObjectName("modern_date_edit")

    def on_customer_search_changed(self, text):
        self.customer_list_widget.clear()
        customers = search_customers(text)
        for customer in customers:
            item = QListWidgetItem(f"{customer['name']} (CPF: {customer['cpf'] or 'N/A'})")
            item.setData(Qt.ItemDataRole.UserRole, customer) # Store full customer object
            self.customer_list_widget.addItem(item)

    def on_customer_selected(self, item):
        self.selected_customer = item.data(Qt.ItemDataRole.UserRole)
        self.selected_customer_label.setText(f"Cliente Selecionado: {self.selected_customer['name']}")

    def add_new_customer(self):
        name, ok = self.getText(self, "Novo Cliente", "Nome do Cliente:")
        if not ok or not name: return

        cpf, ok = self.getText(self, "Novo Cliente", "CPF (opcional):")
        if not ok: return

        phone, ok = self.getText(self, "Novo Cliente", "Telefone (opcional):")
        if not ok: return

        address, ok = self.getText(self, "Novo Cliente", "Endereço (opcional):")
        if not ok: return

        # Converter strings vazias para None para evitar violação de constraint UNIQUE
        cpf = cpf.strip() if cpf and cpf.strip() else None
        phone = phone.strip() if phone and phone.strip() else None
        address = address.strip() if address and address.strip() else None

        success, result = add_customer(name, cpf, phone, address)
        if success:
            QMessageBox.information(self, "Sucesso", f"Cliente '{name}' adicionado com sucesso!")
            self.on_customer_search_changed(name) # Refresh list and pre-select new customer
        else:
            QMessageBox.critical(self, "Erro", result)

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

        self.credit_data = {
            'customer_id': customer_id,
            'observations': self.observations_input.toPlainText(),
            'due_date': self.due_date_input.date().toString("yyyy-MM-dd")
        }
        
        self.accept()

    def get_credit_data(self):
        return self.credit_data

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
