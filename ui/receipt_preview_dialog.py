"""
Diálogo para preview do recibo antes da impressão.
Permite visualizar o recibo e confirmar a impressão.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDialogButtonBox, QGroupBox, QScrollArea, QWidget
)
from PyQt6.QtGui import QFont, QPixmap, QPainter, QKeyEvent
from PyQt6.QtCore import Qt
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
import logging

class ReceiptPreviewDialog(QDialog):
    """
    Diálogo que mostra o preview do recibo antes da impressão.
    """

    def __init__(self, store_info, receipt_details, printer_handler, parent=None):
        super().__init__(parent)
        self.store_info = store_info
        self.receipt_details = receipt_details
        self.printer_handler = printer_handler

        self.setWindowTitle("Preview do Recibo")
        self.setModal(True)
        self.resize(500, 600)  # Tamanho menor para caber na tela

        self.setup_ui()
        self.generate_preview()

    def setup_ui(self):
        """Configura a interface do usuário."""
        layout = QVBoxLayout(self)

        # Título
        title_label = QLabel("Preview do Recibo")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Área de preview com scroll
        preview_group = QGroupBox("Recibo")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Courier New", 10))  # Fonte monoespaçada para melhor formatação
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        preview_layout.addWidget(self.preview_text)

        # Scroll area para o preview
        scroll_area = QScrollArea()
        scroll_area.setWidget(preview_group)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Botões
        buttons_layout = QHBoxLayout()

        # Botão Cancelar
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        # Espaçamento
        buttons_layout.addStretch()

        # Botão Imprimir
        self.print_button = QPushButton("🖨️ IMPRIMIR")
        self.print_button.setObjectName("modern_button_primary")
        self.print_button.setMinimumHeight(40)
        self.print_button.clicked.connect(self.print_receipt)
        buttons_layout.addWidget(self.print_button)

        layout.addLayout(buttons_layout)

        # Foco inicial no botão Cancelar
        self.cancel_button.setFocus()
    def keyPressEvent(self, event: QKeyEvent):
        """Lida com eventos de teclado para navegação entre botões."""
        if event.key() == Qt.Key.Key_Left:
            # Seta esquerda - vai para o botão Cancelar
            self.cancel_button.setFocus()
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Seta direita - vai para o botão Imprimir
            self.print_button.setFocus()
            event.accept()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Enter - executa a ação do botão focado
            focused_button = self.focusWidget()
            if focused_button == self.cancel_button:
                self.reject()
            elif focused_button == self.print_button:
                self.print_receipt()
            event.accept()
        else:
            # Outras teclas - comportamento padrão
            super().keyPressEvent(event)

    def generate_preview(self):
        """Gera o preview do recibo formatado."""
        try:
            # Formatar o recibo como texto
            receipt_text = self._format_receipt_text()
            self.preview_text.setPlainText(receipt_text)

        except Exception as e:
            logging.error(f"Erro ao gerar preview do recibo: {e}")
            self.preview_text.setPlainText(f"Erro ao gerar preview: {e}")

    def _format_receipt_text(self):
        """Formata o recibo como texto para preview."""
        lines = []

        # Cabeçalho da loja
        store_name = self.store_info.get('name', 'LOJA')
        lines.append("=" * 48)
        lines.append(f"{store_name.center(48)}")
        lines.append("=" * 48)

        if self.store_info.get('address'):
            lines.append(f"{self.store_info['address'].center(48)}")
        if self.store_info.get('phone'):
            lines.append(f"{self.store_info['phone'].center(48)}")
        if self.store_info.get('cnpj'):
            lines.append(f"CNPJ: {self.store_info['cnpj']}")

        lines.append("")
        lines.append("=" * 48)
        lines.append("RECIBO - SEM VALOR FISCAL".center(48))
        lines.append("=" * 48)

        # Data e hora
        from datetime import datetime
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        lines.append(f"Data/Hora: {current_time}".center(48))
        lines.append("-" * 48)

        # Itens
        lines.append("DESCRIÇÃO                    QTD    VL.UN   VL.TOT")
        lines.append("-" * 48)

        total_amount = 0.0

        for item in self.receipt_details['items']:
            desc = item['description'][:25]  # Limitar descrição
            total_amount += float(item['total_price'])

            if item['sale_type'] == 'weight':
                qty_str = f"{item['quantity']:.3f}"
                unit_price_str = f"{item['unit_price']:.2f}"
            else:
                qty_str = f"{int(item['quantity'])}"
                unit_price_str = f"{item['unit_price']:.2f}"

            total_price_str = f"{item['total_price']:.2f}"

            # Formatar linha do item
            line = f"{desc:<25} {qty_str:>6} {unit_price_str:>7} {total_price_str:>7}"
            lines.append(line)

        # Totais
        lines.append("=" * 48)
        total_str = f"R$ {total_amount:.2f}"
        lines.append(f"{'TOTAL:':<35}{total_str:>13}")

        # Forma de pagamento
        payment_method = self.receipt_details.get('payment_method', 'N/A')
        lines.append(f"Pagamento: {payment_method}")

        # Troco
        change_amount = self.receipt_details.get('change_amount', 0.0)
        if change_amount > 0:
            change_str = f"R$ {change_amount:.2f}"
            lines.append(f"{'Troco:':<35}{change_str:>13}")

        # Desconto
        discount_value = self.receipt_details.get('discount_value', 0.0)
        if discount_value > 0:
            discount_str = f"R$ {discount_value:.2f}"
            lines.append(f"{'Desconto:':<35}{discount_str:>13}")

        lines.append("=" * 48)

        # Nome do cliente
        customer_name = self.receipt_details.get('customer_name')
        if customer_name:
            lines.append(f"Cliente: {customer_name}")

        # Rodapé
        lines.append("")
        lines.append("OBRIGADO PELA PREFERÊNCIA!".center(48))
        lines.append("")
        lines.append("Este recibo foi gerado automaticamente".center(48))
        lines.append("pelo sistema PDV Moderno".center(48))

        return "\n".join(lines)

    def print_receipt(self):
        """Executa a impressão do recibo."""
        try:
            # Tenta imprimir usando o printer_handler
            success, message = self.printer_handler.print_receipt(
                self.store_info,
                self.receipt_details
            )

            if success:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Impressão Concluída",
                                      "Recibo impresso com sucesso!")
                self.accept()  # Fecha o diálogo
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Erro na Impressão",
                                  f"Não foi possível imprimir o recibo:\n\n{message}")

        except Exception as e:
            logging.error(f"Erro ao imprimir recibo: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erro Crítico",
                               f"Ocorreu um erro inesperado durante a impressão:\n\n{str(e)}")
