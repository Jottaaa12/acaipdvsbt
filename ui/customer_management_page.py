from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QLineEdit, QLabel, QFormLayout, QCheckBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from database import get_all_customers, add_customer, update_customer, delete_customer, log_audit
from decimal import Decimal

class CustomerManagementPage(QWidget):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        self.user = user
        self.setup_ui()
        self.load_customers()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        toolbar_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Recarregar (F5)")
        self.refresh_button.clicked.connect(self.load_customers)
        self.refresh_button.setShortcut("F5")

        self.add_customer_button = QPushButton("Adicionar Cliente")
        self.add_customer_button.clicked.connect(self.on_add_customer)

        self.edit_customer_button = QPushButton("Editar Cliente")
        self.edit_customer_button.clicked.connect(self.on_edit_customer)

        self.delete_customer_button = QPushButton("Excluir Cliente")
        self.delete_customer_button.clicked.connect(self.on_delete_customer)

        if self.user['role'] != 'gerente':
            self.delete_customer_button.setEnabled(False)

        toolbar_layout.addWidget(self.refresh_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.add_customer_button)
        toolbar_layout.addWidget(self.edit_customer_button)
        toolbar_layout.addWidget(self.delete_customer_button)
        layout.addLayout(toolbar_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Nome", "CPF", "Telefone", "Limite de Crédito", "Bloqueado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def load_customers(self):
        customers = get_all_customers()
        self.table.setRowCount(len(customers))

        for row, customer in enumerate(customers):
            self.table.setItem(row, 0, QTableWidgetItem(str(customer['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(customer['name']))
            self.table.setItem(row, 2, QTableWidgetItem(customer.get('cpf', 'N/A')))
            self.table.setItem(row, 3, QTableWidgetItem(customer.get('phone', 'N/A')))
            self.table.setItem(row, 4, QTableWidgetItem(f"R$ {customer['credit_limit']:.2f}"))
            blocked_item = QTableWidgetItem("Sim" if customer['is_blocked'] else "Não")
            self.table.setItem(row, 5, blocked_item)

    def on_add_customer(self):
        dialog = CustomerEditDialog(self.user, parent=self)
        if dialog.exec():
            self.load_customers()

    def on_edit_customer(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione um cliente para editar.")
            return

        row = selected_items[0].row()
        customer_id = int(self.table.item(row, 0).text())
        
        dialog = CustomerEditDialog(self.user, customer_id=customer_id, parent=self)
        if dialog.exec():
            self.load_customers()

    def on_delete_customer(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Atenção", "Selecione um cliente para excluir.")
            return

        row = selected_items[0].row()
        customer_id = int(self.table.item(row, 0).text())
        customer_name = self.table.item(row, 1).text()

        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                     f"Tem certeza que deseja excluir o cliente '{customer_name}'?\nO cliente será removido da visualização, mas seus dados serão mantidos para referência futura.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            success, message = delete_customer(customer_id)
            if success:
                log_audit(self.user['id'], 'DELETE_CUSTOMER', 'customers', customer_id, old_values=f'name: {customer_name}')
                QMessageBox.information(self, "Sucesso", "Cliente excluído com sucesso.")
                self.load_customers()
            else:
                QMessageBox.critical(self, "Erro", f"Não foi possível excluir o cliente: {message}")

class CustomerEditDialog(QDialog):
    def __init__(self, user, customer_id=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.customer_id = customer_id
        self.is_edit = customer_id is not None

        self.setWindowTitle("Editar Cliente" if self.is_edit else "Adicionar Cliente")
        self.setup_ui()

        if self.is_edit:
            self.load_customer_data()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.cpf_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.credit_limit_input = QDoubleSpinBox()
        self.credit_limit_input.setRange(0, 99999.99)
        self.credit_limit_input.setDecimals(2)
        self.credit_limit_input.setPrefix("R$ ")
        self.is_blocked_check = QCheckBox("Cliente Bloqueado")

        # Permissões
        if self.user['role'] != 'gerente':
            self.credit_limit_input.setEnabled(False)
            self.is_blocked_check.setEnabled(False)

        layout.addRow("Nome:", self.name_input)
        layout.addRow("CPF:", self.cpf_input)
        layout.addRow("Telefone:", self.phone_input)
        layout.addRow("Endereço:", self.address_input)
        layout.addRow("Limite de Crédito:", self.credit_limit_input)
        layout.addRow(self.is_blocked_check)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.save_button.clicked.connect(self.on_save)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addRow(buttons)

    def load_customer_data(self):
        # This is not efficient, but for simplicity we get all customers.
        # A get_customer_by_id function would be better.
        customers = get_all_customers()
        customer = next((c for c in customers if c['id'] == self.customer_id), None)
        if customer:
            self.name_input.setText(customer['name'])
            self.cpf_input.setText(customer.get('cpf', ''))
            self.phone_input.setText(customer.get('phone', ''))
            self.address_input.setText(customer.get('address', ''))
            self.credit_limit_input.setValue(float(customer['credit_limit']))
            self.is_blocked_check.setChecked(customer['is_blocked'])

    def on_save(self):
        name = self.name_input.text()
        if not name:
            QMessageBox.warning(self, "Campo Obrigatório", "O nome do cliente é obrigatório.")
            return

        cpf = self.cpf_input.text() or None
        phone = self.phone_input.text() or None
        address = self.address_input.text() or None
        credit_limit = self.credit_limit_input.value()
        is_blocked = self.is_blocked_check.isChecked()

        if self.is_edit:
            success, message = update_customer(self.customer_id, name, cpf, phone, address, credit_limit, is_blocked)
            action = 'UPDATE_CUSTOMER'
            record_id = self.customer_id
        else:
            success, message = add_customer(name, cpf, phone, address, credit_limit, is_blocked)
            action = 'CREATE_CUSTOMER'
            record_id = message if success else None

        if success:
            log_audit(self.user['id'], action, 'customers', record_id, new_values=f'name: {name}')
            QMessageBox.information(self, "Sucesso", "Cliente salvo com sucesso.")
            self.accept()
        else:
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar o cliente: {message}")
