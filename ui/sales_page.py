from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QGridLayout, QGroupBox, QInputDialog, QSpacerItem, QSizePolicy, QAbstractItemView,
    QDialogButtonBox
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtCore import Qt
import json
import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import database as db
from data.credit_repository import associate_sale_to_credit # <-- ADICIONADO
from hardware.scale_handler import ScaleHandler
from hardware.printer_handler import PrinterHandler
from ui.payment_dialog import PaymentDialog
from ui.credit_dialog import CreditDialog
from ui.product_search_dialog import ProductSearchDialog
from ui.theme import ModernTheme
from utils import get_data_path
import logging

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
        right_layout.setSpacing(15)
        
        store_name_label = QLabel(self.load_store_config().get('name', 'PDV'))
        store_name_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        right_layout.addWidget(store_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Label para vendas em espera
        self.held_sales_label = QLabel("Vendas em espera: 0")
        self.held_sales_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.held_sales_label)

        total_panel_layout = QVBoxLayout()
        self.total_label = QLabel("R$ 0,00")
        self.total_label.setStyleSheet(f"color: {ModernTheme.PRIMARY}; font-size: 48px; font-weight: 700;")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(QLabel("TOTAL"), alignment=Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(self.total_label)
        right_layout.addLayout(total_panel_layout)

        sale_info_group = QGroupBox("Informações da Venda")
        sale_info_layout = QGridLayout(sale_info_group)
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

        sale_info_layout.addWidget(QLabel("Peso da Balança:"), 0, 0)
        sale_info_layout.addWidget(self.weight_label, 0, 1)
        sale_info_layout.addWidget(QLabel("Quantidade de Itens:"), 1, 0)
        sale_info_layout.addWidget(self.items_count_label, 1, 1)
        sale_info_layout.addWidget(self.get_weight_button, 2, 0, 1, 3)
        sale_info_layout.addWidget(self.reconnect_scale_button, 2, 0, 1, 3)
        right_layout.addWidget(sale_info_group)

        right_layout.addStretch()
        
        # Botões de ação com Comandas
        self.hold_sale_button = QPushButton("Salvar Venda (F3)")
        self.hold_sale_button.setObjectName("modern_button_secondary")
        self.resume_sale_button = QPushButton("Recuperar Venda (F4)")
        self.resume_sale_button.setObjectName("modern_button_secondary")
        self.finish_sale_button = QPushButton("F1 - FINALIZAR VENDA")
        self.finish_sale_button.setObjectName("modern_button_primary")
        self.cancel_sale_button = QPushButton("F2 - CANCELAR VENDA")
        self.cancel_sale_button.setObjectName("modern_button_outline")
        
        right_layout.addWidget(self.hold_sale_button)
        right_layout.addWidget(self.resume_sale_button)
        right_layout.addWidget(self.finish_sale_button)
        right_layout.addWidget(self.cancel_sale_button)
        top_layout.addLayout(right_layout, 3)

        # Painel Inferior (Atalhos)
        shortcuts_group = QGroupBox("Atalhos Rápidos")
        shortcuts_main_layout = QHBoxLayout(shortcuts_group)
        main_layout.addWidget(shortcuts_group)

        self.dynamic_shortcuts_layout = QHBoxLayout()
        shortcuts_main_layout.addLayout(self.dynamic_shortcuts_layout)
        shortcuts_main_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        self.quick_kg_sale_button = QPushButton("Venda por KG")
        self.quick_kg_sale_button.setObjectName("modern_button_primary")
        self.quick_kg_sale_button.setMinimumHeight(60)
        shortcuts_main_layout.addWidget(self.quick_kg_sale_button)

        self.manual_value_button = QPushButton("Adicionar Valor Manual")
        self.manual_value_button.setObjectName("modern_button_primary")
        self.manual_value_button.setMinimumHeight(60)
        shortcuts_main_layout.addWidget(self.manual_value_button)

        self.toggle_print_button = QPushButton("🖨️")
        self.toggle_print_button.setToolTip("Ativar/Desativar Impressão de Recibo")
        self.toggle_print_button.setCheckable(True)
        self.toggle_print_button.setObjectName("modern_button_outline")
        self.toggle_print_button.setMinimumHeight(60)
        self.toggle_print_button.setFixedWidth(60)
        shortcuts_main_layout.addWidget(self.toggle_print_button)

        self.price_config_button = QPushButton("⚙️")
        self.price_config_button.setObjectName("modern_button_outline")
        self.price_config_button.setMinimumHeight(60)
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
        self.hold_sale_button.clicked.connect(self.hold_current_sale)
        self.resume_sale_button.clicked.connect(self.resume_held_sale)
        self.reconnect_scale_button.clicked.connect(self.force_scale_reconnect)

        # --- CORREÇÃO E ADIÇÃO DE ATALHOS GLOBAIS ---
        QShortcut(QKeySequence("F1"), self).activated.connect(self.open_payment_dialog)
        QShortcut(QKeySequence("F2"), self).activated.connect(self.cancel_sale)
        QShortcut(QKeySequence("F3"), self).activated.connect(self.hold_current_sale)
        QShortcut(QKeySequence("F4"), self).activated.connect(self.resume_held_sale)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.open_product_search_dialog)
        # Atalho global para a tecla Enter
        QShortcut(QKeySequence(Qt.Key.Key_Return), self).activated.connect(self.handle_enter_pressed)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self).activated.connect(self.handle_enter_pressed)

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
            # Se o campo estiver vazio, executa a venda rápida por KG
            self.quick_kg_sale()
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
            button.setMinimumHeight(60)
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
                weight_str, ok = QInputDialog.getText(self, "Entrada Manual de Peso", "Digite o peso em KG (ex: 1,250):")
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
        new_quantity, ok = QInputDialog.getInt(self, "Alterar Quantidade", "Nova quantidade:", 
                                                 int(current_quantity), 1, 9999)

        if ok and new_quantity > 0:
            item['quantity'] = Decimal(str(new_quantity))
            item['total_price'] = item['quantity'] * item['unit_price']
            self.update_sale_display()

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

    def cancel_sale(self):
        if self.current_sale_items and QMessageBox.question(self, "Confirmar", "Deseja cancelar a venda atual?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
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

            # Envia a venda para o banco de dados, agora incluindo o nome do cliente
            sale_success, sale_data = db.register_sale_with_user(
                total_amount, payments, self.current_sale_items, change_amount,
                user_id=self.main_window.current_user["id"],
                cash_session_id=self.main_window.current_cash_session["id"],
                customer_name=self.current_sale_customer_name
            )

            if not sale_success:
                QMessageBox.critical(self, "Erro ao Salvar Venda", f"A venda não foi registrada.\nErro: {sale_data.get('error', 'Desconhecido')}")
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

            QMessageBox.information(self, "Venda Registrada", "Venda registrada com sucesso!")

            if self.toggle_print_button.isChecked():
                store_info = self.load_store_config()
                payment_method_str = ", ".join([f"{p['method']}: R$ {p['amount']:.2f}" for p in payments])
                receipt_details = {'items': self.current_sale_items, 'total_amount': total_amount, 'payment_method': payment_method_str}
                print_success, print_message = self.printer_handler.print_receipt(store_info, receipt_details)
                if not print_success:
                    QMessageBox.warning(self, "Erro na Impressão", f"A venda foi salva, mas houve um erro ao imprimir.\nErro: {print_message}")

            self.current_sale_items.clear()
            self.current_sale_customer_name = None # Limpa o cliente após a venda
            self.update_sale_display()

    def handle_credit_sale_request(self, total_amount):
        if not self.is_cash_session_open(): return
        """Handles the request to process the sale as a credit sale (fiado)."""
        credit_dialog = CreditDialog(total_amount, self.main_window.current_user['id'], self)
        if credit_dialog.exec() == QDialog.DialogCode.Accepted:
            # The credit sale was created successfully in the CreditDialog.
            # Now, we register the original sale for auditing and stock purposes.
            
            selected_customer = credit_dialog.get_selected_customer()
            customer_name = selected_customer['name'] if selected_customer else "Cliente Fiado"

            # We pass an empty list of payments and zero change.
            sale_success, sale_data = db.register_sale_with_user(
                total_amount, [], self.current_sale_items, Decimal('0.00'),
                user_id=self.main_window.current_user["id"],
                cash_session_id=self.main_window.current_cash_session["id"],
                customer_name=customer_name
            )

            if sale_success:
                # Link the original sale to the credit sale
                credit_sale_id = credit_dialog.credit_sale_id
                sale_id = sale_data['id']
                associate_sale_to_credit(credit_sale_id, sale_id)

                QMessageBox.information(self, "Venda Fiado Registrada", 
                                        "A venda foi registrada no fiado do cliente com sucesso.")
                self.current_sale_items.clear()
                self.current_sale_customer_name = None
                self.update_sale_display()
            else:
                QMessageBox.critical(self, "Erro Crítico", 
                                     f"A venda a crédito foi criada, mas houve um erro ao registrar a venda original para baixa de estoque. Verifique o estoque manualmente.\nErro: {sale_data.get('error', 'Desconhecido')}")

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
            QMessageBox.warning(self, "Erro", f"Não foi possível criar o arquivo de configuração: {e}")

    def on_shortcut_button_clicked(self, barcode):
        if not self.is_cash_session_open(): return
        self.product_code_input.setText(barcode)
        self.add_product_to_sale()
        
    def quick_kg_sale(self):
        weight = Decimal(str(self.last_known_weight))
        
        final_weight = None
        if weight <= 0:
            # Se a balança não tem peso, pede manual
            weight_str, ok = QInputDialog.getText(self, "Entrada de Peso Manual", 
                                                    "Balança indisponível. Digite o peso em KG (ex: 1,250):")
            if ok and weight_str:
                try:
                    # Garante que tanto vírgula quanto ponto sejam aceitos
                    final_weight = Decimal(weight_str.replace(",", "."))
                    if final_weight <= 0:
                        QMessageBox.warning(self, "Peso Inválido", "O peso deve ser maior que zero.")
                        return
                except InvalidOperation:
                    QMessageBox.warning(self, "Formato Inválido", "O peso digitado não é um número válido.")
                    return
            else:
                return # Usuário cancelou
        else:
            final_weight = weight
            
        if final_weight:
            self.product_code_input.setText("9999")
            self.add_product_to_sale(weight_from_scale=final_weight)

    def manual_value_sale(self):
        """Adiciona um produto genérico com base em um valor monetário informado."""
        if not self.is_cash_session_open(): return

        # Pede ao usuário para inserir o valor desejado
        value, ok = QInputDialog.getDouble(self, "Adicionar Valor Manual", 
                                             "Digite o valor a ser adicionado (R$):", 
                                             0.0, 0.01, 100000, 2)

        if ok and value > 0:
            # Busca o produto genérico (código 9999) para obter o preço por KG
            generic_product = db.get_product_by_barcode("9999")
            if not generic_product or 'price' not in generic_product:
                QMessageBox.critical(self, "Erro de Configuração", 
                                     "O produto genérico (código 9999) não está configurado corretamente.")
                return

            price_per_kg = Decimal(str(generic_product['price']))
            if price_per_kg <= 0:
                QMessageBox.critical(self, "Erro de Configuração", 
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
        new_price, ok = QInputDialog.getDouble(self, "Alterar Preço", "Novo preço por KG:", current_price, 0.01, 10000, 2)
        if ok and new_price:
            db.update_product_price("9999", new_price)

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
        """Salva a venda atual em espera."""
        if not self.current_sale_items:
            return False
        
        identifier, ok = QInputDialog.getText(self, "Salvar Venda", 
                                              "Digite o nome ou número da comanda:", 
                                              text=f"Comanda {len(self.held_sales) + 1}")
        
        if ok and identifier:
            self.held_sales[identifier] = self.current_sale_items.copy()
            self.current_sale_items.clear()
            self.current_sale_customer_name = None # Limpa o cliente ao salvar
            self.update_sale_display()
            return True
        return False

    def resume_held_sale(self):
        """Recupera uma venda em espera."""
        if not self.held_sales:
            QMessageBox.information(self, "Sem Vendas em Espera", "Não há vendas salvas.")
            return

        if self.current_sale_items:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Venda em Andamento")
            msg_box.setText("Há uma venda em andamento. O que deseja fazer?")
            save_btn = msg_box.addButton("Salvar Venda Atual", QMessageBox.ButtonRole.AcceptRole)
            discard_btn = msg_box.addButton("Descartar", QMessageBox.ButtonRole.DestructiveRole)
            msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()

            clicked_btn = msg_box.clickedButton()
            if clicked_btn == save_btn:
                if not self.hold_current_sale(): return # Aborta se o salvamento for cancelado
            elif clicked_btn == discard_btn:
                self.current_sale_items.clear()
                self.current_sale_customer_name = None
            else: # Cancelar
                return

        items = list(self.held_sales.keys())
        identifier, ok = QInputDialog.getItem(self, "Recuperar Venda", "Selecione a venda para reabrir:", items, 0, False)
        
        if ok and identifier:
            self.current_sale_items = self.held_sales[identifier]
            self.current_sale_customer_name = identifier # Define o cliente
            del self.held_sales[identifier]
            self.update_sale_display()

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