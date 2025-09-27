from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt
import database as db

class PaymentMethodManagementWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_method_id = None

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Lado Esquerdo (Formulário)
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        form_layout.addWidget(QLabel("<b>Gerenciar Formas de Pagamento</b>"))
        self.name_input = QLineEdit(placeholderText="Nome da Forma de Pagamento (ex: Pix)")
        form_layout.addWidget(QLabel("Nome:"))
        form_layout.addWidget(self.name_input)
        
        form_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar")
        self.clear_button = QPushButton("Limpar")
        form_buttons_layout.addWidget(self.save_button)
        form_buttons_layout.addWidget(self.clear_button)
        form_layout.addLayout(form_buttons_layout)

        self.delete_button = QPushButton("Excluir Forma de Pagamento Selecionada")
        form_layout.addWidget(self.delete_button)

        # Lado Direito (Tabela)
        table_layout = QVBoxLayout()
        self.methods_table = QTableWidget()
        self.methods_table.setColumnCount(2)
        self.methods_table.setHorizontalHeaderLabels(["ID", "Nome"])
        self.methods_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.methods_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.methods_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.methods_table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.methods_table)

        main_layout.addLayout(form_layout, 1)
        main_layout.addLayout(table_layout, 2)

        # Conectar sinais
        self.save_button.clicked.connect(self.save_method)
        self.clear_button.clicked.connect(self.clear_fields)
        self.delete_button.clicked.connect(self.delete_method)
        self.methods_table.itemSelectionChanged.connect(self.select_method)

        self.load_payment_methods()

    def load_payment_methods(self):
        self.methods_table.setRowCount(0)
        methods = db.get_all_payment_methods()
        for row_num, method in enumerate(methods):
            self.methods_table.insertRow(row_num)
            self.methods_table.setItem(row_num, 0, QTableWidgetItem(str(method['id'])))
            self.methods_table.setItem(row_num, 1, QTableWidgetItem(method['name']))
        self.clear_fields()

    def save_method(self):
        name = self.name_input.text()
        if not name:
            QMessageBox.warning(self, "Campo Vazio", "O nome da forma de pagamento não pode estar vazio.")
            return

        if self.current_method_id:
            success, message = db.update_payment_method(self.current_method_id, name)
        else:
            success, message = db.add_payment_method(name)
        
        if success:
            QMessageBox.information(self, "Sucesso", "Forma de pagamento salva com sucesso.")
            self.load_payment_methods()
        else:
            QMessageBox.warning(self, "Erro ao Salvar", message)

    def delete_method(self):
        if not self.current_method_id:
            QMessageBox.warning(self, "Atenção", "Selecione uma forma de pagamento na tabela para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                     "Tem certeza que deseja excluir esta forma de pagamento?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = db.delete_payment_method(self.current_method_id)
            if success:
                QMessageBox.information(self, "Sucesso", "Forma de pagamento excluída com sucesso.")
                self.load_payment_methods()
            else:
                QMessageBox.warning(self, "Erro ao Excluir", message)

    def clear_fields(self):
        self.current_method_id = None
        self.name_input.clear()
        self.methods_table.clearSelection()

    def select_method(self):
        selected_items = self.methods_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        self.current_method_id = int(self.methods_table.item(row, 0).text())
        self.name_input.setText(self.methods_table.item(row, 1).text())
