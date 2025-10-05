from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt
import database as db

class ProductSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar Produto por Nome")
        self.setMinimumSize(600, 400)
        self.selected_barcode = None

        # Layout principal
        layout = QVBoxLayout(self)

        # Campo de busca
        self.search_input = QLineEdit(placeholderText="Digite o nome do produto para buscar...")
        self.search_input.setObjectName("modern_input")
        layout.addWidget(self.search_input)

        # Tabela de resultados
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Cód. Barras", "Descrição", "Preço", "Estoque"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.results_table)

        # Botões
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Conexões
        self.search_input.textChanged.connect(self.search_products)
        self.results_table.doubleClicked.connect(self.accept)

        self.search_products() # Busca inicial para mostrar todos os produtos

    def search_products(self):
        search_term = self.search_input.text()
        
        # No futuro, podemos criar uma função de busca mais otimizada no banco de dados
        # Por enquanto, vamos usar a função que busca todos e filtrar aqui
        products = db.get_all_products() 
        
        if search_term:
            products = [p for p in products if search_term.lower() in p['description'].lower()]

        self.results_table.setRowCount(0)
        for row, product in enumerate(products):
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(product['barcode']))
            self.results_table.setItem(row, 1, QTableWidgetItem(product['description']))
            self.results_table.setItem(row, 2, QTableWidgetItem(f"R$ {product['price']:.2f}"))
            self.results_table.setItem(row, 3, QTableWidgetItem(str(product.get('stock', 'N/A'))))

    def accept(self):
        selected_row = self.results_table.currentRow()
        if selected_row >= 0:
            self.selected_barcode = self.results_table.item(selected_row, 0).text()
            super().accept()
        else:
            # Se nenhum item for selecionado, apenas fecha o diálogo sem fazer nada
            super().reject()

    def get_selected_barcode(self):
        return self.selected_barcode
