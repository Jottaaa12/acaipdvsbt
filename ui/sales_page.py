from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, 
    QDialog, QGridLayout, QGroupBox, QInputDialog, QSpacerItem, QSizePolicy, QAbstractItemView
)
from PyQt6.QtGui import QFont
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

        self.setup_ui()

    def setup_ui(self):
        # Layout principal vertical
        main_layout = QVBoxLayout(self)

        # Layout superior (conteúdo principal)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Painel Esquerdo (70%)
        left_layout = QVBoxLayout()
        
        # Input do produto
        product_input_layout = QHBoxLayout()
        product_code_label = QLabel("Código do Produto:")
        self.product_code_input = QLineEdit(placeholderText="Leia o código de barras ou digite aqui")
        self.product_code_input.setObjectName("modern_input")
        product_input_layout.addWidget(product_code_label)
        product_input_layout.addWidget(self.product_code_input)
        left_layout.addLayout(product_input_layout)
        
        # Tabela de itens
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
        
        # Painel Direito (30%)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)
        
        store_name_label = QLabel(self.load_store_config().get('name', 'PDV'))
        store_name_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        right_layout.addWidget(store_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Painel Total
        total_panel_layout = QVBoxLayout()
        self.total_label = QLabel("R$ 0,00")
        self.total_label.setStyleSheet(f"""
            color: {ModernTheme.PRIMARY};
            font-size: 48px;
            font-weight: 700;
        """)
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(QLabel("TOTAL"), alignment=Qt.AlignmentFlag.AlignCenter)
        total_panel_layout.addWidget(self.total_label)
        right_layout.addLayout(total_panel_layout)

        # Novo painel de Informações da Venda
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
        
        # Botões de ação
        self.finish_sale_button = QPushButton("F1 - FINALIZAR VENDA")
        self.finish_sale_button.setObjectName("modern_button_primary")
        self.cancel_sale_button = QPushButton("F2 - CANCELAR VENDA")
        self.cancel_sale_button.setObjectName("modern_button_outline")
        right_layout.addWidget(self.finish_sale_button)
        right_layout.addWidget(self.cancel_sale_button)
        
        top_layout.addLayout(right_layout, 3)

        # Painel Inferior (Atalhos)
        shortcuts_group = QGroupBox("Atalhos Rápidos")
        shortcuts_main_layout = QHBoxLayout(shortcuts_group)
        main_layout.addWidget(shortcuts_group)

        # Layout para atalhos dinâmicos
        self.dynamic_shortcuts_layout = QHBoxLayout()
        shortcuts_main_layout.addLayout(self.dynamic_shortcuts_layout)

        # Spacer para empurrar os botões fixos para a direita
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        shortcuts_main_layout.addItem(spacer)

        # Botões fixos (criados apenas uma vez)
        self.quick_kg_sale_button = QPushButton("Venda por KG")
        self.quick_kg_sale_button.setObjectName("modern_button_primary")
        self.quick_kg_sale_button.setMinimumHeight(60)
        shortcuts_main_layout.addWidget(self.quick_kg_sale_button)

        self.price_config_button = QPushButton("⚙️")
        self.price_config_button.setObjectName("modern_button_outline")
        self.price_config_button.setMinimumHeight(60)
        self.price_config_button.setFixedWidth(60)
        shortcuts_main_layout.addWidget(self.price_config_button)

        # Carregamento inicial dos atalhos dinâmicos
        self.reload_shortcuts()
        
        # Conexões
        self.product_code_input.returnPressed.connect(self.add_product_to_sale)
        self.finish_sale_button.clicked.connect(self.open_payment_dialog)
        self.cancel_sale_button.clicked.connect(self.cancel_sale)
        self.get_weight_button.clicked.connect(self.get_weight_from_scale)
        self.quick_kg_sale_button.clicked.connect(self.quick_kg_sale)
        self.price_config_button.clicked.connect(self.open_price_config_dialog)
        self.sale_items_table.itemSelectionChanged.connect(self.update_remove_button_state)
        self.remove_item_button.clicked.connect(self.remove_selected_item)

    def reload_shortcuts(self):
        """Limpa e recarrega apenas os botões de atalho de produtos."""
        # Limpar apenas os widgets do layout de atalhos dinâmicos
        while self.dynamic_shortcuts_layout.count():
            child = self.dynamic_shortcuts_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Carrega atalhos do config.json e adiciona ao layout dinâmico
        shortcuts = self.load_shortcuts_config()
        for shortcut in shortcuts:
            button = QPushButton(shortcut["name"])
            button.setObjectName("modern_button_secondary")
            button.setMinimumHeight(60)
            button.clicked.connect(lambda checked, b=shortcut["barcode"]: self.on_shortcut_button_clicked(b))
            self.dynamic_shortcuts_layout.addWidget(button)

    def get_weight_from_scale(self):
        """Lê o peso da balança e apenas atualiza o label."""
        success, data = self.scale_handler.get_weight()
        if success:
            weight = data
            if weight > 0:
                self.weight_label.setText(f"{weight:.3f} kg")
            else:
                self.weight_label.setText("0.000 kg")
        else:
            error_message = data
            self.weight_label.setText("Erro kg")
            QMessageBox.warning(self, "Erro Balança", error_message)

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
            # Se um peso não foi passado diretamente, busca da balança
            if weight_from_scale is None:
                success, data = self.scale_handler.get_weight()
                if not success:
                    QMessageBox.warning(self, "Erro de Balança", data)
                    return
                weight_from_scale = data

            quantity = Decimal(str(weight_from_scale))

            if quantity <= 0:
                QMessageBox.warning(self, "Erro de Peso", "Peso inválido ou não informado. Verifique a balança.")
                return
        else:
            quantity = Decimal('1')

        existing_item = next((i for i in self.current_sale_items if i['id'] == product_data['id'] and i['sale_type'] == 'unit'), None)
        
        if existing_item:
            existing_item['quantity'] += quantity
            existing_item['total_price'] = existing_item['quantity'] * existing_item['unit_price']
        else:
            unit_price = product_data['price']
            total_price = quantity * unit_price
            self.current_sale_items.append({
                'id': product_data['id'], 
                'barcode': product_data['barcode'], 
                'description': product_data['description'], 
                'quantity': quantity, 
                'unit_price': unit_price, 
                'total_price': total_price, 
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
            
            qty_str = ""
            if item['sale_type'] == 'weight':
                qty_str = f"{item['quantity']:.3f} kg"
                total_items += Decimal('1')
            else:
                qty_str = str(int(item['quantity']))
                total_items += item['quantity']

            price_str = f"R$ {item['unit_price']:.2f}" + ("/kg" if item['sale_type'] == 'weight' else "")
            self.sale_items_table.setItem(row, 2, QTableWidgetItem(qty_str))
            self.sale_items_table.setItem(row, 3, QTableWidgetItem(price_str))
            self.sale_items_table.setItem(row, 4, QTableWidgetItem(f"R$ {item['total_price']:.2f}"))
            total_sale_amount += item['total_price']
        
        self.total_label.setText(f"R$ {total_sale_amount:.2f}")
        self.items_count_label.setText(str(int(total_items)))
        
        if self.weight_label.text() != "0.000 kg":
            self.weight_label.setText("0.000 kg")

    def cancel_sale(self):
        if self.current_sale_items and QMessageBox.question(self, "Confirmar", "Deseja cancelar a venda atual?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.current_sale_items.clear()
            self.update_sale_display()

    def open_payment_dialog(self):
        if not self.current_sale_items: return
        
        total_amount = sum(item['total_price'] for item in self.current_sale_items)
        dialog = PaymentDialog(total_amount, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 1. Tenta registrar a venda no banco de dados
            sale_success, sale_message_or_id = db.register_sale_with_user(
                total_amount, 
                dialog.payment_method, 
                self.current_sale_items, 
                user_id=self.main_window.current_user["id"], 
                cash_session_id=self.main_window.current_cash_session["id"], 
                training_mode=False
            )

            # 2. Se a venda falhou, informa o erro e para
            if not sale_success:
                QMessageBox.critical(self, "Erro Crítico ao Salvar Venda", 
                                     f"A venda não pôde ser registrada no banco de dados.\n\nErro: {sale_message_or_id}\n\nOs itens permanecerão na tela para nova tentativa.")
                return

            # 3. Se a venda foi salva, tenta imprimir
            QMessageBox.information(self, "Venda Registrada", "Venda registrada com sucesso! Tentando imprimir o recibo...")
            
            store_info = self.load_store_config()
            sale_details = {'items': self.current_sale_items, 'total_amount': total_amount, 'payment_method': dialog.payment_method}
            
            print_success, print_message = self.printer_handler.print_receipt(store_info, sale_details)
            
            # 4. Informa sobre o status da impressão
            if not print_success:
                QMessageBox.warning(self, "Erro na Impressão", 
                                    f"A venda foi salva, mas houve um erro ao imprimir o recibo.\n\nErro: {print_message}")
            
            # 5. Limpa a venda e atualiza a tela
            self.current_sale_items.clear()
            self.update_sale_display()

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
            "store": {
                "name": "Nome da Loja",
                "address": "Endereço da Loja",
                "phone": "Telefone da Loja",
                "cnpj": "CNPJ da Loja"
            },
            "shortcuts": []
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Erro ao Criar Configuração", f"Não foi possível criar o arquivo de configuração padrão em {config_path}.\nErro: {e}")

    def on_shortcut_button_clicked(self, barcode):
        if not self.is_cash_session_open(): return
        
        product_data = db.get_product_by_barcode(barcode)
        if not product_data:
            QMessageBox.warning(self, "Erro de Atalho", f"Produto com código '{barcode}' não encontrado.")
            return

        product_data['price'] = Decimal(str(product_data['price'])).quantize(Decimal('0.01'))
        quantity_to_add = Decimal('1')

        existing_item = next((item for item in self.current_sale_items if item['id'] == product_data['id'] and item['sale_type'] == 'unit'), None)

        if existing_item:
            existing_item['quantity'] += quantity_to_add
            existing_item['total_price'] = existing_item['quantity'] * existing_item['unit_price']
        else:
            self.current_sale_items.append({
                'id': product_data['id'], 
                'barcode': product_data['barcode'], 
                'description': product_data['description'], 
                'quantity': quantity_to_add, 
                'unit_price': product_data['price'], 
                'total_price': quantity_to_add * product_data['price'], 
                'sale_type': 'unit'
            })
        
        self.update_sale_display()

    def quick_kg_sale(self):
        weight_text = self.weight_label.text().replace(' kg', '').replace(',', '.')
        try:
            weight = Decimal(weight_text)
            if weight <= 0:
                QMessageBox.warning(self, "Venda por KG", "Nenhum peso foi calculado. Use o botão 'Calcular Peso da Balança' primeiro.")
                return

            self.product_code_input.setText("9999")
            self.add_product_to_sale(weight_from_scale=weight)

        except ValueError:
            QMessageBox.warning(self, "Erro", "Valor de peso inválido no painel.")
        except Exception as e:
            QMessageBox.critical(self, "Erro Crítico", f"Ocorreu um erro ao processar a venda por KG: {e}")

    def open_price_config_dialog(self):
        generic_product = db.get_product_by_barcode("9999")
        if not generic_product:
            QMessageBox.critical(self, "Erro de Configuração", 
                                 "O produto para 'Venda por KG' (código 9999) não foi encontrado no banco de dados.")
            return
        
        current_price = float(generic_product['price'])

        new_price, ok = QInputDialog.getDouble(self, "Alterar Preço da Venda por KG", 
                                               "Novo preço por KG:", 
                                               current_price, 0.01, 10000, 2)

        if ok and new_price:
            success, message = db.update_product_price("9999", new_price)
            if success:
                QMessageBox.information(self, "Sucesso", f"Preço da 'Venda por KG' atualizado para R$ {new_price:.2f}.")
            else:
                QMessageBox.warning(self, "Erro ao Atualizar Preço", message)

    def update_remove_button_state(self):
        self.remove_item_button.setEnabled(len(self.sale_items_table.selectedItems()) > 0)

    def remove_selected_item(self):
        selected_row = self.sale_items_table.currentRow()
        if selected_row >= 0:
            reply = QMessageBox.question(self, "Confirmar Remoção", 
                                         "Deseja remover o item selecionado?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                del self.current_sale_items[selected_row]
                self.update_sale_display()

    def is_cash_session_open(self):
        if self.main_window.current_cash_session is None:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Caixa Fechado")
            msg_box.setText("O caixa está fechado. É necessário abrir um caixa para iniciar uma venda.")
            
            open_cash_button = msg_box.addButton("Ir para o Caixa", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == open_cash_button:
                self.main_window.change_page("cash")
            
            return False
        return True

    def reload_data(self):
        """Recarrega dados dinâmicos da página, como os atalhos."""
        # Limpa os atalhos antigos
        for i in reversed(range(self.dynamic_shortcuts_layout.count())):
            widget = self.dynamic_shortcuts_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Recarrega os atalhos
        shortcuts = self.load_shortcuts_config()
        for shortcut in shortcuts:
            button = QPushButton(shortcut["name"])
            button.setObjectName("modern_button_secondary")
            button.setMinimumHeight(60)
            button.clicked.connect(lambda checked, b=shortcut["barcode"]: self.on_shortcut_button_clicked(b))
            self.shortcuts_layout.addWidget(button)

        # Adiciona os botões fixos de volta
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.shortcuts_layout.addItem(spacer)
        self.shortcuts_layout.addWidget(self.quick_kg_sale_button)
        self.shortcuts_layout.addWidget(self.price_config_button)
        print("Atalhos da página de vendas recarregados.")