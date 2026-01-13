from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QGridLayout, QGroupBox, QInputDialog, QSpacerItem, QSizePolicy, QAbstractItemView,
    QDialogButtonBox
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QThreadPool
import json
import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import database as db
from data.product_repository import ensure_manual_product_exists
from data.credit_repository import associate_sale_to_credit, create_credit_sale
from hardware.scale_handler import ScaleHandler
from hardware.printer_handler import PrinterHandler
from ui.payment_dialog import PaymentDialog
from ui.success_dialog import SuccessDialog
from ui.credit_dialog import CreditDialog
from ui.product_search_dialog import ProductSearchDialog
from ui.held_sales_dialog import HeldSalesDialog
from ui.receipt_preview_dialog import ReceiptPreviewDialog
from ui.theme import ModernTheme
from ui.worker import Worker
from utils import get_data_path
import logging
from data.audit_repository import log_audit

from ui.message_dialog import MessageDialog
from ui.custom_input_dialog import CustomInputDialog

class SalesPage(QWidget):
    def __init__(self, main_window, scale_handler, printer_handler):
        super().__init__()
        
        self.main_window = main_window
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler
        self.current_sale_items = []
        self.current_sale_customer_name = None # Rastreia o cliente da venda atual
        self.last_known_weight = 0.0
        self.scale_error_count = 0
        self.threadpool = QThreadPool() # Adicionado para tarefas em segundo plano
        
        # Estrutura para Vendas em Espera (Comandas)
        self.held_sales = {}
        
        # Conectar ao sinal de atualização de peso da balança
        self.scale_handler.weight_updated.connect(self._on_weight_updated)
        self.scale_handler.error_occurred.connect(self._on_scale_error)

        # Listas para rastrear conexões que precisam ser desconectadas
        self._signal_connections = []

        self.setup_ui()

    def _on_weight_updated(self, weight):
        """Slot para receber o peso da balança e atualizar a UI."""
        self.scale_error_count = 0
        self.last_known_weight = weight
        if weight > 0:
            self.weight_label.setText(f"{weight:.3f} kg")
        else:
            self.weight_label.setText("0.000 kg")
        
        if hasattr(self, 'reconnect_scale_button'):
            self.reconnect_scale_button.setVisible(False)
            self.get_weight_button.setVisible(True)

    def _on_scale_error(self, error_message):
        """Slot para receber erros da balança."""
        self.last_known_weight = 0.0
        self.weight_label.setText("Erro kg")
        logging.warning(f"SalesPage Scale Error: {error_message}")

        if hasattr(self, 'reconnect_scale_button'):
            self.reconnect_scale_button.setVisible(True)
            self.get_weight_button.setVisible(False)

        self.scale_error_count += 1

        # Exibe o aviso apenas se houver uma sessão de caixa aberta (em atendimento) e após 10 tentativas
        if self.main_window and self.main_window.current_cash_session and self.scale_error_count >= 10:
            QMessageBox.warning(self, "Problema com a Balança", 
                "A balança pode estar desligada ou desconectada.\n\n" 
                "Por favor, verifique a conexão e tente novamente.\n" 
                "O sistema continuará tentando se reconectar.")
            self.scale_error_count = 0 # Reseta o contador para evitar spam de mensagens

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5) # Margem geral reduzida
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Painel Esquerdo
        left_layout = QVBoxLayout()
        product_input_layout = QHBoxLayout()
        product_code_label = QLabel("Código do Produto:")
        self.product_code_input = QLineEdit(placeholderText="Leia o código de barras ou digite aqui")
        self.product_code_input.setObjectName("modern_input")
        self.search_product_button = QPushButton("Buscar (F5)")
        self.search_product_button.setObjectName("modern_button_secondary")
        product_input_layout.addWidget(product_code_label)
        product_input_layout.addWidget(self.product_code_input, 1) # Dar mais espaço ao input
        product_input_layout.addWidget(self.search_product_button)
        left_layout.addLayout(product_input_layout)
        
        self.sale_items_table = QTableWidget()
        self.sale_items_table.setColumnCount(5)
        self.sale_items_table.setHorizontalHeaderLabels(["Cód.", "Descrição", "Qtd/Peso", "Vl. Unit.", "Vl. Total"])
        self.sale_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sale_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sale_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Permitir edição da quantidade com duplo clique
        self.sale_items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Desabilitar edição padrão
        self.sale_items_table.doubleClicked.connect(self.edit_item_quantity)
        left_layout.addWidget(self.sale_items_table)

        self.remove_item_button = QPushButton("Remover Item Selecionado")
        self.remove_item_button.setObjectName("modern_button_error")
        self.remove_item_button.setEnabled(False)
        left_layout.addWidget(self.remove_item_button)
        top_layout.addLayout(left_layout, 7)
        
        # Painel Direito
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)

        store_name_label = QLabel(self.load_store_config().get('name', 'PDV'))
        store_name_label.setFont(QFont("Arial", 18, QFont.Weight.Bold)) # Fonte reduzida
        right_layout.addWidget(store_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Label para vendas em espera
        self.held_sales_label = QLabel("Vendas em espera: 0")
        self.held_sales_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.held_sales_label)

        total_panel_layout = QVBoxLayout()
        total_panel_layout.setContentsMargins(0, 0, 0, 0) # Margens Zero
        total_panel_layout.setSpacing(0)
        
        value_font = QFont("Arial", 28, QFont.Weight.Bold) # Fonte reduzida (era padrão grande no CSS provavelmente)
        self.total_label = QLabel("R$ 0,00")
        self.total_label.setObjectName("total_label")
        self.total_label.setFont(value_font) 
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(QLabel("TOTAL"), alignment=Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(self.total_label)
        right_layout.addLayout(total_panel_layout)

        sale_info_group = QGroupBox("Informações da Venda")
        sale_info_layout = QGridLayout(sale_info_group)
        sale_info_layout.setContentsMargins(5, 5, 5, 5) # Margens compactas
        sale_info_layout.setVerticalSpacing(2)
        self.sale_name_label = QLabel("Nome da Venda: Não identificado")
        self.sale_name_label.setObjectName("sale_name_label")
        self.weight_label = QLabel("0.000 kg")
        self.items_count_label = QLabel("0")
        self.get_weight_button = QPushButton("Calcular Peso da Balança")
        self.get_weight_button.setObjectName("modern_button_secondary")
        self.get_weight_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

        self.reconnect_scale_button = QPushButton("Reconectar Balança")
        self.reconnect_scale_button.setToolTip("Tentar reconectar com a balança")
        self.reconnect_scale_button.setObjectName("modern_button_error")
        self.reconnect_scale_button.setVisible(False)
        self.reconnect_scale_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

        sale_info_layout.addWidget(self.sale_name_label, 0, 0, 1, 2)
        sale_info_layout.addWidget(QLabel("Peso da Balança:"), 1, 0)
        sale_info_layout.addWidget(self.weight_label, 1, 1)
        sale_info_layout.addWidget(QLabel("Quantidade de Itens:"), 2, 0)
        sale_info_layout.addWidget(self.items_count_label, 2, 1)
        sale_info_layout.addWidget(self.get_weight_button, 3, 0, 1, 3)
        sale_info_layout.addWidget(self.reconnect_scale_button, 3, 0, 1, 3)
        right_layout.addWidget(sale_info_group)

        right_layout.addStretch()
        
        # Botões de ação com Comandas
        self.finish_sale_button = QPushButton("F1 - FINALIZAR VENDA")
        self.finish_sale_button.setObjectName("modern_button_primary")
        self.finish_sale_button.setMinimumHeight(50)
        self.cancel_sale_button = QPushButton("F2 - CANCELAR VENDA")
        self.cancel_sale_button.setObjectName("modern_button_outline")
        self.cancel_sale_button.setMinimumHeight(50)
        self.identify_sale_button = QPushButton("Identificar Venda (F6)")
        self.identify_sale_button.setObjectName("modern_button_secondary")
        self.identify_sale_button.setMinimumHeight(50)
        self.hold_sale_button = QPushButton("Salvar Venda (F3)")
        self.hold_sale_button.setObjectName("modern_button_secondary")
        self.hold_sale_button.setMinimumHeight(50)
        self.resume_sale_button = QPushButton("Recuperar Venda (F4)")
        self.resume_sale_button.setObjectName("modern_button_secondary")
        self.resume_sale_button.setMinimumHeight(50)

        right_layout.addWidget(self.finish_sale_button)
        right_layout.addWidget(self.cancel_sale_button)
        right_layout.addWidget(self.identify_sale_button)
        right_layout.addWidget(self.hold_sale_button)
        right_layout.addWidget(self.resume_sale_button)
        top_layout.addLayout(right_layout, 3)

        # Painel Inferior (Atalhos)
        shortcuts_group = QGroupBox("Atalhos Rápidos")
        shortcuts_main_layout = QHBoxLayout(shortcuts_group)
        shortcuts_main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(shortcuts_group)

        self.dynamic_shortcuts_layout = QHBoxLayout()
        shortcuts_main_layout.addLayout(self.dynamic_shortcuts_layout)
        shortcuts_main_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        self.quick_kg_sale_button = QPushButton("Venda por KG")
        self.quick_kg_sale_button.setObjectName("modern_button_primary")
        self.quick_kg_sale_button.setMinimumHeight(50)
        shortcuts_main_layout.addWidget(self.quick_kg_sale_button)

        self.manual_value_button = QPushButton("Adicionar Valor Manual")
        self.manual_value_button.setObjectName("modern_button_primary")
        self.manual_value_button.setMinimumHeight(50)
        shortcuts_main_layout.addWidget(self.manual_value_button)

        self.toggle_print_button = QPushButton("🖨️")
        self.toggle_print_button.setToolTip("Ativar/Desativar Impressão de Recibo")
        self.toggle_print_button.setCheckable(True)
        self.toggle_print_button.setObjectName("modern_button_outline")
        self.toggle_print_button.setMinimumHeight(50)
        self.toggle_print_button.setFixedWidth(60)
        shortcuts_main_layout.addWidget(self.toggle_print_button)

        self.price_config_button = QPushButton("⚙️")
        self.price_config_button.setObjectName("modern_button_outline")
        self.price_config_button.setMinimumHeight(50)
        self.price_config_button.setFixedWidth(60)
        shortcuts_main_layout.addWidget(self.price_config_button)

        self.reload_shortcuts()
        self.load_print_config()
        
        # Conexões
        self.search_product_button.clicked.connect(self.open_product_search_dialog)
        self.finish_sale_button.clicked.connect(self.open_payment_dialog)
        self.cancel_sale_button.clicked.connect(self.cancel_sale)
        self.get_weight_button.clicked.connect(self.get_weight_from_scale)
        self.quick_kg_sale_button.clicked.connect(self.quick_kg_sale)
        self.manual_value_button.clicked.connect(self.manual_value_sale)
        self.price_config_button.clicked.connect(self.open_price_config_dialog)
        self.sale_items_table.itemSelectionChanged.connect(self.update_remove_button_state)
        self.remove_item_button.clicked.connect(self.remove_selected_item)
        self.toggle_print_button.clicked.connect(self.on_toggle_print_button_clicked)
        self.identify_sale_button.clicked.connect(self.identify_sale)
        self.hold_sale_button.clicked.connect(self.hold_current_sale)
        self.resume_sale_button.clicked.connect(self.resume_held_sale)
        self.reconnect_scale_button.clicked.connect(self.force_scale_reconnect)

        # --- CORREÇÃO E ADIÇÃO DE ATALHOS GLOBAIS ---
        QShortcut(QKeySequence("F1"), self).activated.connect(self.open_payment_dialog)
        QShortcut(QKeySequence("F2"), self).activated.connect(self.cancel_sale)
        QShortcut(QKeySequence("F3"), self).activated.connect(self.hold_current_sale)
        QShortcut(QKeySequence("F4"), self).activated.connect(self.resume_held_sale)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.open_product_search_dialog)
        QShortcut(QKeySequence("F6"), self).activated.connect(self.identify_sale)
        # Atalho global para a tecla Enter
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self.handle_enter_pressed)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(self.handle_enter_pressed)

        # Atalho para deletar item da venda
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(self.remove_selected_item)

    # --- Funções de Busca de Produto ---
    def open_product_search_dialog(self):
        dialog = ProductSearchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            barcode = dialog.get_selected_barcode()
            if barcode:
                self.product_code_input.setText(barcode)
                self.add_product_to_sale()

    # --- Funções de Impressão ---
    def load_print_config(self):
        config_path = get_data_path('config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            should_print = config.get('printer', {}).get('auto_print_receipt', True)
            self.toggle_print_button.setChecked(should_print)
        except (FileNotFoundError, json.JSONDecodeError):
            self.toggle_print_button.setChecked(True)
        self.update_print_button_style()

    def update_print_button_style(self):
        if self.toggle_print_button.isChecked():
            self.toggle_print_button.setText("🖨️ ON")
            self.toggle_print_button.setStyleSheet("background-color: #28a745; color: white;")
        else:
            self.toggle_print_button.setText("🖨️ OFF")
            self.toggle_print_button.setStyleSheet("")

    def on_toggle_print_button_clicked(self):
        config_path = get_data_path('config.json')
        config = {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        if 'printer' not in config:
            config['printer'] = {}
        config['printer']['auto_print_receipt'] = self.toggle_print_button.isChecked()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Erro ao Salvar", f"Não foi possível salvar a configuração de impressão.\nErro: {e}")
        self.update_print_button_style()

    # --- Funções de Venda e Itens ---
    def handle_enter_pressed(self):
        """Decide a ação com base no conteúdo do campo de código de produto."""
        if not self.product_code_input.text().strip():
            # Se o campo estiver vazio, verifica se há peso na balança
            if self.last_known_weight > 0:
                self.quick_kg_sale() # Usa o peso da balança
            else:
                self.manual_value_sale() # Balança zerada ou off -> Valor Manual (R$)
        else:
            # Caso contrário, adiciona o produto pelo código
            self.add_product_to_sale()

    def reload_shortcuts(self):
        while self.dynamic_shortcuts_layout.count():
            child = self.dynamic_shortcuts_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        shortcuts = self.load_shortcuts_config()
        for shortcut in shortcuts:
            button = QPushButton(shortcut["name"])
            button.setObjectName("modern_button_secondary")
            button.setMinimumHeight(50)
            button.clicked.connect(lambda checked, b=shortcut["barcode"]: self.on_shortcut_button_clicked(b))
            self.dynamic_shortcuts_layout.addWidget(button)

    def get_weight_from_scale(self):
        self.add_product_to_sale()

    def add_product_to_sale(self, weight_from_scale=None):
        if not self.is_cash_session_open(): return
        barcode = self.product_code_input.text()
        if not barcode: return
        
        product_data = db.get_product_by_barcode(barcode)
        self.product_code_input.clear()
        if not product_data:
            QMessageBox.warning(self, "Produto não Encontrado", f"Produto com código '{barcode}' não encontrado.")
            return
        
        product_data['price'] = Decimal(str(product_data['price'])).quantize(Decimal('0.01'))

        quantity = Decimal('0')
        if product_data['sale_type'] == 'weight':
            # Prioriza o peso manual, se fornecido
            if weight_from_scale is not None:
                quantity = weight_from_scale
            else:
                quantity = Decimal(str(self.last_known_weight))

            if quantity <= 0:
                # Se o peso for inválido, abre o diálogo para entrada manual de texto
                weight_str, ok = CustomInputDialog.get_value(self, "Entrada Manual de Peso", "Digite o peso em KG (ex: 1,250):")
                if ok and weight_str:
                    try:
                        # Garante que tanto vírgula quanto ponto sejam aceitos
                        quantity = Decimal(weight_str.replace(",", "."))
                        if quantity <= 0:
                            QMessageBox.warning(self, "Peso Inválido", "O peso deve ser maior que zero.")
                            return
                    except InvalidOperation:
                        QMessageBox.warning(self, "Formato Inválido", "O peso digitado não é um número válido.")
                        return
                else:
                    # Se o usuário cancelar ou não digitar nada, não adiciona o produto
                    return
        else:
            quantity = Decimal('1')

        existing_item = next((i for i in self.current_sale_items if i['id'] == product_data['id'] and i['sale_type'] == 'unit'), None)
        
        if existing_item:
            existing_item['quantity'] += quantity
            existing_item['total_price'] = existing_item['quantity'] * existing_item['unit_price']
        else:
            self.current_sale_items.append({
                'id': product_data['id'], 'barcode': product_data['barcode'], 'description': product_data['description'], 
                'quantity': quantity, 'unit_price': product_data['price'], 'total_price': quantity * product_data['price'], 
                'sale_type': product_data['sale_type'],
                'peso_kg': quantity if product_data['sale_type'] == 'weight' else 0
            })
        self.update_sale_display()
        self.product_code_input.setFocus() # Foco automático no input

    def edit_item_quantity(self, model_index):
        row = model_index.row()
        item = self.current_sale_items[row]

        if item['sale_type'] == 'weight':
            QMessageBox.information(self, "Ação não permitida", "Não é possível alterar o peso de um item. Remova e adicione novamente.")
            return

        current_quantity = item['quantity']
        qty_str, ok = CustomInputDialog.get_value(self, "Alterar Quantidade", "Nova quantidade:", str(int(current_quantity)))

        if ok:
            try:
                new_quantity = int(qty_str)
                if new_quantity > 0:
                    item['quantity'] = Decimal(str(new_quantity))
                    item['total_price'] = item['quantity'] * item['unit_price']
                    self.update_sale_display()
            except ValueError:
                QMessageBox.warning(self, "Valor Inválido", "A quantidade deve ser um número inteiro.")

    def update_sale_display(self):
        self.sale_items_table.setRowCount(0)
        total_sale_amount = Decimal('0.00')
        total_items = Decimal('0')

        for row, item in enumerate(self.current_sale_items):
            self.sale_items_table.insertRow(row)
            self.sale_items_table.setItem(row, 0, QTableWidgetItem(item['barcode']))
            self.sale_items_table.setItem(row, 1, QTableWidgetItem(item['description']))
            
            if item['sale_type'] == 'weight':
                qty_str = f"{item['quantity']:.3f} kg"
                price_str = f"R$ {item['unit_price']:.2f}/kg"
                total_items += Decimal('1')
            else:
                qty_str = str(int(item['quantity']))
                price_str = f"R$ {item['unit_price']:.2f}"
                total_items += item['quantity']

            self.sale_items_table.setItem(row, 2, QTableWidgetItem(qty_str))
            self.sale_items_table.setItem(row, 3, QTableWidgetItem(price_str))
            self.sale_items_table.setItem(row, 4, QTableWidgetItem(f"R$ {item['total_price']:.2f}"))
            total_sale_amount += item['total_price']
        
        self.total_label.setText(f"R$ {total_sale_amount:.2f}")
        self.items_count_label.setText(str(int(total_items)))
        self.held_sales_label.setText(f"Vendas em espera: {len(self.held_sales)}")

        # Atualizar o nome da venda
        if self.current_sale_customer_name:
            self.sale_name_label.setText(f"Nome da Venda: {self.current_sale_customer_name}")
        else:
            self.sale_name_label.setText("Nome da Venda: Não identificado")

    def cancel_sale(self):
        if self.current_sale_items and MessageDialog.show_confirmation(self, "Confirmar", "Deseja cancelar a venda atual?"):
            self.current_sale_items.clear()
            self.current_sale_customer_name = None # Limpa o cliente
            self.update_sale_display()

    def open_payment_dialog(self):
        if not self.is_cash_session_open(): return
        if not self.current_sale_items: return
        
        total_amount = sum(item['total_price'] for item in self.current_sale_items)
        dialog = PaymentDialog(total_amount, self)
        # Connect the new signal
        dialog.credit_sale_requested.connect(lambda: self.handle_credit_sale_request(total_amount))

        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            result = dialog.result_data
            payments = result['payments']
            change_amount = result['change']
            discount_value = result.get('discount_value', 0.0)

            # FIX: Re-validar a sessão de caixa antes de registrar a venda
            current_session_id = self.main_window.current_cash_session["id"]
            if not db.get_cash_session_by_id(current_session_id):
                MessageDialog.show_error(self, "Erro de Sessão",
                                     "A sessão de caixa atual não é mais válida. Por favor, feche e abra o caixa novamente.")
                self.main_window.current_cash_session = None # Limpa a sessão inválida
                return

            # Envia a venda para o banco de dados, agora incluindo o nome do cliente e desconto
            sale_success, sale_data = db.register_sale_with_user(
                total_amount, payments, self.current_sale_items, change_amount,
                user_id=self.main_window.current_user["id"],
                cash_session_id=current_session_id,
                customer_name=self.current_sale_customer_name,
                discount_value=discount_value
            )

            if not sale_success:
                MessageDialog.show_error(self, "Erro ao Salvar Venda", f"A venda não foi registrada.\nErro: {sale_data.get('error', 'Desconhecido')}")
                return

            # Enviar notificação automática de venda via WhatsApp
            try:
                from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                sales_notifier = get_whatsapp_sales_notifier()
                # A função `notify_sale` espera `payment_details` e `change_amount` separadamente
                payment_details = sale_data.get('payments', [])
                change = sale_data.get('change_amount', 0.0)
                sales_notifier.notify_sale(sale_data, payment_details, float(change))
            except Exception as e:
                logging.warning(f"Erro ao enviar notificação de venda via WhatsApp: {e}")

            # Substituição pelo SuccessDialog
            SuccessDialog("Venda Registrada", "Venda registrada com sucesso!", self).exec()

            if self.toggle_print_button.isChecked():
                store_info = self.load_store_config()
                payment_method_str = ", ".join([f"{p['method']}: R$ {p['amount']:.2f}" for p in payments])
                receipt_details = {
                    'items': self.current_sale_items,
                    'total_amount': total_amount,
                    'payment_method': payment_method_str,
                    'change_amount': change_amount,
                    'discount_value': discount_value,
                    'customer_name': self.current_sale_customer_name
                }
                self.start_print_job(store_info, receipt_details)

            self.current_sale_items.clear()
            self.current_sale_customer_name = None # Limpa o cliente após a venda
            self.update_sale_display()

    def start_print_job(self, store_info, receipt_details):
        """Mostra o preview do recibo antes de imprimir."""
        try:
            # Mostra o diálogo de preview
            preview_dialog = ReceiptPreviewDialog(store_info, receipt_details, self.printer_handler, self)
            preview_dialog.exec()

        except Exception as e:
            logging.error(f"Erro ao mostrar preview do recibo: {e}")
            QMessageBox.critical(self, "Erro no Preview",
                               f"Ocorreu um erro ao mostrar o preview do recibo:\n\n{str(e)}")

    def handle_print_finished(self, result):
        """Lida com o resultado da impressão."""
        print_success, print_message = result
        if not print_success:
            QMessageBox.warning(self, "Erro na Impressão", f"A venda foi salva, mas houve um erro ao imprimir.\nErro: {print_message}")

    def handle_print_error(self, error):
        """Lida com erros inesperados na thread de impressão."""
        logging.error(f"Erro inesperado na thread de impressão: {error}")
        QMessageBox.critical(self, "Erro Crítico de Impressão", f"Ocorreu um erro inesperado durante a impressão.\nDetalhes: {error}")

    def handle_credit_sale_request(self, total_amount):
        if not self.is_cash_session_open(): return
        """Handles the request to process the sale as a credit sale (fiado) with ATOMIC TRANSACTION."""
        credit_dialog = CreditDialog(total_amount, self.main_window.current_user['id'], self)
        
        if credit_dialog.exec() == QDialog.DialogCode.Accepted:
            credit_data = credit_dialog.get_credit_data()
            if not credit_data:
                QMessageBox.critical(self, "Erro", "Não foi possível obter os dados da venda a crédito.")
                return

            selected_customer = credit_dialog.get_selected_customer()
            customer_name = selected_customer['name'] if selected_customer else "Cliente Fiado"
            
            # ATOMIC TRANSACTION START
            conn = db.get_db_connection()
            cursor = conn.cursor()
            
            try:
                # 1. Create the credit sale record
                # Note: create_credit_sale triggers the INSERT. If it fails, it raises sqlite3.Error
                success, result = create_credit_sale(
                    customer_id=credit_data['customer_id'],
                    amount=total_amount,
                    user_id=self.main_window.current_user['id'],
                    observations=credit_data['observations'],
                    due_date=credit_data['due_date'],
                    cursor=cursor # Pass transaction context
                )

                if not success:
                    raise Exception(result or "Erro desconhecido ao criar registro de fiado.")
                
                credit_sale_id = result # When successful, result is the ID

                # 2. Register the main sale for stock control
                # Passing empty list of payments because payment is 'Credit' (handled via logic)
                # We need to make sure register_sale_with_user handles the external cursor correctly
                sale_success, sale_data = db.register_sale_with_user(
                    total_amount, [], self.current_sale_items, Decimal('0.00'),
                    user_id=self.main_window.current_user["id"],
                    cash_session_id=self.main_window.current_cash_session["id"],
                    customer_name=customer_name,
                    cursor=cursor # Pass transaction context
                )

                if not sale_success:
                    raise Exception(sale_data.get('error', "Erro desconhecido ao registrar venda."))

                # 3. Link the original sale to the credit sale
                sale_id = sale_data['id']
                associate_sale_to_credit(credit_sale_id, sale_id, cursor=cursor)

                # COMMIT TRANSACTION
                conn.commit()
                logging.info(f"Transação de venda a crédito concluída com sucesso. SaleID: {sale_id}, CreditID: {credit_sale_id}")

                # Post-transaction actions (Notifications, UI updates)
                try:
                    # Log audit (Best effort, own connection)
                    log_audit(
                        self.main_window.current_user['id'],
                        'CREATE_CREDIT_SALE',
                        'credit_sales',
                        credit_sale_id,
                        f"Cliente: {customer_name}, Valor: {total_amount:.2f}"
                    )
                except Exception as e:
                    logging.warning(f"Erro no log de auditoria pós-transação: {e}")

                # Enviar notificação automática de fiado criado via WhatsApp
                try:
                    from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                    notifier = get_whatsapp_sales_notifier()
                    notifier.notify_credit_created(credit_sale_id)
                except Exception as e:
                    logging.warning(f"Erro ao enviar notificação de fiado criado via WhatsApp: {e}")

                SuccessDialog("Venda Fiado Registrada", "A venda foi registrada no fiado do cliente com sucesso.", self).exec()
                self.current_sale_items.clear()
                self.current_sale_customer_name = None
                self.update_sale_display()

            except Exception as e:
                conn.rollback()
                logging.error(f"Falha crítica na transação de venda a crédito: {e}", exc_info=True)
                MessageDialog.show_error(self, "Erro na Venda", 
                                     f"A venda NÃO foi realizada.\nNenhuma alteração foi salva.\n\nErro: {e}")
            finally:
                conn.close()

    # --- Funções de Configuração (Restauradas) ---
    def load_store_config(self):
        config_path = get_data_path('config.json')
        if not os.path.exists(config_path):
            self._create_default_config(config_path)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('store', {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def load_shortcuts_config(self):
        config_path = get_data_path('config.json')
        if not os.path.exists(config_path):
            self._create_default_config(config_path)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('shortcuts', [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _create_default_config(self, config_path):
        default_config = {
            "store": {"name": "Nome da Loja", "address": "Endereço", "phone": "Telefone", "cnpj": "CNPJ"},
            "shortcuts": [],
            "printer": {"auto_print_receipt": True}
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
        except IOError as e:
            MessageDialog.show_warning(self, "Erro", f"Não foi possível criar o arquivo de configuração: {e}")

    def on_shortcut_button_clicked(self, barcode):
        if not self.is_cash_session_open(): return
        self.product_code_input.setText(barcode)
        self.add_product_to_sale()
        
    def quick_kg_sale(self):
        weight = Decimal(str(self.last_known_weight))
        
        final_weight = None
        if weight <= 0:
            # Se a balança não tem peso, pede manual
            weight_str, ok = CustomInputDialog.get_value(self, "Entrada de Peso Manual", 
                                                    "Balança indisponível. Digite o peso em KG (ex: 1,250):")
            if ok and weight_str:
                try:
                    # Garante que tanto vírgula quanto ponto sejam aceitos
                    final_weight = Decimal(weight_str.replace(",", "."))
                    if final_weight <= 0:
                        MessageDialog.show_warning(self, "Peso Inválido", "O peso deve ser maior que zero.")
                        return
                except InvalidOperation:
                    MessageDialog.show_warning(self, "Formato Inválido", "O peso digitado não é um número válido.")
                    return
            else:
                return # Usuário cancelou
        else:
            final_weight = weight
            
        if final_weight:
            # Garante que o produto 9999 exista
            ensure_manual_product_exists()
            
            self.product_code_input.setText("9999")
            self.add_product_to_sale(weight_from_scale=final_weight)

    def manual_value_sale(self):
        """Adiciona um produto genérico com base em um valor monetário informado."""
        if not self.is_cash_session_open(): return

        # Pede ao usuário para inserir o valor desejado
        val_str, ok = CustomInputDialog.get_value(self, "Adicionar Valor Manual", 
                                             "Digite o valor a ser adicionado (R$):", "0,00")

        if ok:
            try:
                value = float(val_str.replace(",", "."))
            except ValueError:
                value = 0.0
                
            if value > 0:
                # Garante que o produto existe antes de tentar buscar
                ensure_manual_product_exists()
                
                # Busca o produto genérico (código 9999) para obter o preço por KG
                generic_product = db.get_product_by_barcode("9999")
                if not generic_product or 'price' not in generic_product:
                    MessageDialog.show_error(self, "Erro de Configuração", 
                                         "O produto genérico (código 9999) não está configurado corretamente.")
                    return

                price_per_kg = Decimal(str(generic_product['price']))
                if price_per_kg <= 0:
                    MessageDialog.show_error(self, "Erro de Configuração", 
                                         "O preço por KG do produto genérico deve ser maior que zero.")
                    return

                # Calcula o peso equivalente
                value_decimal = Decimal(str(value))
                equivalent_weight = value_decimal / price_per_kg

                # Adiciona o produto à venda com o peso calculado
                self.product_code_input.setText("9999")
                self.add_product_to_sale(weight_from_scale=equivalent_weight)

    def open_price_config_dialog(self):
        generic_product = db.get_product_by_barcode("9999")
        if not generic_product: return
        current_price = float(generic_product['price'])
        price_str, ok = CustomInputDialog.get_value(self, "Alterar Preço", "Novo preço por KG:", f"{current_price:.2f}")
        if ok:
            try:
                new_price = float(price_str.replace(",", "."))
                if new_price > 0:
                    db.update_product_price("9999", new_price)
            except ValueError:
                QMessageBox.warning(self, "Valor Inválido", "O preço digitado inválido.")

    # --- Funções de Gerenciamento de Itens e Comandas ---
    def update_remove_button_state(self):
        self.remove_item_button.setEnabled(len(self.sale_items_table.selectedItems()) > 0)

    def remove_selected_item(self):
        selected_row = self.sale_items_table.currentRow()
        if selected_row >= 0 and QMessageBox.question(self, "Confirmar", "Remover item?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.current_sale_items[selected_row]
            self.update_sale_display()

    def hold_current_sale(self):
        """Salva a venda atual em espera usando o diálogo moderno."""
        if not self.current_sale_items:
            MessageDialog.show_info(self, "Venda Vazia", "Não há itens na venda atual para salvar.")
            return False

        # Usar o novo diálogo moderno, passando o nome atual como sugestão
        suggested_name = self.current_sale_customer_name if self.current_sale_customer_name else None
        result = HeldSalesDialog.show_hold_dialog(self.current_sale_items, self.held_sales, self, suggested_name=suggested_name)
        if result and result['action'] == 'hold':
            identifier = result['identifier']
            self.held_sales[identifier] = self.current_sale_items.copy()
            self.current_sale_items.clear()
            self.current_sale_customer_name = None # Limpa o cliente ao salvar
            self.update_sale_display()
            SuccessDialog("Venda Salva", f"Venda salva com o identificador: '{identifier}'", self).exec()
            return True
        return False

    def resume_held_sale(self):
        """Recupera uma venda em espera usando o diálogo moderno."""
        if not self.held_sales:
            MessageDialog.show_info(self, "Sem Vendas em Espera", "Não há vendas salvas.")
            return

        if self.current_sale_items:
            # Simplificação para usar Modern Dialog (Sim/Não)
            # Ao recuperar uma venda, se houver itens atuais, perguntamos se deseja SALVAR antes.
            # Se disser SIM -> Salva e prossegue (ou aborta se falhar no salvar).
            # Se disser NÃO -> Descarta e prossegue.
            if MessageDialog.show_confirmation(self, "Venda em Andamento", "Existe uma venda em andamento. Deseja salvá-la?\n\n(Selecionar 'Não' irá descartar a venda atual!)"):
                if not self.hold_current_sale(): return # Falha ao salvar, cancela a recuperação
            else:
                self.current_sale_items.clear()
                self.current_sale_customer_name = None

        # Usar o novo diálogo moderno
        result = HeldSalesDialog.show_resume_dialog(self.held_sales, self)
        if result and result['action'] == 'resume':
            sale_key = result['sale_key']
            self.current_sale_items = self.held_sales[sale_key]
            self.current_sale_customer_name = sale_key # Define o cliente
            del self.held_sales[sale_key]
            self.update_sale_display()
            SuccessDialog("Venda Recuperada", f"Venda '{sale_key}' recuperada com sucesso!", self).exec()

    def identify_sale(self):
        """Permite ao usuário identificar a venda atual com um nome."""
        if not self.current_sale_items:
            QMessageBox.information(self, "Venda Vazia", "Não há itens na venda atual para identificar.")
            return

        current_name = self.current_sale_customer_name or ""
        name, ok = QInputDialog.getText(self, "Identificar Venda", 
                                       "Digite o nome ou identificador da venda:",
                                       text=current_name)

        if ok and name.strip():
            self.current_sale_customer_name = name.strip()
            self.update_sale_display()  # Atualizar a exibição do nome
            QMessageBox.information(self, "Venda Identificada",
                                  f"Venda identificada como: '{self.current_sale_customer_name}'")
        elif ok and not name.strip():
            # Se o usuário deixou em branco, limpa o nome
            self.current_sale_customer_name = None
            self.update_sale_display()  # Atualizar a exibição do nome
            QMessageBox.information(self, "Nome Removido", "Nome da venda foi removido.")

    def force_scale_reconnect(self):
        """Força a tentativa de reconexão da balança."""
        logging.info("Botão de reconexão manual da balança pressionado.")
        self.weight_label.setText("Reconectando...")
        # Reconfigura o handler com as mesmas configurações para forçar um reinício
        self.scale_handler.reconfigure(self.scale_handler.mode, **self.scale_handler.config)

    # --- Funções de Validação e Recarga ---
    def is_cash_session_open(self):
        if self.main_window.current_cash_session is None:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Caixa Fechado")
            msg_box.setText("É necessário abrir um caixa para iniciar uma venda.")
            open_cash_button = msg_box.addButton("Ir para o Caixa", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == open_cash_button:
                self.main_window.change_page("cash")
            return False
        return True

    def showEvent(self, event):
        """Sobrescreve o evento que é chamado quando o widget é exibido."""
        logging.info("Acessando a tela de vendas.")
        # A balança agora é iniciada na janela principal, então não precisamos fazer nada aqui.
        super().showEvent(event)

    def hideEvent(self, event):
        """Sobrescreve o evento que é chamado quando o widget é ocultado."""
        logging.info("Saindo da tela de vendas.")
        # Não vamos mais parar a balança ao sair da tela.
        super().hideEvent(event)

    def reload_data(self):
        self.reload_shortcuts()
        self.load_print_config()
        logging.info("Dados da página de vendas recarregados.")
