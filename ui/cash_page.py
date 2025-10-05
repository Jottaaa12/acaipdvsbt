
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QGridLayout,
    QFrame, QSplitter, QTabWidget, QDateEdit, QComboBox, QInputDialog, QTextEdit, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from decimal import Decimal, InvalidOperation
from datetime import datetime

import database as db
from ui.theme import ModernTheme, IconTheme
from utils import format_currency, parse_currency
from ui.cash_manager import CashManager
from ui.cash_closing_dialog import CashClosingDialog
from integrations.whatsapp_manager import WhatsAppManager
from PyQt6.QtCore import QThreadPool
from .worker import Worker
import logging

class CashPage(QWidget):
    '''Página refatorada para uma gestão de caixa moderna e completa.'''

    # Sinal emitido quando o estado do caixa muda (aberto/fechado)
    cash_session_changed = pyqtSignal()

    def __init__(self, current_user):
        super().__init__()
        self.current_user = current_user
        self.session_id = None
        self.last_initial_amount = None
        self.operators = []

        # ThreadPool para operações assíncronas
        self.threadpool = QThreadPool()

        # Gerenciador de operações de caixa assíncronas
        self.cash_manager = CashManager()
        self.cash_manager.session_opened.connect(self.on_session_opened)
        self.cash_manager.session_closed.connect(self.on_session_closed)
        self.cash_manager.status_updated.connect(self.on_status_updated)

        self.setup_ui()
        self.load_initial_data()

        # Timer para atualizações em tempo real (pode ser menos frequente agora)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_live_data)
        self.update_timer.start(30000) # Atualiza a cada 30 segundos

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        col1_widget = self.create_left_column()
        splitter.addWidget(col1_widget)

        col2_widget = self.create_center_column()
        splitter.addWidget(col2_widget)

        col3_widget = self.create_right_column()
        splitter.addWidget(col3_widget)

        splitter.setSizes([250, 400, 350])

    def load_initial_data(self):
        self.operators = db.get_all_users()
        self.history_operator_filter.addItem("Todos", userData=None)
        for op in self.operators:
            self.history_operator_filter.addItem(op['username'], userData=op['id'])
        
        self.update_live_data()
        self.load_session_history()

    def update_live_data(self):
        self.cash_manager.get_status_async()

    def on_status_updated(self, session):
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

        self.status_card = QGroupBox("Status do Caixa")
        status_layout = QVBoxLayout(self.status_card)
        self.status_label = QLabel("VERIFICANDO...")
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

    def update_buttons_state(self, is_open, is_busy=False):
        if is_busy:
            self.open_cash_button.setEnabled(False)
            self.close_cash_button.setEnabled(False)
        else:
            self.open_cash_button.setEnabled(not is_open)
            self.close_cash_button.setEnabled(is_open)
        
        self.supply_button.setEnabled(is_open and not is_busy)
        self.withdrawal_button.setEnabled(is_open and not is_busy)

    # ... (O resto das colunas central e direita permanecem as mesmas) ...
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

        movements_tab = QWidget()
        movements_layout = QVBoxLayout(movements_tab)
        self.movements_table = QTableWidget(0, 4)
        self.movements_table.setHorizontalHeaderLabels(["Tipo", "Valor", "Motivo", "Hora"])
        self.movements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.movements_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        movements_layout.addWidget(self.movements_table)

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

        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        report_layout.addWidget(self.report_display)

        self.tabs.addTab(movements_tab, "Últimas Movimentações")
        self.tabs.addTab(history_tab, "Histórico de Sessões")
        self.tabs.addTab(report_tab, "Relatório da Sessão")
        self.tabs.setTabEnabled(2, False)

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
        self.filter_button = QPushButton(f'{IconTheme.get_icon("filter")} Filtrar')
        self.filter_button.clicked.connect(self.load_session_history)
        self.original_filter_text = f'{IconTheme.get_icon("filter")} Filtrar'
        layout.addWidget(QLabel("De:"))
        layout.addWidget(self.history_start_date)
        layout.addWidget(QLabel("Até:"))
        layout.addWidget(self.history_end_date)
        layout.addWidget(QLabel("Operador:"))
        layout.addWidget(self.history_operator_filter)
        layout.addWidget(self.filter_button)
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
        # Desabilitar botão e alterar texto
        self.filter_button.setEnabled(False)
        self.filter_button.setText("Carregando...")

        start_date = self.history_start_date.date().toString("yyyy-MM-dd")
        end_date = self.history_end_date.date().toString("yyyy-MM-dd")
        operator_id = self.history_operator_filter.currentData()

        worker = Worker(db.get_cash_session_history, start_date, end_date, operator_id)
        worker.signals.finished.connect(self.populate_history_table)
        worker.signals.finished.connect(lambda: self.filter_button.setEnabled(True))
        worker.signals.finished.connect(lambda: self.filter_button.setText(self.original_filter_text))
        worker.signals.error.connect(lambda err: logging.error(f"Erro ao carregar histórico de sessões: {err}"))
        worker.signals.error.connect(lambda err: self.filter_button.setEnabled(True))
        worker.signals.error.connect(lambda err: self.filter_button.setText(self.original_filter_text))
        self.threadpool.start(worker)

    def populate_history_table(self, history):
        self.history_table.setRowCount(len(history))
        for i, session in enumerate(history):
            diff = Decimal(session['difference'])
            diff_item = QTableWidgetItem(format_currency(diff))
            if diff < 0:
                diff_item.setForeground(QColor(ModernTheme.ERROR))
            elif diff > 0:
                diff_item.setForeground(QColor(ModernTheme.SUCCESS))

            username = session['username'] if session['username'] else "[Usuário Removido]"
            self.history_table.setItem(i, 0, QTableWidgetItem(str(session['id'])))
            self.history_table.setItem(i, 1, QTableWidgetItem(username))
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
        total_sales = sum(Decimal(p['total']) for p in report['sales'])

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
            self.last_initial_amount = initial_amount
            self.open_cash_button.setText("Abrindo...")
            self.update_buttons_state(is_open=False, is_busy=True)
            self.cash_manager.open_session_async(self.current_user['id'], initial_amount)
        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor digitado não é um número válido.")

    def on_session_opened(self, success, message):
        self.open_cash_button.setText(f'{IconTheme.get_icon("open")} Abrir Caixa')
        if success:
            QMessageBox.information(self, "Sucesso", f"Caixa aberto com ID: {message}")
            self.update_live_data()
            self.cash_session_changed.emit()

            # Enviar notificação de abertura de caixa via WhatsApp
            try:
                from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                sales_notifier = get_whatsapp_sales_notifier()

                sales_notifier.notify_cash_opening(
                    self.current_user['username'],
                    float(self.last_initial_amount),
                    {'id': 'nova_sessao'}
                )
            except Exception as e:
                logging.warning(f"Erro ao enviar notificação de abertura de caixa: {e}")
        else:
            QMessageBox.warning(self, "Erro", message)
        self.update_buttons_state(is_open=success, is_busy=False)

    def handle_close_cash(self):
        self.close_cash_dialog = CashClosingDialog(self.session_id, self.current_user, self)
        self.close_cash_dialog.closing_confirmed.connect(self.on_closing_confirmed)
        self.close_cash_dialog.show() # Usar show() em vez de exec() para não bloquear

    def on_closing_confirmed(self, data):
        self.update_buttons_state(is_open=True, is_busy=True)
        self.close_cash_button.setText("Fechando...")
        self.cash_manager.close_session_async(
            session_id=self.session_id,
            user_id=self.current_user['id'],
            final_amount=data['final_amount'],
            cash_counts={},
            observations=data['observations']
        )

    def on_session_closed(self, success, message):
        self.close_cash_button.setText(f'{IconTheme.get_icon("close")} Fechar Caixa')
        if hasattr(self, 'close_cash_dialog') and self.close_cash_dialog.isVisible():
            self.close_cash_dialog.accept() # Fecha o diálogo

        if success:
            QMessageBox.information(self, "Caixa Fechado", message)
            self.update_live_data()
            self.load_session_history()
            self.cash_session_changed.emit()

            # Enviar notificação detalhada de fechamento de caixa via WhatsApp
            try:
                from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                sales_notifier = get_whatsapp_sales_notifier()

                # Obter relatório completo da sessão
                report = db.get_cash_session_report(self.session_id)
                if report and report['session']:
                    session_data = report['session']
                    summary_dict = {
                        'id': session_data['id'],
                        'final_amount': float(session_data['final_amount']),
                        'difference': float(session_data['difference'])
                    }

                    sales_notifier.notify_cash_closing(
                        session_data['username'],  # Nome do usuário que abriu
                        float(session_data['initial_amount']),
                        summary_dict
                    )
            except Exception as e:
                logging.warning(f"Erro ao enviar notificação de fechamento de caixa: {e}")
        else:
            QMessageBox.critical(self, "Erro ao Fechar o Caixa", message)

        self.update_buttons_state(is_open=False, is_busy=False)

    def handle_cash_movement(self, m_type):
        # Esta função ainda é síncrona, mas geralmente é rápida.
        # Poderia ser movida para o CashManager se necessário.
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
            # Removida solicitação de senha de gerente para valores altos

            db.add_cash_movement(self.session_id, self.current_user['id'], m_type, amount, reason, authorized_by_id)
            QMessageBox.information(self, "Sucesso", f"{title} registrado com sucesso.")
            self.update_live_data()

        except InvalidOperation:
            QMessageBox.warning(self, "Valor Inválido", "O valor digitado não é um número válido.")

    def check_for_alerts(self, session):
        if not session or not session.get('open_time'): return
        try:
            open_duration = datetime.now() - session['open_time']
            if open_duration.total_seconds() > 24 * 3600:
                self.status_card.setStyleSheet(f"QGroupBox {{ border: 2px solid {ModernTheme.WARNING}; }}")
            else:
                self.status_card.setStyleSheet("")

            expected_cash_str = self.summary_expected_cash.text().replace("R$", "").strip()
            expected_cash = parse_currency(expected_cash_str)
            if expected_cash > 1000:
                self.summary_expected_cash.setStyleSheet(f"color: {ModernTheme.ERROR}; font-weight: bold;")
            else:
                self.summary_expected_cash.setStyleSheet("")
        except (InvalidOperation, TypeError): # TypeError para open_time que pode ser string
            pass

    def send_whatsapp_notification(self, action):
        """Envia notificação via WhatsApp para abertura ou fechamento de caixa."""
        try:
            # Verificar se as notificações estão habilitadas
            whatsapp_enabled = db.load_setting('whatsapp_notifications_enabled', 'false')
            if whatsapp_enabled.lower() != 'true':
                return

            # Obter número do telefone
            phone_number = db.load_setting('whatsapp_notification_number', '')
            if not phone_number:
                logging.warning("WhatsApp: Notificações habilitadas mas número não configurado")
                return

            # Obter dados da sessão atual
            current_session = db.get_current_cash_session()
            if not current_session:
                logging.warning("WhatsApp: Sessão de caixa não encontrada")
                return

            # Criar mensagem baseada na ação
            if action == 'open':
                message = f"""✅ *CAIXA ABERTO*

📅 Data/Hora: {current_session['open_time'].strftime('%d/%m/%Y %H:%M')}
👤 Operador: {current_session['username']}
💰 Saldo Inicial: R$ {current_session['initial_amount']:.2f}
🆔 Sessão: #{current_session['id']}

Caixa aberto com sucesso no sistema PDV."""

            elif action == 'close':
                # Obter relatório da sessão para dados de fechamento
                report = db.get_cash_session_report(current_session['id'])
                if not report or not report['session']:
                    logging.warning("WhatsApp: Relatório da sessão não encontrado")
                    return

                session_data = report['session']
                sales_summary = report['sales']
                total_sales = sum(Decimal(s['total']) for s in sales_summary)

                # Calcular totais por forma de pagamento
                payment_totals = {}
                for sale in sales_summary:
                    method = sale['payment_method']
                    total = Decimal(sale['total'])
                    payment_totals[method] = payment_totals.get(method, Decimal('0')) + total

                # Construir detalhamento das vendas
                sales_breakdown = ""
                if payment_totals:
                    sales_breakdown = "\n\n💰 *DETALHAMENTO DAS VENDAS:*"
                    # Mapeamento de ícones para formas de pagamento
                    payment_icons = {
                        'Dinheiro': '💵',
                        'PIX': '📱',
                        'Débito': '💳',
                        'Crédito': '💳',
                    }

                    for method, total in payment_totals.items():
                        icon = payment_icons.get(method, '💰')
                        sales_breakdown += f"\n{icon} {method}: R$ {total:.2f}"

                # Construir mensagem com detalhamento completo
                message = f"""❌ *CAIXA FECHADO*

📅 Data/Hora: {session_data['close_time'].strftime('%d/%m/%Y %H:%M')}
👤 Operador: {session_data['username']}
💰 Saldo Inicial: R$ {session_data['initial_amount']:.2f}
💰 Total de Vendas: R$ {total_sales:.2f}
💰 Valor Contado: R$ {session_data['final_amount']:.2f}"""

                if session_data['difference'] != 0:
                    diff_symbol = "+" if session_data['difference'] > 0 else ""
                    message += f"\n⚠️ Diferença: {diff_symbol}R$ {session_data['difference']:.2f}"

                message += f"{sales_breakdown}\n🆔 Sessão: #{session_data['id']}\n\nCaixa fechado com sucesso no sistema PDV."

            else:
                logging.warning(f"WhatsApp: Ação desconhecida: {action}")
                return

            # Enviar notificação usando o novo WhatsAppManager
            manager = WhatsAppManager()
            success = manager.send_message(phone_number, message)

            if success:
                logging.info(f"WhatsApp: Notificação de {action} enviada para {phone_number}")
            else:
                logging.warning(f"WhatsApp: Falha ao enviar notificação de {action} para {phone_number}")

        except Exception as e:
            logging.error(f"WhatsApp: Erro ao enviar notificação - {str(e)}", exc_info=True)

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)
