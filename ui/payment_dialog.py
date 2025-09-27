from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGridLayout, QWidget
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from decimal import Decimal, InvalidOperation

class PaymentDialog(QDialog):
    def __init__(self, total_amount, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Finalizar Venda")
        # Garante que total_amount seja um Decimal
        self.total_amount = Decimal(str(total_amount)).quantize(Decimal('0.01'))
        self.payment_method = None

        self.setStyleSheet("""
            QDialog { background-color: #2E2E2E; color: #F0F0F0; }
            QLabel { font-size: 16px; }
            QLineEdit { background-color: #3C3C3C; border: 1px solid #555; border-radius: 5px; padding: 8px; font-size: 18px; }
            QPushButton {
                background-color: #555;
                color: white; border: 2px solid #666;
                padding: 15px; border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:checked { background-color: #5C8A74; border-color: #AEE8C0; }
            QPushButton#confirm_button { background-color: #4A7A64; border: none; }
            QPushButton#confirm_button:hover { background-color: #6BAA8D; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)

        # Total a Pagar
        total_label = QLabel(f"Total a Pagar: R$ {self.total_amount:.2f}")
        total_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(total_label)

        # Botões de Forma de Pagamento
        payment_grid = QGridLayout()
        self.cash_button = QPushButton("Dinheiro")
        self.credit_button = QPushButton("Crédito")
        self.debit_button = QPushButton("Débito")
        self.pix_button = QPushButton("PIX")
        
        for btn in [self.cash_button, self.credit_button, self.debit_button, self.pix_button]:
            btn.setCheckable(True)
            btn.setAutoExclusive(True)

        payment_grid.addWidget(self.cash_button, 0, 0)
        payment_grid.addWidget(self.credit_button, 0, 1)
        payment_grid.addWidget(self.debit_button, 1, 0)
        payment_grid.addWidget(self.pix_button, 1, 1)
        main_layout.addLayout(payment_grid)

        # Campos para pagamento em Dinheiro
        self.cash_layout = QVBoxLayout()
        self.amount_paid_input = QLineEdit(placeholderText="Valor Recebido")
        self.change_label = QLabel("Troco: R$ 0,00")
        self.change_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.cash_layout.addWidget(QLabel("Valor Recebido:"))
        self.cash_layout.addWidget(self.amount_paid_input)
        self.cash_layout.addWidget(self.change_label)
        # Adiciona o layout de dinheiro, mas o esconde inicialmente
        cash_widget = QWidget()
        cash_widget.setLayout(self.cash_layout)
        self.cash_widget_container = main_layout.addWidget(cash_widget)
        cash_widget.setVisible(False)

        # Botão de Confirmação
        self.confirm_button = QPushButton("Confirmar Pagamento")
        self.confirm_button.setObjectName("confirm_button")
        self.confirm_button.setEnabled(False)
        main_layout.addWidget(self.confirm_button)

        # Conexões
        self.cash_button.toggled.connect(cash_widget.setVisible)
        self.cash_button.toggled.connect(self.toggle_confirm_button)
        self.credit_button.toggled.connect(self.toggle_confirm_button)
        self.debit_button.toggled.connect(self.toggle_confirm_button)
        self.pix_button.toggled.connect(self.toggle_confirm_button)
        
        self.amount_paid_input.textChanged.connect(self.calculate_change)
        self.confirm_button.clicked.connect(self.accept_payment)

    def toggle_confirm_button(self, checked):
        if not checked:
            return

        sender = self.sender()
        if sender == self.cash_button:
            self.confirm_button.setEnabled(False)
            self.calculate_change()
        else:
            self.confirm_button.setEnabled(True)

    def calculate_change(self):
        try:
            paid_amount_str = self.amount_paid_input.text().replace(",", ".")
            paid_amount = Decimal(paid_amount_str).quantize(Decimal('0.01'))
            change = paid_amount - self.total_amount
            if change >= 0:
                self.change_label.setText(f"Troco: R$ {change:.2f}")
                if self.cash_button.isChecked():
                    self.confirm_button.setEnabled(True)
            else:
                self.change_label.setText("Valor insuficiente")
                self.confirm_button.setEnabled(False)
        except (InvalidOperation, ValueError):
            self.change_label.setText("Troco: R$ 0,00")
            self.confirm_button.setEnabled(False)

    def accept_payment(self):
        if self.cash_button.isChecked():
            try:
                paid_amount_str = self.amount_paid_input.text().replace(",", ".")
                paid_amount = Decimal(paid_amount_str)
                if paid_amount < self.total_amount:
                    return
            except (InvalidOperation, ValueError):
                return
            self.payment_method = "Dinheiro"
        elif self.credit_button.isChecked():
            self.payment_method = "Crédito"
        elif self.debit_button.isChecked():
            self.payment_method = "Débito"
        elif self.pix_button.isChecked():
            self.payment_method = "PIX"
        
        if self.payment_method:
            self.accept()