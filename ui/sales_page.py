from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QGridLayout, QGroupBox, QInputDialog, QSpacerItem, QSizePolicy, QAbstractItemView
)
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtCore import Qt
import json
import os
from decimal import Decimal, ROUND_HALF_UP
import database as db
from hardware.scale_handler import ScaleHandler
from hardware.printer_handler import PrinterHandler
from ui.payment_dialog import PaymentDialog
from ui.theme import ModernTheme
from utils import get_data_path

class SalesPage(QWidget):
    def __init__(self, main_window, scale_handler, printer_handler):
        super().__init__()
        
        self.main_window = main_window
        self.scale_handler = scale_handler
        self.printer_handler = printer_handler
        self.current_sale_items = []
        self.last_known_weight = 0.0
        
        # Estrutura para Vendas em Espera (Comandas)
        self.held_sales = {}
        
        # Conectar ao sinal de atualização de peso da balança
        self.scale_handler.weight_updated.connect(self._on_weight_updated)
        self.scale_handler.error_occurred.connect(self._on_scale_error)

        self.setup_ui()

    def _on_weight_updated(self, weight):
        """Slot para receber o peso da balança e atualizar a UI."""
        self.last_known_weight = weight
        if weight > 0:
            self.weight_label.setText(f"{weight:.3f} kg")
        else:
            self.weight_label.setText("0.000 kg")

    def _on_scale_error(self, error_message):
        """Slot para receber erros da balança."""
        self.last_known_weight = 0.0
        self.weight_label.setText("Erro kg")
        print(f"SalesPage Scale Error: {error_message}")

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
        product_input_layout.addWidget(product_code_label)
        product_input_layout.addWidget(self.product_code_input)
        left_layout.addLayout(product_input_layout)
        
        self.sale_items_table = QTableWidget()
        self.sale_items_table.setColumnCount(5)
        self.sale_items_table.setHorizontalHeaderLabels(["Cód.", "Descrição", "Qtd/Peso", "Vl. Unit.", "Vl. Total"])
        self.sale_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sale_items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sale_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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

        sale_info_layout.addWidget(QLabel("Peso da Balança:"), 0, 0)
        sale_info_layout.addWidget(self.weight_label, 0, 1)
        sale_info_layout.addWidget(QLabel("Quantidade de Itens:"), 1, 0)
        sale_info_layout.addWidget(self.items_count_label, 1, 1)
        sale_info_layout.addWidget(self.get_weight_button, 2, 0, 1, 2)
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
        self.product_code_input.returnPressed.connect(self.add_product_to_sale)
        self.finish_sale_button.clicked.connect(self.open_payment_dialog)
        self.cancel_sale_button.clicked.connect(self.cancel_sale)
        self.get_weight_button.clicked.connect(self.get_weight_from_scale)
        self.quick_kg_sale_button.clicked.connect(self.quick_kg_sale)
        self.price_config_button.clicked.connect(self.open_price_config_dialog)
        self.sale_items_table.itemSelectionChanged.connect(self.update_remove_button_state)
        self.remove_item_button.clicked.connect(self.remove_selected_item)
        self.toggle_print_button.clicked.connect(self.on_toggle_print_button_clicked)
        self.hold_sale_button.clicked.connect(self.hold_current_sale)
        self.resume_sale_button.clicked.connect(self.resume_held_sale)

        # --- CORREÇÃO E ADIÇÃO DE ATALHOS GLOBAIS ---
        QShortcut(QKeySequence("F1"), self).activated.connect(self.open_payment_dialog)
        QShortcut(QKeySequence("F2"), self).activated.connect(self.cancel_sale)
        QShortcut(QKeySequence("F3"), self).activated.connect(self.hold_current_sale)
        QShortcut(QKeySequence("F4"), self).activated.connect(self.resume_held_sale)

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
                # Se o peso for inválido, abre o diálogo para entrada manual
                weight, ok = QInputDialog.getDouble(self, "Entrada Manual de Peso", "Digite o peso em KG:", decimals=3, min=0.001)
                if ok and weight > 0:
                    quantity = Decimal(str(weight))
                else:
                    # Se o usuário cancelar ou inserir peso inválido, não adiciona o produto
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
                'sale_type': product_data['sale_type']
            })
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
            self.update_sale_display()

    def open_payment_dialog(self):
        if not self.current_sale_items: return
        
        total_amount = sum(item['total_price'] for item in self.current_sale_items)
        dialog = PaymentDialog(total_amount, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_data:
            payments = dialog.result_data['payments']

            # Send payments list directly (new format) instead of concatenated string
            sale_success, sale_message_or_id = db.register_sale_with_user(
                total_amount, payments, self.current_sale_items,
                user_id=self.main_window.current_user["id"],
                cash_session_id=self.main_window.current_cash_session["id"]
            )

            if not sale_success:
                QMessageBox.critical(self, "Erro ao Salvar Venda", f"A venda não foi registrada.\nErro: {sale_message_or_id}")
                return

            # Enviar notificação automática de venda via WhatsApp
            try:
                from integrations.whatsapp_sales_notifications import get_whatsapp_sales_notifier
                sales_notifier = get_whatsapp_sales_notifier()

                # Preparar dados da venda para notificação
                sale_data = {
                    'id': sale_message_or_id if isinstance(sale_message_or_id, (int, str)) else 'N/A',
                    'customer_name': 'Cliente',  # Pode ser expandido para capturar nome do cliente
                    'total_amount': float(total_amount)
                }

                # Preparar detalhes dos pagamentos para notificação
                payment_details = [{'method': p['method'], 'amount': float(p['amount'])} for p in payments]

                # Enviar notificação (não bloqueante)
                sales_notifier.notify_sale(sale_data, payment_details)
            except Exception as e:
                print(f"Aviso: Erro ao enviar notificação de venda via WhatsApp: {e}")
                # Não exibir erro para usuário pois a venda foi salva com sucesso

            QMessageBox.information(self, "Venda Registrada", "Venda registrada com sucesso!")

            if self.toggle_print_button.isChecked():
                store_info = self.load_store_config()
                # Create payment method string for receipt
                payment_method_str = ", ".join([f"{p['method']}: R$ {p['amount']:.2f}" for p in payments])
                sale_details = {'items': self.current_sale_items, 'total_amount': total_amount, 'payment_method': payment_method_str}
                print_success, print_message = self.printer_handler.print_receipt(store_info, sale_details)
                if not print_success:
                    QMessageBox.warning(self, "Erro na Impressão", f"A venda foi salva, mas houve um erro ao imprimir.\nErro: {print_message}")

            self.current_sale_items.clear()
            self.update_sale_display()

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
            weight_val, ok = QInputDialog.getDouble(self, "Entrada de Peso Manual", 
                                                    "Balança não disponível. Digite o peso em KG:",
                                                    decimals=3, min=0.001)
            if ok and weight_val > 0:
                final_weight = Decimal(str(weight_val))
            else:
                return # Usuário cancelou
        else:
            final_weight = weight
            
        if final_weight:
            self.product_code_input.setText("9999")
            self.add_product_to_sale(weight_from_scale=final_weight)

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
            else: # Cancelar
                return

        items = list(self.held_sales.keys())
        identifier, ok = QInputDialog.getItem(self, "Recuperar Venda", "Selecione a venda para reabrir:", items, 0, False)
        
        if ok and identifier:
            self.current_sale_items = self.held_sales[identifier]
            del self.held_sales[identifier]
            self.update_sale_display()

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

    def reload_data(self):
        self.reload_shortcuts()
        self.load_print_config()
        print("Dados da página de vendas recarregados.")
