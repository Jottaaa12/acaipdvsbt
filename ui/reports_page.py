from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout, QDateEdit, QTabWidget,
    QFileDialog, QMessageBox, QDialog, QTextEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
import database as db
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from utils import format_currency
from .worker import Worker

class ReportsPage(QWidget):
    """Página para visualização de relatórios."""

    def __init__(self):
        super().__init__()
        self.current_report_data = None  # Armazena os dados do último relatório gerado
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título
        title_label = QLabel("Central de Relatórios")
        title_label.setObjectName("title")
        main_layout.addWidget(title_label)

        # Abas para cada tipo de relatório
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Cria as abas
        sales_tab = self.create_sales_report_tab()
        stock_tab = self.create_stock_report_tab()
        cash_history_tab = self.create_cash_history_tab()

        tab_widget.addTab(sales_tab, "Vendas")
        tab_widget.addTab(stock_tab, "Estoque")
        tab_widget.addTab(cash_history_tab, "Histórico de Caixa")

        # Conecta o sinal de mudança de aba
        tab_widget.currentChanged.connect(self.on_tab_changed)

        # Gera o relatório de vendas inicial (após todos os widgets serem criados)
        # Usamos QTimer.singleShot para garantir que tudo esteja inicializado
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.generate_initial_report)

    def on_tab_changed(self, index):
        """Chamado quando o usuário muda de aba."""
        # 0: Vendas, 1: Estoque, 2: Histórico de Caixa
        if index == 2: # Aba de Histórico de Caixa
            self.generate_cash_history_report()

    def create_sales_report_tab(self):
        """Cria a aba de relatório de vendas."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Filtros
        filter_group = QGroupBox("Filtrar Período")
        filter_layout = QHBoxLayout(filter_group)

        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setDate(QDate.currentDate())
        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.setDate(QDate.currentDate())

        today_button = QPushButton("Hoje")
        week_button = QPushButton("Esta Semana")
        month_button = QPushButton("Este Mês")
        generate_button = QPushButton("Gerar Relatório")
        generate_button.setObjectName("modern_button_primary")
        
        export_button = QPushButton("Exportar para CSV")
        export_button.clicked.connect(self.export_report_to_csv)


        filter_layout.addWidget(QLabel("De:"))
        filter_layout.addWidget(self.start_date_edit)
        filter_layout.addWidget(QLabel("Até:"))
        filter_layout.addWidget(self.end_date_edit)
        filter_layout.addStretch()
        filter_layout.addWidget(today_button)
        filter_layout.addWidget(week_button)
        filter_layout.addWidget(month_button)
        filter_layout.addWidget(generate_button)
        filter_layout.addWidget(export_button)
        layout.addWidget(filter_group)

        # Conexões dos botões de filtro
        today_button.clicked.connect(self.set_date_today)
        week_button.clicked.connect(self.set_date_this_week)
        month_button.clicked.connect(self.set_date_this_month)
        generate_button.clicked.connect(self.generate_sales_report)

        # Área de Resumo
        summary_group = QGroupBox("Resumo do Período")
        summary_layout = QGridLayout(summary_group)
        self.total_revenue_label = QLabel("R$ 0,00")
        self.total_sales_label = QLabel("0")
        self.avg_ticket_label = QLabel("R$ 0,00")
        summary_layout.addWidget(QLabel("Faturamento Total:"), 0, 0)
        summary_layout.addWidget(self.total_revenue_label, 0, 1)
        summary_layout.addWidget(QLabel("Total de Vendas:"), 1, 0)
        summary_layout.addWidget(self.total_sales_label, 1, 1)
        summary_layout.addWidget(QLabel("Ticket Médio:"), 2, 0)
        summary_layout.addWidget(self.avg_ticket_label, 2, 1)
        layout.addWidget(summary_group)

        # Tabelas de detalhes
        details_layout = QHBoxLayout()
        
        # Tabela de formas de pagamento
        payment_group = QGroupBox("Vendas por Forma de Pagamento")
        payment_layout = QVBoxLayout(payment_group)
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(4)
        self.payment_table.setHorizontalHeaderLabels(["Forma de Pagamento", "Nº de Vendas", "Valor Total", "% do Faturamento"])
        self.payment_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        payment_layout.addWidget(self.payment_table)
        details_layout.addWidget(payment_group)

        # Tabela de produtos mais vendidos
        products_group = QGroupBox("Produtos Mais Vendidos")
        products_layout = QVBoxLayout(products_group)
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(3)
        self.products_table.setHorizontalHeaderLabels(["Produto", "Quantidade Vendida", "Faturamento"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        products_layout.addWidget(self.products_table)
        details_layout.addWidget(products_group)

        layout.addLayout(details_layout)

        return widget

    def create_stock_report_tab(self):
        """Cria a aba de relatório de estoque."""
        widget = QWidget()
        # Placeholder - a ser implementado
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Relatório de Estoque - Em breve"))
        return widget

    def create_cash_history_tab(self):
        """Cria a aba de histórico de caixa."""
        widget = QWidget()
        self.cash_history_tab = widget  # Armazena referência para encontrar botões
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Ações
        actions_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self.generate_cash_history_report)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # Tabela de histórico
        self.cash_history_table = QTableWidget()
        self.cash_history_table.setColumnCount(9)
        self.cash_history_table.setHorizontalHeaderLabels([
            "ID", "Abertura", "Fechamento", "Valor Inicial",
            "Valor Esperado", "Valor Contado", "Diferença", "Usuário", "Detalhes"
        ])
        self.cash_history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cash_history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.cash_history_table)

        return widget

    # --- Funções de Lógica para Relatório de Vendas ---

    def generate_cash_history_report(self):
        """Gera e exibe o relatório de histórico de caixa de forma assíncrona."""
        # Desabilita o botão durante a geração
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Carregando...")

        # Cria worker para executar o relatório em background
        worker = Worker(db.get_cash_session_history)
        worker.signals.finished.connect(self.on_cash_history_report_ready)
        worker.signals.error.connect(self.on_report_error)
        worker.signals.finished.connect(self.on_cash_history_report_finished)

        # Inicia o worker
        from PyQt6.QtCore import QThreadPool
        threadpool = QThreadPool.globalInstance()
        threadpool.start(worker)

    def on_cash_history_report_ready(self, history_data):
        """Slot chamado quando o relatório de histórico de caixa está pronto."""
        self.cash_history_table.setRowCount(0)
        for row, item in enumerate(history_data):
            self.cash_history_table.insertRow(row)

            # Formata a diferença com cor
            difference = item['difference']
            diff_item = QTableWidgetItem(f"R$ {difference:.2f}")
            if difference > 0:
                diff_item.setForeground(Qt.GlobalColor.darkGreen)
            elif difference < 0:
                diff_item.setForeground(Qt.GlobalColor.red)

            # Formata datas para string
            open_time_str = item['open_time'].strftime('%d/%m/%Y %H:%M:%S') if item['open_time'] else ''
            close_time_str = item['close_time'].strftime('%d/%m/%Y %H:%M:%S') if item['close_time'] else 'Em aberto'

            self.cash_history_table.setItem(row, 0, QTableWidgetItem(str(item['id'])))
            self.cash_history_table.setItem(row, 1, QTableWidgetItem(open_time_str))
            self.cash_history_table.setItem(row, 2, QTableWidgetItem(close_time_str))
            self.cash_history_table.setItem(row, 3, QTableWidgetItem(format_currency(item['initial_amount'])))
            self.cash_history_table.setItem(row, 4, QTableWidgetItem(f"R$ {item['expected_amount']:.2f}"))
            self.cash_history_table.setItem(row, 5, QTableWidgetItem(f"R$ {item['final_amount']:.2f}"))
            self.cash_history_table.setItem(row, 6, diff_item)
            self.cash_history_table.setItem(row, 7, QTableWidgetItem(item['user_opened']))

            # Botão de detalhes
            details_button = QPushButton("Ver Detalhes")
            details_button.clicked.connect(lambda _, sid=item['id']: self.show_session_details(sid))
            self.cash_history_table.setCellWidget(row, 8, details_button)

    def on_cash_history_report_finished(self):
        """Slot chamado quando o worker de histórico de caixa termina."""
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Atualizar")

    def show_session_details(self, session_id):
        """Busca e exibe o relatório detalhado de uma sessão de caixa."""
        worker = Worker(db.get_cash_session_report, session_id)
        worker.signals.finished.connect(self.on_detail_report_ready)
        worker.signals.error.connect(self.on_report_error)
        from PyQt6.QtCore import QThreadPool
        threadpool = QThreadPool.globalInstance()
        threadpool.start(worker)

    def on_detail_report_ready(self, report_data):
        """Exibe o diálogo com o relatório detalhado da sessão."""
        if not report_data or not report_data.get('session'):
            QMessageBox.warning(self, "Erro", "Não foi possível gerar o relatório detalhado para esta sessão.")
            return

        report_text = self._generate_session_report_text(report_data)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Detalhes da Sessão de Caixa #{report_data['session']['id']}")
        dialog.setMinimumSize(600, 700)

        layout = QVBoxLayout(dialog)
        
        report_display = QTextEdit()
        report_display.setReadOnly(True)
        report_display.setFont(QFont("Courier New", 10))
        report_display.setText(report_text)
        
        layout.addWidget(report_display)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def _generate_session_report_text(self, report_data):
        """Gera o texto formatado para o relatório de uma sessão."""
        s_info = report_data['session']
        sales_summary = report_data['sales']
        movements = report_data['movements']

        cash_sales = sum(Decimal(s['total']) for s in sales_summary if s['payment_method'] == 'Dinheiro')
        supplies = sum(Decimal(m['amount']) for m in movements if m['type'] == 'suprimento')
        withdrawals = sum(Decimal(m['amount']) for m in movements if m['type'] == 'sangria')

        header = "RELATÓRIO DE FECHAMENTO DE CAIXA".center(50, '=')
        session_details = (
            f"Sessão ID: {s_info['id']}\n"
            f"Operador:  {s_info['username']}\n"
            f"Abertura:  {s_info['open_time'].strftime('%d/%m/%Y %H:%M')}\n"
            f"Fechamento:{s_info['close_time'].strftime('%d/%m/%Y %H:%M') if s_info['close_time'] else 'EM ABERTO'}\n"
        )
        
        summary_header = "RESUMO FINANCEIRO (CAIXA FÍSICO)".center(50, '-')
        summary_lines = (
            f"(+) Fundo de Troco:           {format_currency(s_info['initial_amount']).rjust(15)}\n"
            f"(+) Vendas em Dinheiro:       {format_currency(cash_sales).rjust(15)}\n"
            f"(+) Suprimentos:              {format_currency(supplies).rjust(15)}\n"
            f"(-) Sangrias:                 {format_currency(withdrawals, is_negative=True).rjust(15)}\n"
            f"{'='*50}\n"
            f"(=) SALDO ESPERADO:           {format_currency(s_info['expected_amount']).rjust(15)}\n"
            f"    SALDO CONTADO:            {format_currency(s_info['final_amount']).rjust(15)}\n"
            f"{'='*50}\n"
            f"(=) DIFERENÇA:                {format_currency(s_info['difference'], is_negative=(s_info['difference'] < 0)).rjust(15)}\n"
        )

        other_sales_header = "VENDAS (OUTRAS FORMAS)".center(50, '-')
        other_sales_lines = ""
        other_sales_summary = [s for s in sales_summary if s['payment_method'] != 'Dinheiro']
        if other_sales_summary:
            for item in other_sales_summary:
                other_sales_lines += f"{item['payment_method'].ljust(25)} {format_currency(item['total']).rjust(24)}\n"
        else:
            other_sales_lines = "Nenhuma venda em outras formas de pagamento.\n"

        grand_total_header = "TOTAIS GERAIS".center(50, '-')
        grand_total_lines = (
            f"Faturamento Bruto (Todas Formas): {format_currency(report_data['total_revenue']).rjust(15)}\n"
            f"Faturamento - Sangrias:         {format_currency(report_data['total_after_sangria']).rjust(15)}\n"
        )

        obs_header = "OBSERVAÇÕES".center(50, '-')
        obs_text = s_info['observations'] if s_info.get('observations') else "Nenhuma observação."

        return (
            f"{header}\n"
            f"{session_details}\n"
            f"{summary_header}\n"
            f"{summary_lines}"
            f"{other_sales_header}\n"
            f"{other_sales_lines}\n"
            f"{grand_total_header}\n"
            f"{grand_total_lines}\n"
            f"{obs_header}\n"
            f"{obs_text}\n"
            f"{'='*50}\n"
        )

    def set_date_today(self):
        today = QDate.currentDate()
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)

    def set_date_this_week(self):
        today = QDate.currentDate()
        start_of_week = today.addDays(-today.dayOfWeek() + 1)
        self.start_date_edit.setDate(start_of_week)
        self.end_date_edit.setDate(today)

    def set_date_this_month(self):
        today = QDate.currentDate()
        start_of_month = QDate(today.year(), today.month(), 1)
        self.start_date_edit.setDate(start_of_month)
        self.end_date_edit.setDate(today)

    def generate_initial_report(self):
        """Gera o relatório inicial sem interferir com os botões."""
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        # Cria worker para executar o relatório em background
        worker = Worker(db.get_sales_report, start_date, end_date)
        worker.signals.finished.connect(self.on_sales_report_ready)
        worker.signals.error.connect(self.on_report_error)
        worker.signals.finished.connect(self.on_report_finished)

        # Inicia o worker
        from PyQt6.QtCore import QThreadPool
        threadpool = QThreadPool.globalInstance()
        threadpool.start(worker)

    def generate_sales_report(self):
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        # Verifica se o botão existe antes de tentar acessá-lo
        if hasattr(self, 'generate_button') and self.generate_button:
            # Desabilita o botão durante a geração
            self.generate_button.setEnabled(False)
            self.generate_button.setText("Gerando...")

        # Cria worker para executar o relatório em background
        worker = Worker(db.get_sales_report, start_date, end_date)
        worker.signals.finished.connect(self.on_sales_report_ready)
        worker.signals.error.connect(self.on_report_error)
        worker.signals.finished.connect(self.on_report_finished)

        # Inicia o worker
        from PyQt6.QtCore import QThreadPool
        threadpool = QThreadPool.globalInstance()
        threadpool.start(worker)

    def on_sales_report_ready(self, report_data):
        """Slot chamado quando o relatório de vendas está pronto."""
        self.current_report_data = report_data

        # Atualiza resumo
        total_revenue = report_data['total_revenue']
        self.total_revenue_label.setText(format_currency(total_revenue))
        self.total_sales_label.setText(str(report_data['total_sales_count']))
        self.avg_ticket_label.setText(format_currency(report_data['average_ticket']))

        # Atualiza tabela de formas de pagamento
        self.payment_table.setRowCount(0)
        for row, item in enumerate(report_data['payment_methods']):
            self.payment_table.insertRow(row)

            percentage = (item['total'] / total_revenue * 100) if total_revenue > 0 else 0

            self.payment_table.setItem(row, 0, QTableWidgetItem(item['payment_method']))
            self.payment_table.setItem(row, 1, QTableWidgetItem(str(item['count'])))
            self.payment_table.setItem(row, 2, QTableWidgetItem(f"R$ {item['total']:.2f}"))
            self.payment_table.setItem(row, 3, QTableWidgetItem(f"{percentage:.1f}%"))

        # Adiciona linha de totais
        total_row = self.payment_table.rowCount()
        self.payment_table.insertRow(total_row)
        bold_font = QFont()
        bold_font.setBold(True)

        total_label_item = QTableWidgetItem("TOTAL")
        total_label_item.setFont(bold_font)

        total_sales_item = QTableWidgetItem(str(report_data['total_sales_count']))
        total_sales_item.setFont(bold_font)

        total_revenue_item = QTableWidgetItem(f"R$ {total_revenue:.2f}")
        total_revenue_item.setFont(bold_font)

        total_percent_item = QTableWidgetItem("100.0%")
        total_percent_item.setFont(bold_font)

        self.payment_table.setItem(total_row, 0, total_label_item)
        self.payment_table.setItem(total_row, 1, total_sales_item)
        self.payment_table.setItem(total_row, 2, total_revenue_item)
        self.payment_table.setItem(total_row, 3, total_percent_item)

        # Atualiza tabela de produtos
        self.products_table.setRowCount(0)
        for row, item in enumerate(report_data['top_products']):
            self.products_table.insertRow(row)
            self.products_table.setItem(row, 0, QTableWidgetItem(item['description']))
            self.products_table.setItem(row, 1, QTableWidgetItem(str(item['quantity_sold'])))
            self.products_table.setItem(row, 2, QTableWidgetItem(f"R$ {item['revenue']:.2f}"))

    def on_report_error(self, error_info):
        """Slot chamado quando há erro na geração do relatório."""
        error, traceback_str = error_info
        QMessageBox.critical(self, "Erro ao Gerar Relatório",
                           f"Ocorreu um erro ao gerar o relatório:\n{error}")

    def on_report_finished(self):
        """Slot chamado quando o worker termina (sucesso ou erro)."""
        # Reabilita o botão se ele existir
        if hasattr(self, 'generate_button') and self.generate_button:
            self.generate_button.setEnabled(True)
            self.generate_button.setText("Gerar Relatório")

    def export_report_to_csv(self):
        if not self.current_report_data:
            QMessageBox.warning(self, "Atenção", "Nenhum relatório foi gerado. Por favor, gere um relatório primeiro.")
            return

        default_filename = f"relatorio_vendas_{self.start_date_edit.date().toString('yyyy-MM-dd')}_a_{self.end_date_edit.date().toString('yyyy-MM-dd')}.csv"
        
        fileName, _ = QFileDialog.getSaveFileName(self, "Exportar Relatório para CSV", default_filename, "Arquivos CSV (*.csv);;Todos os Arquivos (*)")

        if fileName:
            try:
                with open(fileName, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)

                    # Escreve o resumo
                    writer.writerow(["Resumo do Periodo", ""])
                    writer.writerow(["Faturamento Total", f"R$ {self.current_report_data['total_revenue']:.2f}"])
                    writer.writerow(["Total de Vendas", self.current_report_data['total_sales_count']])
                    writer.writerow(["Ticket Medio", f"R$ {self.current_report_data['average_ticket']:.2f}"])
                    writer.writerow([])  # Linha em branco

                    # Escreve os detalhes por forma de pagamento
                    writer.writerow(["Vendas por Forma de Pagamento", "N de Vendas", "Valor Total", "% do Faturamento"])
                    total_revenue = self.current_report_data['total_revenue']
                    for item in self.current_report_data['payment_methods']:
                        percentage = (item['total'] / total_revenue * 100) if total_revenue > 0 else 0
                        writer.writerow([
                            item['payment_method'],
                            item['count'],
                            f"R$ {item['total']:.2f}",
                            f"{percentage:.1f}%"
                        ])
                    writer.writerow([])  # Linha em branco

                    # Escreve os detalhes dos produtos mais vendidos
                    writer.writerow(["Produtos Mais Vendidos", "Quantidade Vendida", "Faturamento"])
                    for item in self.current_report_data['top_products']:
                        writer.writerow([
                            item['description'],
                            item['quantity_sold'],
                            f"R$ {item['revenue']:.2f}"
                        ])
                
                QMessageBox.information(self, "Sucesso", f"""Relatório exportado com sucesso para:
{fileName}""")

            except Exception as e:
                QMessageBox.critical(self, "Erro ao Exportar", f"""Ocorreu um erro ao salvar o arquivo CSV:
{e}""")
