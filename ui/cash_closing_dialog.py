from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, 
    QGridLayout, QGroupBox, QTextEdit, QDialogButtonBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging
import database as db
from utils import format_currency, parse_currency

class CashClosingDialog(QDialog):
    '''Dialog focado na contagem de dinheiro e exibição de um relatório final.'''
    
    # Sinal emitido com os dados de fechamento quando o usuário confirma.
    # O dicionário contém: final_amount, observations
    closing_confirmed = pyqtSignal(dict)

    def __init__(self, session_id, current_user, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.current_user = current_user
        self.expected_summary = None

        self.setWindowTitle("Fechamento de Caixa")
        self.setModal(True)
        self.setMinimumWidth(500)

        self.setup_ui()
        self.load_expected_values()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        self.counting_widget = QWidget()
        self.setup_counting_ui(self.counting_widget)
        self.layout.addWidget(self.counting_widget)

        self.report_widget = QWidget()
        self.setup_report_ui(self.report_widget)
        self.layout.addWidget(self.report_widget)
        self.report_widget.setVisible(False)

    def setup_counting_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        
        title = QLabel("Contagem de Dinheiro em Caixa")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        cash_group = QGroupBox("Dinheiro")
        cash_layout = QGridLayout(cash_group)
        cash_layout.addWidget(QLabel("Total contado em dinheiro (cédulas + moedas): "), 0, 0)
        self.counted_cash_input = QLineEdit("0,00")
        self.counted_cash_input.setFont(QFont("Segoe UI", 12))
        cash_layout.addWidget(self.counted_cash_input, 0, 1)
        layout.addWidget(cash_group)

        obs_group = QGroupBox("Observações")
        obs_layout = QVBoxLayout(obs_group)
        self.observations_input = QTextEdit()
        self.observations_input.setPlaceholderText("Adicione qualquer observação relevante sobre o fechamento...")
        obs_layout.addWidget(self.observations_input)
        layout.addWidget(obs_group)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Gerar Relatório de Fechamento")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        button_box.accepted.connect(self.show_final_report)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.counting_buttons = button_box

    def setup_report_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        
        title = QLabel("Relatório de Fechamento")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        self.final_report_display = QTextEdit()
        self.final_report_display.setReadOnly(True)
        self.final_report_display.setFont(QFont("Courier New", 10))
        layout.addWidget(self.final_report_display)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.confirm_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm_button.setText("Confirmar e Fechar Caixa")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Voltar")
        button_box.accepted.connect(self.confirm_and_emit)
        button_box.rejected.connect(self.back_to_counting)
        layout.addWidget(button_box)
        self.report_buttons = button_box

    def load_expected_values(self):
        report = db.get_cash_session_report(self.session_id)
        if not report or not report['session']:
            QMessageBox.critical(self, "Erro", "Não foi possível carregar os dados da sessão de caixa.")
            self.reject()
            return

        session_data = report['session']
        if not session_data:
            logging.error(f"Não foram encontrados dados para a sessão de caixa ID: {self.session_id}")
            QMessageBox.critical(self, "Erro", "Não foram encontrados dados para a sessão de caixa.")
            return
        sales_summary = report['sales']
        movements = report['movements']

        # --- Novos dados de Fiado ---
        session_date = session_data['open_time'].strftime('%Y-%m-%d')
        credit_payments = db.get_credit_payments_by_period(session_date, session_date)
        new_credit_sales = db.get_credit_sales_by_period(session_date, session_date)
        all_pending_credit_sales = db.get_all_pending_credit_sales() # Todos os fiados pendentes


        initial = Decimal(session_data['initial_amount'])
        cash_sales = sum(Decimal(s['total']) for s in sales_summary if s['payment_method'] == 'Dinheiro')
        # Adiciona pagamentos de fiado recebidos em dinheiro ao total de vendas em dinheiro
        cash_from_credit = sum(p['total_paid'] for p in credit_payments if p['payment_method'] == 'Dinheiro')
        cash_sales += cash_from_credit

        other_sales = {s['payment_method']: Decimal(s['total']) for s in sales_summary if s['payment_method'] != 'Dinheiro'}
        supplies = sum(Decimal(m['amount']) for m in movements if m['type'] == 'suprimento')
        withdrawals = sum(Decimal(m['amount']) for m in movements if m['type'] == 'sangria')

        total_weight_kg = db.get_total_weight_by_cash_session(self.session_id)

        expected_cash = initial + cash_sales + supplies - withdrawals

        self.expected_summary = {
            "initial": initial,
            "cash_sales": cash_sales,
            "other_sales": other_sales,
            "supplies": supplies,
            "withdrawals": withdrawals,
            "expected_cash": expected_cash,
            "session_info": session_data,
            "total_revenue": report['total_revenue'],
            "total_after_sangria": report['total_after_sangria'],
            "total_weight_kg": total_weight_kg,
            "total_discounts": report.get('total_discounts', Decimal('0.00')),
            "credit_payments": credit_payments, # Adicionado
            "new_credit_sales": new_credit_sales, # Adicionado
            "all_pending_credit_sales": all_pending_credit_sales # Adicionado
        }

    def show_final_report(self):
        try:
            counted_cash = parse_currency(self.counted_cash_input.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor contado em dinheiro é inválido.")
            return

        expected_cash = self.expected_summary['expected_cash']
        difference = counted_cash - expected_cash
        observations = self.observations_input.toPlainText().strip()

        self.final_data = {
            "final_amount": counted_cash,
            "observations": observations
        }

        report_text = self.generate_report_text(counted_cash, difference, observations)
        self.final_report_display.setText(report_text)

        self.counting_widget.setVisible(False)
        self.report_widget.setVisible(True)
        self.adjustSize()

    def generate_report_text(self, counted_cash, difference, observations):
        s_info = self.expected_summary['session_info']
        
        header = "RELATÓRIO DE FECHAMENTO DE CAIXA".center(50, '=')
        session_details = (
            f"Sessão ID: {self.session_id}\n"
            f"Operador:  {s_info['username']}\n"
            f"Abertura:  {s_info['open_time'].strftime('%d/%m/%Y %H:%M')}\n"
            f"Fechamento:{datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        )
        
        summary_header = "RESUMO FINANCEIRO".center(50, '-')
        summary_lines = (
            f"(+) Fundo de Troco:           {format_currency(self.expected_summary['initial']).rjust(15)}\n"
            f"(+) Vendas em Dinheiro:       {format_currency(self.expected_summary['cash_sales']).rjust(15)}\n"
            f"(+) Suprimentos:              {format_currency(self.expected_summary['supplies']).rjust(15)}\n"
            f"(-) Sangrias:                 {format_currency(self.expected_summary['withdrawals'], is_negative=True).rjust(15)}\n"
            f"{'='*50}\n"
            f"(=) SALDO ESPERADO EM CAIXA:  {format_currency(self.expected_summary['expected_cash']).rjust(15)}\n"
            f"    SALDO CONTADO EM CAIXA:   {format_currency(counted_cash).rjust(15)}\n"
            f"{'-'*50}\n"
            f"(=) DIFERENÇA DE CAIXA:       {format_currency(difference).rjust(15)}\n"
        )

        credit_payments_header = "ENTRADAS POR PAGAMENTO DE FIADO".center(50, '-')
        credit_payments_lines = ""
        if self.expected_summary['credit_payments']:
            for payment in self.expected_summary['credit_payments']:
                credit_payments_lines += f"{payment['payment_method'].ljust(25)} {format_currency(payment['total_paid']).rjust(24)}\n"
        else:
            credit_payments_lines = "Nenhum pagamento de fiado recebido no dia.\n"

        other_sales_header = "VENDAS (OUTRAS FORMAS)".center(50, '-')
        other_sales_lines = ""
        if self.expected_summary['other_sales']:
            for method, total in self.expected_summary['other_sales'].items():
                other_sales_lines += f"{method.ljust(25)} {format_currency(total).rjust(24)}\n"
        else:
            other_sales_lines = "Nenhuma venda em outras formas de pagamento.\n"

        new_credit_sales_header = "FIADOS CRIADOS NO DIA (A RECEBER)".center(50, '-')
        new_credit_sales_lines = ""
        if self.expected_summary['new_credit_sales']:
            total_credit_today = Decimal('0')
            for sale in self.expected_summary['new_credit_sales']:
                new_credit_sales_lines += f"{sale['customer_name'][:24].ljust(25)} {format_currency(sale['amount']).rjust(24)}\n"
                total_credit_today += sale['amount']
            new_credit_sales_lines += f"{'-'*50}\n"
            new_credit_sales_lines += f"Total Fiado Hoje: {format_currency(total_credit_today).rjust(33)}\n"
        else:
            new_credit_sales_lines = "Nenhuma venda a crédito criada no dia.\n"

        all_pending_credit_header = "TODOS OS FIADOS PENDENTES (A RECEBER)".center(50, '-')
        all_pending_credit_lines = ""
        if self.expected_summary['all_pending_credit_sales']:
            total_pending_credit = Decimal('0')
            for sale in self.expected_summary['all_pending_credit_sales']:
                all_pending_credit_lines += f"{sale['customer_name'][:24].ljust(25)} {format_currency(sale['balance_due']).rjust(24)}\n"
                total_pending_credit += sale['balance_due']
            all_pending_credit_lines += f"{'-'*50}\n"
            all_pending_credit_lines += f"Total Fiado Pendente: {format_currency(total_pending_credit).rjust(30)}\n"
        else:
            all_pending_credit_lines = "Nenhum fiado pendente encontrado.\n"

        grand_total_header = "TOTAIS GERAIS".center(50, '-')
        grand_total_lines = (
            f"Faturamento Bruto (Todas Formas): {format_currency(self.expected_summary['total_revenue']).rjust(15)}\n"
            f"Faturamento - Sangrias:         {format_currency(self.expected_summary['total_after_sangria']).rjust(15)}\n"
            f"Total de Descontos Concedidos:  {format_currency(self.expected_summary['total_discounts']).rjust(15)}\n"
            f"Total de Açaí Vendido (kg):     {format(self.expected_summary.get('total_weight_kg', 0.0), '.3f').rjust(15)}\n"
        )

        obs_header = "OBSERVAÇÕES".center(50, '-')
        obs_text = observations if observations else "Nenhuma observação."

        return (
            f"{header}\n"
            f"{session_details}\n"
            f"{summary_header}\n"
            f"{summary_lines}"
            f"{credit_payments_header}\n"
            f"{credit_payments_lines}\n"
            f"{other_sales_header}\n"
            f"{other_sales_lines}\n"
            f"{new_credit_sales_header}\n"
            f"{new_credit_sales_lines}\n"
            f"{all_pending_credit_header}\n"
            f"{all_pending_credit_lines}\n"
            f"{grand_total_header}\n"
            f"{grand_total_lines}\n"
            f"{obs_header}\n"
            f"{obs_text}\n"
            f"{ '='*50}\n"
        )

    def confirm_and_emit(self):
        """Emite o sinal com os dados de fechamento e fecha o diálogo."""
        if not self.final_data:
            QMessageBox.critical(self, "Erro", "Não há dados finais para submeter.")
            return
        
        # Desabilita o botão para evitar cliques duplos
        self.confirm_button.setEnabled(False)
        self.confirm_button.setText("Fechando...")

        self.closing_confirmed.emit(self.final_data)
        # O diálogo não será fechado aqui. A CashPage o fechará quando receber a confirmação do worker.

    def back_to_counting(self):
        """Volta para a tela de contagem para corrigir ou revisar."""
        self.report_widget.setVisible(False)
        self.counting_widget.setVisible(True)
        self.adjustSize()
