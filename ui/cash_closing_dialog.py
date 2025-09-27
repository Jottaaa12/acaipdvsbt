'''
Dialog Aprimorado para Fechamento de Caixa

Foco em contagem, observações e um relatório final claro.
'''

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, 
    QGridLayout, QGroupBox, QTextEdit, QDialogButtonBox, QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from decimal import Decimal, InvalidOperation
import database as db
from utils import format_currency, parse_currency, to_reais

class CashClosingDialog(QDialog):
    '''Dialog focado na contagem de dinheiro e exibição de um relatório final.'''
    
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
        
        # --- Passo 1: Contagem e Observações ---
        self.counting_widget = QWidget()
        self.setup_counting_ui(self.counting_widget)
        self.layout.addWidget(self.counting_widget)

        # --- Passo 2: Relatório Final (inicialmente oculto) ---
        self.report_widget = QWidget()
        self.setup_report_ui(self.report_widget)
        self.layout.addWidget(self.report_widget)
        self.report_widget.setVisible(False)

    def setup_counting_ui(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        
        title = QLabel("Contagem de Dinheiro em Caixa")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Campo para valor contado em dinheiro
        cash_group = QGroupBox("Dinheiro")
        cash_layout = QGridLayout(cash_group)
        cash_layout.addWidget(QLabel("Total contado em dinheiro (cédulas + moedas): "), 0, 0)
        self.counted_cash_input = QLineEdit("0,00")
        self.counted_cash_input.setFont(QFont("Segoe UI", 12))
        cash_layout.addWidget(self.counted_cash_input, 0, 1)
        layout.addWidget(cash_group)

        # Campo para observações
        obs_group = QGroupBox("Observações")
        obs_layout = QVBoxLayout(obs_group)
        self.observations_input = QTextEdit()
        self.observations_input.setPlaceholderText("Adicione qualquer observação relevante sobre o fechamento...")
        obs_layout.addWidget(self.observations_input)
        layout.addWidget(obs_group)

        # Botões de ação
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

        # Botões de ação
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Confirmar e Fechar Caixa")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Voltar")
        button_box.accepted.connect(self.confirm_close_cash)
        button_box.rejected.connect(self.back_to_counting)
        layout.addWidget(button_box)
        self.report_buttons = button_box

    def load_expected_values(self):
        '''Carrega os valores esperados do banco de dados para o cálculo.'''
        report = db.get_cash_session_report(self.session_id)
        if not report or not report['session']:
            QMessageBox.critical(self, "Erro", "Não foi possível carregar os dados da sessão de caixa.")
            self.reject()
            return

        session_data = report['session']
        sales_summary = report['sales']
        movements = report['movements']

        initial = Decimal(session_data['initial_amount'])
        cash_sales = sum(Decimal(s['total']) for s in sales_summary if s['payment_method'] == 'Dinheiro')
        other_sales = {s['payment_method']: Decimal(s['total']) for s in sales_summary if s['payment_method'] != 'Dinheiro'}
        supplies = sum(Decimal(m['amount']) for m in movements if m['type'] == 'suprimento')
        withdrawals = sum(Decimal(m['amount']) for m in movements if m['type'] == 'sangria')

        expected_cash = initial + cash_sales + supplies - withdrawals
        
        self.expected_summary = {
            "initial": initial,
            "cash_sales": cash_sales,
            "other_sales": other_sales,
            "supplies": supplies,
            "withdrawals": withdrawals,
            "expected_cash": expected_cash,
            "session_info": session_data
        }

    def show_final_report(self):
        '''Calcula os totais, gera o relatório e muda para a visualização de relatório.'''
        try:
            counted_cash = parse_currency(self.counted_cash_input.text())
        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor contado em dinheiro é inválido.")
            return

        expected_cash = self.expected_summary['expected_cash']
        difference = counted_cash - expected_cash
        observations = self.observations_input.toPlainText().strip()

        # Armazena os valores para o fechamento final
        self.final_data = {
            "counted_cash": counted_cash,
            "difference": difference,
            "observations": observations
        }

        # Gera o texto do relatório
        report_text = self.generate_report_text(counted_cash, difference, observations)
        self.final_report_display.setText(report_text)

        # Alterna as visualizações
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
            f"Fechamento:{db.datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        )
        
        summary_header = "RESUMO FINANCEIRO".center(50, '-')
        summary_lines = (
            f"(+) Fundo de Troco:           {format_currency(self.expected_summary['initial']).rjust(15)}\n"
            f"(+) Vendas em Dinheiro:       {format_currency(self.expected_summary['cash_sales']).rjust(15)}\n"
            f"(+) Suprimentos:              {format_currency(self.expected_summary['supplies']).rjust(15)}\n"
            f"(-) Sangrias:                 {format_currency(self.expected_summary['withdrawals'], is_negative=True).rjust(15)}\n"
            f"{"-