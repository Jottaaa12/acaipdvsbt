
import json
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import pyqtSignal, Qt
from config_manager import ConfigManager

class ShortcutManagementWidget(QWidget):
    """
    A widget for managing quick access shortcuts in the application.
    Allows users to add, edit, and remove shortcuts which are saved in config.json.
    """
    shortcuts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gerenciador de Atalhos Rápidos")
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_shortcuts()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # Left side: Editor
        editor_groupbox = QGroupBox("Editar Atalho")
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.barcode_edit = QLineEdit()
        self.save_button = QPushButton("Salvar Atalho")
        self.clear_button = QPushButton("Limpar Campos")

        form_layout.addRow("Nome do Atalho:", self.name_edit)
        form_layout.addRow("Código de Barras:", self.barcode_edit)
        form_layout.addRow(self.save_button)
        form_layout.addRow(self.clear_button)

        editor_groupbox.setLayout(form_layout)

        # Right side: List
        list_groupbox = QGroupBox("Atalhos Existentes")
        list_layout = QVBoxLayout()

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Nome", "Código de Barras"])
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.remove_button = QPushButton("Remover Atalho Selecionado")

        list_layout.addWidget(self.table_widget)
        list_layout.addWidget(self.remove_button)
        list_groupbox.setLayout(list_layout)

        main_layout.addWidget(editor_groupbox, 1)
        main_layout.addWidget(list_groupbox, 2)

        # Connect signals
        self.save_button.clicked.connect(self.add_or_update_shortcut)
        self.clear_button.clicked.connect(self.clear_fields)
        self.remove_button.clicked.connect(self.remove_shortcut)
        self.table_widget.itemSelectionChanged.connect(self.on_item_selected)

    def load_shortcuts(self):
        shortcuts = self.config_manager.get_section("shortcuts")
        if not shortcuts:
            shortcuts = []

        self.table_widget.setRowCount(0)
        for shortcut in shortcuts:
            row_position = self.table_widget.rowCount()
            self.table_widget.insertRow(row_position)
            self.table_widget.setItem(row_position, 0, QTableWidgetItem(shortcut.get("name")))
            self.table_widget.setItem(row_position, 1, QTableWidgetItem(shortcut.get("barcode")))

    def save_shortcuts(self):
        shortcuts = []
        for row in range(self.table_widget.rowCount()):
            name = self.table_widget.item(row, 0).text()
            barcode = self.table_widget.item(row, 1).text()
            shortcuts.append({"name": name, "barcode": barcode})

        self.config_manager.update_section("shortcuts", shortcuts)
        self.shortcuts_changed.emit()

    def add_or_update_shortcut(self):
        name = self.name_edit.text().strip()
        barcode = self.barcode_edit.text().strip()

        if not name or not barcode:
            return

        selected_items = self.table_widget.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            self.table_widget.item(row, 0).setText(name)
            self.table_widget.item(row, 1).setText(barcode)
        else:
            row_position = self.table_widget.rowCount()
            self.table_widget.insertRow(row_position)
            self.table_widget.setItem(row_position, 0, QTableWidgetItem(name))
            self.table_widget.setItem(row_position, 1, QTableWidgetItem(barcode))

        self.save_shortcuts()
        self.clear_fields()

    def remove_shortcut(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        for selection in selected_rows:
            self.table_widget.removeRow(selection.row())
            
        self.save_shortcuts()
        self.clear_fields()

    def on_item_selected(self):
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            self.clear_fields()
            return

        row = selected_items[0].row()
        name = self.table_widget.item(row, 0).text()
        barcode = self.table_widget.item(row, 1).text()

        self.name_edit.setText(name)
        self.barcode_edit.setText(barcode)

    def clear_fields(self):
        self.name_edit.clear()
        self.barcode_edit.clear()
        self.table_widget.clearSelection()
