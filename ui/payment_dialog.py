from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout, 
    QWidget, QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence, QDoubleValidator
from PyQt6.QtCore import Qt, pyqtSignal
from decimal import Decimal, InvalidOperation
from .theme import ModernTheme
import database as db
import logging

class PaymentDialog(QDialog):
    credit_sale_requested = pyqtSignal()

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
        
        # Carregar métodos de pagamento do banco de dados
        self.db_payment_methods = db.get_all_payment_methods()

        # --- UI Initialization ---
        self.setup_ui()
        self.setStyleSheet(ModernTheme.get_payment_dialog_stylesheet())
        self.setup_shortcuts()
        self.update_display()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- Display Total ---
        self.total_label = QLabel(f"Total a Pagar: R$ {self.total_amount:.2f}")
        self.total_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
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

        # --- Payment Method Selection (Dynamic) ---
        payment_methods_frame = QFrame()
        payment_grid = QGridLayout(payment_methods_frame)
        payment_grid.setSpacing(15)

        # Hardcoded buttons for layout purposes
        self.cash_button = QPushButton("💵 F1 - Dinheiro")
        self.credit_button = QPushButton("💳 F2 - Crédito")
        self.debit_button = QPushButton("💳 F3 - Débito")
        self.pix_button = QPushButton("⚡ F4 - PIX")
        self.credit_sale_button = QPushButton("👤 F5 - Fiado")

        # Map from hardcoded button object to its name for dynamic assignment
        button_name_map = {
            self.cash_button: "Dinheiro",
            self.credit_button: "Crédito",
            self.debit_button: "Débito",
            self.pix_button: "PIX"
        }

        self.payment_buttons_map = {}
        # Dynamically associate buttons with DB methods
        for btn, name in button_name_map.items():
            for db_method in self.db_payment_methods:
                if db_method['name'].upper() == name.upper():
                    self.payment_buttons_map[btn] = db_method
                    break

        # Setup button properties and connect signals
        for btn in button_name_map.keys():
            btn.setObjectName("paymentMethodButton")
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.clicked.connect(self.on_payment_method_selected)

        self.credit_sale_button.setObjectName("creditSaleButton")

        payment_grid.addWidget(self.cash_button, 0, 0)
        payment_grid.addWidget(self.credit_button, 0, 1)
        payment_grid.addWidget(self.debit_button, 1, 0)
        payment_grid.addWidget(self.pix_button, 1, 1)
        
        main_layout.addWidget(payment_methods_frame)
        main_layout.addWidget(self.credit_sale_button)

        # --- Amount Input ---
        self.amount_paid_input = QLineEdit(placeholderText="Valor a adicionar")
        self.amount_paid_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.amount_paid_input.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        validator = QDoubleValidator(0.00, 99999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.amount_paid_input.setValidator(validator)
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


    def setup_shortcuts(self):
        QShortcut(QKeySequence("F1"), self).activated.connect(lambda: self.cash_button.click())
        QShortcut(QKeySequence("D"), self).activated.connect(lambda: self.cash_button.click())
        
        QShortcut(QKeySequence("F2"), self).activated.connect(lambda: self.credit_button.click())
        QShortcut(QKeySequence("C"), self).activated.connect(lambda: self.credit_button.click())

        QShortcut(QKeySequence("F3"), self).activated.connect(lambda: self.debit_button.click())
        QShortcut(QKeySequence("B"), self).activated.connect(lambda: self.debit_button.click())

        QShortcut(QKeySequence("F4"), self).activated.connect(lambda: self.pix_button.click())
        QShortcut(QKeySequence("P"), self).activated.connect(lambda: self.pix_button.click())

        QShortcut(QKeySequence("F5"), self).activated.connect(self.credit_sale_button.click)

        self.credit_sale_button.clicked.connect(self.on_credit_sale_clicked)

        # Shortcut for deleting a payment
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.on_remove_payment_clicked)

    def on_credit_sale_clicked(self):
        self.credit_sale_requested.emit()
        self.accept() # Close the payment dialog

    def get_selected_payment_method(self):
        for btn, method_obj in self.payment_buttons_map.items():
            if btn.isChecked():
                return method_obj
        return None

    def on_payment_method_selected(self):
        method = self.get_selected_payment_method()
        if not method:
            return

        if method['name'] == "Dinheiro":
            self.amount_paid_input.setFocus()
            self.amount_paid_input.selectAll()
        else:
            # For other methods, assume full remaining amount
            self.amount_paid_input.setText(str(self.remaining_amount).replace('.', ','))
            self.amount_paid_input.setFocus()
            self.amount_paid_input.selectAll()

    def on_add_payment_clicked(self):
        method_obj = self.get_selected_payment_method()
        if not method_obj:
            self.remaining_label.setText("Selecione um método!")
            return

        amount_str = self.amount_paid_input.text().strip().replace(',', '.')
        
        if not amount_str:
            amount = self.remaining_amount
        else:
            try:
                amount = Decimal(amount_str).quantize(Decimal('0.01'))
                if amount <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.remaining_label.setText("Valor inválido!")
                return

        self.payments.append({'method_id': method_obj['id'], 'method_name': method_obj['name'], 'amount': amount})
        self.amount_paid_input.clear()

        for btn in self.payment_buttons_map:
            if btn.isChecked():
                btn.setAutoExclusive(False)
                btn.setChecked(False)
                btn.setAutoExclusive(True)
                break
        
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
        
        self.payments_list.clear()
        for p in self.payments:
            item = QListWidgetItem(f"{p['method_name']}: R$ {p['amount']:.2f}")
            self.payments_list.addItem(item)

        if self.remaining_amount > 0:
            self.remaining_label.setText(f"Restante: R$ {self.remaining_amount:.2f}")
            self.remaining_label.setProperty("status", "warning")
            self.change_label.setText("")
            self.change_label.setProperty("status", "")
            self.finalize_button.setEnabled(False)
            self.add_payment_button.setText("Adicionar Pagamento")
            self.add_payment_button.setEnabled(True)
        else:
            change = -self.remaining_amount
            self.remaining_label.setText("Pago!")
            self.remaining_label.setProperty("status", "success")
            self.change_label.setText(f"Troco: R$ {change:.2f}")
            self.change_label.setProperty("status", "success")
            self.finalize_button.setEnabled(True)
            self.add_payment_button.setText("Venda Paga")
            self.add_payment_button.setEnabled(False)
            self.finalize_button.setFocus()

        self.remaining_label.style().unpolish(self.remaining_label)
        self.remaining_label.style().polish(self.remaining_label)
        self.change_label.style().unpolish(self.change_label)
        self.change_label.style().polish(self.change_label)

    def on_finalize_clicked(self):
        if self.remaining_amount > 0:
            return

        self.finalize_button.setEnabled(False)
        self.finalize_button.setText("Processando...")

        total_paid = sum(p['amount'] for p in self.payments)
        change = total_paid - self.total_amount

        final_payments = []
        for p in self.payments:
            final_payments.append({'method': p['method_id'], 'amount': p['amount']})

        logging.debug(f"Finalizing payment with data: {final_payments}")

        self.result_data = {
            'payments': final_payments,
            'total_paid': total_paid,
            'change': change
        }
        self.accept()

    def keyPressEvent(self, event):
        # Override default Enter behavior to avoid closing the dialog unexpectedly
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if self.amount_paid_input.hasFocus():
                self.on_add_payment_clicked()
            elif self.finalize_button.hasFocus() and self.finalize_button.isEnabled():
                self.on_finalize_clicked()
            return
        super().keyPressEvent(event)
