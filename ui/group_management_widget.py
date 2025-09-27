
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
)
from PyQt6.QtCore import Qt
import database as db

class GroupManagementWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_group_id = None

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Lado Esquerdo (Formulário)
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        form_layout.addWidget(QLabel("<b>Gerenciar Grupo de Produtos</b>"))
        self.name_input = QLineEdit(placeholderText="Nome do Grupo (ex: Bebidas)")
        form_layout.addWidget(QLabel("Nome do Grupo:"))
        form_layout.addWidget(self.name_input)
        
        form_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Salvar Grupo")
        self.clear_button = QPushButton("Limpar")
        form_buttons_layout.addWidget(self.save_button)
        form_buttons_layout.addWidget(self.clear_button)
        form_layout.addLayout(form_buttons_layout)

        self.delete_button = QPushButton("Excluir Grupo Selecionado")
        form_layout.addWidget(self.delete_button)

        # Lado Direito (Tabela)
        table_layout = QVBoxLayout()
        self.groups_table = QTableWidget()
        self.groups_table.setColumnCount(2)
        self.groups_table.setHorizontalHeaderLabels(["ID", "Nome do Grupo"])
        self.groups_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.groups_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.groups_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.groups_table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.groups_table)

        main_layout.addLayout(form_layout, 1)
        main_layout.addLayout(table_layout, 2)

        # Conectar sinais
        self.save_button.clicked.connect(self.save_group)
        self.clear_button.clicked.connect(self.clear_fields)
        self.delete_button.clicked.connect(self.delete_group)
        self.groups_table.itemSelectionChanged.connect(self.select_group)

        self.load_groups()

    def load_groups(self):
        self.groups_table.setRowCount(0)
        groups = db.get_all_groups()
        for row_num, group in enumerate(groups):
            self.groups_table.insertRow(row_num)
            self.groups_table.setItem(row_num, 0, QTableWidgetItem(str(group['id'])))
            self.groups_table.setItem(row_num, 1, QTableWidgetItem(group['name']))
        self.clear_fields()

    def save_group(self):
        name = self.name_input.text()
        if not name:
            QMessageBox.warning(self, "Campo Vazio", "O nome do grupo não pode estar vazio.")
            return

        if self.current_group_id:
            success, message = db.update_group(self.current_group_id, name)
        else:
            success, message = db.add_group(name)
        
        if success:
            QMessageBox.information(self, "Sucesso", "Grupo salvo com sucesso.")
            self.load_groups()
        else:
            QMessageBox.warning(self, "Erro ao Salvar", message)

    def delete_group(self):
        if not self.current_group_id:
            QMessageBox.warning(self, "Atenção", "Selecione um grupo na tabela para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                     "Tem certeza que deseja excluir este grupo? Os produtos neste grupo ficarão sem grupo.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            success, message = db.delete_group(self.current_group_id)
            if success:
                QMessageBox.information(self, "Sucesso", "Grupo excluído com sucesso.")
                self.load_groups()
            else:
                QMessageBox.warning(self, "Erro ao Excluir", message)

    def clear_fields(self):
        self.current_group_id = None
        self.name_input.clear()
        self.groups_table.clearSelection()

    def select_group(self):
        selected_items = self.groups_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        self.current_group_id = int(self.groups_table.item(row, 0).text())
        self.name_input.setText(self.groups_table.item(row, 1).text())
