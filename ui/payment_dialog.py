from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout, 
    QWidget, QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QDoubleValidator
from PyQt6.QtCore import Qt, pyqtSignal
from decimal import Decimal, InvalidOperation

class PaymentDialog(QDialog):
    """
    A dialog for handling sale payments, including multiple payment methods,
    discounts, and surcharges.
    """
    def __init__(self, total_amount, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Finalizar Venda")
        self.setMinimumSize(550, 650)

        # --- Data Properties ---
        self.total_amount = Decimal(str(total_amount)).quantize(Decimal('0.01'))
        self.remaining_amount = self.total_amount
        self.payments = []
        self.result_data = None

        # --- UI Initialization ---
        self.setup_ui()
        self.apply_styles()
        self.setup_shortcuts()
        self.update_display()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Display Total ---
        self.total_label = QLabel(f"Total a Pagar: R$ {self.total_amount:.2f}")
        self.total_label.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setObjectName("totalLabel")
        main_layout.addWidget(self.total_label)

        # --- Display Remaining and Change ---
        info_layout = QHBoxLayout()
        self.remaining_label = QLabel()
        self.remaining_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.remaining_label.setObjectName("remainingLabel")
        
        self.change_label = QLabel()
        self.change_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.change_label.setObjectName("changeLabel")

        info_layout.addWidget(self.remaining_label, alignment=Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(info_layout)

        # --- Payments List ---
        main_layout.addWidget(QLabel("Pagamentos Adicionados:"))
        self.payments_list = QListWidget()
        self.payments_list.setAlternatingRowColors(True)
        main_layout.addWidget(self.payments_list)

        # --- Remove Payment Button ---
        self.remove_payment_button = QPushButton("Remover Pagamento Selecionado")
        self.remove_payment_button.setObjectName("removePaymentButton")
        self.remove_payment_button.setEnabled(False)
        self.remove_payment_button.clicked.connect(self.on_remove_payment_clicked)
        main_layout.addWidget(self.remove_payment_button)
        self.payments_list.itemSelectionChanged.connect(self.update_remove_button_state)


        # --- Payment Method Selection ---
        payment_grid = QGridLayout()
        self.cash_button = QPushButton("F1 - Dinheiro")
        self.credit_button = QPushButton("F2 - Crédito")
        self.debit_button = QPushButton("F3 - Débito")
        self.pix_button = QPushButton("F4 - PIX")
        
        self.payment_buttons = {
            "Dinheiro": self.cash_button, "Crédito": self.credit_button,
            "Débito": self.debit_button, "PIX": self.pix_button
        }
        for btn in self.payment_buttons.values():
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(self.on_payment_method_selected)

        payment_grid.addWidget(self.cash_button, 0, 0)
        payment_grid.addWidget(self.credit_button, 0, 1)
        payment_grid.addWidget(self.debit_button, 1, 0)
        payment_grid.addWidget(self.pix_button, 1, 1)
        main_layout.addLayout(payment_grid)

        # --- Amount Input ---
        self.amount_paid_input = QLineEdit(placeholderText="Valor a adicionar")
        self.amount_paid_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.amount_paid_input.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        # Validator for currency input (e.g., 123.45 or 123,45)
        validator = QDoubleValidator(0.00, 99999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.amount_paid_input.setValidator(validator)
        self.amount_paid_input.returnPressed.connect(self.on_add_payment_clicked)
        main_layout.addWidget(self.amount_paid_input)

        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        self.add_payment_button = QPushButton("Adicionar Pagamento")
        self.add_payment_button.setObjectName("addPaymentButton")
        self.add_payment_button.clicked.connect(self.on_add_payment_clicked)
        
        self.finalize_button = QPushButton("Finalizar Venda")
        self.finalize_button.setObjectName("finalizeButton")
        self.finalize_button.setEnabled(False)
        self.finalize_button.clicked.connect(self.on_finalize_clicked)

        action_layout.addWidget(self.add_payment_button)
        action_layout.addWidget(self.finalize_button)
        main_layout.addLayout(action_layout)

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QLabel {
                font-size: 14px;
                color: #bdc3c7;
            }
            QLabel#totalLabel {
                color: #ecf0f1;
                padding-bottom: 10px;
            }
            QLabel#remainingLabel, QLabel#changeLabel {
                padding: 5px;
                border-radius: 5px;
            }
            QLineEdit {
                background-color: #34495e;
                border: 1px solid #4a627a;
                border-radius: 5px;
                padding: 12px;
                font-size: 18px;
                color: #ecf0f1;
            }
            QListWidget {
                background-color: #34495e;
                border: 1px solid #4a627a;
                border-radius: 5px;
                font-size: 16px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:alternate {
                background-color: #3a5064;
            }
            QPushButton {
                background-color: #34495e;
                color: #ecf0f1;
                border: 2px solid #4a627a;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a627a;
            }
            QPushButton:checked {
                background-color: #16a085;
                border-color: #1abc9c;
            }
            QPushButton#addPaymentButton {
                background-color: #2980b9;
                border: none;
            }
            QPushButton#addPaymentButton:hover {
                background-color: #3498db;
            }
            QPushButton#finalizeButton {
                background-color: #27ae60;
                border: none;
            }
            QPushButton#finalizeButton:hover {
                background-color: #2ecc71;
            }
            QPushButton#removePaymentButton {
                background-color: #c0392b;
                border: none;
            }
            QPushButton#removePaymentButton:hover {
                background-color: #e74c3c;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
                border-color: #95a5a6;
            }
        """)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F1"), self).activated.connect(lambda: self.cash_button.click())
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self.cash_button.click())
        
        QShortcut(QKeySequence("F2"), self).activated.connect(lambda: self.credit_button.click())
        QShortcut(QKeySequence("C"), self).activated.connect(lambda: self.credit_button.click())

        QShortcut(QKeySequence("F3"), self).activated.connect(lambda: self.debit_button.click())
        QShortcut(QKeySequence("B"), self).activated.connect(lambda: self.debit_button.click())

        QShortcut(QKeySequence("F4"), self).activated.connect(lambda: self.pix_button.click())
        QShortcut(QKeySequence("P"), self).activated.connect(lambda: self.pix_button.click())

    def get_selected_payment_method(self):
        for method, btn in self.payment_buttons.items():
            if btn.isChecked():
                return method
        return None

    def on_payment_method_selected(self):
        method = self.get_selected_payment_method()
        if method == "Dinheiro":
            self.amount_paid_input.setFocus()
            self.amount_paid_input.selectAll()
        elif method:
            # For other methods, assume full remaining amount
            self.amount_paid_input.setText(str(self.remaining_amount).replace('.', ','))
            self.amount_paid_input.setFocus()
            self.amount_paid_input.selectAll()
            # Pressing Enter should finalize immediately
            self.amount_paid_input.returnPressed.connect(self.on_add_payment_clicked)

    def on_add_payment_clicked(self):
        method = self.get_selected_payment_method()
        if not method:
            # Simple feedback, could be a QMessageBox
            self.remaining_label.setText("Selecione um método!")
            self.remaining_label.setStyleSheet("background-color: #c0392b;")
            return

        amount_str = self.amount_paid_input.text().strip().replace(',', '.')
        
        # Special case for cash: if input is empty, assume exact remaining amount
        if method == "Dinheiro" and not amount_str:
            amount = self.remaining_amount
        else:
            try:
                amount = Decimal(amount_str).quantize(Decimal('0.01'))
                if amount <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.remaining_label.setText("Valor inválido!")
                self.remaining_label.setStyleSheet("background-color: #c0392b;")
                return

        self.payments.append({'method': method, 'amount': amount})
        self.amount_paid_input.clear()
        self.update_display()

    def update_remove_button_state(self):
        self.remove_payment_button.setEnabled(len(self.payments_list.selectedItems()) > 0)

    def on_remove_payment_clicked(self):
        selected_items = self.payments_list.selectedItems()
        if not selected_items:
            return

        selected_row = self.payments_list.currentRow()
        
        if 0 <= selected_row < len(self.payments):
            del self.payments[selected_row]
        
        self.update_display()


    def update_display(self):
        total_paid = sum(p['amount'] for p in self.payments)
        self.remaining_amount = self.total_amount - total_paid
        
        # Update payments list
        self.payments_list.clear()
        for p in self.payments:
            item = QListWidgetItem(f"{p['method']}: R$ {p['amount']:.2f}")
            self.payments_list.addItem(item)

        # Update labels
        if self.remaining_amount > 0:
            self.remaining_label.setText(f"Restante: R$ {self.remaining_amount:.2f}")
            self.remaining_label.setStyleSheet("background-color: #e67e22;")
            self.change_label.setText("")
            self.change_label.setStyleSheet("")
            self.finalize_button.setEnabled(False)
            self.add_payment_button.setText("Adicionar Pagamento")
            self.add_payment_button.setEnabled(True)
        else:
            change = -self.remaining_amount
            self.remaining_label.setText("Pago!")
            self.remaining_label.setStyleSheet("background-color: #27ae60;")
            self.change_label.setText(f"Troco: R$ {change:.2f}")
            self.change_label.setStyleSheet("background-color: #2ecc71;")
            self.finalize_button.setEnabled(True)
            self.add_payment_button.setText("Venda Paga")
            self.add_payment_button.setEnabled(False)
            self.finalize_button.setFocus()

    def on_finalize_clicked(self):
        if self.remaining_amount > 0:
            return # Should not happen if button is disabled

        # Prevent multiple clicks
        self.finalize_button.setEnabled(False)
        self.finalize_button.setText("Processando...")

        total_paid = sum(p['amount'] for p in self.payments)
        change = total_paid - self.total_amount

        self.result_data = {
            'payments': self.payments,
            'total_paid': total_paid,
            'change': change
        }
        self.accept()

    def keyPressEvent(self, event):
        # Override default Enter behavior to avoid closing the dialog unexpectedly
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.amount_paid_input.hasFocus():
                self.on_add_payment_clicked()
            elif self.finalize_button.isEnabled():
                self.on_finalize_clicked()
            return
        super().keyPressEvent(event)