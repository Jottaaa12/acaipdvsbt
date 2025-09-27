'''
Página de Gestão de Caixa Refatorada

Este arquivo implementa a nova interface de três colunas para a gestão de caixa,
seguindo as especificações do projeto de refatoração.
'''

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QGridLayout,
    QFrame, QSplitter, QTabWidget, QDateEdit, QComboBox, QInputDialog, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QDate
from PyQt6.QtGui import QFont, QColor
from decimal import Decimal, InvalidOperation
import database as db
from ui.theme import ModernTheme, IconTheme
from utils import format_currency, parse_currency

class CashPage(QWidget):
    '''Página refatorada para uma gestão de caixa moderna e completa.'''

    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.session_id = None
        self.operators = []

        self.setup_ui()
        self.load_initial_data()

        # Timer para alertas e atualizações em tempo real
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_live_data)
        self.update_timer.start(5000) # Verifica a cada 5 segundos

    def setup_ui(self):
        '''Configura a interface principal com o layout de três colunas.'''
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- Coluna 1: Ações e Status ---
        col1_widget = self.create_left_column()
        splitter.addWidget(col1_widget)

        # --- Coluna 2: Resumo Financeiro ---
        col2_widget = self.create_center_column()
        splitter.addWidget(col2_widget)

        # --- Coluna 3: Detalhes e Histórico ---
        col3_widget = self.create_right_column()
        splitter.addWidget(col3_widget)

        splitter.setSizes([250, 400, 350])

    def load_initial_data(self):
        '''Carrega dados que não mudam com frequência, como a lista de operadores.'''
        self.operators = db.get_all_users()
        self.history_operator_filter.addItem("Todos", userData=None)
        for op in self.operators:
            self.history_operator_filter.addItem(op['username'], userData=op['id'])
        
        self.update_live_data()
        self.load_session_history()

    def update_live_data(self):
        '''Função principal que atualiza todos os dados da página.'''
        session = db.get_current_cash_session()
        self.session_id = session['id'] if session else None

        self.update_status_card(session)
        self.update_buttons_state(bool(session))

        if self.session_id:
            self.update_financial_summary()
            self.update_payment_methods_summary()
            self.update_movements_tab()
            self.check_for_alerts(session)
        else:
            self.clear_financial_summary()
            self.clear_payment_methods_summary()
            self.clear_movements_tab()

    # ==========================================================================
    # --- Coluna 1: Ações e Status
    # ==========================================================================
    def create_left_column(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Card de Status
        self.status_card = QGroupBox("Status do Caixa")
        status_layout = QVBoxLayout(self.status_card)
        self.status_label = QLabel("CAIXA FECHADO")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        status_layout.addWidget(self.status_label)

        self.status_details_widget = QWidget()
        details_layout = QGridLayout(self.status_details_widget)
        details_layout.setContentsMargins(0, 10, 0, 0)
        self.session_id_label = QLabel()
        self.operator_label = QLabel()
        self.open_time_label = QLabel()
        self.initial_amount_label = QLabel()
        details_layout.addWidget(QLabel("<b>Sessão:</b>"), 0, 0)
        details_layout.addWidget(self.session_id_label, 0, 1)
        details_layout.addWidget(QLabel("<b>Operador:</b>"), 1, 0)
        details_layout.addWidget(self.operator_label, 1, 1)
        details_layout.addWidget(QLabel("<b>Abertura:</b>"), 2, 0)
        details_layout.addWidget(self.open_time_label, 2, 1)
        details_layout.addWidget(QLabel("<b>Fundo de Troco:</b>"), 3, 0)
        details_layout.addWidget(self.initial_amount_label, 3, 1)
        status_layout.addWidget(self.status_details_widget)

        # Card de Ações
        actions_card = QGroupBox("Ações")
        actions_layout = QVBoxLayout(actions_card)
        self.open_cash_button = QPushButton(f'{IconTheme.get_icon("open")} Abrir Caixa')
        self.open_cash_button.setObjectName("modern_button_primary")
        self.open_cash_button.clicked.connect(self.handle_open_cash)
        self.close_cash_button = QPushButton(f'{IconTheme.get_icon("close")} Fechar Caixa')
        self.close_cash_button.setObjectName("modern_button_error")
        self.close_cash_button.clicked.connect(self.handle_close_cash)
        self.supply_button = QPushButton(f'{IconTheme.get_icon("supply")} Suprimento')
        self.supply_button.setObjectName("modern_button_secondary")
        self.supply_button.clicked.connect(lambda: self.handle_cash_movement('suprimento'))
        self.withdrawal_button = QPushButton(f'{IconTheme.get_icon("withdrawal")} Sangria')
        self.withdrawal_button.setObjectName("modern_button_secondary")
        self.withdrawal_button.clicked.connect(lambda: self.handle_cash_movement('sangria'))
        actions_layout.addWidget(self.open_cash_button)
        actions_layout.addWidget(self.close_cash_button)
        actions_layout.addWidget(self.supply_button)
        actions_layout.addWidget(self.withdrawal_button)

        layout.addWidget(self.status_card)
        layout.addWidget(actions_card)
        layout.addStretch()
        return widget

    def update_status_card(self, session):
        if session:
            self.status_label.setText("CAIXA ABERTO")
            self.status_label.setStyleSheet(f"background-color: {ModernTheme.SUCCESS}; color: white; padding: 8px; border-radius: 5px;")
            self.session_id_label.setText(f"#{session['id']}")
            self.operator_label.setText(session['username'])
            self.open_time_label.setText(session['open_time'].strftime('%d/%m/%Y %H:%M'))
            self.initial_amount_label.setText(format_currency(session['initial_amount']))
            self.status_details_widget.setVisible(True)
        else:
            self.status_label.setText("CAIXA FECHADO")
            self.status_label.setStyleSheet(f"background-color: {ModernTheme.ERROR}; color: white; padding: 8px; border-radius: 5px;")
            self.status_details_widget.setVisible(False)

    def update_buttons_state(self, is_open):
        self.open_cash_button.setEnabled(not is_open)
        self.close_cash_button.setEnabled(is_open)
        self.supply_button.setEnabled(is_open)
        self.withdrawal_button.setEnabled(is_open)

    # ==========================================================================
    # --- Coluna 2: Resumo Financeiro
    # ==========================================================================
    def create_center_column(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Card: Resumo da Sessão
        summary_card = QGroupBox("Resumo da Sessão Atual")
        summary_layout = QGridLayout(summary_card)
        self.summary_initial = self.create_summary_row(summary_layout, 0, "(+) Fundo de Troco:")
        self.summary_cash_sales = self.create_summary_row(summary_layout, 1, "(+) Vendas em Dinheiro:")
        self.summary_other_sales = self.create_summary_row(summary_layout, 2, "(+) Outras Formas de Pagamento:")
        self.summary_supplies = self.create_summary_row(summary_layout, 3, "(+) Suprimentos:")
        self.summary_withdrawals = self.create_summary_row(summary_layout, 4, "(-) Sangrias:")
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        summary_layout.addWidget(separator, 5, 0, 1, 2)

        self.summary_total_sales = self.create_summary_row(summary_layout, 6, "(=) Total de Vendas na Sessão:")
        self.summary_expected_cash = self.create_summary_row(summary_layout, 7, "(=) Saldo Esperado em Dinheiro:")
        self.summary_expected_cash.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        summary_layout.setColumnStretch(1, 1)

        # Card: Vendas por Forma de Pagamento
        payments_card = QGroupBox("Vendas por Forma de Pagamento")
        payments_layout = QVBoxLayout(payments_card)
        self.payments_table = QTableWidget(0, 2)
        self.payments_table.setHorizontalHeaderLabels(["Forma de Pagamento", "Total"])
        self.payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payments_table.setStyleSheet("border: none;")
        payments_layout.addWidget(self.payments_table)

        layout.addWidget(summary_card)
        layout.addWidget(payments_card)
        return widget

    def create_summary_row(self, layout, row, label_text):
        label = QLabel(label_text)
        value_label = QLabel(format_currency(0))
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(label, row, 0)
        layout.addWidget(value_label, row, 1)
        return value_label

    def update_financial_summary(self):
        report = db.get_cash_session_report(self.session_id)
        if not report or not report['session']:
            return

        session_data = report['session']
        sales_summary = report['sales']
        movements = report['movements']

        initial = Decimal(session_data['initial_amount'])
        cash_sales = sum(Decimal(s['total']) for s in sales_summary if s['payment_method'] == 'Dinheiro')
        other_sales = sum(Decimal(s['total']) for s in sales_summary if s['payment_method'] != 'Dinheiro')
        supplies = sum(Decimal(m['amount']) for m in movements if m['type'] == 'suprimento')
        withdrawals = sum(Decimal(m['amount']) for m in movements if m['type'] == 'sangria')

        total_sales = cash_sales + other_sales
        expected_cash = initial + cash_sales + supplies - withdrawals

        self.summary_initial.setText(format_currency(initial))
        self.summary_cash_sales.setText(format_currency(cash_sales))
        self.summary_other_sales.setText(format_currency(other_sales))
        self.summary_supplies.setText(format_currency(supplies))
        self.summary_withdrawals.setText(format_currency(withdrawals, is_negative=True))
        self.summary_total_sales.setText(format_currency(total_sales))
        self.summary_expected_cash.setText(format_currency(expected_cash))

    def clear_financial_summary(self):
        self.summary_initial.setText(format_currency(0))
        self.summary_cash_sales.setText(format_currency(0))
        self.summary_other_sales.setText(format_currency(0))
        self.summary_supplies.setText(format_currency(0))
        self.summary_withdrawals.setText(format_currency(0, is_negative=True))
        self.summary_total_sales.setText(format_currency(0))
        self.summary_expected_cash.setText(format_currency(0))

    def update_payment_methods_summary(self):
        summary = db.get_payment_summary_by_cash_session(self.session_id)
        self.payments_table.setRowCount(len(summary))
        for i, item in enumerate(summary):
            self.payments_table.setItem(i, 0, QTableWidgetItem(item['payment_method']))
            self.payments_table.setItem(i, 1, QTableWidgetItem(format_currency(item['total'])))

    def clear_payment_methods_summary(self):
        self.payments_table.setRowCount(0)

    # ==========================================================================
    # --- Coluna 3: Detalhes e Histórico
    # ==========================================================================
    def create_right_column(self):
        self.tabs = QTabWidget()

        # Aba 1: Últimas Movimentações
        movements_tab = QWidget()
        movements_layout = QVBoxLayout(movements_tab)
        self.movements_table = QTableWidget(0, 4)
        self.movements_table.setHorizontalHeaderLabels(["Tipo", "Valor", "Motivo", "Hora"])
        self.movements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.movements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        movements_layout.addWidget(self.movements_table)

        # Aba 2: Histórico de Sessões
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        filter_widget = self.create_history_filters()
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["ID", "Operador", "Data de Fechamento", "Diferença (R$)"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.itemSelectionChanged.connect(self.on_history_session_selected)
        history_layout.addWidget(filter_widget)
        history_layout.addWidget(self.history_table)

        # Aba 3: Relatório da Sessão
        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        report_layout.addWidget(self.report_display)

        self.tabs.addTab(movements_tab, "Últimas Movimentações")
        self.tabs.addTab(history_tab, "Histórico de Sessões")
        self.tabs.addTab(report_tab, "Relatório da Sessão")
        self.tabs.setTabEnabled(2, False) # Desabilitar aba de relatório por padrão

        return self.tabs

    def create_history_filters(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 10)
        self.history_start_date = QDateEdit(calendarPopup=True)
        self.history_start_date.setDate(QDate.currentDate().addMonths(-1))
        self.history_end_date = QDateEdit(calendarPopup=True)
        self.history_end_date.setDate(QDate.currentDate())
        self.history_operator_filter = QComboBox()
        filter_button = QPushButton(f'{IconTheme.get_icon("filter")} Filtrar')
        filter_button.clicked.connect(self.load_session_history)
        layout.addWidget(QLabel("De:"))
        layout.addWidget(self.history_start_date)
        layout.addWidget(QLabel("Até:"))
        layout.addWidget(self.history_end_date)
        layout.addWidget(QLabel("Operador:"))
        layout.addWidget(self.history_operator_filter)
        layout.addWidget(filter_button)
        layout.addStretch()
        return widget

    def update_movements_tab(self):
        movements = db.get_cash_session_report(self.session_id)['movements']
        self.movements_table.setRowCount(len(movements))
        for i, m in enumerate(movements):
            self.movements_table.setItem(i, 0, QTableWidgetItem(m['type'].capitalize()))
            self.movements_table.setItem(i, 1, QTableWidgetItem(format_currency(m['amount'])))
            self.movements_table.setItem(i, 2, QTableWidgetItem(m['reason']))
            self.movements_table.setItem(i, 3, QTableWidgetItem(m['timestamp'].strftime('%H:%M:%S')))

    def clear_movements_tab(self):
        self.movements_table.setRowCount(0)

    def load_session_history(self):
        start_date = self.history_start_date.date().toString("yyyy-MM-dd")
        end_date = self.history_end_date.date().toString("yyyy-MM-dd")
        operator_id = self.history_operator_filter.currentData()

        history = db.get_cash_session_history(start_date, end_date, operator_id)
        self.history_table.setRowCount(len(history))
        for i, session in enumerate(history):
            diff = Decimal(session['difference'])
            diff_item = QTableWidgetItem(format_currency(diff))
            if diff < 0:
                diff_item.setForeground(QColor(ModernTheme.ERROR))
            elif diff > 0:
                diff_item.setForeground(QColor(ModernTheme.SUCCESS))

            self.history_table.setItem(i, 0, QTableWidgetItem(str(session['id'])))
            self.history_table.setItem(i, 1, QTableWidgetItem(session['user_opened']))
            self.history_table.setItem(i, 2, QTableWidgetItem(session['close_time'].strftime('%d/%m/%Y %H:%M')))
            self.history_table.setItem(i, 3, diff_item)

    def on_history_session_selected(self):
        selected_items = self.history_table.selectedItems()
        if not selected_items:
            return
        
        session_id = int(self.history_table.item(selected_items[0].row(), 0).text())
        self.generate_session_report(session_id)
        self.tabs.setTabEnabled(2, True)
        self.tabs.setCurrentIndex(2)

    def generate_session_report(self, session_id):
        report = db.get_cash_session_report(session_id)
        if not report or not report['session']:
            self.report_display.setHtml("<h1>Relatório não encontrado</h1>")
            return

        s = report['session']
        total_sales = sum(Decimal(p['total']) for p in report['sales']) # Novo cálculo

        html = f"""
        <h1>Relatório da Sessão #{s['id']}</h1>
        <p><b>Operador:</b> {s['username']}</p>
        <p><b>Abertura:</b> {s['open_time'].strftime('%d/%m/%Y %H:%M')}</p>
        <p><b>Fechamento:</b> {s['close_time'].strftime('%d/%m/%Y %H:%M')}</p>
        <hr>
        <h2>Resumo Financeiro</h2>
        <table width='100%'>
            <tr><td>(+) Fundo de Troco:</td><td align='right'>{format_currency(s['initial_amount'])}</td></tr>
            <tr><td>(+) Total de Vendas:</td><td align='right'>{format_currency(total_sales)}</td></tr>
            <tr><td>(-) Valor Contado:</td><td align='right'>{format_currency(s['final_amount'])}</td></tr>
            <tr><td><b>(=) Diferença:</b></td><td align='right'><b>{format_currency(s['difference'])}</b></td></tr>
        </table>
        <p><i><b>Observações:</b> {s.get('observations', 'Nenhuma')}</i></p>
        <hr>
        <h2>Vendas por Forma de Pagamento</h2>
        <table width='100%'>
        """
        for p in report['sales']:
            html += f"<tr><td>{p['payment_method']}</td><td align='right'>{format_currency(p['total'])}</td></tr>"
        html += "</table><hr><h2>Movimentações de Caixa</h2><table width='100%'>"
        for m in report['movements']:
            auth_by = f" (Autorizado por: {m['authorized_by']})" if m['authorized_by'] else ""
            html += f"<tr><td>{m['type'].capitalize()}{auth_by}</td><td align='right'>{format_currency(m['amount'])}</td></tr>"
        html += "</table>"
        self.report_display.setHtml(html)

    # ==========================================================================
    # --- Lógica de Ações e Alertas
    # ==========================================================================
    def handle_open_cash(self):
        amount_text, ok = QInputDialog.getText(self, "Abrir Caixa", "Valor inicial (fundo de troco):", text="0,00")
        if not ok: return
        try:
            initial_amount = parse_currency(amount_text)
            session_id, msg = db.open_cash_session(self.current_user['id'], initial_amount)
            if session_id:
                QMessageBox.information(self, "Sucesso", f"Caixa aberto com ID: {session_id}")
                self.update_live_data()
            else:
                QMessageBox.warning(self, "Erro", msg)
        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor digitado não é um número válido.")

    def handle_close_cash(self):
        from ui.cash_closing_dialog import CashClosingDialog # Importação local
        dialog = CashClosingDialog(self.session_id, self.current_user, self)
        if dialog.exec():
            self.update_live_data()
            self.load_session_history()
            QMessageBox.information(self, "Caixa Fechado", "A sessão de caixa foi fechada com sucesso.")

    def handle_cash_movement(self, m_type):
        title = "Suprimento" if m_type == 'suprimento' else "Sangria"
        amount_text, ok = QInputDialog.getText(self, title, f"Valor do {title.lower()}:", text="0,00")
        if not ok: return

        try:
            amount = parse_currency(amount_text)
            if amount <= 0:
                QMessageBox.warning(self, "Valor Inválido", "O valor deve ser maior que zero.")
                return

            reason, ok = QInputDialog.getText(self, title, f"Motivo do {title.lower()}:")
            if not ok or not reason.strip():
                QMessageBox.warning(self, "Motivo Obrigatório", "É necessário informar um motivo.")
                return

            authorized_by_id = None
            # Exigir senha de gerente para valores altos
            if amount > 50:
                manager_user, ok_user = QInputDialog.getText(self, "Autorização Necessária", "Usuário do gerente:")
                if not ok_user: return

                manager_pass, ok_pass = QInputDialog.getText(self, "Autorização Necessária", f"Senha de {manager_user}:", echo=QLineEdit.EchoMode.Password)
                if not ok_pass: return

                manager = db.authenticate_user(manager_user, manager_pass)
                if manager and manager['role'] == 'gerente':
                    authorized_by_id = manager['id']
                else:
                    QMessageBox.critical(self, "Falha na Autorização", "Credenciais de gerente inválidas ou usuário não possui permissão.")
                    return

            db.add_cash_movement(self.session_id, self.current_user['id'], m_type, amount, reason, authorized_by_id)
            QMessageBox.information(self, "Sucesso", f"{title} registrado com sucesso.")
            self.update_live_data()

        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor digitado não é um número válido.")

    def check_for_alerts(self, session):
        # Alerta 1: Duração da sessão
        open_duration = datetime.now() - session['open_time']
        if open_duration.total_seconds() > 24 * 3600: # 24 horas
            self.status_card.setStyleSheet(f"QGroupBox {{ border: 2px solid {ModernTheme.WARNING}; }}")
        else:
            self.status_card.setStyleSheet("")

        # Alerta 2: Limite de dinheiro em caixa
        expected_cash_str = self.summary_expected_cash.text().replace("R$", "").strip()
        try:
            expected_cash = parse_currency(expected_cash_str)
            if expected_cash > 1000:
                self.summary_expected_cash.setStyleSheet(f"color: {ModernTheme.ERROR}; font-weight: bold;")
            else:
                self.summary_expected_cash.setStyleSheet("")
        except InvalidOperation:
            pass # Ignora se o valor ainda não for um número válido

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)