from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QComboBox, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool
from decimal import Decimal, InvalidOperation
import database as db
from .worker import Worker

class ProductManagementWindow(QWidget):
    data_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_product_id = None
        self.groups = []
        self.threadpool = QThreadPool()

        main_layout = QHBoxLayout(self)

        # Formulário
        form_layout = QVBoxLayout()
        self.desc_input = QLineEdit(placeholderText="Descrição do Produto")
        self.barcode_input = QLineEdit(placeholderText="Código de Barras")
        self.price_input = QLineEdit(placeholderText="Preço de Venda (ex: 12.99)")
        self.stock_input = QLineEdit(placeholderText="Estoque Atual")
        self.sale_type_combo = QComboBox()
        self.sale_type_combo.addItems(["Por Unidade", "Por Peso"])
        self.group_combo = QComboBox()

        form_layout.addWidget(QLabel("Descrição:"))
        form_layout.addWidget(self.desc_input)
        form_layout.addWidget(QLabel("Código de Barras:"))
        form_layout.addWidget(self.barcode_input)
        form_layout.addWidget(QLabel("Preço (R$):"))
        form_layout.addWidget(self.price_input)
        form_layout.addWidget(QLabel("Estoque:"))
        form_layout.addWidget(self.stock_input)
        form_layout.addWidget(QLabel("Tipo de Venda:"))
        form_layout.addWidget(self.sale_type_combo)
        form_layout.addWidget(QLabel("Grupo:"))
        form_layout.addWidget(self.group_combo)
        form_layout.addStretch()

        form_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.clear_button = QPushButton("Limpar")
        self.delete_button = QPushButton("Excluir")
        form_buttons_layout.addWidget(self.save_button)
        form_buttons_layout.addWidget(self.clear_button)
        form_layout.addLayout(form_buttons_layout)
        form_layout.addWidget(self.delete_button)

        # Tabela
        table_layout = QVBoxLayout()
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(7)
        self.products_table.setHorizontalHeaderLabels(["ID", "Descrição", "Cód. Barras", "Preço", "Estoque", "Tipo", "Grupo"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_layout.addWidget(self.products_table)

        main_layout.addLayout(form_layout, 1)
        main_layout.addLayout(table_layout, 2)

        # Conexões
        self.save_button.clicked.connect(self.save_product)
        self.clear_button.clicked.connect(self.clear_fields)
        self.delete_button.clicked.connect(self.delete_product)
        self.products_table.itemSelectionChanged.connect(self.select_product)

        self.load_groups_into_combo()
        self.load_products()

    def load_products(self):
        self.products_table.setRowCount(0)
        self.show_loading_message()
        worker = Worker(db.get_all_products)
        worker.signals.result.connect(self.populate_products_table)
        self.threadpool.start(worker)

    def populate_products_table(self, products):
        self.products_table.setRowCount(0)
        if not products:
            self.show_no_results_message()
            return

        for row_num, product in enumerate(products):
            self.products_table.insertRow(row_num)
            self.products_table.setItem(row_num, 0, QTableWidgetItem(str(product['id'])))
            self.products_table.setItem(row_num, 1, QTableWidgetItem(product['description']))
            self.products_table.setItem(row_num, 2, QTableWidgetItem(product['barcode']))
            self.products_table.setItem(row_num, 3, QTableWidgetItem(f"R$ {product['price']:.2f}"))
            self.products_table.setItem(row_num, 4, QTableWidgetItem(str(product['stock'])))
            self.products_table.setItem(row_num, 5, QTableWidgetItem("Por Peso" if product['sale_type'] == 'weight' else "Por Unidade"))
            self.products_table.setItem(row_num, 6, QTableWidgetItem(product['group_name'] or "Nenhum"))
        self.clear_fields()

    def show_loading_message(self):
        self.products_table.setRowCount(1)
        loading_item = QTableWidgetItem("Carregando produtos...")
        loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.products_table.setItem(0, 0, loading_item)
        self.products_table.setSpan(0, 0, 1, self.products_table.columnCount())

    def show_no_results_message(self):
        self.products_table.setRowCount(1)
        no_results_item = QTableWidgetItem("Nenhum produto encontrado")
        no_results_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.products_table.setItem(0, 0, no_results_item)
        self.products_table.setSpan(0, 0, 1, self.products_table.columnCount())

    def load_groups_into_combo(self):
        self.group_combo.clear()
        self.groups = db.get_all_groups()
        self.group_combo.addItem("Nenhum", None)
        for group in self.groups:
            self.group_combo.addItem(group['name'], group['id'])

    def save_product(self):
        desc = self.desc_input.text()
        barcode = self.barcode_input.text()
        price_str = self.price_input.text()
        stock_str = self.stock_input.text()
        sale_type = 'weight' if self.sale_type_combo.currentText() == "Por Peso" else 'unit'
        group_id = self.group_combo.currentData()

        if not all([desc, barcode, price_str, stock_str]):
            QMessageBox.warning(self, "Campos Incompletos", "Todos os campos são obrigatórios.")
            return
        
        try:
            price_str = self.price_input.text().replace(",", ".")
            stock_str = self.stock_input.text().replace(",", ".")
            price = Decimal(price_str)
            stock = Decimal(stock_str)
        except InvalidOperation:
            QMessageBox.warning(self, "Erro de Formato", "O valor de 'Preço' ou 'Estoque' é inválido. Use apenas números e vírgula/ponto.")
            return

        if self.current_product_id:
            success, message = db.update_product(self.current_product_id, desc, barcode, price, stock, sale_type, group_id)
        else:
            success, message = db.add_product(desc, barcode, price, stock, sale_type, group_id)
        
        if success:
            QMessageBox.information(self, "Sucesso", "Produto salvo com sucesso.")
            self.data_changed.emit()
            self.load_products()
        else:
            QMessageBox.warning(self, "Erro ao Salvar", message)

    def delete_product(self):
        if not self.current_product_id:
            QMessageBox.warning(self, "Nenhum Produto Selecionado", "Por favor, selecione um produto na tabela para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                   "Deseja realmente excluir este produto?", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = db.delete_product(self.current_product_id)
            if success:
                QMessageBox.information(self, "Sucesso", "Produto excluído com sucesso.")
                self.data_changed.emit()
                self.load_products()
            else:
                QMessageBox.warning(self, "Erro ao Excluir", message)

    def clear_fields(self):
        self.current_product_id = None
        self.desc_input.clear()
        self.barcode_input.clear()
        self.price_input.clear()
        self.stock_input.clear()
        self.sale_type_combo.setCurrentIndex(0)
        self.group_combo.setCurrentIndex(0)
        self.products_table.clearSelection()

    def select_product(self):
        selected_items = self.products_table.selectedItems()
        if not selected_items: return
        
        row = selected_items[0].row()
        self.current_product_id = int(self.products_table.item(row, 0).text())
        self.desc_input.setText(self.products_table.item(row, 1).text())
        self.barcode_input.setText(self.products_table.item(row, 2).text())
        self.price_input.setText(self.products_table.item(row, 3).text().replace("R$ ", ""))
        self.stock_input.setText(self.products_table.item(row, 4).text())
        self.sale_type_combo.setCurrentText(self.products_table.item(row, 5).text())
        group_name = self.products_table.item(row, 6).text()
        if self.group_combo.findText(group_name) > -1:
            self.group_combo.setCurrentText(group_name)
        else:
            self.group_combo.setCurrentIndex(0)
